"""
exchange.py — Exchange adapter async.

Pool di connessioni limitato (aiohttp), WebSocket multiplexing,
rate limiter a token bucket. Progettato per non esaurire FD.

Architettura:
  - Una ClientSession globale con connection limit (max 10 conn/host)
  - Un WebSocket per simbolo, fan-out a N subscriber interni
  - Rate limiter con backoff progressivo
"""
from __future__ import annotations
import asyncio, json, logging, time, math
from typing import Optional, Callable, Awaitable
from dataclasses import dataclass

log = logging.getLogger("denaro-neo")

try:
    import aiohttp
except ImportError:
    log.critical("aiohttp required — pip install aiohttp")
    raise


# ─── Token Bucket Rate Limiter ───────────────────────────────────────────

class TokenBucket:
    """
    Rate limiter a token bucket.
    Consente burst iniziali ma mantiene la media nel tempo.

    >>> limiter = TokenBucket(rate=10, burst=20)
    >>> await limiter.acquire()  # True se abbiamo un token
    """

    __slots__ = ("_rate", "_burst", "_tokens", "_last_refill")

    def __init__(self, rate: float = 10.0, burst: int = 20):
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    async def acquire(self, tokens: float = 1.0, max_wait: float = 5.0) -> bool:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(float(self._burst), self._tokens + elapsed * self._rate)
        self._last_refill = now

        if self._tokens >= tokens:
            self._tokens -= tokens
            return True

        wait = (tokens - self._tokens) / self._rate
        if wait > max_wait:
            return False
        await asyncio.sleep(wait)
        self._tokens = 0.0
        self._last_refill = time.monotonic()
        return True


# ─── Exchange Adapter ────────────────────────────────────────────────────

class ExchangeAdapter:
    """
    Adapter async per exchange.
    Pool di connessioni unico condiviso tra tutti i componenti.

    connection_pool: max 10 connessioni simultanee per host.
    ws_multiplex: singola WS per simbolo, dispatch a subscriber.
    """

    __slots__ = (
        "_session", "_ws_connections", "_subscribers",
        "_rate_limiter", "_rate_limiter_ws",
        "_last_request", "_min_interval", "_ws_lock"
    )

    def __init__(self, rate_limit: float = 10.0, burst: int = 20):
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws_connections: dict[str, aiohttp.ClientWebSocketResponse] = {}
        self._subscribers: dict[str, list[Callable]] = {}
        self._rate_limiter = TokenBucket(rate=rate_limit, burst=burst)
        self._rate_limiter_ws = TokenBucket(rate=rate_limit / 2, burst=burst // 2)
        self._last_request: float = 0.0
        self._min_interval: float = 0.1  # 100ms tra richieste REST
        self._ws_lock = asyncio.Lock()

    async def start(self) -> None:
        """Crea sessione HTTP con pool limitato."""
        connector = aiohttp.TCPConnector(
            limit=10,          # max 10 connessioni totali
            limit_per_host=5,   # max 5 per host
            ttl_dns_cache=300,  # cache DNS 5 min
            force_close=False,  # keepalive
        )
        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=10),
            headers={
                "User-Agent": "denaro-neo/1.0",
                # Fix 2026-08-05 (brotli): aiohttp negozia br ma non riesce a
                # decodificarlo su questa pila -> Kraken risponde "br" e ogni
                # fetch fallisce (errore cronico dal log 2026-07-11).
                # Forzando gzip/deflate il server rispetta il negoziato e
                # aiohttp decodifica nativamente via zlib.
                "Accept-Encoding": "gzip, deflate",
            },
        )

    async def stop(self) -> None:
        """Chiude WS e sessione."""
        for sym in list(self._ws_connections.keys()):
            await self._close_ws(sym)
        if self._session:
            await self._session.close()
            self._session = None

    # ── REST (con rate limit) ────────────────────────────────────────────

    async def request(self, method: str, url: str, **kwargs) -> dict:
        """Richiesta HTTP con rate limit e retry."""
        if not self._session:
            raise RuntimeError("Session not started")

        if not await self._rate_limiter.acquire():
            log.warning("Rate limited — request dropped")
            return {}

        for attempt in range(3):
            try:
                async with self._session.request(method, url, **kwargs) as resp:
                    if resp.status == 429:
                        retry_after = int(resp.headers.get("Retry-After", "5"))
                        log.warning(f"429: retry in {retry_after}s (attempt {attempt+1})")
                        await asyncio.sleep(retry_after)
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                if attempt == 2:
                    log.error(f"Request failed after 3 attempts: {e}")
                    return {}
                await asyncio.sleep(1 * 2 ** attempt)
        return {}

    async def get(self, url: str, **kwargs) -> dict:
        return await self.request("GET", url, **kwargs)

    async def post(self, url: str, **kwargs) -> dict:
        return await self.request("POST", url, **kwargs)

    # ── WebSocket (multiplexing) ─────────────────────────────────────────

    async def subscribe(self, symbol: str, callback: Callable) -> None:
        """
        Sottoscrivi a un canale WS per symbol.
        La WS viene aperta una volta sola e i messaggi sono
        dispatcati a tutti i subscriber.
        """
        async with self._ws_lock:
            if symbol not in self._subscribers:
                self._subscribers[symbol] = []
            self._subscribers[symbol].append(callback)
            if symbol not in self._ws_connections:
                asyncio.create_task(self._ws_loop(symbol))

    async def unsubscribe(self, symbol: str, callback: Callable) -> None:
        async with self._ws_lock:
            if symbol in self._subscribers:
                self._subscribers[symbol] = [
                    cb for cb in self._subscribers[symbol] if cb != callback
                ]
                if not self._subscribers[symbol]:
                    await self._close_ws(symbol)
                    del self._subscribers[symbol]

    async def _ws_loop(self, symbol: str) -> None:
        """WS loop con riconnessione automatica."""
        ws_symbol = symbol.replace("/", "")
        url = "wss://ws.kraken.com/v2"
        subscribe_msg = json.dumps({
            "method": "subscribe",
            "params": {"channel": "ticker", "symbol": [ws_symbol]},
        })

        reconnect_delay = 1.0
        while True:
            try:
                async with self._session.ws_connect(
                    url,
                    heartbeat=20.0,
                    max_msg_size=2 ** 20,
                ) as ws:
                    self._ws_connections[symbol] = ws
                    reconnect_delay = 1.0
                    await ws.send_str(subscribe_msg)
                    async for raw in ws:
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        await self._dispatch(symbol, data)
            except Exception as e:
                log.warning(f"WS {symbol} disconnected: {e}")
            finally:
                self._ws_connections.pop(symbol, None)

            if not self._subscribers.get(symbol):
                break  # nessun subscriber — esci

            await asyncio.sleep(reconnect_delay)
            reconnect_delay = min(reconnect_delay * 2, 30.0)

    async def _dispatch(self, symbol: str, data: dict) -> None:
        """Dispatch messaggio a tutti i subscriber."""
        for cb in self._subscribers.get(symbol, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(data)
                else:
                    cb(data)
            except Exception:
                log.exception(f"Subscriber error for {symbol}")

    async def _close_ws(self, symbol: str) -> None:
        ws = self._ws_connections.pop(symbol, None)
        if ws:
            await ws.close()

    # ── Health ───────────────────────────────────────────────────────────

    @property
    def is_connected(self) -> bool:
        return bool(self._ws_connections)

    @property
    def connection_count(self) -> int:
        return len(self._ws_connections)

    @property
    def subscriber_count(self) -> int:
        return sum(len(subs) for subs in self._subscribers.values())

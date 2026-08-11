"""
Exchange adapter for Alpha-Omega Trading System.

Merges: neo/exchange.py (async aiohttp + WS) + shadowgrid_v2.py (CCXT integration).

Features:
- Async aiohttp + WebSocket multiplexing
- Token bucket rate limiter with exponential backoff
- Connection pooling (max 10 conn, 5/host)
- Automatic reconnection with jitter
- CCXT fallback for REST endpoints not in WS
- Order lifecycle tracking
- Fee-aware fill simulation for paper mode
"""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import os
import time
import urllib.parse
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable

log = logging.getLogger("alpha_omega.exchange")

try:
    import aiohttp
except ImportError:
    log.critical("aiohttp required — pip install aiohttp")
    raise

try:
    import ccxt
    import ccxt.pro as ccxtpro
except ImportError:
    log.warning("ccxt not installed — some features unavailable")
    ccxt = None
    ccxtpro = None


@dataclass
class Order:
    """Normalized order representation."""
    id: str
    symbol: str
    exchange: str
    side: str  # 'buy' or 'sell'
    type: str  # 'limit' or 'market'
    price: float
    amount: float
    filled: float = 0.0
    status: str = 'pending'  # pending, open, partial, filled, cancelled, rejected
    fee: float = 0.0
    fee_currency: str = ''
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    client_order_id: str = ''
    strategy: str = ''
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'symbol': self.symbol,
            'exchange': self.exchange,
            'side': self.side,
            'type': self.type,
            'price': self.price,
            'amount': self.amount,
            'filled': self.filled,
            'status': self.status,
            'fee': self.fee,
            'fee_currency': self.fee_currency,
            'timestamp': self.timestamp,
            'client_order_id': self.client_order_id,
            'strategy': self.strategy,
        }


@dataclass
class Ticker:
    """Normalized ticker data."""
    symbol: str
    exchange: str
    bid: float
    ask: float
    last: float
    high: float
    low: float
    open: float
    close: float
    volume: float
    timestamp: int = field(default_factory=lambda: int(time.time() * 1000))
    
    @property
    def spread(self) -> float:
        return self.ask - self.bid if self.ask > 0 and self.bid > 0 else 0.0
    
    @property
    def spread_pct(self) -> float:
        if self.last > 0 and self.spread > 0:
            return (self.spread / self.last) * 100
        return 0.0


@dataclass
class OHLCV:
    """Normalized OHLCV candle."""
    symbol: str
    exchange: str
    timeframe: str
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


class TokenBucket:
    """
    Token bucket rate limiter with burst allowance.
    Thread-safe for asyncio.
    """
    __slots__ = ("rate", "burst", "tokens", "last_update", "_lock")

    def __init__(self, rate: float, burst: int):
        self.rate = rate      # tokens per second
        self.burst = burst    # max tokens
        self.tokens = float(burst)
        self.last_update = time.monotonic()
        self._lock = asyncio.Lock()

    async def take(self, tokens: int = 1) -> float:
        """Wait until tokens available. Returns wait time in seconds."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self.last_update
            self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
            self.last_update = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return 0.0
            
            # Need to wait
            wait_time = (tokens - self.tokens) / self.rate
            self.tokens = 0
            return wait_time

    async def consume(self, tokens: int = 1) -> None:
        wait = await self.take(tokens)
        if wait > 0:
            await asyncio.sleep(wait)


class ConnectionPool:
    """
    aiohttp connection pool with per-host limits.
    """
    __slots__ = ("_session", "_connector", "_max_connections", "_max_per_host")

    def __init__(self, max_connections: int = 10, max_per_host: int = 5):
        self._max_connections = max_connections
        self._max_per_host = max_per_host
        self._connector: Optional[aiohttp.TCPConnector] = None
        self._session: Optional[aiohttp.ClientSession] = None

    async def start(self) -> None:
        if self._session is None:
            self._connector = aiohttp.TCPConnector(
                limit=self._max_connections,
                limit_per_host=self._max_per_host,
                ttl_dns_cache=300,
                enable_cleanup_closed=True,
            )
            timeout = aiohttp.ClientTimeout(total=30, connect=10)
            self._session = aiohttp.ClientSession(
                connector=self._connector,
                timeout=timeout,
                headers={'User-Agent': 'AlphaOmega/2.2'},
            )
            log.info(f"Connection pool started: max={self._max_connections}, per_host={self._max_per_host}")

    async def close(self) -> None:
        if self._session:
            await self._session.close()
            self._session = None
        if self._connector:
            await self._connector.close()
            self._connector = None
        log.info("Connection pool closed")

    @property
    def session(self) -> Optional[aiohttp.ClientSession]:
        return self._session


class ExchangeAdapter(ABC):
    """
    Abstract exchange adapter.
    Implementazioni concrete: KrakenAdapter, OKXAdapter.
    Supports both live and sandbox/testnet modes for paper trading.
    """

    __slots__ = (
        "exchange_id", "api_key", "api_secret", "passphrase",
        "paper_mode", "sandbox_mode",
        "rate_limiter", "pool", "ws",
        "_ws_task", "_ws_callbacks", "_reconnect_attempts", "_closed"
    )

    def __init__(
        self,
        exchange_id: str,
        api_key: str = "",
        api_secret: str = "",
        passphrase: str = "",
        paper_mode: bool = True,
        sandbox_mode: bool = True,
        sandbox_api_key: str = "",
        sandbox_api_secret: str = "",
        sandbox_passphrase: str = "",
        rate_limit_rps: float = 5.0,
        rate_limit_burst: int = 10,
    ):
        self.exchange_id = exchange_id
        self.api_key = api_key
        self.api_secret = api_secret
        self.passphrase = passphrase
        self.paper_mode = paper_mode
        self.sandbox_mode = sandbox_mode and not paper_mode == False  # sandbox only for paper
        
        # Use sandbox credentials if in sandbox mode and provided
        if self.sandbox_mode and sandbox_api_key:
            self.api_key = sandbox_api_key
            self.api_secret = sandbox_api_secret
            self.passphrase = sandbox_passphrase
        
        self.rate_limiter = TokenBucket(rate_limit_rps, rate_limit_burst)
        self.pool = ConnectionPool(max_connections=10, max_per_host=5)
        self.ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_callbacks: Dict[str, List[Callable]] = defaultdict(list)
        self._reconnect_attempts = 0
        self._closed = False

    @property
    def _is_sandbox(self) -> bool:
        """Check if using sandbox/testnet endpoints."""
        return self.sandbox_mode and not self.paper_mode == False

    def _get_rest_base(self) -> str:
        """Get REST base URL (live or sandbox). Override in subclass."""
        if self._is_sandbox:
            return self._sandbox_rest_base()
        return self._rest_base_live()

    def _get_ws_url(self) -> str:
        """Get WebSocket URL (live or sandbox). Override in subclass."""
        if self._is_sandbox:
            return self._sandbox_ws_url()
        return self._ws_url_live()

    @abstractmethod
    def _rest_base_live(self) -> str:
        """Live REST API base URL."""
        pass

    @abstractmethod
    def _sandbox_rest_base(self) -> str:
        """Sandbox/Testnet REST API base URL."""
        pass

    @abstractmethod
    def _ws_url_live(self) -> str:
        """Live WebSocket URL."""
        pass

    @abstractmethod
    def _sandbox_ws_url(self) -> str:
        """Sandbox/Testnet WebSocket URL."""
        pass

    @abstractmethod
    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        """Generate signed headers for authenticated request."""
        pass

    @abstractmethod
    def _ws_subscribe_msg(self, channels: List[str], symbols: List[str]) -> Dict:
        """WebSocket subscription message."""
        pass

    @abstractmethod
    def _parse_ticker(self, data: Dict) -> Ticker:
        """Parse raw ticker data."""
        pass

    @abstractmethod
    def _parse_ohlcv(self, data: Dict) -> OHLCV:
        """Parse raw OHLCV data."""
        pass

    @abstractmethod
    def _parse_order(self, data: Dict) -> Order:
        """Parse raw order data."""
        pass

    # ── REST API ─────────────────────────────────────────────────────────

    async def _request(
        self,
        method: str,
        path: str,
        params: Optional[Dict] = None,
        signed: bool = False
    ) -> Dict:
        """Make authenticated or public REST request with rate limiting."""
        await self.rate_limiter.consume(1)
        
        session = self.pool.session
        if not session:
            raise RuntimeError("Connection pool not started")
        
        # Use sandbox or live REST base URL
        rest_base = self._get_rest_base()
        url = f"{rest_base}{path}"
        headers = {"Accept": "application/json"}
        
        if signed:
            timestamp = str(int(time.time() * 1000))
            headers.update(self._sign_request(method, path, params or {}, timestamp))
        
        try:
            if method == "GET":
                async with session.get(url, params=params, headers=headers) as resp:
                    return await self._handle_response(resp)
            else:
                async with session.post(url, json=params, headers=headers) as resp:
                    return await self._handle_response(resp)
        except aiohttp.ClientError as e:
            log.error(f"REST request failed: {method} {path} - {e}")
            raise

    async def _handle_response(self, resp: aiohttp.ClientResponse) -> Dict:
        text = await resp.text()
        if resp.status >= 400:
            log.error(f"HTTP {resp.status}: {text}")
            raise Exception(f"HTTP {resp.status}: {text}")
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"raw": text}

    async def get_ticker(self, symbol: str) -> Ticker:
        data = await self._request("GET", self._ticker_endpoint(symbol))
        return self._parse_ticker(data)

    async def get_ohlcv(self, symbol: str, timeframe: str = "1m", limit: int = 100) -> List[OHLCV]:
        data = await self._request("GET", self._ohlcv_endpoint(symbol, timeframe, limit))
        if isinstance(data, list):
            return [self._parse_ohlcv(d) for d in data]
        return []

    @abstractmethod
    def _ticker_endpoint(self, symbol: str) -> str:
        pass

    @abstractmethod
    def _ohlcv_endpoint(self, symbol: str, timeframe: str, limit: int) -> str:
        pass

    # ── Order Management ─────────────────────────────────────────────────

    async def create_order(
        self,
        symbol: str,
        side: str,
        type: str,
        amount: float,
        price: Optional[float] = None,
        client_order_id: str = "",
        strategy: str = "",
    ) -> Order:
        """Create order (paper or live)."""
        if self.paper_mode:
            return await self._create_paper_order(symbol, side, type, amount, price, client_order_id, strategy)
        return await self._create_live_order(symbol, side, type, amount, price, client_order_id, strategy)

    async def _create_paper_order(self, symbol, side, type, amount, price, client_order_id, strategy) -> Order:
        """Simulate order creation for paper trading."""
        order = Order(
            id=f"paper_{self.exchange_id}_{int(time.time()*1000)}_{hash(symbol)%10000}",
            symbol=symbol,
            exchange=self.exchange_id,
            side=side,
            type=type,
            price=price or 0.0,
            amount=amount,
            status='open' if type == 'limit' else 'filled',
            client_order_id=client_order_id,
            strategy=strategy,
        )
        return order

    @abstractmethod
    async def _create_live_order(self, symbol, side, type, amount, price, client_order_id, strategy) -> Order:
        pass

    async def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel order."""
        if self.paper_mode:
            return True
        return await self._cancel_live_order(order_id, symbol)

    @abstractmethod
    async def _cancel_live_order(self, order_id: str, symbol: str) -> bool:
        pass

    async def get_order(self, order_id: str, symbol: str) -> Order:
        if self.paper_mode:
            # In paper mode, orders are managed locally
            raise NotImplementedError("Paper orders managed by engine")
        data = await self._request("GET", self._order_endpoint(order_id, symbol), signed=True)
        return self._parse_order(data)

    @abstractmethod
    def _order_endpoint(self, order_id: str, symbol: str) -> str:
        pass

    # ── WebSocket ────────────────────────────────────────────────────────

    async def start_ws(self, symbols: List[str], channels: List[str] = None) -> None:
        """Start WebSocket connection with auto-reconnect."""
        await self.pool.start()
        
        channels = channels or ["ticker", "trade", "orderbook"]
        
        while not self._closed:
            try:
                await self._connect_ws(symbols, channels)
                self._reconnect_attempts = 0
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._reconnect_attempts += 1
                wait = min(2 ** self._reconnect_attempts, 60) + (hash(str(e)) % 5)
                log.warning(f"WS disconnected ({e}), reconnecting in {wait}s (attempt {self._reconnect_attempts})")
                await asyncio.sleep(wait)

    async def _connect_ws(self, symbols: List[str], channels: List[str]) -> None:
        session = self.pool.session
        if not session:
            raise RuntimeError("Pool not started")
        
        # Use sandbox or live WebSocket URL
        ws_url = self._get_ws_url()
        ws = await session.ws_connect(
            ws_url,
            heartbeat=30,
            autoping=True,
        )
        self.ws = ws
        
        # Subscribe
        msg = self._ws_subscribe_msg(channels, symbols)
        await ws.send_json(msg)
        
        log.info(f"WS connected: {self.exchange_id} subscribed to {channels} for {symbols}")
        
        # Message loop
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                try:
                    data = json.loads(msg.data)
                    await self._handle_ws_message(data)
                except json.JSONDecodeError:
                    pass
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
            elif msg.type == aiohttp.WSMsgType.CLOSED:
                break
        
        if not self._closed:
            raise Exception("WS connection closed")

    async def _handle_ws_message(self, data: Dict) -> None:
        """Route WS message to callbacks."""
        # Override in subclass to parse and emit events
        pass

    def on(self, event: str, callback: Callable) -> None:
        """Register callback for WS events: ticker, trade, orderbook, order."""
        self._ws_callbacks[event].append(callback)

    def _emit(self, event: str, data: Any) -> None:
        for cb in self._ws_callbacks.get(event, []):
            try:
                if asyncio.iscoroutinefunction(cb):
                    asyncio.create_task(cb(data))
                else:
                    cb(data)
            except Exception as e:
                log.error(f"Callback error for {event}: {e}")

    async def stop_ws(self) -> None:
        self._closed = True
        if self._ws_task:
            self._ws_task.cancel()
            try:
                await self._ws_task
            except asyncio.CancelledError:
                pass
        if self.ws:
            await self.ws.close()
        await self.pool.close()
        log.info(f"WS stopped: {self.exchange_id}")

    # ── Balance & Account ────────────────────────────────────────────────

    async def get_balance(self) -> Dict[str, float]:
        """Get account balances."""
        if self.paper_mode:
            return {"paper": 10000.0}
        data = await self._request("GET", self._balance_endpoint(), signed=True)
        return self._parse_balance(data)

    @abstractmethod
    def _balance_endpoint(self) -> str:
        pass

    @abstractmethod
    def _parse_balance(self, data: Dict) -> Dict[str, float]:
        pass


# ─── Kraken Adapter ──────────────────────────────────────────────────────

class KrakenAdapter(ExchangeAdapter):
    """Kraken REST + WS adapter with sandbox support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ws_channels = {}

    def _rest_base_live(self) -> str:
        """Live REST API base URL."""
        return "https://api.kraken.com"

    def _sandbox_rest_base(self) -> str:
        """Sandbox/Testnet REST API base URL (Kraken Spot Pilot)."""
        return "https://api.pilot.kraken.com"

    def _ws_url_live(self) -> str:
        """Live WebSocket URL."""
        return "wss://ws.kraken.com"

    def _sandbox_ws_url(self) -> str:
        """Sandbox WebSocket URL (Kraken Pilot)."""
        return "wss://ws.pilot.kraken.com"

    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        post_data = urllib.parse.urlencode(params) if params else ""
        message = timestamp + method.upper() + path + hashlib.sha256(post_data.encode()).hexdigest()
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha512
        ).hexdigest()
        return {
            "API-Key": self.api_key,
            "API-Sign": signature,
        }

    def _ws_subscribe_msg(self, channels: List[str], symbols: List[str]) -> Dict:
        # Map standard channels to Kraken WS channels
        kraken_channels = []
        for ch in channels:
            if ch == "ticker":
                kraken_channels.append("ticker")
            elif ch == "trade":
                kraken_channels.append("trade")
            elif ch == "orderbook":
                kraken_channels.append("book")
        
        # Convert symbols to Kraken format
        ws_symbols = [self._to_kraken_symbol(s) for s in symbols]
        
        return {
            "event": "subscribe",
            "pair": ws_symbols,
            "subscription": {"name": kraken_channels[0] if kraken_channels else "ticker"},
        }

    def _to_kraken_symbol(self, symbol: str) -> str:
        # BTC/EUR -> XBT/EUR, DOGE/EUR -> DOGE/EUR
        base, quote = symbol.split("/")
        if base == "BTC":
            base = "XBT"
        return f"{base}/{quote}"

    def _from_kraken_symbol(self, symbol: str) -> str:
        parts = symbol.replace("XBT", "BTC").split("/")
        if len(parts) == 2:
            return f"{parts[0]}/{parts[1]}"
        return symbol

    def _ticker_endpoint(self, symbol: str) -> str:
        return f"/0/public/Ticker?pair={self._to_kraken_symbol(symbol).replace('/', '')}"

    def _ohlcv_endpoint(self, symbol: str, timeframe: str, limit: int) -> str:
        interval_map = {"1m": 1, "5m": 5, "15m": 15, "1h": 60, "1d": 1440}
        interval = interval_map.get(timeframe, 1)
        return f"/0/public/OHLC?pair={self._to_kraken_symbol(symbol).replace('/', '')}&interval={interval}"

    def _order_endpoint(self, order_id: str, symbol: str) -> str:
        return f"/0/private/QueryOrders?txid={order_id}"

    def _balance_endpoint(self) -> str:
        return "/0/private/Balance"

    def _parse_ticker(self, data: Dict) -> Ticker:
        result = data.get("result", {})
        for pair, t in result.items():
            # Handle both list and scalar values from WebSocket
            open_val = t.get("o", 0)
            if isinstance(open_val, list):
                open_val = open_val[0] if open_val else 0
            return Ticker(
                symbol=self._from_kraken_symbol(pair),
                exchange="kraken",
                bid=float(t["b"][0]) if isinstance(t.get("b"), list) and t["b"] else float(t.get("b", 0)),
                ask=float(t["a"][0]) if isinstance(t.get("a"), list) and t["a"] else float(t.get("a", 0)),
                last=float(t["c"][0]) if isinstance(t.get("c"), list) and t["c"] else float(t.get("c", 0)),
                high=float(t["h"][1]) if isinstance(t.get("h"), list) and len(t.get("h", [])) > 1 else float(t.get("h", 0)),
                low=float(t["l"][1]) if isinstance(t.get("l"), list) and len(t.get("l", [])) > 1 else float(t.get("l", 0)),
                open=float(open_val),
                close=float(t["c"][0]) if isinstance(t.get("c"), list) and t["c"] else float(t.get("c", 0)),
                volume=float(t["v"][1]) if isinstance(t.get("v"), list) and len(t.get("v", [])) > 1 else float(t.get("v", 0)),
            )
        return Ticker(symbol="", exchange="kraken", bid=0, ask=0, last=0, high=0, low=0, open=0, close=0, volume=0)

    def _parse_ohlcv(self, data: Dict) -> OHLCV:
        # Kraken returns: [timestamp, open, high, low, close, vwap, volume, count]
        if isinstance(data, list) and len(data) >= 7:
            # Handle both list and scalar values from WebSocket
            def _to_float(val):
                if isinstance(val, list) and val:
                    return float(val[0])
                return float(val) if val is not None else 0.0
            return OHLCV(
                symbol="",  # Will be set by caller
                exchange="kraken",
                timeframe="1m",
                timestamp=int(data[0]) if isinstance(data[0], (int, float, str)) else int(data[0][0]) if isinstance(data[0], list) and data[0] else 0,
                open=_to_float(data[1]),
                high=_to_float(data[2]),
                low=_to_float(data[3]),
                close=_to_float(data[4]),
                volume=_to_float(data[6]),
            )
        return OHLCV(symbol="", exchange="kraken", timeframe="1m", timestamp=0, open=0, high=0, low=0, close=0, volume=0)

    def _parse_order(self, data: Dict) -> Order:
        # Simplified
        return Order(id="", symbol="", exchange="kraken", side="buy", type="limit", price=0, amount=0)

    def _parse_balance(self, data: Dict) -> Dict[str, float]:
        result = data.get("result", {})
        return {k: float(v) for k, v in result.items() if float(v) > 0}

    async def _create_live_order(self, symbol, side, type, amount, price, client_order_id, strategy) -> Order:
        params = {
            "pair": self._to_kraken_symbol(symbol),
            "type": side,
            "ordertype": type,
            "volume": str(amount),
        }
        if type == "limit" and price:
            params["price"] = str(price)
        if client_order_id:
            params["userref"] = client_order_id
        
        data = await self._request("POST", "/0/private/AddOrder", params, signed=True)
        result = data.get("result", {})
        txids = result.get("txid", [])
        order_id = txids[0] if txids else ""
        
        return Order(
            id=order_id,
            symbol=symbol,
            exchange="kraken",
            side=side,
            type=type,
            price=price or 0.0,
            amount=amount,
            status="open",
            client_order_id=client_order_id,
            strategy=strategy,
        )

    async def _cancel_live_order(self, order_id: str, symbol: str) -> bool:
        data = await self._request("POST", "/0/private/CancelOrder", {"txid": order_id}, signed=True)
        return len(data.get("result", {})) > 0

    async def _handle_ws_message(self, data: Dict) -> None:
        if isinstance(data, list) and len(data) >= 4:
            channel = data[2]
            pair = self._from_kraken_symbol(data[3])
            
            if channel == "ticker":
                ticker_data = data[1]
                # Handle both list and scalar values
                def _val(data, key, idx=0, default=0):
                    v = data.get(key, default)
                    if isinstance(v, list) and v:
                        return v[idx] if len(v) > idx else v[0]
                    return v if v is not None else default
                ticker = Ticker(
                    symbol=pair,
                    exchange="kraken",
                    bid=float(_val(ticker_data, "b", 0)),
                    ask=float(_val(ticker_data, "a", 0)),
                    last=float(_val(ticker_data, "c", 0)),
                    high=float(_val(ticker_data, "h", 1)),
                    low=float(_val(ticker_data, "l", 1)),
                    open=float(_val(ticker_data, "o", 0)),
                    close=float(_val(ticker_data, "c", 0)),
                    volume=float(_val(ticker_data, "v", 1)),
                )
                self._emit("ticker", ticker)
            elif channel == "trade":
                for trade in data[1]:
                    # Handle both list and scalar values in trade data
                    def _trade_val(val):
                        if isinstance(val, list) and val:
                            return val[0]
                        return val
                    self._emit("trade", {
                        "symbol": pair,
                        "price": float(_trade_val(trade[0])),
                        "volume": float(_trade_val(trade[1])),
                        "timestamp": int(float(_trade_val(trade[2])) * 1000),
                        "side": 0 if _trade_val(trade[3]) == "b" else 1,
                    })


# ─── OKX Adapter ────────────────────────────────────────────────────────

class OKXAdapter(ExchangeAdapter):
    """OKX REST + WS adapter with EEA passphrase and demo trading support."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._ws_channels = {}

    def _rest_base_live(self) -> str:
        """Live REST API base URL (EEA for European users)."""
        return "https://eea.okx.com"

    def _sandbox_rest_base(self) -> str:
        """Sandbox/Demo REST API base URL (same as live, uses header for demo mode)."""
        return "https://www.okx.com"

    def _ws_url_live(self) -> str:
        """Live WebSocket URL - EEA endpoint for EU users."""
        return "wss://eea.okx.com:8443/ws/v5/public"

    def _sandbox_ws_url(self) -> str:
        """Sandbox WebSocket URL - EEA endpoint for EU users."""
        return "wss://eea.okx.com:8443/ws/v5/public"

    def _sign_request(self, method: str, path: str, params: Dict, timestamp: str) -> Dict[str, str]:
        body = json.dumps(params) if params else ""
        message = timestamp + method.upper() + "/api/v5" + path + body
        signature = hmac.new(
            self.api_secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        headers = {
            "OK-ACCESS-KEY": self.api_key,
            "OK-ACCESS-SIGN": signature,
            "OK-ACCESS-TIMESTAMP": timestamp,
            "OK-ACCESS-PASSPHRASE": self.passphrase,
            "Content-Type": "application/json",
        }
        # Add demo trading header for sandbox mode
        if self._is_sandbox:
            headers["x-simulated-trading"] = "1"
        return headers

    def _ws_subscribe_msg(self, channels: List[str], symbols: List[str]) -> Dict:
        okx_channels = []
        for ch in channels:
            if ch == "ticker":
                okx_channels.append("tickers")
            elif ch == "trade":
                okx_channels.append("trades")
            elif ch == "orderbook":
                okx_channels.append("books5")
        
        args = [
            {"channel": ch, "instId": self._to_okx_symbol(s)}
            for ch in okx_channels
            for s in symbols
        ]
        
        return {"op": "subscribe", "args": args}

    def _to_okx_symbol(self, symbol: str) -> str:
        return symbol.replace("/", "-")

    def _from_okx_symbol(self, symbol: str) -> str:
        return symbol.replace("-", "/")

    def _ticker_endpoint(self, symbol: str) -> str:
        return f"/api/v5/market/ticker?instId={self._to_okx_symbol(symbol)}"

    def _ohlcv_endpoint(self, symbol: str, timeframe: str, limit: int) -> str:
        tf_map = {"1m": "1m", "5m": "5m", "15m": "15m", "1h": "1H", "1d": "1D"}
        tf = tf_map.get(timeframe, "1m")
        return f"/api/v5/market/candles?instId={self._to_okx_symbol(symbol)}&bar={tf}&limit={limit}"

    def _order_endpoint(self, order_id: str, symbol: str) -> str:
        return f"/api/v5/trade/order-details?ordId={order_id}&instId={self._to_okx_symbol(symbol)}"

    def _balance_endpoint(self) -> str:
        return "/api/v5/account/balance"

    def _parse_ticker(self, data: Dict) -> Ticker:
        result = data.get("data", [{}])[0]
        return Ticker(
            symbol=self._from_okx_symbol(result.get("instId", "")),
            exchange="okx",
            bid=float(result.get("bidPx", 0)),
            ask=float(result.get("askPx", 0)),
            last=float(result.get("last", 0)),
            high=float(result.get("high24h", 0)),
            low=float(result.get("low24h", 0)),
            open=float(result.get("open24h", 0)),
            close=float(result.get("last", 0)),
            volume=float(result.get("vol24h", 0)),
        )

    def _parse_ohlcv(self, data: Dict) -> OHLCV:
        # OKX returns: [ts, o, h, l, c, vol, volCcy, volUsd, confirm]
        if isinstance(data, list) and len(data) >= 6:
            return OHLCV(
                symbol="",
                exchange="okx",
                timeframe="1m",
                timestamp=int(data[0]),
                open=float(data[1]),
                high=float(data[2]),
                low=float(data[3]),
                close=float(data[4]),
                volume=float(data[5]),
            )
        return OHLCV(symbol="", exchange="okx", timeframe="1m", timestamp=0, open=0, high=0, low=0, close=0, volume=0)

    def _parse_order(self, data: Dict) -> Order:
        result = data.get("data", [{}])[0]
        return Order(
            id=result.get("ordId", ""),
            symbol=self._from_okx_symbol(result.get("instId", "")),
            exchange="okx",
            side=result.get("side", "buy"),
            type=result.get("ordType", "limit"),
            price=float(result.get("px", 0)),
            amount=float(result.get("sz", 0)),
            filled=float(result.get("fillSz", 0)),
            status=result.get("state", "pending"),
            fee=float(result.get("fee", 0)),
            fee_currency=result.get("feeCcy", ""),
        )

    def _parse_balance(self, data: Dict) -> Dict[str, float]:
        result = data.get("data", [{}])[0]
        balances = {}
        for detail in result.get("details", []):
            ccy = detail.get("ccy", "")
            avail = float(detail.get("availBal", 0))
            if avail > 0:
                balances[ccy] = avail
        return balances

    async def _create_live_order(self, symbol, side, type, amount, price, client_order_id, strategy) -> Order:
        params = {
            "instId": self._to_okx_symbol(symbol),
            "tdMode": "cash",
            "side": side,
            "ordType": type,
            "sz": str(amount),
        }
        if type == "limit" and price:
            params["px"] = str(price)
        if client_order_id:
            params["clOrdId"] = client_order_id
        
        data = await self._request("POST", "/api/v5/trade/order", params, signed=True)
        result = data.get("data", [{}])[0]
        
        return Order(
            id=result.get("ordId", ""),
            symbol=symbol,
            exchange="okx",
            side=side,
            type=type,
            price=price or 0.0,
            amount=amount,
            status="open",
            client_order_id=client_order_id,
            strategy=strategy,
        )

    async def _cancel_live_order(self, order_id: str, symbol: str) -> bool:
        params = {"instId": self._to_okx_symbol(symbol), "ordId": order_id}
        data = await self._request("POST", "/api/v5/trade/cancel-order", params, signed=True)
        return data.get("code", "1") == "0"

    async def _handle_ws_message(self, data: Dict) -> None:
        if "event" in data and data["event"] == "subscribe":
            return
        
        if "data" in data:
            channel = data.get("arg", {}).get("channel", "")
            
            if channel == "tickers":
                for item in data["data"]:
                    ticker = Ticker(
                        symbol=self._from_okx_symbol(item["instId"]),
                        exchange="okx",
                        bid=float(item["bidPx"]),
                        ask=float(item["askPx"]),
                        last=float(item["last"]),
                        high=float(item["high24h"]),
                        low=float(item["low24h"]),
                        open=float(item["open24h"]),
                        close=float(item["last"]),
                        volume=float(item["vol24h"]),
                    )
                    self._emit("ticker", ticker)
            elif channel == "trades":
                for item in data["data"]:
                    self._emit("trade", {
                        "symbol": self._from_okx_symbol(item["instId"]),
                        "price": float(item["px"]),
                        "volume": float(item["sz"]),
                        "timestamp": int(item["ts"]),
                        "side": 0 if item["side"] == "buy" else 1,
                    })


# ─── Factory ─────────────────────────────────────────────────────────────

def create_exchange(
    exchange_id: str,
    api_key: str = "",
    api_secret: str = "",
    passphrase: str = "",
    paper_mode: bool = True,
    sandbox_mode: bool = True,
    sandbox_api_key: str = "",
    sandbox_api_secret: str = "",
    sandbox_passphrase: str = "",
    rate_limit_rps: float = 5.0,
    rate_limit_burst: int = 10,
) -> ExchangeAdapter:
    """Factory function to create exchange adapter with sandbox support."""
    exchange_id = exchange_id.lower()
    
    if exchange_id == "kraken":
        return KrakenAdapter(
            exchange_id, api_key, api_secret, passphrase,
            paper_mode, sandbox_mode,
            sandbox_api_key, sandbox_api_secret, sandbox_passphrase,
            rate_limit_rps, rate_limit_burst
        )
    elif exchange_id == "okx":
        return OKXAdapter(
            exchange_id, api_key, api_secret, passphrase,
            paper_mode, sandbox_mode,
            sandbox_api_key, sandbox_api_secret, sandbox_passphrase,
            rate_limit_rps, rate_limit_burst
        )
    else:
        raise ValueError(f"Unsupported exchange: {exchange_id}")

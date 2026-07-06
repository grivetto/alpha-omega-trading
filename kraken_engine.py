#!/usr/bin/env python3
"""
KRAKEN ENGINE v3 — Production-grade adapter with WebSocket order book + ticker.
Machine a profit: order book microstructure, fee-aware routing, VaR-grade reliability.
"""
from __future__ import annotations

import json, logging, os, random, time, math
from typing import Optional, Tuple
from urllib.error import URLError, HTTPError
import ccxt

log = logging.getLogger("kraken_v2")
SYMBOL = "DOGE/EUR"
_WS_ENABLED = os.environ.get("KRAKEN_WS_DISABLE", "0") != "1"

# --- Error classification -----------------------------------------------------

_RETRYABLE = {429, 500, 502, 503, 504}
def _is_retryable(err: Exception) -> bool:
    if isinstance(err, HTTPError):
        return err.code in _RETRYABLE
    if isinstance(err, (ccxt.RateLimitExceeded, ccxt.NetworkError, ccxt.RequestTimeout, ccxt.DDoSProtection)):
        return True
    if isinstance(err, (URLError, ConnectionError, TimeoutError, OSError)):
        return True
    msg = str(getattr(err, "message", str(err))).lower()
    if any(kw in msg for kw in ("timeout", "econnrefused", "econnreset", "temporarily")):
        return True
    return False

def _with_retry(max_attempts=3, base_delay=0.5):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            last = None
            for a in range(1, max_attempts + 1):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    if not _is_retryable(e) or a == max_attempts:
                        raise
                    msg = str(getattr(e, "message", str(e))).lower()
                    is_rate_limit = isinstance(e, ccxt.RateLimitExceeded) or "rate limit" in msg
                    delay = base_delay * (2 ** (a - 1))
                    if is_rate_limit:
                        delay *= 5  # longer backoff for rate limits
                    jitter = random.uniform(0, delay * 0.1)
                    total = delay + jitter
                    log.warning(f"{fn.__name__}: {e.__class__.__name__} retry {a}/{max_attempts} in {total:.1f}s")
                    time.sleep(total)
            raise last
        return wrapper
    return decorator

def _fix_base64_secret(s: str) -> str:
    s = s.strip()
    m = len(s) % 4
    return s + "=" * (4 - m) if m else s


# --- WebSocket feed (ticker + order book) -------------------------------------

class _KrakenWSFeed:
    WS_URL = "wss://ws.kraken.com/v2"

    def __init__(self, symbol: str = SYMBOL):
        self.symbol = symbol
        self._latest_price: Optional[float] = None
        self._order_book: dict = {"bid": [], "ask": []}
        self._running = False
        self._reconnect_delay = 1.0

    @property
    def connected(self) -> bool:
        return self._running and self._latest_price is not None

    @property
    def last_price(self) -> Optional[float]:
        return self._latest_price

    @property
    def order_book(self) -> dict:
        return self._order_book

    def start(self) -> None:
        if not _WS_ENABLED:
            log.info("WS disabled via KRAKEN_WS_DISABLE")
            return
        try:
            import threading
            self._running = True
            t = threading.Thread(target=self._run_loop, daemon=True, name="kraken-ws")
            t.start()
            log.info("WS ticker + book feed started")
        except Exception as e:
            log.warning(f"WS thread failed: {e}")

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        import asyncio
        try:
            asyncio.run(self._ws_loop())
        except Exception as e:
            log.warning(f"WS loop exited: {e}")

    async def _ws_loop(self) -> None:
        try:
            import asyncio
            import websockets
        except ImportError:
            log.warning("websockets not installed")
            return

        ws_symbol = self.symbol.replace("/", "")
        subscribe = json.dumps({
            "method": "subscribe",
            "params": {"channel": "ticker", "symbol": [ws_symbol]},
        })
        book_sub = json.dumps({
            "method": "subscribe",
            "params": {"channel": "book", "symbol": [ws_symbol], "depth": 10},
        })

        while self._running:
            try:
                async with websockets.connect(self.WS_URL, ssl=True, ping_interval=20, ping_timeout=10, max_size=2**20) as ws:
                    log.info("WS connected")
                    self._reconnect_delay = 1.0
                    await ws.send(subscribe)
                    await ws.send(book_sub)
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if data.get("channel") == "heartbeat":
                            continue
                        if data.get("channel") == "ticker":
                            self._process_ticker(data)
                        elif data.get("channel") == "book":
                            self._process_book(data)
            except Exception as e:
                if not self._running:
                    break
                log.warning(f"WS disconnected ({e}) reconnect in {self._reconnect_delay:.0f}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    def _process_ticker(self, data: dict) -> None:
        try:
            ticker = data["data"][0]
            p = float(ticker.get("last", 0))
            if p > 0:
                self._latest_price = p
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    def _process_book(self, data: dict) -> None:
        """Process order book snapshot/update."""
        try:
            book = data["data"][0]
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            if bids and asks:
                self._order_book = {
                    "bid": [[float(b[0]), float(b[1])] for b in bids[:10]],
                    "ask": [[float(a[0]), float(a[1])] for a in asks[:10]],
                }
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    def get_micro_data(self) -> dict:
        """Extract microstructure features from order book."""
        book = self._order_book
        bids = book.get("bid", [])
        asks = book.get("ask", [])
        if not bids or not asks:
            return {"bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
                    "cum_bid": 0, "cum_ask": 0, "price": self._latest_price or 0}

        best_bid, best_bid_vol = bids[0][0], bids[0][1] if bids else (0, 0)
        best_ask, best_ask_vol = asks[0][0], asks[0][1] if asks else (0, 0)

        cum_bid = sum(v for _, v in bids)
        cum_ask = sum(v for _, v in asks)

        mid = self._latest_price or (best_bid + best_ask) / 2

        return {
            "bid": best_bid, "ask": best_ask,
            "bid_vol": best_bid_vol, "ask_vol": best_ask_vol,
            "cum_bid": cum_bid, "cum_ask": cum_ask,
            "price": mid,
        }


# --- Main Engine ---------------------------------------------------------------

class KrakenEngine:
    """CCXT Kraken adapter with WS ticker, order book, retry, fee awareness."""

    def __init__(self, api_key: str, api_secret: str):
        secret = _fix_base64_secret(api_secret)
        self.ex = ccxt.kraken({
            "apiKey": api_key, "secret": secret,
            "enableRateLimit": True, "rateLimit": 150,
            "options": {"defaultType": "spot"},
        })
        for attempt in range(3):
            try:
                self.ex.load_markets()
                break
            except Exception as e:
                log.warning(f"load_markets attempt {attempt+1}/3: {e}")
                if attempt < 2:
                    time.sleep(5)
        else:
            log.error("load_markets failed after 3 attempts — using defaults")
        self._last_request: float = 0.0
        self._min_interval = 0.15
        self._ws = _KrakenWSFeed(SYMBOL)
        self._ws.start()
        # Cache market precision — CCXT returns tick size, convert to decimal places
        self._amount_precision = 8
        self._price_precision = 7
        self._taker_fee = 0.0026
        self._maker_fee = 0.0016
        try:
            m = self.ex.market(SYMBOL)
            tick_amount = m.get("precision", {}).get("amount", 1e-8)
            tick_price = m.get("precision", {}).get("price", 1e-8)
            self._amount_precision = max(0, int(round(-math.log10(tick_amount)))) if tick_amount and tick_amount > 0 else 8
            self._price_precision = max(0, int(round(-math.log10(tick_price)))) if tick_price and tick_price > 0 else 7
            self._taker_fee = m.get("taker", 0.0026)
            self._maker_fee = m.get("maker", 0.0016)
        except Exception:
            log.warning("market precision fetch failed — using defaults")

    def _throttle(self) -> None:
        now = time.time()
        w = self._last_request + self._min_interval - now
        if w > 0:
            time.sleep(w)
        self._last_request = time.time()

    @property
    def is_healthy(self) -> bool:
        if self._ws.connected:
            return True
        try:
            self.fetch_ticker()
            return True
        except Exception:
            return False

    @property
    def ws_connected(self) -> bool:
        return self._ws.connected

    @property
    def ws_price(self) -> Optional[float]:
        return self._ws.last_price

    def get_microstructure(self) -> dict:
        """Return order book microstructure for core."""
        return self._ws.get_micro_data()

    @property
    def maker_fee(self) -> float:
        return self._maker_fee

    @property
    def taker_fee(self) -> float:
        return self._taker_fee

    # --- Price ---------------------------------------------------------------

    @_with_retry(max_attempts=3)
    def fetch_ticker(self, symbol: str = SYMBOL) -> float:
        ws = self._ws.last_price
        if ws is not None and ws > 0:
            return ws
        self._throttle()
        return float(self.ex.fetch_ticker(symbol)["last"])

    # --- Balance -------------------------------------------------------------

    @_with_retry(max_attempts=3)
    def fetch_balance(self, currency: str = "EUR") -> float:
        self._throttle()
        bal = self.ex.fetch_balance()
        return float(bal.get("total", {}).get(currency, 0) or 0)

    # --- Orders (fee-aware) --------------------------------------------------

    @_with_retry(max_attempts=3)
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> dict:
        self._throttle()
        try:
            return self.ex.create_limit_buy_order(symbol, amount, price, {"oflags": "post"})
        except ccxt.InvalidOrder:
            return self.ex.create_limit_buy_order(symbol, amount, price)

    @_with_retry(max_attempts=3)
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> dict:
        self._throttle()
        try:
            return self.ex.create_limit_sell_order(symbol, amount, price, {"oflags": "post"})
        except ccxt.InvalidOrder:
            return self.ex.create_limit_sell_order(symbol, amount, price)

    @_with_retry(max_attempts=2)
    def cancel_all_orders(self, symbol: str = SYMBOL) -> list:
        self._throttle()
        try:
            orders = self.ex.fetch_open_orders(symbol) or []
            for o in orders:
                try:
                    self._throttle()
                    self.ex.cancel_order(o["id"], symbol)
                except Exception:
                    pass
            return orders
        except Exception:
            return []

    @_with_retry(max_attempts=2)
    def fetch_open_orders(self, symbol: str = SYMBOL) -> list:
        self._throttle()
        return self.ex.fetch_open_orders(symbol) or []

    def cancel_order(self, order_id: str, symbol: str = SYMBOL) -> None:
        self._throttle()
        try:
            self.ex.cancel_order(order_id, symbol)
        except Exception:
            pass

    # --- Precision -----------------------------------------------------------

    def round_amount(self, qty: float, symbol: str = SYMBOL) -> float:
        return round(qty, int(self._amount_precision))

    def round_price(self, price: float, symbol: str = SYMBOL) -> float:
        return round(price, int(self._price_precision))

    # --- Cleanup -------------------------------------------------------------

    def close(self) -> None:
        self._ws.stop()
        log.info("KrakenEngine closed")


# Backwards compat
_SYMBOL = SYMBOL
_fix_base64_secret = _fix_base64_secret

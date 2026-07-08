#!/usr/bin/env python3
"""
MEXC ENGINE v1 — Production-grade adapter with WebSocket ticker + order book.
Stessa interfaccia di KrakenEngine / BybitEngine per compatibilità con DenaroCore.

MEXC specifics:
  - Spot pairs in USDT (default SOL/USDT)
  - WS: wbs.mexc.com/ws
  - Maker fee: 0%, Taker fee: 0.1% (spot)
"""
from __future__ import annotations

import json, logging, os, random, time, math
from typing import Optional
from urllib.error import URLError, HTTPError
import ccxt

log = logging.getLogger("mexc_v1")
SYMBOL = "SOL/USDT"
_WS_ENABLED = os.environ.get("MEXC_WS_DISABLE", "0") != "1"

# --- Error classification --------------------------------------------------

_RETRYABLE = {429, 500, 502, 503, 504}

def _is_retryable(err: Exception) -> bool:
    if isinstance(err, HTTPError):
        return err.code in _RETRYABLE
    if isinstance(err, (ccxt.RateLimitExceeded, ccxt.NetworkError,
                        ccxt.RequestTimeout, ccxt.DDoSProtection)):
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
                        delay *= 5
                    jitter = random.uniform(0, delay * 0.1)
                    total = delay + jitter
                    log.warning(f"{fn.__name__}: {e.__class__.__name__} retry {a}/{max_attempts} in {total:.1f}s")
                    time.sleep(total)
            raise last
        return wrapper
    return decorator


# --- WebSocket feed (ticker + order book) ----------------------------------

class _MexcWSFeed:
    """MEXC WebSocket — ticker + order book per un symbol."""
    WS_URL = "wss://wbs.mexc.com/ws"

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
            log.info("MEXC WS disabled via MEXC_WS_DISABLE")
            return
        try:
            import threading
            self._running = True
            t = threading.Thread(target=self._run_loop, daemon=True, name="mexc-ws")
            t.start()
            log.info("MEXC WS ticker + book feed started")
        except Exception as e:
            log.warning(f"MEXC WS thread failed: {e}")

    def stop(self) -> None:
        self._running = False

    def _run_loop(self) -> None:
        import asyncio
        try:
            asyncio.run(self._ws_loop())
        except Exception as e:
            log.warning(f"MEXC WS loop exited: {e}")

    async def _ws_loop(self) -> None:
        try:
            import asyncio
            import websockets
        except ImportError:
            log.warning("websockets not installed")
            return

        ws_symbol = self.symbol.replace("/", "").upper()

        while self._running:
            try:
                async with websockets.connect(
                    self.WS_URL, ssl=True,
                    ping_interval=20, ping_timeout=10, max_size=2**20,
                ) as ws:
                    log.info("MEXC WS connected")
                    self._reconnect_delay = 1.0

                    # Subscribe: ticker + depth
                    await ws.send(json.dumps({
                        "method": "SUBSCRIPTION",
                        "params": [f"{ws_symbol}@ticker"],
                    }))
                    await ws.send(json.dumps({
                        "method": "SUBSCRIPTION",
                        "params": [f"{ws_symbol}@depth20"],
                    }))

                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        chan = data.get("c", "") or data.get("channel", "")
                        if "ticker" in chan:
                            self._process_ticker(data)
                        elif "depth" in chan:
                            self._process_book(data)
            except Exception as e:
                if not self._running:
                    break
                log.warning(f"MEXC WS disconnected ({e}) reconnect in {self._reconnect_delay:.0f}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    def _process_ticker(self, data: dict) -> None:
        try:
            d = data.get("d", data)
            p = float(d.get("lastPrice", d.get("p", 0)))
            if p > 0:
                self._latest_price = p
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    def _process_book(self, data: dict) -> None:
        try:
            d = data.get("d", data)
            bids_raw = d.get("bids", d.get("b", []))
            asks_raw = d.get("asks", d.get("a", []))
            bids = [[float(p), float(q)] for p, q in bids_raw]
            asks = [[float(p), float(q)] for p, q in asks_raw]
            bids.sort(key=lambda x: x[0], reverse=True)
            asks.sort(key=lambda x: x[0])
            self._order_book = {"bid": bids[:10], "ask": asks[:10]}
        except (KeyError, IndexError, TypeError, ValueError):
            pass

    def get_micro_data(self) -> dict:
        """Interfaccia compatibile con KrakenEngine."""
        bids = self._order_book.get("bid", [])
        asks = self._order_book.get("ask", [])
        best_bid = bids[0][0] if bids else 0.0
        best_ask = asks[0][0] if asks else 0.0
        best_bid_vol = bids[0][1] if bids else 0.0
        best_ask_vol = asks[0][1] if asks else 0.0
        cum_bid = sum(v for _, v in bids)
        cum_ask = sum(v for _, v in asks)
        mid = self._latest_price or ((best_bid + best_ask) / 2 if best_bid > 0 and best_ask > 0 else 0)
        return {
            "bid": best_bid, "ask": best_ask,
            "bid_vol": best_bid_vol, "ask_vol": best_ask_vol,
            "cum_bid": cum_bid, "cum_ask": cum_ask,
            "price": mid,
        }


# --- MEXC Engine ----------------------------------------------------------

class MexcEngine:
    """MEXC exchange adapter — interfaccia compatibile con KrakenEngine."""

    def __init__(self, api_key: str, api_secret: str, symbol: str = SYMBOL):
        self._ws = _MexcWSFeed(symbol)
        self._symbol = symbol
        self._last_request: float = 0.0
        self._min_interval: float = 0.15
        self._maker_fee = 0.0      # MEXC spot maker: 0%
        self._taker_fee = 0.001    # MEXC spot taker: 0.1%
        self._amount_precision: int = 4
        self._price_precision: int = 5

        secret = api_secret.strip()
        self.ex = ccxt.mexc({
            "apiKey": api_key,
            "secret": secret,
            "enableRateLimit": True,
            "rateLimit": 150,
            "options": {"defaultType": "spot"},
        })

        try:
            self.ex.load_markets()
            m = self.ex.market(symbol)
            self._amount_precision = m.get("precision", {}).get("amount", 4)
            if isinstance(self._amount_precision, float) and self._amount_precision > 0:
                self._amount_precision = max(0, int(-math.log10(self._amount_precision)))
            self._price_precision = m.get("precision", {}).get("price", 5)
            if isinstance(self._price_precision, float) and self._price_precision > 0:
                self._price_precision = max(0, int(-math.log10(self._price_precision)))
            self._maker_fee = m.get("maker", 0.0)
            self._taker_fee = m.get("taker", 0.001)
            log.info(f"MEXC markets loaded — {symbol} amount_prec={self._amount_precision} price_prec={self._price_precision}")
        except Exception as e:
            log.warning(f"MEXC load_markets fallback precision: {e}")

        self._ws.start()

    @property
    def ws_connected(self) -> bool:
        return self._ws.connected

    def get_microstructure(self) -> dict:
        return self._ws.get_micro_data()

    @property
    def maker_fee(self) -> float:
        return self._maker_fee

    @property
    def taker_fee(self) -> float:
        return self._taker_fee

    def _throttle(self) -> None:
        now = time.time()
        wait = self._last_request + self._min_interval - now
        if wait > 0:
            time.sleep(wait)
        self._last_request = time.time()

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
    def fetch_balance(self, currency: str = "USDT") -> float:
        self._throttle()
        bal = self.ex.fetch_balance()
        return float(bal.get("total", {}).get(currency, 0) or 0)

    # --- Orders --------------------------------------------------------------

    @_with_retry(max_attempts=3)
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> dict:
        self._throttle()
        try:
            return self.ex.create_limit_buy_order(symbol, amount, price, {"postOnly": True})
        except ccxt.InvalidOrder:
            return self.ex.create_limit_buy_order(symbol, amount, price)

    @_with_retry(max_attempts=3)
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> dict:
        self._throttle()
        try:
            return self.ex.create_limit_sell_order(symbol, amount, price, {"postOnly": True})
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
        log.info("MexcEngine closed")


# Backwards compat
_fix_base64_secret = lambda s: s  # MEXC no need for base64 fix

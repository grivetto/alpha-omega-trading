#!/usr/bin/env python3
"""
MEXC ENGINE v5 — Production-grade adapter con caching, lockout protection,
rate limiting adattivo, WebSocket ticker, e Invalid key detection.

v5 fixes (stessa pattern di KrakenEngine v5 / BybitEngine v5):
  - Balance CACHE: refresh ogni BALANCE_CACHE_TTL sec (default 15s)
  - Open orders CACHE: refresh ogni ORDERS_CACHE_TTL sec (default 10s)
  - Invalid key detection: rileva MEXC retCode → PermanentError
  - Error classification: permanente/temporaneo/lockout
  - Rate limiter adattivo
  - fetch_balance("FULL") support per main.py v5
  - Stats tracking per health endpoint
"""
from __future__ import annotations

import json, logging, os, random, time, math
from typing import Any, Optional, Tuple
from urllib.error import URLError, HTTPError
from dataclasses import dataclass
from enum import Enum
import ccxt

log = logging.getLogger("mexc_v5")
SYMBOL = "SOL/USDT"
_WS_ENABLED = os.environ.get("MEXC_WS_DISABLE", "0") != "1"

# ─── Config ──────────────────────────────────────────────────────────────────
BALANCE_CACHE_TTL = float(os.environ.get("BALANCE_CACHE_TTL", "15"))
ORDERS_CACHE_TTL = float(os.environ.get("ORDERS_CACHE_TTL", "10"))
REST_MIN_INTERVAL = float(os.environ.get("REST_MIN_INTERVAL", "0.3"))


# ─── Error classification ─────────────────────────────────────────────────────

class ErrClass(Enum):
    RETRYABLE = "retryable"
    PERMANENT = "permanent"
    LOCKOUT = "lockout"
    OK = "ok"

class MexcPermanentError(Exception):
    """Error that should NEVER be retried."""
    pass

_RETRYABLE_CODES = {429, 500, 502, 503, 504}

def classify_error(err: Exception) -> Tuple[ErrClass, str]:
    """Classify error into retryable/permanent/lockout."""
    msg = str(getattr(err, "message", str(err))).lower()

    # MEXC-specific: invalid key (retCode 10003 = invalid key, 10004 = invalid sign)
    if "retcode" in msg and ("10003" in msg or "10004" in msg):
        return ErrClass.PERMANENT, "MexcInvalidKey"
    if "invalid api key" in msg or "api key is invalid" in msg:
        return ErrClass.PERMANENT, "MexcInvalidKey"

    # CCXT classification
    if isinstance(err, ccxt.AuthenticationError):
        return ErrClass.PERMANENT, "AuthenticationError"
    if isinstance(err, ccxt.BadRequest) and "insufficient" in msg:
        return ErrClass.PERMANENT, "InsufficientFunds"
    if isinstance(err, ccxt.BadRequest):
        return ErrClass.PERMANENT, "BadRequest"
    if isinstance(err, ccxt.InvalidOrder):
        return ErrClass.PERMANENT, "InvalidOrder"
    if isinstance(err, ccxt.NotSupported):
        return ErrClass.PERMANENT, "NotSupported"

    # Lockout
    if "lockout" in msg or "temporary lockout" in msg:
        return ErrClass.LOCKOUT, "TemporaryLockout"
    if isinstance(err, ccxt.DDoSProtection) and "lockout" in msg:
        return ErrClass.LOCKOUT, "DDoSProtection+Lockout"

    # Retryable
    if isinstance(err, HTTPError):
        return (ErrClass.RETRYABLE, f"HTTP_{err.code}") if err.code in _RETRYABLE_CODES \
            else (ErrClass.PERMANENT, f"HTTP_{err.code}")
    if isinstance(err, (ccxt.RateLimitExceeded, ccxt.NetworkError, ccxt.RequestTimeout)):
        return ErrClass.RETRYABLE, err.__class__.__name__
    if isinstance(err, (URLError, ConnectionError, TimeoutError, OSError)):
        return ErrClass.RETRYABLE, err.__class__.__name__

    log.warning(f"Unclassified MEXC error: type={type(err).__name__} msg={str(err)[:200]}")
    return ErrClass.RETRYABLE, "Unknown"


def _with_retry(max_attempts=3, base_delay=0.5):
    def decorator(fn):
        def wrapper(self, *args, **kwargs):
            last = None
            for a in range(1, max_attempts + 1):
                try:
                    return fn(self, *args, **kwargs)
                except Exception as e:
                    ec, reason = classify_error(e)
                    last = e
                    if ec == ErrClass.PERMANENT:
                        log.critical(f"{fn.__name__}: PERMANENT ({reason}) — aborting")
                        raise MexcPermanentError(reason) from e
                    if ec == ErrClass.LOCKOUT:
                        delay = getattr(self, '_lockout_backoff', 60)
                        log.warning(f"{fn.__name__}: LOCKOUT — backoff {delay:.0f}s (attempt {a}/{max_attempts})")
                        time.sleep(delay)
                        continue
                    if a == max_attempts:
                        raise
                    is_rate_limit = isinstance(e, ccxt.RateLimitExceeded) or "rate limit" in reason.lower()
                    delay = base_delay * (2 ** (a - 1))
                    if is_rate_limit:
                        delay *= 5
                    total = delay + random.uniform(0, delay * 0.1)
                    log.warning(f"{fn.__name__}: {reason} retry {a}/{max_attempts} in {total:.1f}s")
                    time.sleep(total)
            raise last
        return wrapper
    return decorator


# ─── Cache ─────────────────────────────────────────────────────────────────────

@dataclass
class _CacheEntry:
    value: Any
    ts: float = 0.0

    def is_fresh(self, ttl: float) -> bool:
        return time.time() - self.ts < ttl


# ─── WebSocket feed ────────────────────────────────────────────────────────────

class _MexcWSFeed:
    """MEXC WebSocket — ticker."""
    WS_URL = "wss://wbs.mexc.com/ws"

    def __init__(self, symbol: str = SYMBOL):
        self.symbol = symbol
        self._latest_price: Optional[float] = None
        self._order_book: dict = {"bid": [], "ask": []}
        self._running = False
        self._reconnect_delay = 1.0
        self._last_ticker_ts: float = 0.0

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
            log.info("MEXC WS disabled")
            return
        try:
            import threading
            self._running = True
            t = threading.Thread(target=self._run_loop, daemon=True, name="mexc-ws")
            t.start()
            log.info("MEXC WS feed started")
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
            import asyncio, websockets
        except ImportError:
            log.warning("websockets not installed")
            return

        # MEXC WS: subscribe to ticker
        ws_symbol = self.symbol.replace("/", "").upper()
        subscribe = json.dumps({
            "method": "SUBSCRIPTION",
            "params": [f"{ws_symbol}@ticker"],
        })

        while self._running:
            try:
                async with websockets.connect(self.WS_URL, ssl=True, ping_interval=20, ping_timeout=10) as ws:
                    log.info("MEXC WS connected")
                    self._reconnect_delay = 1.0
                    await ws.send(subscribe)
                    async for raw in ws:
                        if not self._running:
                            break
                        try:
                            data = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        # Process ticker data
                        if isinstance(data, dict) and "c" in data and "lastPrice" not in data:
                            # MEXC format: {"c": "0.123", ...}
                            p = float(data.get("c", 0))
                            if p > 0:
                                self._latest_price = p
                                self._last_ticker_ts = time.time()
                        elif isinstance(data, dict) and data.get("c"):
                            p = float(data["c"])
                            if p > 0:
                                self._latest_price = p
                                self._last_ticker_ts = time.time()
            except Exception as e:
                if not self._running:
                    break
                log.warning(f"MEXC WS disconnected ({e}) reconnect in {self._reconnect_delay:.0f}s")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 30.0)

    def get_micro_data(self) -> dict:
        return {
            "bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
            "cum_bid": 0, "cum_ask": 0, "price": self._latest_price or 0,
        }


# ─── Main Engine ───────────────────────────────────────────────────────────────

class MexcEngine:
    """CCXT MEXC adapter con caching, WS, invalid key detection."""

    def __init__(self, api_key: str, api_secret: str, symbol: str = SYMBOL):
        self.symbol = symbol
        self.ex = ccxt.mexc({
            "apiKey": api_key, "secret": api_secret,
            "enableRateLimit": True, "rateLimit": 100,
            "options": {"defaultType": "spot"},
        })

        # Validate credentials immediately
        try:
            self.ex.fetch_balance()
            log.info("MEXC API credentials validated")
        except ccxt.AuthenticationError:
            raise MexcPermanentError("Invalid MEXC API credentials")
        except Exception:
            log.warning("MEXC credentials validation: will retry in main loop")

        for attempt in range(3):
            try:
                self.ex.load_markets()
                break
            except Exception as e:
                log.warning(f"MEXC load_markets attempt {attempt+1}/3: {e}")
                if attempt < 2:
                    time.sleep(5)

        self._last_request: float = 0.0
        self._min_interval = REST_MIN_INTERVAL
        self._ws = _MexcWSFeed(self.symbol)
        self._ws.start()

        self._amount_precision = 8
        self._price_precision = 5
        self._taker_fee = 0.001
        self._maker_fee = 0.0
        try:
            m = self.ex.market(self.symbol)
            self._amount_precision = max(0, int(round(-math.log10(m.get("precision", {}).get("amount", 1e-8)))))
            self._price_precision = max(0, int(round(-math.log10(m.get("precision", {}).get("price", 1e-8)))))
            self._taker_fee = m.get("taker", 0.001)
            self._maker_fee = m.get("maker", 0.0)
        except Exception:
            pass

        # Caches
        self._balance_cache: _CacheEntry = _CacheEntry(None)
        self._orders_cache: _CacheEntry = _CacheEntry(None)
        self._balance_ttl = BALANCE_CACHE_TTL
        self._orders_ttl = ORDERS_CACHE_TTL

        # Stats
        self._api_calls = 0
        self._cache_hits = 0
        self._lockout_mode = False
        self._lockout_backoff = 30.0

    @property
    def in_lockout(self) -> bool:
        return self._lockout_mode

    @property
    def lockout_remaining(self) -> float:
        return 0.0

    @property
    def ws_connected(self) -> bool:
        return self._ws.connected

    @property
    def ws_stale(self) -> bool:
        return False

    @property
    def ws_price(self) -> Optional[float]:
        return self._ws.last_price

    def clear_lockout(self) -> None:
        if self._lockout_mode:
            self._lockout_mode = False
            log.info("MEXC LOCKOUT CLEARED")

    def get_stats(self) -> dict:
        return {
            "api_calls": self._api_calls,
            "cache_hits": self._cache_hits,
            "cache_misses": self._api_calls - self._cache_hits,
            "lockout": self._lockout_mode,
            "ws_connected": self._ws.connected,
        }

    def invalidate_caches(self) -> None:
        self._balance_cache = _CacheEntry(None)
        self._orders_cache = _CacheEntry(None)

    def _throttle(self) -> None:
        now = time.time()
        w = self._last_request + self._min_interval - now
        if w > 0:
            time.sleep(w)
        self._last_request = time.time()

    # --- Price ---------------------------------------------------------------

    @_with_retry(max_attempts=2)
    def fetch_ticker(self, symbol: str = SYMBOL) -> float:
        ws = self._ws.last_price
        if ws is not None and ws > 0:
            return ws
        self._throttle()
        self._api_calls += 1
        return float(self.ex.fetch_ticker(symbol)["last"])

    # --- Balance (cached) ----------------------------------------------------

    @_with_retry(max_attempts=3)
    def fetch_balance(self, currency: str = "USDT") -> float:
        if self._balance_cache.is_fresh(self._balance_ttl) and self._balance_cache.value is not None:
            self._cache_hits += 1
            cached = self._balance_cache.value
            return cached if currency == "FULL" else cached.get(currency, 0.0)

        self._api_calls += 1
        self._throttle()
        try:
            bal = self.ex.fetch_balance()
            total = bal.get("total", {})
            free = bal.get("free", {})
            used = bal.get("used", {})
            base_asset = self.symbol.split("/")[0]
            result = {
                "USDT": float(total.get("USDT", 0) or 0),
                base_asset: float(total.get(base_asset, 0) or 0),
                "total": total, "free": free, "used": used,
            }
            self._balance_cache = _CacheEntry(result, time.time())
            self.clear_lockout()
            return result if currency == "FULL" else result.get(currency, 0.0)
        except Exception as e:
            if self._balance_cache.value is not None:
                cached = self._balance_cache.value
                return cached if currency == "FULL" else cached.get(currency, 0.0)
            raise

    def fetch_full_balance(self) -> dict:
        return self.fetch_balance("FULL")

    # --- Orders (cached) ----------------------------------------------------

    @_with_retry(max_attempts=2)
    def fetch_open_orders(self, symbol: str = SYMBOL) -> list:
        if self._orders_cache.is_fresh(self._orders_ttl) and self._orders_cache.value is not None:
            self._cache_hits += 1
            return self._orders_cache.value
        self._api_calls += 1
        self._throttle()
        orders = self.ex.fetch_open_orders(symbol) or []
        self._orders_cache = _CacheEntry(orders, time.time())
        self.clear_lockout()
        return orders

    # --- Orders --------------------------------------------------------------

    @_with_retry(max_attempts=3)
    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> dict:
        self._api_calls += 1
        self._throttle()
        try:
            result = self.ex.create_limit_buy_order(symbol, amount, price, {"postOnly": True})
            self.clear_lockout()
            self.invalidate_caches()
            return result
        except Exception as e:
            if "insufficient" in str(e).lower():
                raise MexcPermanentError(f"Insufficient funds for buy {amount} @ {price}")
            raise

    @_with_retry(max_attempts=3)
    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> dict:
        self._api_calls += 1
        self._throttle()
        try:
            result = self.ex.create_limit_sell_order(symbol, amount, price, {"postOnly": True})
            self.clear_lockout()
            self.invalidate_caches()
            return result
        except Exception as e:
            if "insufficient" in str(e).lower():
                raise MexcPermanentError(f"Insufficient funds for sell {amount} @ {price}")
            raise

    @_with_retry(max_attempts=2)
    def cancel_all_orders(self, symbol: str = SYMBOL) -> list:
        self._api_calls += 1
        self._throttle()
        try:
            orders = self.ex.fetch_open_orders(symbol) or []
            for o in orders:
                try:
                    self.ex.cancel_order(o["id"], symbol)
                except Exception:
                    pass
            self.invalidate_caches()
            return orders
        except Exception:
            return []

    def cancel_order(self, order_id: str, symbol: str = SYMBOL) -> None:
        self._api_calls += 1
        self._throttle()
        try:
            self.ex.cancel_order(order_id, symbol)
        except Exception:
            pass

    def fetch_order(self, order_id: str, symbol: str = SYMBOL) -> dict:
        self._api_calls += 1
        self._throttle()
        return self.ex.fetch_order(order_id, symbol)

    # --- OHLCV (for VaR hydration) ---------------------------------------------

    @_with_retry(max_attempts=2)
    def fetch_ohlcv(self, symbol: str = SYMBOL, timeframe: str = "1m", limit: int = 50) -> list[float]:
        self._api_calls += 1
        self._throttle()
        ohlcv = self.ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit) or []
        return [c[4] for c in ohlcv if len(c) >= 5]

    # --- Precision -----------------------------------------------------------

    def round_amount(self, qty: float, symbol: str = SYMBOL) -> float:
        return round(qty, int(self._amount_precision))

    def round_price(self, price: float, symbol: str = SYMBOL) -> float:
        return round(price, int(self._price_precision))

    @property
    def maker_fee(self) -> float:
        return self._maker_fee

    @property
    def taker_fee(self) -> float:
        return self._taker_fee

    def get_microstructure(self) -> dict:
        return self._ws.get_micro_data()

    def close(self) -> None:
        self._ws.stop()
        log.info("MexcEngine closed")

"""Exchange wrapper — Binance REST + WebSocket con retry esponenziali e rate limit adattivo.
USDC-only enforcement — nessun USDT mai toccato."""
from __future__ import annotations
import asyncio
import hashlib
import hmac
import json
import logging
import time
import urllib.parse
from collections import OrderedDict
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Optional, Union

import aiohttp

from .config import Config
from .models import PairState

log = logging.getLogger("denaro.exchange")

# ── Retry Strategy ────────────────────────────────────────────────────────

class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class RetryExhausted(Exception):
    """All retries exhausted."""


async def _retryable_request(
    coro_factory,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 20.0,
    retryable_codes: frozenset = frozenset({-1003, -1013, -2010, -2011, 429, 418, 500, 502, 503, 504}),
) -> Any:
    """Execute a request with exponential backoff.
    
    retryable_codes: -1003=rate limit, -1013=filter failure, -2010/2011=order error
                     429/418=HTTP rate limit, 5xx=Binance internal
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return await coro_factory()
        except (PermissionError, ValueError) as e:
            # Non-retryable: auth error, bad order
            raise
        except (ConnectionError, aiohttp.ClientError, asyncio.TimeoutError) as e:
            last_exc = e
            if attempt >= max_retries:
                raise RetryExhausted(f"All {max_retries} retries failed: {e}") from e
            delay = min(base_delay * (2 ** attempt) + (0.1 * attempt), max_delay)
            log.warning("Retry %d/%d in %.1fs: %s", attempt + 1, max_retries, delay, e)
            await asyncio.sleep(delay)
        except Exception as e:
            last_exc = e
            # Check if it's a dict response with retryable code
            if hasattr(e, '__cause__') and isinstance(e.__cause__, dict):
                code = e.__cause__.get("code", 0)
                if code in retryable_codes and attempt < max_retries:
                    delay = min(base_delay * (2 ** attempt) + (0.1 * attempt), max_delay)
                    log.warning("Retry %d/%d in %.1fs: code %s", attempt + 1, max_retries, delay, code)
                    await asyncio.sleep(delay)
                    continue
            if attempt >= max_retries:
                raise RetryExhausted(f"All {max_retries} retries failed: {e}") from e
            delay = min(base_delay * (2 ** attempt) + (0.1 * attempt), max_delay)
            log.warning("Retry %d/%d in %.1fs: %s", attempt + 1, max_retries, delay, e)
            await asyncio.sleep(delay)
    raise RetryExhausted(f"All {max_retries} retries failed") from last_exc


# ── Rate Limiter (sliding window with adaptive throttling) ────────────────

class RateLimitState(str, Enum):
    NORMAL = "NORMAL"
    THROTTLED = "THROTTLED"
    BACKOFF = "BACKOFF"


@dataclass
class RateLimitBucket:
    max_rpm: int = 1200
    max_owr: int = 10
    _requests: list[float] = field(default_factory=list)
    _order_weights: list[float] = field(default_factory=list)
    _state: RateLimitState = RateLimitState.NORMAL
    _state_until: float = 0.0
    _consecutive_throttles: int = 0

    def check(self, weight: int = 1) -> float:
        """Return seconds to wait. 0 = ok."""
        now = time.time()
        
        # State-based rate limit
        if self._state == RateLimitState.BACKOFF:
            wait = self._state_until - now
            if wait > 0:
                return min(wait, 30)
            self._state = RateLimitState.NORMAL
        
        if self._state == RateLimitState.THROTTLED:
            wait = self._state_until - now
            if wait > 0:
                return min(wait, 5)
            self._state = RateLimitState.NORMAL
        
        # Sliding window
        cutoff = now - 60
        self._requests = [t for t in self._requests if t > cutoff]
        self._order_weights = [t for t in self._order_weights if t > cutoff]
        
        if len(self._requests) >= self.max_rpm:
            return self._requests[0] + 60 - now
        
        # Order weight check (last 10s)
        recent_10 = [t for t in self._order_weights if t > now - 10]
        if len(recent_10) >= self.max_owr:
            return 1.0
        
        return 0.0

    def record(self, weight: int = 1) -> None:
        now = time.time()
        self._requests.append(now)
        if weight > 1:
            self._order_weights.extend([now] * (weight // 2))

    def throttle(self) -> None:
        """Called when we hit a rate limit error — increase backoff."""
        self._consecutive_throttles += 1
        delay = min(2 ** self._consecutive_throttles, 30)
        self._state = RateLimitState.BACKOFF
        self._state_until = time.time() + delay
        log.warning("Rate limiter BACKOFF for %.1fs (hit #%d)", delay, self._consecutive_throttles)

    def success(self) -> None:
        """Called on successful request — decay throttle counter."""
        if self._consecutive_throttles > 0:
            self._consecutive_throttles = max(0, self._consecutive_throttles - 1)
        if self._state != RateLimitState.NORMAL:
            self._state = RateLimitState.NORMAL


# ── Market Cache ─────────────────────────────────────────────────────────

class MarketCache:
    """Lazy-loaded exchange.markets() — never reload on hot path."""
    def __init__(self) -> None:
        self._data: dict[str, Any] = {}
        self._loaded = False
        self._load_time = 0.0
        self._load_lock = asyncio.Lock()

    async def load(self, session: aiohttp.ClientSession, api_key: str, secret: str,
                   base_url: str) -> dict[str, Any]:
        if self._loaded and time.time() - self._load_time < 3600:
            return self._data
        async with self._load_lock:
            # Double-check after acquiring lock
            if self._loaded and time.time() - self._load_time < 3600:
                return self._data
            try:
                resp = await session.get(f"{base_url}/api/v3/exchangeInfo",
                                         timeout=aiohttp.ClientTimeout(total=15))
                data = await resp.json()
                for s in data.get("symbols", []):
                    self._data[s["symbol"]] = s
                self._loaded = True
                self._load_time = time.time()
                log.info("Market cache loaded: %d symbols", len(self._data))
            except Exception as e:
                log.warning("Market cache load failed: %s — using stale data", e)
            return self._data

    def get(self, symbol: str) -> dict[str, Any]:
        # Binance API uses SOLUSDC, our config uses SOL/USDC
        s = symbol.replace("/", "")
        return self._data.get(s, {})

    def precision(self, symbol: str) -> tuple[int, int]:
        """Return (price_precision, amount_precision) for symbol."""
        info = self.get(symbol)
        if not info:
            return (8, 8)
        pp, ap = 8, 8
        for f in info.get("filters", []):
            ft = f.get("filterType")
            if ft == "LOT_SIZE":
                step_str = f.get("stepSize", "1")
                if "." in step_str:
                    ap = len(step_str.split(".")[1].rstrip("0"))
                else:
                    ap = 0
            elif ft == "PRICE_FILTER":
                tick_str = f.get("tickSize", "0.01")
                if "." in tick_str:
                    pp = len(tick_str.split(".")[1].rstrip("0"))
                else:
                    pp = 0
            elif ft == "MARKET_LOT_SIZE":
                step_str = f.get("stepSize", "1")
                if "." in step_str and ap == 8:
                    ap = len(step_str.split(".")[1].rstrip("0"))
        return (max(0, pp), max(0, ap))

    def min_notional(self, symbol: str) -> float:
        info = self.get(symbol)
        for f in info.get("filters", []):
            ft = f.get("filterType")
            if ft in ("MIN_NOTIONAL", "NOTIONAL"):
                return float(f.get("minNotional", "5"))
        return 5.0

    def lot_step_size(self, symbol: str) -> float:
        info = self.get(symbol)
        for f in info.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                return float(f.get("stepSize", "1"))
        return 0.00001

    def min_qty(self, symbol: str) -> float:
        info = self.get(symbol)
        for f in info.get("filters", []):
            if f.get("filterType") == "LOT_SIZE":
                return float(f.get("minQty", "0"))
        return 0.0

    def quote_asset(self, symbol: str) -> str:
        info = self.get(symbol)
        return info.get("quoteAsset", "")

    def base_asset(self, symbol: str) -> str:
        info = self.get(symbol)
        return info.get("baseAsset", "")

    def is_spot(self, symbol: str) -> bool:
        info = self.get(symbol)
        return info.get("status") == "TRADING" and "SPOT" in info.get("permissions", [])

    def validate_usdc_pair(self, symbol: str) -> bool:
        """Ensure this is a valid USDC-traded pair (NOT USDT)."""
        info = self.get(symbol)
        if not info:
            return False
        quote = info.get("quoteAsset", "")
        if quote == "USDT":
            log.critical("BLOCKED: %s is USDT pair — USDC only!", symbol)
            return False
        return quote == "USDC" and info.get("status") == "TRADING"


# ── Exchange ─────────────────────────────────────────────────────────────

class Exchange:
    """Async Binance exchange wrapper — USDC-only."""
    BASE = "https://api.binance.com"
    WS_BASE = "wss://stream.binance.com:9443/ws"
    WS_COMBINED = "wss://stream.binance.com:9443/stream"

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        self.base_url = cfg.testnet and "https://testnet.binance.vision" or self.BASE
        self.ws_url = cfg.testnet and "wss://testnet.binance.vision/ws" or self.WS_BASE
        self.ws_combined = cfg.testnet and "wss://testnet.binance.vision/stream" or self.WS_COMBINED
        self.key = cfg.api_key
        self._secret = cfg.api_secret.encode()
        self.session: Optional[aiohttp.ClientSession] = None
        self.rate_limiter = RateLimitBucket()
        self.markets = MarketCache()
        
        # Caches
        self._price_cache: dict[str, tuple[float, float]] = {}      # symbol -> (price, ts)
        self._imbalance_cache: dict[str, tuple[float, float]] = {}
        self._balance_cache: tuple[float, dict[str, float]] = (0.0, {})
        self._last_balance_fetch = 0.0
        self._last_ohlcv_fetch: dict[str, float] = {}

    async def start(self) -> None:
        self.session = aiohttp.ClientSession(
            headers={"X-MBX-APIKEY": self.key},
            timeout=aiohttp.ClientTimeout(total=15),
        )
        await self.markets.load(self.session, self.key, self.cfg.api_secret, self.base_url)
        
        # Validate all pairs are USDC
        for pair in self.cfg.pairs:
            if not self.markets.validate_usdc_pair(pair):
                raise ValueError(f"Pair {pair} is NOT a valid USDC pair! Refusing to start.")

    async def stop(self) -> None:
        if self.session:
            await self.session.close()

    def _sign(self, params: dict) -> dict:
        params["timestamp"] = int(time.time() * 1000)
        params["recvWindow"] = self.cfg.recv_window
        qs = urllib.parse.urlencode(params)
        params["signature"] = hmac.new(self._secret, qs.encode(), hashlib.sha256).hexdigest()
        return params

    async def _request(self, method: str, path: str,
                       params: Optional[dict] = None,
                       data: Optional[dict] = None,
                       signed: bool = False,
                       weight: int = 1) -> Union[dict[str, Any], list[Any]]:
        """Generic rate-limited HTTP request with retry."""
        if not self.session:
            raise RuntimeError("Exchange not started")
        
        params = params or {}
        
        # Normalize symbol: SOL/USDC → SOLUSDC for Binance API
        if "symbol" in params:
            params["symbol"] = params["symbol"].replace("/", "")
        
        # Rate limit check
        while (wait := self.rate_limiter.check(weight)) > 0:
            log.debug("Rate limit wait: %.1fs", wait)
            await asyncio.sleep(min(wait, 5))
        
        if signed:
            params = self._sign(params)
        
        url = f"{self.base_url}{path}"
        
        async def _do_request():
            nonlocal url, method, params, data, weight
            if method == "GET":
                resp = await self.session.get(url, params=params)
            elif method == "POST":
                resp = await self.session.post(url, data=params)
            elif method == "DELETE":
                resp = await self.session.delete(url, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            self.rate_limiter.record(weight)
            
            if resp.status in (429, 418):
                self.rate_limiter.throttle()
                retry_after = int(resp.headers.get("Retry-After", "5"))
                raise ConnectionError(f"HTTP {resp.status}: rate limited, retry after {retry_after}s")
            
            text = await resp.text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                raise ConnectionError(f"Invalid JSON response ({resp.status}): {text[:200]}")
            
            if isinstance(data, dict) and "code" in data:
                code = data["code"]
                msg = data.get("msg", "")
                if code in (-2015, -2008):
                    raise PermissionError(f"Auth error ({code}): {msg}")
                if code in (-1013, -2010, -2011):
                    raise ValueError(f"Order error ({code}): {msg}")
                if code == -1003:
                    self.rate_limiter.throttle()
                    raise ConnectionError(f"Rate limited ({code}): {msg}")
                if code == -1121:
                    raise ValueError(f"Invalid symbol ({code}): {msg}")
                # Other non-critical errors
                log.warning("Binance API error %s: %s", code, msg)
            
            return data
        
        try:
            result = await _retryable_request(_do_request, max_retries=3, base_delay=1.0)
            self.rate_limiter.success()
            return result
        except (PermissionError, ValueError):
            # Don't swallow these — they need immediate attention
            raise
        except RetryExhausted as e:
            log.error("Request failed after retries: %s %s — %s", method, path, e)
            raise ConnectionError(str(e)) from e

    async def _get(self, path: str, params: Optional[dict] = None,
                   signed: bool = False, weight: int = 1) -> Any:
        return await self._request("GET", path, params=params, signed=signed, weight=weight)

    async def _post(self, path: str, params: dict, weight: int = 1) -> dict[str, Any]:
        result = await self._request("POST", path, params=params, signed=True, weight=weight)
        return result if isinstance(result, dict) else {}

    async def _delete(self, path: str, params: dict, weight: int = 1) -> dict[str, Any]:
        result = await self._request("DELETE", path, params=params, signed=True, weight=weight)
        return result if isinstance(result, dict) else {}

    # ── Public endpoints ──

    async def ticker_price(self, symbol: str) -> float:
        """Get current price with in-memory cache (0.3s TTL)."""
        now = time.time()
        cached = self._price_cache.get(symbol)
        if cached and now - cached[1] < 0.3:
            return cached[0]
        try:
            data = await self._get("/api/v3/ticker/price", {"symbol": symbol}, weight=1)
            if isinstance(data, dict):
                price = float(data.get("price", 0))
                self._price_cache[symbol] = (price, now)
                return price
        except Exception as e:
            # Fall back to cache if available
            if cached:
                return cached[0]
            log.warning("Price fetch failed: %s", e)
        return 0.0

    async def depth(self, symbol: str, limit: int = 20) -> dict[str, Any]:
        data = await self._get("/api/v3/depth", {"symbol": symbol, "limit": limit}, weight=5)
        return data if isinstance(data, dict) else {"bids": [], "asks": []}

    async def ohlcv(self, symbol: str, interval: str = "5m", limit: int = 30) -> list[list[Any]]:
        data = await self._get("/api/v3/klines",
                               {"symbol": symbol, "interval": interval, "limit": limit},
                               weight=1)
        return data if isinstance(data, list) else []

    async def exchange_info(self, symbol: Optional[str] = None) -> dict[str, Any]:
        params = {}
        if symbol:
            params["symbol"] = symbol
        data = await self._get("/api/v3/exchangeInfo", params=params, weight=10)
        return data if isinstance(data, dict) else {}

    # ── Signed endpoints ──

    async def fetch_balance(self) -> dict[str, float]:
        """Get all non-zero balances, cached for balance_interval seconds."""
        now = time.time()
        if now - self._last_balance_fetch < self.cfg.balance_interval and self._balance_cache[0] > 0:
            return self._balance_cache[1]
        data = await self._get("/api/v3/account", signed=True, weight=10)
        balances: dict[str, float] = {}
        for item in data.get("balances", []):
            free = float(item["free"])
            locked = float(item["locked"])
            total = free + locked
            if total > 0.00001:
                balances[item["asset"]] = total
        # Always add USDC even if zero — important for display
        balances.setdefault("USDC", 0.0)
        self._balance_cache = (now, balances)
        self._last_balance_fetch = now
        return balances

    async def free_balance(self, asset: str) -> float:
        """Get free balance for a single asset (uncached)."""
        data = await self._get("/api/v3/account", signed=True, weight=10)
        for item in data.get("balances", []):
            if item["asset"] == asset:
                return float(item["free"])
        return 0.0

    async def balance(self) -> dict[str, dict[str, float]]:
        """Get all balances with free/locked detail (for loop.py consumption)."""
        data = await self._get("/api/v3/account", signed=True, weight=10)
        result: dict[str, dict[str, float]] = {}
        for item in data.get("balances", []):
            free = float(item["free"])
            locked = float(item["locked"])
            if free > 0.00001 or locked > 0.00001:
                result[item["asset"]] = {"free": free, "locked": locked}
        result.setdefault("USDC", {"free": 0.0, "locked": 0.0})
        return result

    async def open_orders(self, symbol: str) -> list[dict[str, Any]]:
        return await self._get("/api/v3/openOrders", {"symbol": symbol}, signed=True, weight=3)

    async def all_open_orders(self) -> list[dict[str, Any]]:
        return await self._get("/api/v3/openOrders", signed=True, weight=20)

    async def place_limit_order(self, symbol: str, side: OrderSide, price: float,
                                amount: float) -> Optional[dict[str, Any]]:
        """Place a LIMIT order with proper precision rounding."""
        side_str = "BUY" if side == OrderSide.BUY else "SELL"
        pp, ap = self.markets.precision(symbol)
        
        # Round to market precision
        price_r = round(price, pp)
        amount_r = round(amount, ap)
        
        # Validate minimum notional
        if price_r * amount_r < self.markets.min_notional(symbol):
            log.warning("[%s] LIMIT %s too small: %.4f * %.6f = %.2f < %.2f min notional",
                        symbol, side_str, price_r, amount_r, price_r * amount_r,
                        self.markets.min_notional(symbol))
            return None
        
        params = {
            "symbol": symbol,
            "side": side_str,
            "type": "LIMIT",
            "timeInForce": "GTC",
            "price": f"{price_r:.{pp}f}",
            "quantity": f"{amount_r:.{ap}f}",
        }
        log.info("ORDER %s %s LIMIT %.6f x %.6f", symbol, side_str, price_r, amount_r)
        if self.cfg.dry_run:
            return None
        
        try:
            result = await self._post("/api/v3/order", params, weight=5)
            return result
        except ValueError as e:
            log.warning("[%s] LIMIT %s rejected: %s", symbol, side_str, e)
            return None

    async def place_market_order(self, symbol: str, side: OrderSide, amount: float,
                                 quote: bool = False) -> Optional[dict[str, Any]]:
        """Place a MARKET order. amount = base qty by default, quote qty if quote=True."""
        side_str = "BUY" if side == OrderSide.BUY else "SELL"
        key = "quoteOrderQty" if quote else "quantity"
        _, ap = self.markets.precision(symbol)
        
        if quote:
            qty = f"{amount:.2f}"
        else:
            qty = f"{amount:.{ap}f}"
        
        # Notional check for non-quote orders
        if not quote:
            price = await self.ticker_price(symbol)
            if price > 0 and price * amount < self.markets.min_notional(symbol):
                log.warning("[%s] MARKET %s too small: %.6f * %.2f < %.2f",
                            symbol, side_str, amount, price, self.markets.min_notional(symbol))
                return None
        
        params = {
            "symbol": symbol,
            "side": side_str,
            "type": "MARKET",
            key: qty,
        }
        log.info("ORDER %s %s MARKET %s=%s", symbol, side_str, key, qty)
        if self.cfg.dry_run:
            return None
        
        try:
            result = await self._post("/api/v3/order", params, weight=5)
            return result
        except ValueError as e:
            log.warning("[%s] MARKET %s rejected: %s", symbol, side_str, e)
            return None

    async def cancel_order(self, symbol: str, order_id: str) -> Optional[dict[str, Any]]:
        params = {"symbol": symbol, "orderId": order_id}
        if self.cfg.dry_run:
            return None
        try:
            return await self._delete("/api/v3/order", params, weight=1)
        except Exception as e:
            log.debug("[%s] Cancel %s: %s", symbol, order_id, e)
            return None

    async def cancel_all_orders(self, symbol: str) -> int:
        orders = await self.open_orders(symbol)
        count = 0
        for o in orders:
            try:
                await self.cancel_order(symbol, o["orderId"])
                count += 1
                await asyncio.sleep(0.05)
            except Exception as e:
                log.warning("[%s] Cancel %s: %s", symbol, o.get("orderId", "?"), e)
        if count:
            log.info("[%s] Cancelled %d orders", symbol, count)
        return count

    async def order_status(self, symbol: str, order_id: str) -> Optional[dict[str, Any]]:
        try:
            return await self._get("/api/v3/order",
                                   {"symbol": symbol, "orderId": order_id},
                                   signed=True, weight=2)
        except Exception as e:
            log.debug("[%s] Status %s: %s", symbol, order_id, e)
            return None

    # ── Helpers ──

    def round_amount(self, symbol: str, amount: float) -> float:
        _, ap = self.markets.precision(symbol)
        return round(amount, ap)

    def round_price(self, symbol: str, price: float) -> float:
        pp, _ = self.markets.precision(symbol)
        return round(price, pp)

    async def get_min_notional_buy(self, symbol: str) -> float:
        """Return the minimum BUY order value in quote currency."""
        min_not = self.markets.min_notional(symbol)
        # For a BUY, we need at least 'minNotional' worth of quote
        return max(min_not, 5.0)

    @property
    def is_ready(self) -> bool:
        return self.session is not None and not self.session.closed

    async def close(self) -> None:
        """Close HTTP session."""
        if self.session and not self.session.closed:
            await self.session.close()


# ── WebSocket Client ─────────────────────────────────────────────────────

class WSClient:
    """Async WebSocket client for Binance streams with auto-reconnect."""
    
    def __init__(self, exchange: Exchange) -> None:
        self.exchange = exchange
        self._prices: dict[str, float] = {}
        self._depths: dict[str, dict[str, Any]] = {}
        self._trades: dict[str, list[float]] = {}
        self._volumes: dict[str, list[float]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def get_price(self, symbol: str) -> float:
        nkey = symbol.replace("/", "").upper()
        return self._prices.get(nkey, 0.0)

    def get_imbalance(self, symbol: str) -> float:
        nkey = symbol.replace("/", "").upper()
        depth = self._depths.get(nkey)
        if not depth:
            return 1.0
        bids = sum(b[1] for b in depth.get("bids", []))
        asks = sum(a[1] for a in depth.get("asks", []))
        return bids / asks if asks > 0 else 1.0

    def get_bid_ask(self, symbol: str) -> tuple[float, float]:
        nkey = symbol.replace("/", "").upper()
        depth = self._depths.get(nkey)
        if not depth:
            return (0.0, 0.0)
        bids = depth.get("bids", [])
        asks = depth.get("asks", [])
        best_bid = float(bids[0][0]) if bids else 0.0
        best_ask = float(asks[0][0]) if asks else 0.0
        return (best_bid, best_ask)

    def get_spread_pct(self, symbol: str) -> float:
        bid, ask = self.get_bid_ask(symbol)
        if bid <= 0 or ask <= 0:
            return 0.0
        return (ask - bid) / bid

    def get_recent_trades(self, symbol: str) -> list[float]:
        nkey = symbol.replace("/", "").upper()
        return self._trades.get(nkey, [])

    def get_recent_volumes(self, symbol: str) -> list[float]:
        nkey = symbol.replace("/", "").upper()
        return self._volumes.get(nkey, [])

    def get_vwap(self, symbol: str, lookback: int = 20) -> float:
        """Volume-weighted average price from recent trades."""
        nkey = symbol.replace("/", "").upper()
        trades = self._trades.get(nkey, [])
        if not trades:
            return 0.0
        return sum(trades[-lookback:]) / min(len(trades), lookback)

    async def start(self, symbols: list[str]) -> None:
        self._running = True
        streams = []
        for s in symbols:
            norm = s.replace("/", "").lower()
            streams.extend([
                f"{norm}@ticker",
                f"{norm}@depth20@100ms",
                f"{norm}@aggTrade",
                f"{norm}@kline_5m",
            ])
        url = f"{self.exchange.ws_combined}?streams={'/'.join(streams)}"
        self._task = asyncio.create_task(self._run(url))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _run(self, url: str) -> None:
        retries = 0
        while self._running:
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.ws_connect(url, heartbeat=30,
                                                   receive_timeout=60) as ws:
                        log.info("WS connected: %s ...", url[:80])
                        retries = 0
                        async for msg in ws:
                            if not self._running:
                                break
                            if msg.type == aiohttp.WSMsgType.TEXT:
                                try:
                                    self._on_message(json.loads(msg.data))
                                except json.JSONDecodeError:
                                    pass
                            elif msg.type == aiohttp.WSMsgType.ERROR:
                                log.warning("WS error: %s", ws.exception())
                                break
            except asyncio.CancelledError:
                break
            except Exception as e:
                if not self._running:
                    break
                retries += 1
                wait = min(2 ** retries, 30)
                log.warning("WS disconnect (retry %d in %ds): %s", retries, wait, e)
                await asyncio.sleep(wait)

    def _on_message(self, msg: dict[str, Any]) -> None:
        data = msg.get("data", msg)
        stream = msg.get("stream", "")
        if not stream:
            return

        if "@ticker" in stream:
            sym = data.get("s", "").upper()
            price = float(data.get("c", 0))
            if sym and price:
                self._prices[sym] = price

        elif "@depth20" in stream:
            sym = data.get("s", "").upper()
            if sym:
                self._depths[sym] = {
                    "bids": data.get("b", []),
                    "asks": data.get("a", []),
                }

        elif "@aggTrade" in stream:
            sym = data.get("s", "").upper()
            price = float(data.get("p", 0))
            qty = float(data.get("q", 0))
            if sym and price:
                trades = self._trades.setdefault(sym, [])
                trades.append(price)
                vols = self._volumes.setdefault(sym, [])
                vols.append(qty)
                if len(trades) > 100:
                    self._trades[sym] = trades[-100:]
                    self._volumes[sym] = vols[-100:]

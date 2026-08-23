#!/usr/bin/env python3
"""Denaro v7 — OKX Engine using CCXT.

Direct CCXT-based implementation for OKX with identical interface to KrakenEngine.
Supports both REST and WebSocket for real-time market data.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

import ccxt
import ccxt.pro as ccxtpro

from .exchange import ExchangeAdapter

log = logging.getLogger("denaro.okx")


class OKXPermanentError(Exception):
    """Non-retryable OKX API error."""
    pass


class OKXLockoutError(Exception):
    """Temporary lockout / rate limit from OKX."""
    pass


class OKXEngine:
    """OKX engine with CCXT/CCXT Pro for REST + WebSocket."""

    SYMBOL_MAP = {
        "BTC/USDT": "BTC-USDT",
        "ETH/USDT": "ETH-USDT",
        "SOL/USDT": "SOL-USDT",
        "XRP/USDT": "XRP-USDT",
        "ADA/USDT": "ADA-USDT",
        "DOGE/USDT": "DOGE-USDT",
        "LINK/USDT": "LINK-USDT",
        "AVAX/USDT": "AVAX-USDT",
        "BICO/USDT": "BICO-USDT",
        "GRVT/USDT": "GRVT-USDT",
    }

    def __init__(self,
                 api_key: str,
                 secret: str,
                 passphrase: str,
                 symbol: str = "BTC/USDT",
                 sandbox: bool = False,
                 ws_enabled: bool = True,
                 eea: bool = False) -> None:

        self.api_key = api_key
        self.secret = secret
        self.passphrase = passphrase
        self.symbol = symbol
        self.sandbox = sandbox
        self.ws_enabled = ws_enabled
        self.eea = eea

        self._okx_symbol = self.SYMBOL_MAP.get(symbol, symbol)
        self._ex: Optional[ccxt.okx] = None
        self._ws: Optional[ccxtpro.okx] = None
        self._ws_task: Optional[asyncio.Task] = None
        self._ws_loop: Optional[asyncio.AbstractEventLoop] = None
        self._ws_thread: Optional[threading.Thread] = None

        self._last_ticker: float = 0.0
        self._last_book: Dict = {}
        self._ws_connected: bool = False
        self._ws_stale_ts: float = 0.0
        self._lockout_until: float = 0.0

        self._api_calls = 0
        self._cache_hits = 0
        self._cache_misses = 0

        self._balance_cache: Optional[Dict] = None
        self._balance_cache_ts: float = 0.0
        self._orders_cache: Optional[List] = None
        self._orders_cache_ts: float = 0.0

        self._initialize_rest()

    def _initialize_rest(self) -> None:
        """Initialize CCXT REST client. Supports EEA hostname for EU accounts."""
        config = {
            'apiKey': self.api_key,
            'secret': self.secret,
            'password': self.passphrase,
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            },
        }
        if self.eea:
            # OKX EEA: chiavi EU separate, hostname eea.okx.com obbligatorio
            config['hostname'] = 'eea.okx.com'
            log.info("OKX EEA endpoint enabled (eea.okx.com)")
        elif self.sandbox:
            config['urls'] = {
                'api': {
                    'rest': 'https://www.okx.com/api/v5',
                    'public': 'https://www.okx.com/api/v5',
                    'private': 'https://www.okx.com/api/v5',
                },
            }

        self._ex = ccxt.okx(config)

    def start_ws(self) -> None:
        """Start WebSocket connection in background thread."""
        if not self.ws_enabled:
            return

        def run_ws_loop():
            self._ws_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._ws_loop)
            self._ws_loop.run_until_complete(self._ws_main())

        self._ws_thread = threading.Thread(target=run_ws_loop, daemon=True)
        self._ws_thread.start()
        log.info("OKX WebSocket thread started")

    async def _ws_main(self) -> None:
        """WebSocket main loop for ticker + orderbook."""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                self._ws = ccxtpro.okx({
                    'apiKey': self.api_key,
                    'secret': self.secret,
                    'password': self.passphrase,
                    'enableRateLimit': True,
                    'options': {'defaultType': 'spot'},
                })

                await self._ws.load_markets()

                ticker_task = asyncio.create_task(self._ws_watch_ticker())
                book_task = asyncio.create_task(self._ws_watch_orderbook())

                done, pending = await asyncio.wait(
                    [ticker_task, book_task],
                    return_when=asyncio.FIRST_COMPLETED
                )

                for task in pending:
                    task.cancel()

            except Exception as e:
                log.warning(f"OKX WS error (attempt {attempt + 1}/{max_retries}): {e}")
                await asyncio.sleep(retry_delay)
                retry = min(retry_delay * 2, 60)

            finally:
                if self._ws:
                    await self._ws.close()

        self._ws_connected = False
        log.error("OKX WebSocket permanently disconnected")

    async def _ws_watch_ticker(self) -> None:
        """Watch ticker via WebSocket."""
        while True:
            try:
                ticker = await self._ws.watch_ticker(self._okx_symbol)
                self._last_ticker = float(ticker['last'])
                self._ws_stale_ts = 0.0
            except Exception as e:
                self._ws_stale_ts = time.time()
                log.debug(f"WS ticker error: {e}")
                await asyncio.sleep(0.5)

    async def _ws_watch_orderbook(self) -> None:
        """Watch orderbook via WebSocket."""
        while True:
            try:
                book = await self._ws.watch_order_book(self._okx_symbol, limit=50)
                self._last_book = book
                self._ws_connected = True
                self._ws_stale_ts = 0.0
            except Exception as e:
                self._ws_connected = False
                self._ws_stale_ts = time.time()
                log.debug(f"WS book error: {e}")
                await asyncio.sleep(0.5)

    def fetch_ticker(self, symbol: str = None) -> float:
        """Get latest price from WS or REST fallback."""
        if self.ws_enabled and self._ws_connected and self._ws_stale_ts == 0.0:
            self._cache_hits += 1
            return self._last_ticker if self._last_ticker > 0 else self._fetch_ticker_rest(symbol)

        self._cache_misses += 1
        return self._fetch_ticker_rest(symbol)

    def _fetch_ticker_rest(self, symbol: str = None) -> float:
        """REST fallback for ticker."""
        self._api_calls += 1
        try:
            ticker = self._ex.fetch_ticker(symbol or self._okx_symbol)
            return float(ticker['last'])
        except ccxt.RateLimitExceeded as e:
            self._lockout_until = time.time() + 60
            raise OKXLockoutError(f"Rate limited: {e}")
        except ccxt.BadRequest as e:
            raise OKXPermanentError(f"Bad request: {e}")
        except ccxt.InvalidOrder as e:
            raise OKXPermanentError(f"Invalid order: {e}")
        except ccxt.NotSupported as e:
            raise OKXPermanentError(f"Not supported: {e}")
        except Exception as e:
            if "rate limit" in str(e).lower():
                self._lockout_until = time.time() + 60
                raise OKXLockoutError(f"Rate limited: {e}")
            if "authentication" in str(e).lower() or "signature" in str(e).lower():
                raise OKXPermanentError(f"Auth failed: {e}")
            raise OKXLockoutError(f"REST ticker error: {e}")

    def get_microstructure(self) -> Dict:
        """Current order book microstructure from WS or REST."""
        if self.ws_enabled and self._ws_connected and self._last_book:
            return self._parse_microstructure(self._last_book)
        return self._fetch_microstructure_rest()

    def _fetch_microstructure_rest(self) -> Dict:
        """REST fallback for order book."""
        self._api_calls += 1
        try:
            book = self._ex.fetch_order_book(self._okx_symbol, limit=50)
            return self._parse_microstructure(book)
        except Exception as e:
            log.warning(f"OKX microstructure fetch failed: {e}")
            return {"bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
                    "cum_bid": 0, "cum_ask": 0, "price": 0}

    def _parse_microstructure(self, book: Dict) -> Dict:
        """Parse OKX order book into microstructure metrics."""
        bids = book.get('bids', [])[:20]
        asks = book.get('asks', [])[:20]

        if not bids or not asks:
            return {"bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
                    "cum_bid": 0, "cum_ask": 0, "price": 0}

        bid_price = float(bids[0][0])
        bid_vol = float(bids[0][1])
        ask_price = float(asks[0][0])
        ask_vol = float(asks[0][1])

        mid = (bid_price + ask_price) / 2

        cum_bid = sum(float(b[0]) * float(b[1]) for b in bids if b[0] > mid * 0.99)
        cum_ask = sum(float(a[0]) * float(a[1]) for a in asks if a[0] < mid * 1.01)

        spread_pct = (ask_price - bid_price) / mid
        imbalance = bid_vol / max(ask_vol, 1e-10)

        return {
            "bid": bid_price,
            "ask": ask_price,
            "bid_vol": bid_vol,
            "ask_vol": ask_vol,
            "cum_bid_depth_1pct": cum_bid,
            "cum_ask_depth_1pct": cum_ask,
            "bid_ask_spread_pct": spread_pct,
            "bid_ask_imbalance": imbalance,
            "price": mid,
        }

    def fetch_balance(self, currency: str = "USDT") -> float:
        return float(self.fetch_full_balance().get(currency.upper(), 0.0))

    def fetch_full_balance(self) -> Dict:
        """Fetch full balance from OKX (cached)."""
        if self._balance_cache and time.time() - self._balance_cache_ts < 15:
            self._cache_hits += 1
            return self._balance_cache

        self._cache_misses += 1
        self._api_calls += 1
        try:
            balance = self._ex.fetch_balance()
            total = {}
            for curr, info in balance.items():
                if isinstance(info, dict) and 'total' in info:
                    total[curr] = float(info['total'])
                elif isinstance(info, (int, float)):
                    total[curr] = float(info)

            self._balance_cache = total
            self._balance_cache_ts = time.time()
            return total
        except ccxt.RateLimitExceeded as e:
            self._lockout_until = time.time() + 60
            raise OKXLockoutError(f"Balance rate limited: {e}")
        except Exception as e:
            log.error(f"OKX balance fetch failed: {e}")
            return self._balance_cache or {}

    def fetch_open_orders(self, symbol: str = None) -> List:
        """Fetch open orders from OKX (cached)."""
        if self._orders_cache and time.time() - self._orders_cache_ts < 10:
            self._cache_hits += 1
            return self._orders_cache

        self._cache_misses += 1
        self._api_calls += 1
        try:
            orders = self._ex.fetch_open_orders(symbol or self._okx_symbol)
            self._orders_cache = orders
            self._orders_cache_ts = time.time()
            return orders
        except ccxt.RateLimitExceeded as e:
            self._lockout_until = time.time() + 60
            raise OKXLockoutError(f"Orders rate limited: {e}")
        except Exception as e:
            log.error(f"OKX open orders fetch failed: {e}")
            return []

    def create_limit_buy_order(self, symbol: str, amount: float, price: float) -> Dict:
        self._api_calls += 1
        self._invalidate_caches()
        try:
            order = self._ex.create_limit_buy_order(symbol or self._okx_symbol, amount, price)
            return {"id": order['id'], "symbol": order['symbol']}
        except ccxt.RateLimitExceeded as e:
            self._lockout_until = time.time() + 60
            raise OKXLockoutError(f"Buy rate limited: {e}")
        except ccxt.InvalidOrder as e:
            raise OKXPermanentError(f"Invalid buy order: {e}")
        except Exception as e:
            if "rate limit" in str(e).lower():
                self._lockout_until = time.time() + 60
                raise OKXLockoutError(f"Buy rate limited: {e}")
            raise OKXPermanentError(f"Buy order failed: {e}")

    def create_limit_sell_order(self, symbol: str, amount: float, price: float) -> Dict:
        self._api_calls += 1
        self._invalidate_caches()
        try:
            order = self._ex.create_limit_sell_order(symbol or self._okx_symbol, amount, price)
            return {"id": order['id'], "symbol": order['symbol']}
        except ccxt.RateLimitExceeded as e:
            self._lockout_until = time.time() + 60
            raise OKXLockoutError(f"Sell rate limited: {e}")
        except ccxt.InvalidOrder as e:
            raise OKXPermanentError(f"Invalid sell order: {e}")
        except Exception as e:
            if "rate limit" in str(e).lower():
                self._lockout_until = time.time() + 60
                raise OKXLockoutError(f"Sell rate limited: {e}")
            raise OKXPermanentError(f"Sell order failed: {e}")

    def cancel_order(self, order_id: str, symbol: str = None) -> None:
        self._api_calls += 1
        self._invalidate_caches()
        try:
            self._ex.cancel_order(order_id, symbol or self._okx_symbol)
        except Exception as e:
            log.warning(f"OKX cancel order {order_id} failed: {e}")

    def cancel_all_orders(self, symbol: str = None) -> List:
        self._api_calls += 1
        self._invalidate_caches()
        try:
            return self._ex.cancel_all_orders(symbol or self._okx_symbol)
        except Exception as e:
            log.warning(f"OKX cancel all failed: {e}")
            return []

    def fetch_order(self, order_id: str, symbol: str = None) -> Dict:
        self._api_calls += 1
        try:
            return self._ex.fetch_order(order_id, symbol or self._okx_symbol)
        except Exception as e:
            log.warning(f"OKX fetch order {order_id} failed: {e}")
            return {"status": "closed", "filled": 0}

    def round_amount(self, qty: float, symbol: str = None) -> float:
        market = self._ex.market(symbol or self._okx_symbol)
        precision = market['precision']['amount']
        if precision:
            return round(qty - (qty % precision), int(-precision))
        return qty

    def round_price(self, price: float, symbol: str = None) -> float:
        market = self._ex.market(symbol or self._okx_symbol)
        precision = market['precision']['price']
        if precision:
            return round(price - (price % precision), int(-precision))
        return price

    def get_stats(self) -> Dict:
        return {
            "api_calls": self._api_calls,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "ws_connected": self._ws_connected,
            "ws_stale": self.ws_stale(),
        }

    def is_healthy(self) -> bool:
        return self._ws_connected or time.time() - self._last_ticker < 60

    @property
    def in_lockout(self) -> bool:
        return time.time() < self._lockout_until

    @property
    def lockout_remaining(self) -> float:
        return max(0.0, self._lockout_until - time.time())

    def ws_connected(self) -> bool:
        return self._ws_connected

    def ws_stale(self) -> bool:
        return self._ws_stale_ts > 0 and time.time() - self._ws_stale_ts > 30

    def _invalidate_caches(self) -> None:
        self._balance_cache = None
        self._orders_cache = None

    def close(self) -> None:
        if self._ws_loop:
            self._ws_loop.call_soon_threadsafe(self._ws_loop.stop)


import threading
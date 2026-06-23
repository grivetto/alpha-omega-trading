"""Denaro v3 Data Feeder — Cached API access layer.

Fetch ONCE, serve MANY. Invalidate only when necessary.
Single entry point for ALL exchange data. Reduces API calls by ~90%.
"""

import time
from typing import Dict, List, Optional, Any
from loguru import logger

from .config import APIConfig


class DataFeeder:
    """Cached wrapper around ccxt exchange. One fetch = N reads."""

    def __init__(self, exchange, config: APIConfig):
        self._exchange = exchange
        self._config = config
        self._cache: Dict[str, tuple[float, Any]] = {}
        self._trade_count: int = 0  # Incremented after each fill

    def _get(self, key: str, ttl: int) -> Optional[Any]:
        """Return cached value if not expired."""
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < ttl:
                return value
        return None

    def _set(self, key: str, value: Any):
        """Store value in cache."""
        self._cache[key] = (time.time(), value)

    def invalidate(self, prefix: str = ""):
        """Remove all cached entries matching prefix. Called after trades."""
        if prefix:
            self._cache = {k: v for k, v in self._cache.items() if not k.startswith(prefix)}
        else:
            self._cache.clear()

    # ── Balance ────────────────────────────────────────────
    def get_balance(self) -> Dict[str, Dict[str, float]]:
        """Fetch balance once per cycle. Invalidate after trade."""
        key = "balance"
        cached = self._get(key, self._config.cache_ttl_balance)
        if cached is not None:
            return cached
        try:
            balance = self._exchange.fetch_balance()
            self._set(key, balance)
            return balance
        except Exception as e:
            logger.error(f"Balance fetch failed: {e}")
            return self._get(key, 99999) or {"free": {}, "used": {}, "total": {}}

    def get_free_balance(self, asset: str) -> float:
        """Return free balance for a specific asset."""
        balance = self.get_balance()
        return float(balance.get(asset, {}).get("free", 0) or 0)

    def get_total_balance(self, asset: str) -> float:
        """Return total (free + locked) balance for a specific asset."""
        balance = self.get_balance()
        return float(balance.get(asset, {}).get("total", 0) or 0)

    # ── OHLCV ──────────────────────────────────────────────
    def get_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[List[float]]:
        """Fetch OHLCV with caching. Used by grid + indicators."""
        key = f"ohlcv:{symbol}:{timeframe}:{limit}"
        ttl = self._config.cache_ttl_ohlcv if timeframe in ("1h", "4h") else 120
        cached = self._get(key, ttl)
        if cached is not None:
            return cached
        try:
            ohlcv = self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            self._set(key, ohlcv)
            return ohlcv
        except Exception as e:
            logger.error(f"OHLCV fetch failed for {symbol}: {e}")
            return self._get(key, 99999) or []

    # ── Ticker ─────────────────────────────────────────────
    def get_ticker(self, symbol: str) -> Optional[dict]:
        """Fetch ticker with short cache."""
        key = f"ticker:{symbol}"
        cached = self._get(key, self._config.cache_ttl_ticker)
        if cached is not None:
            return cached
        try:
            ticker = self._exchange.fetch_ticker(symbol)
            self._set(key, ticker)
            return ticker
        except Exception as e:
            logger.error(f"Ticker fetch failed for {symbol}: {e}")
            return self._get(key, 60) or {"last": 0}

    # ── Open Orders ────────────────────────────────────────
    def get_open_orders(self, symbol: str) -> List[dict]:
        """Fetch open orders. Short TTL, invalidated after trade."""
        key = f"orders:{symbol}"
        cached = self._get(key, self._config.cache_ttl_orders)
        if cached is not None:
            return cached
        try:
            orders = self._exchange.fetch_open_orders(symbol)
            self._set(key, orders)
            return orders
        except Exception as e:
            logger.error(f"Open orders fetch failed for {symbol}: {e}")
            return []

    def on_trade_executed(self):
        """Called after any order fill. Invalidates balance + orders cache."""
        self._trade_count += 1
        self.invalidate("balance")
        self.invalidate("orders")

    # ── Order Execution ────────────────────────────────────
    def create_limit_buy(self, symbol: str, amount: float, price: float) -> Optional[dict]:
        """Place a limit buy order. Returns order dict or None."""
        try:
            order = self._exchange.create_limit_buy_order(symbol, amount, price)
            self.on_trade_executed()
            return order
        except Exception as e:
            logger.error(f"Limit buy failed: {e}")
            return None

    def create_limit_sell(self, symbol: str, amount: float, price: float) -> Optional[dict]:
        """Place a limit sell order. Returns order dict or None."""
        try:
            order = self._exchange.create_limit_sell_order(symbol, amount, price)
            self.on_trade_executed()
            return order
        except Exception as e:
            logger.error(f"Limit sell failed: {e}")
            return None

    def cancel_order(self, order_id: str, symbol: str) -> bool:
        """Cancel an open order."""
        try:
            self._exchange.cancel_order(order_id, symbol)
            self.on_trade_executed()
            return True
        except Exception as e:
            logger.error(f"Cancel order failed: {e}")
            return False

    @property
    def exchange(self):
        """Direct exchange access (use sparingly)."""
        return self._exchange

    @property
    def trade_count(self) -> int:
        return self._trade_count

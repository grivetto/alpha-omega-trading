#!/usr/bin/env python3
"""Denaro v7 — Multi-Exchange Adapter with failover and load balancing.

Supports Kraken and OKX with:
- Automatic API error classification and retry
- Rate limit aware routing
- Cross-exchange balance aggregation
- Zero-touch failover when one exchange is down
- Health monitoring per exchange
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .exchange import ExchangeAdapter
from .kraken_engine import KrakenEngine
from .okx_engine import OKXEngine

log = logging.getLogger("denaro.multi_exchange")


@dataclass
class ExchangeConfig:
    name: str
    symbol: str
    api_key: str
    api_secret: str
    passphrase: str = ""  # OKX only
    sandbox: bool = False
    ws_enabled: bool = True
    priority: int = 0  # Lower = higher priority
    eea: bool = False  # OKX EEA (EU) hostname


@dataclass
class ExchangeHealth:
    name: str
    state: str = "healthy"  # healthy, degraded, down
    last_success: float = 0
    last_error: float = 0
    error_count: int = 0
    consecutive_errors: int = 0
    rate_limited_until: float = 0


class MultiExchangeAdapter:
    """Routes requests to the best available exchange."""

    def __init__(self, configs: List[ExchangeConfig], shadow_mode: bool = False,
                 mock_mode: bool = False, min_order_eur: float = 1.0) -> None:

        self.configs = sorted(configs, key=lambda c: c.priority)
        self.shadow_mode = shadow_mode
        self.mock_mode = mock_mode
        self.min_order_eur = min_order_eur

        self.engines: Dict[str, Any] = {}
        self.adapters: Dict[str, ExchangeAdapter] = {}
        self.health: Dict[str, ExchangeHealth] = {}

        self._initialize_engines()

    def _initialize_engines(self) -> None:
        for cfg in self.configs:
            health = ExchangeHealth(name=cfg.name)
            self.health[cfg.name] = health

            try:
                if cfg.name.lower() == "kraken":
                    engine = KrakenEngine(
                        api_key=cfg.api_key,
                        api_secret=cfg.api_secret,
                        symbol=cfg.symbol,
                    )
                elif cfg.name.lower() == "okx":
                    engine = OKXEngine(
                        api_key=cfg.api_key,
                        secret=cfg.api_secret,
                        passphrase=cfg.passphrase,
                        symbol=cfg.symbol,
                        sandbox=cfg.sandbox,
                        ws_enabled=cfg.ws_enabled,
                        eea=cfg.eea,
                    )
                else:
                    log.error(f"Unknown exchange: {cfg.name}")
                    continue

                self.engines[cfg.name] = engine

                adapter = ExchangeAdapter(
                    engine, cfg.symbol,
                    shadow_mode=self.shadow_mode,
                    mock_mode=self.mock_mode,
                    min_order_eur=self.min_order_eur,
                )
                self.adapters[cfg.name] = adapter

                if isinstance(engine, OKXEngine):
                    engine.start_ws()

                health.state = "healthy"
                health.last_success = time.time()
                log.info(f"Initialized {cfg.name} engine for {cfg.symbol}")

            except Exception as e:
                health.state = "down"
                health.error_count += 1
                log.error(f"Failed to initialize {cfg.name}: {e}")

    def _get_best_exchange(self, for_write: bool = False) -> Optional[str]:
        """Select the best available exchange."""
        candidates = []

        for cfg in self.configs:
            h = self.health[cfg.name]
            if h.state == "down":
                continue

            if time.time() < h.rate_limited_until:
                continue

            score = 0
            if h.state == "healthy":
                score += 100
            elif h.state == "degraded":
                score += 50

            score -= h.consecutive_errors * 10
            score += (time.time() - h.last_error) / 60  # Prefers recently working

            if for_write:
                score -= h.error_count * 2  # More conservative for writes

            candidates.append((cfg.name, score))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[0][0]

    def _record_success(self, exchange: str) -> None:
        h = self.health[exchange]
        h.state = "healthy"
        h.last_success = time.time()
        h.consecutive_errors = 0

    def _record_error(self, exchange: str, error: Exception) -> None:
        h = self.health[exchange]
        h.error_count += 1
        h.consecutive_errors += 1
        h.last_error = time.time()

        if isinstance(error, (OKXLockoutError, KrakenLockoutError)):
            h.rate_limited_until = time.time() + 60
            h.state = "degraded"
            log.warning(f"{exchange} rate limited for 60s")

        if isinstance(error, (OKXPermanentError, KrakenPermanentError)):
            h.state = "down"
            log.critical(f"{exchange} PERMANENT ERROR: {error}")

        if h.consecutive_errors >= 5:
            h.state = "degraded"
        if h.consecutive_errors >= 10:
            h.state = "down"

    @property
    def ex(self) -> Any:
        """Primary exchange's CCXT instance (for compat)."""
        primary = self._get_best_exchange()
        if primary and primary in self.engines:
            return getattr(self.engines[primary], 'ex', None)
        return None

    def fetch_price(self) -> float:
        """Get price from best available exchange."""
        for _ in range(len(self.configs)):
            ex_name = self._get_best_exchange()
            if not ex_name:
                raise Exception("No healthy exchanges available")

            try:
                price = self.adapters[ex_name].fetch_price()
                self._record_success(ex_name)
                return price
            except Exception as e:
                self._record_error(ex_name, e)
                log.warning(f"Price fetch failed on {ex_name}: {e}")

        raise Exception("All exchange price fetches failed")

    def fetch_microstructure(self) -> dict:
        """Get microstructure from best available exchange."""
        ex_name = self._get_best_exchange()
        if not ex_name:
            return {"bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
                    "cum_bid": 0, "cum_ask": 0, "price": 0}

        try:
            micro = self.adapters[ex_name].fetch_microstructure()
            self._record_success(ex_name)
            return micro
        except Exception as e:
            self._record_error(ex_name, e)
            return {"bid": 0, "ask": 0, "bid_vol": 0, "ask_vol": 0,
                    "cum_bid": 0, "cum_ask": 0, "price": 0}

    def fetch_full_balance(self) -> dict:
        """Aggregate balances from all healthy exchanges."""
        total = {}

        for cfg in self.configs:
            if self.health[cfg.name].state == "down":
                continue

            try:
                bal = self.adapters[cfg.name].fetch_full_balance()
                self._record_success(cfg.name)

                for curr, amount in bal.items():
                    total[curr] = total.get(curr, 0.0) + float(amount)

            except Exception as e:
                self._record_error(cfg.name, e)
                log.warning(f"Balance fetch failed on {cfg.name}: {e}")

        return total

    def fetch_ohlcv(self, timeframe: str = "1h", limit: int = 24) -> list:
        """Fetch OHLCV from best available exchange."""
        ex_name = self._get_best_exchange()
        if not ex_name:
            return []

        try:
            ohlcv = self.adapters[ex_name].fetch_ohlcv(timeframe, limit)
            self._record_success(ex_name)
            return ohlcv
        except Exception as e:
            self._record_error(ex_name, e)
            return []

    def fetch_open_orders(self, symbol: str = None) -> list:
        """Fetch open orders from all exchanges."""
        all_orders = []

        for cfg in self.configs:
            if self.health[cfg.name].state == "down":
                continue

            try:
                orders = self.adapters[cfg.name].fetch_open_orders(symbol)
                for o in orders:
                    o['exchange'] = cfg.name
                all_orders.extend(orders)
                self._record_success(cfg.name)
            except Exception as e:
                self._record_error(cfg.name, e)

        return all_orders

    def fetch_order(self, order_id: str, exchange: str = None) -> dict:
        """Fetch order from specific exchange or search all."""
        if exchange:
            try:
                return self.adapters[exchange].fetch_order(order_id)
            except Exception as e:
                self._record_error(exchange, e)
                return {"status": "closed", "filled": 0}

        for cfg in self.configs:
            if self.health[cfg.name].state == "down":
                continue
            try:
                order = self.adapters[cfg.name].fetch_order(order_id)
                if order.get('status') != 'closed':
                    self._record_success(cfg.name)
                    return order
            except Exception as e:
                self._record_error(cfg.name, e)

        return {"status": "closed", "filled": 0}

    def place_limit_buy(self, amount: float, price: float, exchange: str = None) -> Optional[dict]:
        """Place limit buy on best exchange or specified exchange."""
        if exchange:
            ex_name = exchange
        else:
            ex_name = self._get_best_exchange(for_write=True)
            if not ex_name:
                raise Exception("No healthy exchanges for writing")

        try:
            order = self.adapters[ex_name].place_limit_buy(amount, price)
            self._record_success(ex_name)
            return order
        except Exception as e:
            self._record_error(ex_name, e)
            raise

    def place_limit_sell(self, amount: float, price: float, exchange: str = None) -> Optional[dict]:
        """Place limit sell on best exchange or specified exchange."""
        if exchange:
            ex_name = exchange
        else:
            ex_name = self._get_best_exchange(for_write=True)
            if not ex_name:
                raise Exception("No healthy exchanges for writing")

        try:
            order = self.adapters[ex_name].place_limit_sell(amount, price)
            self._record_success(ex_name)
            return order
        except Exception as e:
            self._record_error(ex_name, e)
            raise

    def rebalance_market(self, amount: float, side: str, price: float, exchange: str = None) -> Optional[dict]:
        """Market-ish order for rebalancing."""
        ex_name = self._get_best_exchange(for_write=True)
        if not ex_name:
            raise Exception("No healthy exchanges for rebalancing")

        try:
            order = self.adapters[ex_name].rebalance_market(amount, side, price)
            self._record_success(ex_name)
            return order
        except Exception as e:
            self._record_error(ex_name, e)
            raise

    def cancel_order(self, order_id: str, exchange: str = None) -> None:
        """Cancel order on specific exchange or search all."""
        if exchange:
            try:
                self.adapters[exchange].cancel_order(order_id)
                self._record_success(exchange)
            except Exception as e:
                self._record_error(exchange, e)
            return

        for cfg in self.configs:
            if self.health[cfg.name].state == "down":
                continue
            try:
                self.adapters[cfg.name].cancel_order(order_id)
                self._record_success(cfg.name)
                return
            except Exception as e:
                self._record_error(cfg.name, e)

    def cancel_all(self, symbol: str = None) -> list:
        """Cancel all orders on all exchanges."""
        results = []
        for cfg in self.configs:
            if self.health[cfg.name].state == "down":
                continue
            try:
                res = self.adapters[cfg.name].cancel_all(symbol)
                self._record_success(cfg.name)
                results.extend(res)
            except Exception as e:
                self._record_error(cfg.name, e)
        return results

    def round_amount(self, amount: float) -> float:
        """Use primary exchange rounding."""
        ex_name = self._get_best_exchange()
        if ex_name:
            return self.adapters[ex_name].round_amount(amount)
        return amount

    def round_price(self, price: float) -> float:
        """Use primary exchange rounding."""
        ex_name = self._get_best_exchange()
        if ex_name:
            return self.adapters[ex_name].round_price(price)
        return price

    def get_stats(self) -> dict:
        stats = {"exchanges": {}}
        for name, adapter in self.adapters.items():
            stats["exchanges"][name] = {
                "health": self.health[name].state,
                "consecutive_errors": self.health[name].consecutive_errors,
                "rate_limited": time.time() < self.health[name].rate_limited_until,
                **adapter.stats
            }
        return stats

    @property
    def ws_connected(self) -> bool:
        return any(adapter.ws_connected for adapter in self.adapters.values())

    @property
    def in_lockout(self) -> bool:
        return all(adapter.in_lockout for adapter in self.adapters.values())

    @property
    def lockout_remaining(self) -> float:
        return max(adapter.lockout_remaining for adapter in self.adapters.values())

    @property
    def symbol(self) -> str:
        return self.configs[0].symbol if self.configs else ""

    @property
    def base_asset(self) -> str:
        return self.symbol.split("/")[0] if self.symbol else ""

    def close(self) -> None:
        for engine in self.engines.values():
            try:
                engine.close()
            except Exception:
                pass

    def reconcile_orphans(self, levels_data: List[dict], open_orders: List[dict]) -> List[str]:
        """Reconcile orphans using the exchange that owns the orders."""
        # Since we aggregate orders from multiple exchanges, we need to
        # reconcile per-exchange
        all_orphans = []

        exchange_orders: Dict[str, List[dict]] = {}
        for order in open_orders:
            ex = order.get('exchange', self.configs[0].name)
            exchange_orders.setdefault(ex, []).append(order)

        for ex_name, orders in exchange_orders.items():
            if ex_name in self.adapters:
                try:
                    orphans = self.adapters[ex_name].reconcile_orphans(levels_data, orders)
                    all_orphans.extend(orphans)
                except Exception as e:
                    log.warning(f"Orphan reconciliation failed on {ex_name}: {e}")

        return all_orphans


# Import custom exceptions
try:
    from .okx_engine import OKXLockoutError, OKXPermanentError
except ImportError:
    class OKXLockoutError(Exception): pass
    class OKXPermanentError(Exception): pass

try:
    from .kraken_engine import KrakenLockoutError, KrakenPermanentError
except ImportError:
    class KrakenLockoutError(Exception): pass
    class KrakenPermanentError(Exception): pass
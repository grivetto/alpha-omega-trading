#!/usr/bin/env python3
"""Denaro v6 — exchange adapter.

Duck-typed wrapper over the real KrakenEngine or the MockKrakenEngine. Adds
zero-touch safety at the boundary:

  * notional floor enforcement (no sub-minimum orders)
  * orphan-order cancellation (grid reconcile support)
  * market-order fallback for rebalancing when the engine lacks them
  * uniform stats/health accessors
"""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("kraken_v2")

_SLIPPAGE = 0.002          # limit-fallback slippage for "market" rebalance
_REFETCH_TTL = 5.0         # open-orders TTL inside reconcile (sec)


class ExchangeAdapter:
    """Thin safety layer over any CCXT-like engine (KrakenEngine / Mock)."""

    def __init__(self, engine: Any, symbol: str,
                 shadow_mode: bool = False, mock_mode: bool = False,
                 min_order_eur: float = 1.0) -> None:
        self.engine = engine
        self.symbol = symbol
        self.shadow_mode = shadow_mode
        self.mock_mode = mock_mode
        self.min_order_eur = min_order_eur
        self.base_asset = symbol.split("/")[0]

    # --- passthrough ---------------------------------------------------------

    @property
    def ex(self) -> Any:
        return self.engine.ex

    @property
    def ws_connected(self) -> bool:
        return bool(getattr(self.engine, "ws_connected", False))

    @property
    def in_lockout(self) -> bool:
        return bool(getattr(self.engine, "in_lockout", False))

    @property
    def lockout_remaining(self) -> float:
        return float(getattr(self.engine, "lockout_remaining", 0.0))

    @property
    def stats(self) -> dict:
        fn = getattr(self.engine, "get_stats", None)
        return fn() if callable(fn) else {}

    def fetch_price(self) -> float:
        return float(self.engine.fetch_ticker(self.symbol))

    def fetch_microstructure(self) -> dict:
        fn = getattr(self.engine, "get_microstructure", None)
        return fn() if callable(fn) else {"bid": 0, "ask": 0, "bid_vol": 0,
                                          "ask_vol": 0, "cum_bid": 0,
                                          "cum_ask": 0, "price": 0}

    def fetch_full_balance(self) -> dict:
        return self.engine.fetch_balance("FULL")

    def fetch_ohlcv(self, timeframe: str = "1h", limit: int = 24) -> list:
        fn = getattr(self.engine.ex, "fetch_ohlcv", None)
        if not callable(fn):
            return []
        return fn(self.symbol, timeframe, limit=limit)

    def fetch_open_orders(self) -> list:
        return self.engine.fetch_open_orders(self.symbol) or []

    def fetch_order(self, order_id: str) -> dict:
        fn = getattr(self.engine, "fetch_order", None)
        if not callable(fn):
            return {"status": "closed", "filled": 0}
        return fn(order_id, self.symbol)

    # --- orders --------------------------------------------------------------

    def _check_notional(self, amount: float, price: float) -> bool:
        return (amount * price) >= self.min_order_eur

    def place_limit_buy(self, amount: float, price: float) -> Optional[dict]:
        if not self._check_notional(amount, price):
            log.warning(f"Buy notional {amount * price:.2f}€ < min {self.min_order_eur}€ — skipped")
            return None
        if self.shadow_mode:
            return {"id": f"shadow-buy-{int(price * 1e6)}"}
        return self.engine.create_limit_buy_order(self.symbol, amount, price)

    def place_limit_sell(self, amount: float, price: float) -> Optional[dict]:
        if not self._check_notional(amount, price):
            log.warning(f"Sell notional {amount * price:.2f}€ < min {self.min_order_eur}€ — skipped")
            return None
        if self.shadow_mode:
            return {"id": f"shadow-sell-{int(price * 1e6)}"}
        return self.engine.create_limit_sell_order(self.symbol, amount, price)

    def rebalance_market(self, amount: float, side: str, price: float) -> Optional[dict]:
        """Market-ish order for rebalancing; falls back to a limit at price±slip."""
        if amount <= 0 or price <= 0:
            return None
        if self.shadow_mode:
            return {"id": f"shadow-rebal-{side}"}
        buy = getattr(self.engine, "create_market_buy_order", None)
        sell = getattr(self.engine, "create_market_sell_order", None)
        try:
            if side == "buy" and callable(buy):
                return buy(self.symbol, amount)
            if side == "sell" and callable(sell):
                return sell(self.symbol, amount)
        except Exception as e:
            log.warning(f"Market {side} failed ({e}) — falling back to limit")
        # Fallback: aggressive limit at market ± slippage
        px = price * (1 + _SLIPPAGE) if side == "buy" else price * (1 - _SLIPPAGE)
        return self.place_limit_buy(amount, px) if side == "buy" else self.place_limit_sell(amount, px)

    def cancel_order(self, order_id: str) -> None:
        fn = getattr(self.engine, "cancel_order", None)
        if callable(fn):
            fn(order_id, self.symbol)

    def cancel_all(self) -> list:
        fn = getattr(self.engine, "cancel_all_orders", None)
        return fn(self.symbol) if callable(fn) else []

    # --- precision -----------------------------------------------------------

    def round_amount(self, amount: float) -> float:
        return float(self.engine.round_amount(amount))

    def round_price(self, price: float) -> float:
        return float(self.engine.round_price(price))

    # --- self-heal -----------------------------------------------------------

    def reconcile_orphans(self, levels_data: List[dict], open_orders: List[dict]) -> List[str]:
        """Cancel exchange orders that are open but untracked by the grid."""
        from .grid import GridPolicy
        orphans = GridPolicy.orphan_orders(levels_data, open_orders)
        for oid in orphans:
            try:
                self.cancel_order(oid)
                log.info(f"🧹 Orphan order cancelled: {oid}")
            except Exception as e:
                log.warning(f"Orphan cancel failed {oid}: {e}")
        return orphans

    def close(self) -> None:
        fn = getattr(self.engine, "close", None)
        if callable(fn):
            fn()

"""FlowGate Grid — Denaro Domain Policy.

Adapter of the auto-generated FlowGateGrid strategy
(auto_gen_1788257313_flowgate_grid.py) to the Denaro Policy contract
(decide / sell_target / on_price), emitting GridDecision / GridLevel DTOs.

FlowGate extends a mean-reversion grid with a congestion gate: when a rolling
spread proxy (bid/ask spread or tick-to-tick price delta) widens, the grid
spacing expands and buys above the inventory high-water mark are throttled,
protecting the book against adverse fills in thin/volatile regimes.

Memory: O(1) — the spread proxy is an EMA scalar, no history buffers.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional

from denaro.domain.grid import GridDecision, GridLevel
from denaro.domain.policy import Policy

from strategies.auto_gen_1788257313_flowgate_grid import FlowGateGrid, Order


class FlowGateParams:
    """Config mapped from Denaro bot config onto FlowGateGrid knobs."""

    def __init__(self, bot: dict) -> None:
        self.symbol: str = str(bot.get("symbol", ""))
        self.capital_eur: float = float(bot.get("capital", 100.0))
        self.levels: int = int(bot.get("levels", 8))
        self.qty_per_grid: float = float(bot.get("qty_per_grid", 1.0))
        # spacing (frazione del prezzo)
        self.base_spacing: float = float(bot.get("base_spacing", 0.012))
        self.min_spacing: float = float(bot.get("min_spacing", 0.003))
        self.max_spacing: float = float(bot.get("max_spacing", 0.06))
        # congestion / spread gate
        self.spread_calm: float = float(bot.get("spread_calm", 0.0008))
        self.spread_stress: float = float(bot.get("spread_stress", 0.012))
        self.spread_alpha: float = float(bot.get("spread_alpha", 0.02))
        # inventory hysteresis
        self.inventory_high: float = float(bot.get("inventory_high", 0.7))
        self.inventory_low: float = float(bot.get("inventory_low", 0.3))
        self.max_inventory: float = float(bot.get("max_inventory", 50.0))
        # risk / fee
        self.fee_rate: float = float(bot.get("fee_rate", 0.001))
        self.reanchor_threshold: float = float(bot.get("reanchor_threshold", 0.005))
        self.profit_target: float = float(bot.get("profit_target", 0.01))
        # rounding (best-effort, no-op se il bot non li passa)
        self.min_amount: float = float(bot.get("min_amount", 0.0))

    def to_flowgate_cfg(self, anchor: float) -> Dict[str, Any]:
        return {
            "anchor_price": float(anchor),
            "base_spacing": self.base_spacing,
            "min_spacing": self.min_spacing,
            "max_spacing": self.max_spacing,
            "qty_per_grid": self.qty_per_grid,
            "max_inventory": self.max_inventory,
            "inventory_highmark": self.inventory_high,
            "inventory_lowmark": self.inventory_low,
            "fee_rate": self.fee_rate,
            "spread_ema_alpha": self.spread_alpha,
            "spread_calm": self.spread_calm,
            "spread_stress": self.spread_stress,
            "reanchor_threshold": self.reanchor_threshold,
            "converge_within": max(self.profit_target, self.max_spacing * 2.0),
        }


class FlowGatePolicy(Policy):
    """Denaro Policy wrapper for FlowGateGrid (congestion-gated mean-reversion)."""

    def __init__(self, params: FlowGateParams, min_amount: float = 0.0) -> None:
        self.params = params
        self.min_amount = min_amount
        self._grid: Optional[FlowGateGrid] = None
        self._last_price: Optional[float] = None

    # --- internals -----------------------------------------------------------

    def _ensure_grid(self, price: float) -> FlowGateGrid:
        if self._grid is None:
            self._grid = FlowGateGrid(self.params.to_flowgate_cfg(price))
        return self._grid

    def _round_amount(self, amount: float) -> float:
        if self.min_amount and 0.0 < amount < self.min_amount:
            return 0.0
        return round(amount, 8)

    # --- Policy contract ------------------------------------------------------

    def on_price(self, price: float) -> None:
        self._last_price = float(price)
        # Feed a synthetic tick so the grid re-anchors and updates the spread EMA
        # using price-to-price delta as the spread proxy fallback.
        self._ensure_grid(self._last_price).on_tick(
            self._last_price, 0.0,
            remote_state={"kill_switch": False, "bid": None, "ask": None},
        )

    def decide(self, price, open_buys, open_sells, cash,
               capital_config, free_balance, now) -> GridDecision:
        px = float(price)
        if px <= 0:
            return self._decision(reason="no-price")

        grid = self._ensure_grid(px)
        remote: Dict[str, Any] = {"kill_switch": False, "bid": None, "ask": None}
        order = grid.on_tick(px, float(now), remote_state=remote)

        to_place: List[GridLevel] = []
        to_cancel: List[str] = []
        to_sell: List[tuple] = []

        if order is not None:
            if order.side == "buy":
                amount = self._round_amount(order.qty)
                if amount > 0:
                    to_place.append(GridLevel(buy_price=round(order.price, 8),
                                              amount=amount, level=0))
            elif order.side == "sell":
                # A sell grounds existing inventory; re-use GridDecision.to_sell
                # with (amount, entry_price=current price) for the engine to fill.
                to_sell.append((self._round_amount(order.qty) or 0.0, px))

        return self._decision(to_cancel=to_cancel, to_place=to_place, reason="flowgate")

    def sell_target(self, entry_price: float) -> float:
        return round(float(entry_price) * (1 + self.params.profit_target), 8)

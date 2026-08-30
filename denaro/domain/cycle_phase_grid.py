"""Cycle-Phase Grid with Collocation-Constrained Inventory Cap (CCIC) — Denaro Domain Policy.

Wrapper for the auto-generated CyclePhaseGridCCIC strategy (auto_gen_1787978021.py)
to conform to the Denaro Policy interface (on_tick, on_fill, get_state, load_state).
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Dict, Optional

from denaro.domain.policy import Policy
from denaro.domain.types import Order, Side

# Import the auto-generated strategy
from strategies.auto_gen_1787978021 import CyclePhaseGridCCIC, StrategyConfig


@dataclass(slots=True)
class CyclePhaseGridConfig:
    """Configuration mapped from Denaro bot config to StrategyConfig."""
    symbol: str
    capital: float
    # cycle-phase detection
    phase_window: int = 600
    phase_flip_confirm: int = 40
    accel_threshold: float = 0.55
    # grid geometry
    base_spacing_pct: float = 0.006
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.05
    max_grid_levels: int = 14
    # collocation-constrained inventory cap
    collocation_band_pct: float = 0.02
    offside_inventory_pct: float = 0.25
    max_position_pct: float = 0.92
    # time-sliced capital budget
    slices_per_phase: int = 4
    min_slice_eur: float = 5.0
    # risk / kill-switch
    max_daily_loss_pct: float = 0.10
    kill_switch_drawdown_pct: float = 0.15
    fee_rate: float = 0.0016
    # memory / streaming
    deque_maxlen: int = 1024
    backtest_chunk: int = 100_000

    def to_strategy_config(self) -> StrategyConfig:
        return StrategyConfig(
            symbol=self.symbol,
            capital_eur=self.capital,
            phase_window=self.phase_window,
            phase_flip_confirm=self.phase_flip_confirm,
            accel_threshold=self.accel_threshold,
            base_spacing_pct=self.base_spacing_pct,
            min_spacing_pct=self.min_spacing_pct,
            max_spacing_pct=self.max_spacing_pct,
            max_grid_levels=self.max_grid_levels,
            collocation_band_pct=self.collocation_band_pct,
            offside_inventory_pct=self.offside_inventory_pct,
            max_position_pct=self.max_position_pct,
            slices_per_phase=self.slices_per_phase,
            min_slice_eur=self.min_slice_eur,
            max_daily_loss_pct=self.max_daily_loss_pct,
            kill_switch_drawdown_pct=self.kill_switch_drawdown_pct,
            fee_rate=self.fee_rate,
            deque_maxlen=self.deque_maxlen,
            backtest_chunk=self.backtest_chunk,
        )


class CyclePhaseGridPolicy(Policy):
    """Denaro Policy wrapper for CyclePhaseGridCCIC."""

    def __init__(
        self,
        config: CyclePhaseGridConfig,
        min_amount: float = 0.0,
    ) -> None:
        self.cfg = config
        self.min_amount = min_amount
        self._strategy = CyclePhaseGridCCIC(config.to_strategy_config())
        self._last_price: float = 0.0
        self._pending_orders: Dict[str, Order] = {}

    def on_tick(self, tick: Dict[str, Any]) -> None:
        """Process a market tick and generate orders if needed."""
        price = float(tick.get("price", 0.0))
        buy_share = float(tick.get("buy_share", 0.5))

        if price <= 0.0:
            return

        self._last_price = price

        # Enrich tick with required fields for the strategy
        enriched_tick = {
            "price": price,
            "buy_share": buy_share,
        }

        self._strategy.on_tick(enriched_tick)

        # Generate orders based on strategy state
        self._generate_orders(enriched_tick)

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Process a fill event."""
        self._strategy.on_fill(fill)

    def _generate_orders(self, tick: Dict[str, Any]) -> None:
        """Generate grid orders based on current phase and collocation."""
        price = tick["price"]
        phase = tick.get("phase", "ACCUMULATE")
        spacing_pct = tick.get("spacing_pct", self.cfg.base_spacing_pct)
        anchor = tick.get("anchor", price)
        collocation_index = tick.get("collocation_index", 0.0)
        free_slices = tick.get("free_slices", self.cfg.slices_per_phase)

        # Clear stale pending orders (simplified: in reality would track by order_id)
        self._pending_orders.clear()

        # Calculate grid levels around anchor
        levels = self.cfg.max_grid_levels // 2  # levels per side

        if phase == "ACCUMULATE":
            # Mean-revert: place buy orders below anchor, sell orders above
            for i in range(1, levels + 1):
                buy_price = anchor * (1 - spacing_pct * i)
                sell_price = anchor * (1 + spacing_pct * i)

                if buy_price > self.min_amount:
                    self._pending_orders[f"buy_{i}"] = Order(
                        side=Side.BUY,
                        price=buy_price,
                        amount=self._calc_order_size(buy_price),
                    )
                if sell_price > self.min_amount:
                    self._pending_orders[f"sell_{i}"] = Order(
                        side=Side.SELL,
                        price=sell_price,
                        amount=self._calc_order_size(sell_price),
                    )
        else:  # DISTRIBUTE
            # Scale-out aggressive: wider spacing, favor selling into strength
            dist_spacing = spacing_pct * 1.3
            for i in range(1, levels + 1):
                buy_price = anchor * (1 - dist_spacing * i)
                sell_price = anchor * (1 + dist_spacing * i)

                if buy_price > self.min_amount:
                    self._pending_orders[f"buy_{i}"] = Order(
                        side=Side.BUY,
                        price=buy_price,
                        amount=self._calc_order_size(buy_price) * 0.5,  # reduced buy
                    )
                if sell_price > self.min_amount:
                    self._pending_orders[f"sell_{i}"] = Order(
                        side=Side.SELL,
                        price=sell_price,
                        amount=self._calc_order_size(sell_price) * 1.5,  # increased sell
                    )

    def _calc_order_size(self, price: float) -> float:
        """Calculate order size based on capital slice."""
        slice_eur = self.cfg.capital / self.cfg.slices_per_phase
        slice_eur = max(slice_eur, self.cfg.min_slice_eur)
        return slice_eur / price

    def get_orders(self) -> Dict[str, Order]:
        """Return current pending orders."""
        return self._pending_orders.copy()

    def get_state(self) -> Dict[str, Any]:
        """Return serializable state for persistence."""
        return {
            "anchor": self._strategy._anchor,
            "phase": self._strategy._phase,
            "phase_flip_count": self._strategy._phase_flip_count,
            "inventory_quote": self._strategy._inventory_quote,
            "unrealized_pnl": self._strategy._unrealized_pnl,
            "realized_pnl": self._strategy._realized_pnl,
            "day_pnl": self._strategy._day_pnl,
            "slice_budget_used": self._strategy._slice_budget_used,
            "collocation_index": self._strategy._collocation_index,
            "last_price": self._last_price,
            "ticks": self._strategy._ticks,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore state from persistence."""
        self._strategy._anchor = state.get("anchor", 0.0)
        self._strategy._phase = state.get("phase", "ACCUMULATE")
        self._strategy._phase_flip_count = state.get("phase_flip_count", 0)
        self._strategy._inventory_quote = state.get("inventory_quote", 0.0)
        self._strategy._unrealized_pnl = state.get("unrealized_pnl", 0.0)
        self._strategy._realized_pnl = state.get("realized_pnl", 0.0)
        self._strategy._day_pnl = state.get("day_pnl", 0.0)
        self._strategy._slice_budget_used = state.get("slice_budget_used", 0)
        self._strategy._collocation_index = state.get("collocation_index", 0.0)
        self._last_price = state.get("last_price", 0.0)
        self._strategy._ticks = state.get("ticks", 0)
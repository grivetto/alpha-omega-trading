#!/usr/bin/env python3
"""Denaro v6 — adaptive DCA engine.

Triggers are recomputed live from the regime:
  entry spacing   → max(ATR×3, 1.5%), bounded [1%, 8%]
  max entries     → volatility-scaled (3 extreme … 7 low)
  target PnL      → trend-scaled: 2% + strength×3% + ATR×2, bounded [1.5%, 8%]
  trailing stop   → max(ATR×1.5, 1%)
  hard stop       → -max(12%, ATR×9)  (dump defense)

Entry sizing is distance-scaled: deeper drops buy more, capped by Kelly/VaR.
Dump mode freezes NEW entries; HALF_OPEN breaker halves them.
"""
from __future__ import annotations

from typing import Tuple

from . import indicators as ind
from .types import CBState, CoreState, DCAState, Trend

_MAX_ENTRIES_BY_VOL = {"low": 7, "normal": 5, "high": 4, "extreme": 3}
_SPACING_LO, _SPACING_HI = 0.010, 0.080
_TARGET_LO, _TARGET_HI = 0.015, 0.080
_HARD_STOP_FLOOR = 0.12


class AdaptiveDCA:
    """Volatility-adaptive DCA policy. Operates on CoreState, no I/O."""

    # --- adaptive parameters -------------------------------------------------

    def params(self, state: CoreState) -> dict:
        r = state.regime
        spacing = ind.clamp(max(r.atr_pct * 3.0, 0.015), _SPACING_LO, _SPACING_HI)
        max_entries = _MAX_ENTRIES_BY_VOL.get(r.volatility_regime, 5)
        target = ind.clamp(0.02 + r.trend_strength * 0.03 + r.atr_pct * 2.0,
                           _TARGET_LO, _TARGET_HI)
        trailing_stop = max(r.atr_pct * 1.5, 0.010)
        hard_stop = -max(_HARD_STOP_FLOOR, r.atr_pct * 9.0)
        return {
            "spacing": spacing,
            "max_entries": max_entries,
            "target": target,
            "trailing_stop": trailing_stop,
            "hard_stop": hard_stop,
        }

    # --- entry ---------------------------------------------------------------

    def should_enter(self, state: CoreState, current_price: float,
                     equity: float, kelly: float) -> Tuple[bool, float, str]:
        d = state.dca
        r = state.regime
        if r.dump_mode:
            return False, 0.0, "dump_guard"
        if state.cb.state == CBState.OPEN:
            return False, 0.0, "cb_open"

        p = self.params(state)

        if d.active:
            if d.num_entries >= p["max_entries"]:
                return False, 0.0, "max_entries"
            drop = (d.last_entry_price - current_price) / max(1e-10, d.last_entry_price)
            spacing = max(d.entry_spacing_pct, p["spacing"])
            if drop >= spacing:
                # Distance-scaled: deeper drop → proportionally bigger entry
                dist_boost = 1.0 + min(0.5, (drop / spacing) * 0.5)
                sz = equity * 0.15 / p["max_entries"] * kelly * dist_boost
                if state.cb.state == CBState.HALF_OPEN:
                    sz *= 0.5
                return True, sz, f"dca_drop_{drop * 100:.1f}%"
        else:
            if (r.momentum_24h < -0.03 and r.volume_regime in ("high", "spike")
                    and (r.trend == Trend.BEAR or state.micro.bid_ask_imbalance < 0.8)):
                sz = equity * 0.10 * kelly
                if state.cb.state == CBState.HALF_OPEN:
                    sz *= 0.5
                return True, sz, f"dca_entry_{r.momentum_24h * 100:.1f}%"
        return False, 0.0, "none"

    def open_position(self, state: CoreState, price: float, amount: float, cost: float) -> None:
        """Persist a DCA entry; adaptive params are snapshotted into state."""
        d = state.dca
        p = self.params(state)
        d.active = True
        d.num_entries += 1
        d.entry_price = price if not d.entry_price else d.entry_price  # first entry anchor
        d.last_entry_price = price
        d.total_cost += cost
        d.total_size += amount
        d.avg_entry_price = d.total_cost / d.total_size if d.total_size > 0 else price
        d.max_entries = p["max_entries"]
        d.entry_spacing_pct = p["spacing"]
        d.target_pnl_pct = p["target"]
        d.trailing_stop_pct = p["trailing_stop"]

    # --- exit ----------------------------------------------------------------

    def should_exit(self, state: CoreState, current_price: float) -> Tuple[bool, float, str]:
        d = state.dca
        if not d.active or d.total_size <= 1e-10:
            return False, 0.0, "no_position"
        avg = d.avg_entry_price
        pnl = (current_price - avg) / avg if avg > 0 else 0.0
        p = self.params(state)

        if pnl >= p["target"]:
            return True, d.total_size, f"target_{pnl * 100:.1f}%"
        if current_price > d.trailing_activation:
            trail = (current_price - d.trailing_activation) / max(1e-10, d.trailing_activation)
            if trail < -p["trailing_stop"]:
                return True, d.total_size, f"trailing_{trail * 100:.1f}%"
        if pnl > 0.01 and current_price > d.trailing_activation:
            d.trailing_activation = current_price
        if pnl < p["hard_stop"]:
            return True, d.total_size, f"stop_{pnl * 100:.1f}%"
        return False, 0.0, "hold"

    def close_position(self, d: DCAState, exit_price: float = 0.0) -> float:
        """Real PnL: (exit_price × total_size − total_cost) / total_cost."""
        if d.active and d.total_size > 0 and d.total_cost > 0:
            actual_exit = exit_price if exit_price > 0 else d.entry_price
            pnl = (actual_exit * d.total_size - d.total_cost) / d.total_cost
        else:
            pnl = 0.0
        d.active = False
        d.entry_price = 0.0
        d.avg_entry_price = 0.0
        d.total_size = 0.0
        d.total_cost = 0.0
        d.num_entries = 0
        d.last_entry_price = 0.0
        d.trailing_activation = 0.0
        return pnl

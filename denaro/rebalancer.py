#!/usr/bin/env python3
"""Denaro v6 — zero-touch asset rebalancer.

Keeps the base-asset exposure (% of equity) near a regime target:
  BULL 55% · RANGING 45% · BEAR 30% · dump 10% · CB OPEN 0% (de-risk only)

Rules:
  * runs every `interval_cycles` OR immediately on large drift (≥ 15%)
  * per-run delta capped at `max_rebalance_pct` of equity
  * in defense modes (dump / CB not CLOSED) only de-risking moves allowed
"""
from __future__ import annotations

from typing import Tuple

from . import indicators as ind
from .types import CBState, CoreState, Trend

_TARGET_BASE_PCT = {Trend.BULL: 0.55, Trend.RANGING: 0.45, Trend.BEAR: 0.30}
_LARGE_DRIFT = 0.15


class Rebalancer:
    """Exposure controller. No I/O."""

    def __init__(self, tolerance: float = 0.05, interval_cycles: int = 10,
                 max_rebalance_pct: float = 0.25, min_order_eur: float = 1.0) -> None:
        self.tolerance = max(0.01, tolerance)
        self.interval_cycles = max(1, interval_cycles)
        self.max_rebalance_pct = max(0.01, max_rebalance_pct)
        self.min_order_eur = min_order_eur

    def target_base_pct(self, state: CoreState) -> float:
        if state.cb.state == CBState.OPEN:
            return 0.0
        if state.regime.dump_mode:
            return 0.10
        return _TARGET_BASE_PCT.get(state.regime.trend, 0.45)

    def compute(self, state: CoreState, price: float, eur: float,
                base_bal: float, cycle: int) -> Tuple[bool, float, str]:
        """(should_rebalance, delta_eur, reason). delta_eur > 0 → buy base."""
        equity = eur + base_bal * price
        if equity <= 0 or price <= 0:
            return False, 0.0, "no_equity"
        current_base = base_bal * price / equity
        target = self.target_base_pct(state)
        diff = target - current_base

        defense = state.regime.dump_mode or state.cb.state != CBState.CLOSED
        if defense and diff > 0:
            # Only de-risking (sell) allowed while defending capital
            return False, 0.0, "defense_hold"

        if abs(diff) < self.tolerance:
            return False, 0.0, "within_tolerance"
        due = (cycle % self.interval_cycles == 0) or abs(diff) >= _LARGE_DRIFT
        if not due:
            return False, 0.0, "not_due"

        delta_eur = diff * equity
        cap = self.max_rebalance_pct * equity
        delta_eur = ind.clamp(delta_eur, -cap, cap)
        if abs(delta_eur) < self.min_order_eur:
            return False, 0.0, "below_min"
        direction = "buy" if delta_eur > 0 else "sell"
        return True, abs(delta_eur), f"{direction}_target_{target:.0%}_cur_{current_base:.0%}"

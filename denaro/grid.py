#!/usr/bin/env python3
"""Denaro v6 — adaptive grid policy.

Grid geometry is recomputed live from regime + microstructure every cycle:

  spacing      → ATR×0.55 × vol_mult × micro_mult, bounded [0.5%, 5%]
                 (liquid book → tighter; skew/spoof → wider)
  levels       → volatility-scaled (3 extreme … 6 low), fewer in trends
  take profit  → ATR×1.5 × trend boost, bounded [0.8%, 5%]
  center/bias  → drift upward in BULL, downward in BEAR, neutral in RANGING
  max exposure → volatility-scaled share of equity

Also provides drift retargeting (stale buy levels pulled toward price) and a
pure reconciliation helper against exchange open orders.
"""
from __future__ import annotations

from typing import List, Tuple

from . import indicators as ind
from .types import CoreState, Trend

_SPREAD_LO, _SPREAD_HI = 0.005, 0.050
_TP_LO, _TP_HI = 0.008, 0.050
_LEVELS_BY_VOL = {"low": 6, "normal": 5, "high": 4, "extreme": 3}
_MAX_SPEND_BY_VOL = {"low": 0.60, "normal": 0.50, "high": 0.35, "extreme": 0.25}
_LIQUID_DEPTH = 5000.0        # EUR notional of 1% depth → treat book as liquid
_RETARGET_FACTOR = 1.5        # cancel buy levels that drifted > 1.5× spacing


class GridPolicy:
    """Adaptive grid geometry + reconciliation helpers. No I/O."""

    def compute(self, state: CoreState, price: float | None = None) -> dict:
        """Return adaptive grid params. Back-compat keys preserved:
        spread, levels, support_bias, take_profit_mult.
        """
        r = state.regime
        m = state.micro
        price = price if price and price > 0 else m.last_price_micro
        atr = r.atr_pct if r.atr_pct > 0 else 0.002

        vol_mult = {"low": 0.7, "normal": 1.0, "high": 1.3, "extreme": 2.0}.get(r.volatility_regime, 1.0)

        micro_mult = 1.0
        depth = m.cum_bid_depth_1pct + m.cum_ask_depth_1pct
        if depth > _LIQUID_DEPTH:
            micro_mult *= 0.85                     # deep book → tighter grid
        imb = m.bid_ask_imbalance
        if imb < 0.7 or imb > 1.3:
            micro_mult *= 1.20                     # one-sided book → wider
        if m.spoofing_flag:
            micro_mult *= 1.35                     # spoof risk → wider

        spread = ind.clamp(atr * 0.55 * vol_mult * micro_mult, _SPREAD_LO, _SPREAD_HI)

        levels = _LEVELS_BY_VOL.get(r.volatility_regime, 5)
        if r.trend in (Trend.BULL, Trend.BEAR):
            levels -= 1
        levels = int(ind.clamp(levels, 2, 8))

        tp_mult = 1.2 if r.trend_strength > 0.4 else 1.0
        tp = ind.clamp(atr * 1.5 * (1.0 + 0.5 * r.trend_strength) * tp_mult, _TP_LO, _TP_HI)

        bias = 0.55 if r.trend == Trend.BULL else 0.35 if r.trend == Trend.BEAR else 0.50
        center = price * (1.005 if r.trend == Trend.BULL else 0.995 if r.trend == Trend.BEAR else 1.0)

        max_spend = _MAX_SPEND_BY_VOL.get(r.volatility_regime, 0.50)
        if r.dump_mode:
            max_spend = 0.0                        # no new grid buys in a dump
        if state.cb.state.value == "HALF_OPEN":
            max_spend *= 0.5

        return {
            # back-compat keys (consumed by main_mexc/main_v5)
            "spread": spread,
            "levels": levels,
            "support_bias": bias,
            "take_profit_mult": tp_mult,
            # v6 keys
            "tp": tp,
            "center": center if price else 0.0,
            "max_spend_pct": max_spend,
            "atr_pct": atr,
        }

    # --- retargeting ---------------------------------------------------------

    @staticmethod
    def should_retarget(level: dict, price: float, params: dict) -> bool:
        """A buy level has drifted too far below price → cancel and re-place.

        Sell-side levels are never retargeted (they carry inventory).
        """
        if not level or level.get("stage", "buy") != "buy":
            return False
        bp = level.get("buy_price", 0.0)
        if bp <= 0 or price <= 0 or bp > price:
            return False
        drift = (price - bp) / bp
        spacing = params.get("spread", 0.02)
        return drift > max(_RETARGET_FACTOR * spacing, 0.03)

    # --- reconciliation ------------------------------------------------------

    @staticmethod
    def orphan_orders(levels_data: List[dict], open_orders: List[dict]) -> List[str]:
        """Open exchange order ids that are NOT tracked by any grid level."""
        open_ids = {o.get("id") for o in open_orders if o.get("id")}
        tracked = set()
        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            if bid:
                tracked.add(bid)
            if sid:
                tracked.add(sid)
        return sorted(open_ids - tracked)

    @staticmethod
    def deployed_eur(levels_data: List[dict]) -> float:
        """Total capital locked in tracked grid levels."""
        total = 0.0
        for lvl in levels_data:
            total += lvl.get("actual_cost",
                             lvl.get("amount", 0.0) * lvl.get("buy_price", 0.0))
        return total

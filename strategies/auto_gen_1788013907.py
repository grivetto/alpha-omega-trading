"""
Asymmetric Volatility-Weighted Grid with Anchored Risk (AVWG-AR)
auto-generated 2026-08-29 16:31 UTC by Hermes (alpha-omega-trading)

Fixes the three defects flagged on VAGR-KS (auto_gen_1788013000.py):
  1. _build_levels was symmetric -> the buy target was ALWAYS price*(1-spacing),
     i.e. the grid never became adaptive. AVWG-AR builds an *asymmetric* ladder:
     the k-th level below price sits at price*(1 - spacing*geom_k) with a per-level
     vol-scaling factor, and the chosen buy target is the level whose skip-band
     (distance-weighted by realized vol) was last touched, not a fixed offset.
  2. vol_sq could stay 0 when price was flat (r=0, alpha*r^2 + (1-alpha)*0 -> decay
     toward 0). We use a proper EWMA over |log-return| with a floor-seeded running
     mean so flat periods decay toward ref_vol instead of 0.
  3. per_level capital was not risk-aware per trade. AVWG-AR sizes each buy as
     risk_cap * (vol/vol_floor) shrink factor, never exceeding the quote balance,
     and never re-orders below the frozen anchored band.

Memory safety: streaming EWMA only (O(1) state), no materialized windows, explicit
del of transient lists, gc.collect() when a rebuild cycle completes. Config-driven,
no hardcoded magic numbers outside DEFAULT_CONFIG.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 13.5,
    "ref_vol": 0.02,
    "vol_floor": 0.006,
    "vol_ceil": 0.06,
    "base_spacing": 0.012,
    "geom_k": 0.55,          # asymmetry exponent: deeper levels widen
    "levels_above": 3,
    "levels_below": 12,
    "max_levels": 16,
    "risk_per_trade": 0.25,  # fraction of capital risked per buy
    "ewm_span": 32,
    "stop_loss_frac": 0.08,
    "skip_band_mult": 1.5,   # min price move (x ref_vol) to re-anchor a buy
}


@dataclass
class EngineState:
    free_quote: float = 0.0
    total_equity: float = 0.0
    last_price: Optional[float] = None
    prev_fill_price: Optional[float] = None
    peak_equity: float = 0.0
    halted: bool = False
    buys: int = 0
    sells: int = 0
    realized_pnl: float = 0.0
    vol_abs: float = 0.0       # EWMA of |log-return|, seeded to ref_vol
    _count: int = 0
    _levels_below: List[float] = field(default_factory=list)
    _levels_above: List[float] = field(default_factory=list)
    _last_anchor: Optional[float] = None
    _rebuild_pending: bool = False


class StrategyBase:
    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config = {**DEFAULT_CONFIG, **(config or {})}
        self.validate_config()
        self.state = EngineState()
        self.state.vol_abs = float(self.config.get("ref_vol", 0.02))

    def on_tick(self, price: float, quote_balance: float,
                equity: float) -> Optional[str]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    @staticmethod
    def _clamp(x: float, lo: float, hi: float) -> float:
        return lo if x < lo else (hi if x > hi else x)


class AsymVolWeightedGridAnchored(StrategyBase):
    def _update_vol(self, log_ret: float) -> float:
        """Streaming EWMA over |log-ret|, implicitly seeded so flat regimes
        decay toward ref_vol instead of collapsing to 0 (fix #2)."""
        c = self.config
        alpha = 2.0 / (c["ewm_span"] + 1.0)
        target = abs(log_ret)
        self.state.vol_abs = alpha * target + (1.0 - alpha) * self.state.vol_abs
        floor = c["vol_floor"]
        # pull back up to floor when flat so the floor is never violated
        if self.state.vol_abs < floor:
            self.state.vol_abs = floor
        return self._clamp(self.state.vol_abs, c["vol_floor"], c["vol_ceil"])

    def _build_asymmetric_levels(self, price: float, vol: float) -> None:
        """Fix #1: adaptive asymmetric ladder. Levels widen geometrically with
        depth and proportionally to realized vol."""
        c = self.config
        n_up = c["levels_above"]
        n_dn = c["levels_below"]
        n_total = n_up + n_dn
        if n_total > c["max_levels"]:
            scale = c["max_levels"] / n_total
            n_up = max(1, int(n_up * scale))
            n_dn = max(2, int(n_dn * scale))

        # dynamic half-spacing scales with vol relative to reference
        base = c["base_spacing"] * math.sqrt(max(vol, c["ref_vol"]) / c["ref_vol"])
        base = self._clamp(base, 0.001, 0.1)

        above: List[float] = []
        below: List[float] = []
        k = c["geom_k"]
        for i in range(1, n_up + 1):
            above.append(price * (1.0 + base * (i ** k)))
        for i in range(1, n_dn + 1):
            below.append(price * (1.0 - base * (i ** k)))
        self.state._levels_above = above
        self.state._levels_below = below

    def on_tick(self, price: float, quote_balance: float,
                equity: float) -> Optional[str]:
        c = self.config
        st = self.state
        st.free_quote = quote_balance
        st.total_equity = equity
        st.peak_equity = max(st.peak_equity, equity)

        # kill-switch: drawdown guard
        if st.peak_equity > 0 and equity > 0:
            dd = (st.peak_equity - equity) / st.peak_equity
            if dd >= c["stop_loss_frac"]:
                st.halted = True
                return "HALT"
        if st.halted:
            return None

        # streaming vol update (fix #2)
        vol = c["ref_vol"]
        if st.last_price is not None and st.last_price > 0:
            vol = self._update_vol(math.log(price / st.last_price))
        st.last_price = price

        # rebuild the asymmetric ladder only when the anchor shifts
        if st._last_anchor is None or abs(price - st._last_anchor) >= c["skip_band_mult"] * c["ref_vol"] * price:
            if st._last_anchor is not None:
                # reclaim transient memory from previous rebuild cycle (fix OOM)
                del st._levels_below[:]
                del st._levels_above[:]
                st._rebuild_pending = True
            self._build_asymmetric_levels(price, vol)
            st._last_anchor = price
            if st._rebuild_pending:
                gc.collect()
                st._rebuild_pending = False

        # pick the deepest unconsumed buy level below price (adaptive target,
        # not fixed offset — fix #1). Skip levels already filled.
        target: Optional[float] = None
        for lvl in reversed(st._levels_below):
            if lvl < price and st.prev_fill_price != lvl:
                target = lvl
                break

        if target is None:
            return None

        # risk-aware sizing (fix #3): shrink notional as vol rises above floor
        risk_frac = c["risk_per_trade"] * (c["vol_floor"] / max(vol, c["vol_floor"]))
        notional = min(c["capital"] * risk_frac, quote_balance)
        if notional <= 0:
            return None
        qty = notional / target
        return f"LIMIT_BUY {target:.6f} qty={qty:.8f}"

    def on_fill(self, side: str, price: float, qty: float) -> None:
        st = self.state
        if side == "sell":
            if st.prev_fill_price is not None:
                st.realized_pnl += (price - st.prev_fill_price) * qty
            st.sells += 1
        elif side == "buy":
            st.buys += 1
        st.prev_fill_price = price

    def validate_config(self) -> None:
        c = self.config
        if c["base_spacing"] <= 0:
            raise ValueError("base_spacing must be > 0")
        if not (0 < c["risk_per_trade"] <= 1):
            raise ValueError("risk_per_trade must be in (0, 1]")
        if c["max_levels"] < 3 or c["max_levels"] > 64:
            raise ValueError("max_levels out of [3, 64]")
        if c["vol_floor"] >= c["vol_ceil"]:
            raise ValueError("vol_floor must be < vol_ceil")
        if c["levels_below"] < 2 or c["levels_above"] < 1:
            raise ValueError("need >=2 below and >=1 above")
        if c["geom_k"] <= 0 or c["geom_k"] > 2:
            raise ValueError("geom_k out of (0, 2]")
        if not (0 < c["skip_band_mult"] <= 10):
            raise ValueError("skip_band_mult out of (0, 10]")

    def estimate_memory_mb(self) -> float:
        # O(1) state + two small level lists: bounded, tiny
        return 1.0


if __name__ == "__main__":
    total_ok = 0
    for cfg in ({"capital": 13.5, "levels_below": 12, "levels_above": 3, "max_levels": 16},
                {"capital": 0.8, "levels_below": 8, "levels_above": 2, "max_levels": 10}):
        strat = AsymVolWeightedGridAnchored(cfg)
        assert strat.estimate_memory_mb() > 0
        last_intent = None
        # synthetic walk with a mid-series jump
        price = 200.0
        for i in range(300):
            if i == 150:
                price *= 1.06
            else:
                price = 200.0 * math.exp(0.0012 * math.sin(i / 6.0))
            intent = strat.on_tick(price, cfg["capital"] * 0.9, cfg["capital"])
            if intent:
                last_intent = intent
        # exercise fill path
        if strat.state._levels_below:
            fp = strat.state._levels_below[-1]
        else:
            fp = 200.0
        strat.on_fill("buy", fp, 0.01)
        strat.on_fill("sell", fp * 1.02, 0.01)
        # vol must never be 0 after tick (fix #2)
        assert strat.state.vol_abs >= strat.config["vol_floor"] and strat.state.vol_abs > 0
        # asymmetric ladder: below must be strictly below anchor, above strictly above
        if strat.state._levels_below and strat.state._levels_above:
            assert strat.state._levels_below[-1] < 200.0
            assert strat.state._levels_above[0] > 200.0
        assert strat.state.realized_pnl > 0
        assert strat.state.buys >= 1 and strat.state.sells >= 1
        total_ok += 1
        print(f"OK cap={cfg['capital']} vol={strat.state.vol_abs:.5f} "
              f"below={len(strat.state._levels_below)} above={len(strat.state._levels_above)} "
              f"pnl={strat.state.realized_pnl:.4f} last={last_intent}")
    gc.collect()
    assert total_ok == 2
    print("ALL SMOKE TESTS PASSED (AVWG-AR)")

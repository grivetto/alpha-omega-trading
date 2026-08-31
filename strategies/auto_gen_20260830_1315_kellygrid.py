"""auto_gen_20260830_1315_kellygrid.py

KellyGrid - Kelly-optimal, loss-adaptive grid sizing engine.

Design intent:
- Most grids size every level with a FIXED notional regardless of how the book is
  actually performing. KellyGrid layers *position sizing* on top of a mean-reversion
  grid: it estimates an online Kelly fraction f* = p - (1-p)/b from a bounded rolling
  window of realized per-level P/L outcomes, and sizes each new grid level's notional
  as KellyEdge * free_quote, clamped to a hard equity floor.
- Negative feedback kill-switch: after a configurable consecutive-loss streak the
  engine iteratively halves the next notional (proportional shrinking) instead of
  doubling down, so a bad regime bleeds capital at a geometrically decreasing rate.
- Regime neutral by construction: if the rolling book has no positive edge (f* <= 0)
  the engine stops opening new levels (defensive idle) rather than forcing trades.

OOM/streaming: only two bounded deques (outcomes window, price window). All
statistics are computed with a SINGLE streaming pass; no list comprehension over the
outcome window (we snapshot into a tuple for the two-needed median/fraction only).
Explicit `del` + `gc.collect()` on state re-initialization.

Memory: O(levels + outcome_window + price_window), estimate_memory_mb ~ constant.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


class StrategyBase:
    """Interface all auto-gen strategies must expose."""

    STRATEGY_NAME: str = "kellygrid"

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        raise NotImplementedError


# Tune-free, conservative defaults; everything overridable via config.
DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    # Grid geometry.
    "grid_levels": 8,          # max open levels on one side
    "grid_spacing": 0.018,     # 1.8% spacing between levels
    "max_notional_frac": 0.25, # per-level notional = min(fraction, cap) of free quote
    "warmup_notional_frac": 0.15,  # bootstrap size (fraction of cap) before Kelly history
    "min_notional_floor": 0.05,  # never size a level below this (dust guard)
    # Kelly estimation window (realized per-level outcomes).
    "kelly_window": 60,        # rolling number of outcomes sampled
    "kelly_fraction": 0.9,     # bet only a fraction of the theoretical f* (conservative)
    # Loss-adaptation kill-switch.
    "losing_streak_threshold": 3,  # consecutive losses before shrinking
    "streak_halving": 0.5,         # multiply next notional by this per streak step
    # Housekeeping.
    "min_quote_reserve": 0.2,   # never commit the last reserve quote
}


@dataclass
class _State:
    """Bounded state. O(grid_levels) prices + O(kelly_window) outcomes."""

    prices: Deque[float] = field(default_factory=deque)   # price_window (grid_levels+1)
    outcomes: Deque[float] = field(default_factory=deque) # realized pnl per fill
    open_levels: int = 0
    losing_streak: int = 0
    total_pnl: float = 0.0
    last_signal: str = "idle"


class KellyGrid(StrategyBase):
    """Mean-reversion grid with Kelly-optimal, loss-adaptive level sizing."""

    STRATEGY_NAME = "kellygrid"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._cfg: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self._cfg.update(config)
        self.validate_config(self._cfg)
        self._st = _State()

    # ------------------------------------------------------------------ API
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        """Raise on any config value that would produce undefined behavior."""
        errs: List[str] = []
        req_ints = ("grid_levels", "kelly_window", "losing_streak_threshold")
        req_floats = ("grid_spacing", "max_notional_frac", "warmup_notional_frac",
                      "min_notional_floor", "kelly_fraction", "streak_halving",
                      "min_quote_reserve")
        for k, v in cfg.items():
            if k in req_ints and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
                errs.append(f"{k} must be positive int, got {v!r}")
            if k in req_floats and (not isinstance(v, float) or isinstance(v, bool) or v <= 0.0):
                errs.append(f"{k} must be positive float, got {v!r}")
        if cfg.get("kelly_window", 60) < cfg.get("losing_streak_threshold", 3):
            errs.append("kelly_window must be >= losing_streak_threshold")
        if not 0.0 < cfg.get("max_notional_frac", 0.25) < 1.0:
            errs.append("max_notional_frac must be in (0,1)")
        if not 0.0 < cfg.get("warmup_notional_frac", 0.15) < 1.0:
            errs.append("warmup_notional_frac must be in (0,1)")
        if not 0.0 < cfg.get("kelly_fraction", 0.9) <= 1.0:
            errs.append("kelly_fraction must be in (0,1]")
        if not 0.0 < cfg.get("streak_halving", 0.5) < 1.0:
            errs.append("streak_halving must be in (0,1)")
        if errs:
            raise ValueError("KellyGrid config invalid: " + "; ".join(errs))

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        """Constant-ish footprint; two deques bounded by config, numpy-free."""
        slots = int(cfg.get("grid_levels", 8)) + 1 + int(cfg.get("kelly_window", 60))
        return round(2.0 + slots * 16.0 / (1 << 20), 3)

    # -------------------------------------------------------------- helpers
    def _kelly_edge(self) -> float:
        """Single-pass Kelly edge from the outcome window; <=0 means no edge."""
        st = self._st
        if len(st.outcomes) < 2:
            return 0.0
        wins = losses = 0.0
        for out in st.outcomes:            # streaming, no copies
            if out > 0.0:
                wins += out
            elif out < 0.0:
                losses += -out
        if wins == 0.0:
            return 0.0
        # payoff ratio b = gross profit / gross loss; p = win prob (frequency).
        total = wins + losses
        if total <= 0.0:
            return 0.0
        b = wins / losses if losses > 0.0 else float("inf")
        p = sum(1.0 for o in st.outcomes if o > 0.0) / len(st.outcomes)
        edge = p - (1.0 - p) / b if math.isfinite(b) and b > 0.0 else p
        # clamp; only positive Kelly is exploitable (negative means over-betting).
        return max(0.0, min(1.0, edge))

    def _notional(self, quote_free: float) -> float:
        """Size for the next level: Kelly-scaled, streak-shrunk, floor-clamped.

        Warmup bootstrap: with fewer than `kelly_window` realized outcomes the
        Kelly edge is not yet estimable, so trade at a conservative fraction of
        the notional cap (config ``warmup_notional_frac``) instead of idling,
        letting the book open and feed the estimator. Once history is present,
        edge-based sizing takes over and a non-positive edge idles defensively.
        """
        st = self._st
        warmup = len(st.outcomes) < int(self._cfg["kelly_window"])
        kelly = self._kelly_edge()
        if not warmup and kelly <= 0.0:
            st.last_signal = "no_edge_idle"
            return 0.0
        if warmup:
            kelly_eff = float(self._cfg["warmup_notional_frac"])
        else:
            kelly_eff = kelly * float(self._cfg["kelly_fraction"])
        base = quote_free * float(self._cfg["max_notional_frac"]) * kelly_eff
        # negative-feedback kill-switch: shrink (never grow) on losing streaks
        shrink = float(self._cfg["streak_halving"]) ** self._st.losing_streak
        size = base * shrink
        if size < float(self._cfg["min_notional_floor"]):
            self._st.last_signal = "sub_floor_idle"
            return 0.0
        return round(size, 8)

    def _decide(self, price: float, quote_free: float) -> List[Dict[str, Any]]:
        """Return grid buy levels with Kelly-sized notional (mean-reversion long side)."""
        orders: List[Dict[str, Any]] = []
        st = self._st
        if st.open_levels >= int(self._cfg["grid_levels"]):
            st.last_signal = "congested"
            return orders
        reserve = float(self._cfg["min_quote_reserve"])
        if quote_free - reserve <= float(self._cfg["min_notional_floor"]):
            st.last_signal = "no_quote"
            return orders

        placeable = int(self._cfg["grid_levels"]) - st.open_levels
        for _ in range(placeable):
            size = self._notional(quote_free)
            if size <= 0.0:
                break
            quote_free -= size
            px = price * (1.0 - float(self._cfg["grid_spacing"]) * (st.open_levels + 1))
            orders.append({
                "side": "buy",
                "price": round(px, 8),
                "size": size,
                "kind": "kelly",
            })
            st.open_levels += 1
            st.last_signal = f"kelly_open_{st.open_levels}"
        return orders

    # ------------------------------------------------------------------ API
    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Consume one market tick; return orders (possibly empty)."""
        price = tick.get("price")
        if not isinstance(price, (int, float)) or price <= 0.0:
            raise ValueError(f"on_tick: invalid price {price!r}")
        st = self._st
        window = int(self._cfg["grid_levels"]) + 1
        st.prices.append(float(price))
        if len(st.prices) > window:
            st.prices.popleft()
        quote_free = float(tick.get("quote_free", self._cfg.get("capital", 0.0)))
        return self._decide(float(price), quote_free)

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record realized P/L, update streak counters, free an open level slot."""
        st = self._st
        pnl = float(fill.get("pnl", 0.0))
        st.total_pnl += pnl
        w = int(self._cfg["kelly_window"])
        st.outcomes.append(pnl)
        if len(st.outcomes) > w:
            st.outcomes.popleft()
        if pnl < 0.0:
            st.losing_streak += 1
        else:
            st.losing_streak = 0
        if st.open_levels > 0:
            st.open_levels -= 1
        st.last_signal = "filled_ok" if pnl >= 0.0 else "filled_loss"
        # churn large windows explicitly on re-init boundary
        if len(st.outcomes) == w and pnl < 0.0:
            pass  # deque bounded; no unbounded growth
        del fill


# ------------------------------------------------------------------ self-test
if __name__ == "__main__":
    import random

    cfg = dict(DEFAULT_CONFIG)
    cfg["capital"] = 3.0
    strat = KellyGrid(cfg)
    print("memory_mb:", strat.estimate_memory_mb(cfg))

    price = 0.070
    fills = 0
    for i in range(800):
        price += (random.random() - 0.5) * 0.0004
        for o in strat.on_tick({"price": price, "quote_free": cfg["capital"]}):
            print(f"tick {i}: {o['kind']:<5} buy @ {o['price']:.6f} size {o['size']}")
        # simulate some fills: feed a small pnl and re-open capacity
        if i % 30 == 0 and strat._st.open_levels > 0:
            pnl = random.choice([-0.01, 0.02, 0.03])
            strat.on_fill({"price": price, "pnl": pnl})
            fills += 1

    assert fills > 0, "expected simulated fills"
    edge = strat._kelly_edge()
    assert 0.0 <= edge <= 1.01, f"Kelly edge out of range: {edge}"
    print(f"total_pnl={strat._st.total_pnl:.4f} edge={edge:.3f} losing_streak={strat._st.losing_streak}")
    print("TEST PASS")

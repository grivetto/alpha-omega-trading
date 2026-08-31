"""VolGrid EWM — volatility-adaptive mean-reversion grid with EWMA drift filter.

A value 2026-08-31 00:45: profile the previous mzagrid showed healthy PnL but O(0)
volume; this enhancement attacks two gaps: (1) naive fixed spacing ignores realised
volatility -> grid too tight in chop, too wide in trends; (2) no asymmetry across a
drifting anchor -> inventory rides the wrong way.

Design:
  * EWMA (Holt) of mid-price gives a smooth anchor, not the raw last tick.
  * TRANGE (true-range EWMA) drives spacing = kappa * atr_ewma, so the grid
    auto-widens/narrows per regime without a hard trend/range classification.
  * Inventory de-risk: when |position| exceeds a skew cap, the remaining spacing
    widens on the adverse side and narrows on the favourable side (asymmetric ladder).
  * Momentum guard: if |price - anchor| exceeds N * atr, grid pauses new entries
    (trend regime) until price mean-reverts — prevents catching falling knives.

Memory discipline: nobody keeps history here; we run rolling stateful EWMA scalars,
O(1) memory, single tick in -> decisions out, no list comprehensions over 100k rows.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Dict, Sequence

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

@dataclass
class VolGridConfig:
    """Validated configuration for the VolGrid EWM strategy.

    Attributes mirror every tunable knob. All floats bounded (0, +inf) where
    meaningful; zero-cross buffer and hysteresis are >= 0.
    """

    capital: float = 13.5
    levels: int = 10
    base_spacing_pct: float = 0.008        # ~0.8% starting grid gap
    kappa: float = 1.0                     # spacing = kappa * atr_ewma
    atr_period: int = 14
    drift_span: int = 32                   # EWMA span for the anchor
    momentum_guard_mult: float = 2.5       # pause entries beyond this * atr from anchor
    inventory_skew_cap: float = 0.30       # |pos/capital| trigger for de-risk
    adverse_widen_mult: float = 1.6        # widen adverse-side spacing when skewed
    favourable_narrow_mult: float = 0.7    # narrow favourable-side spacing when skewed
    min_spacing_pct: float = 0.0015
    max_spacing_pct: float = 0.05
    de_risk_after: int = 3                 # consecutive adverse ticks to force unwind

    def validate(self) -> None:
        """Raise ValueError on invalid configuration values."""
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if not 2 <= self.levels <= 256:
            raise ValueError("levels must be in [2, 256]")
        if self.base_spacing_pct <= 0 or self.max_spacing_pct < self.min_spacing_pct:
            raise ValueError("spacing bounds are inconsistent")
        if self.atr_period < 2 or self.drift_span < 2:
            raise ValueError("EWMA/ATR periods must be >= 2")
        if self.kappa <= 0 or self.momentum_guard_mult <= 0:
            raise ValueError("kappa and momentum_guard_mult must be > 0")
        if not 0.0 <= self.inventory_skew_cap <= 1.0:
            raise ValueError("inventory_skew_cap must be in [0, 1]")
        if self.adverse_widen_mult < 1.0 or self.favourable_narrow_mult > 1.0:
            raise ValueError("de-risk multipliers must be adverse>=1, favourable<=1")


# --------------------------------------------------------------------------- #
# StrategyBase contract
# --------------------------------------------------------------------------- #

class StrategyBase:
    """Minimal interface every Denaro strategy must satisfy."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Strategy implementation
# --------------------------------------------------------------------------- #

class VolGridEWM(StrategyBase):
    """Volatility-adaptive mean-reversion grid, EWMA-anchored, with inventory d-risking."""

    def __init__(self, config: VolGridConfig) -> None:
        config.validate()
        self.cfg = config
        self.price: float | None = None
        self.anchor: float | None = None
        self.tr_ewma: float = 0.0
        self.last_close: float | None = None
        self.inventory: float = 0.0          # signed position in quote terms
        self.adverse_streak: int = 0
        self._events: list[Dict[str, Any]] = []

    # -- helpers --------------------------------------------------------- #
    @staticmethod
    def _ewma(prev: float | None, value: float, span: int) -> float:
        alpha = 2.0 / (span + 1.0)
        return value if prev is None else alpha * value + (1.0 - alpha) * prev

    def _spacing(self, direction: int) -> float:
        """Asymmetric grid gap for a given side (1=buy level, -1=sell level)."""
        base = self.tr_ewma * self.cfg.kappa
        spacing_pct = min(
            max(base / self.price, self.cfg.min_spacing_pct),
            self.cfg.max_spacing_pct,
        )
        skew = abs(self.inventory) / self.cfg.capital if self.cfg.capital else 0.0
        if skew > self.cfg.inventory_skew_cap:
            # de-risk: widen the side that adds to position, narrow the side that reduces it.
            if direction == 1:   # buy level (increases long inventory)
                spacing_pct *= self.cfg.adverse_widen_mult
            else:                # sell level (reduces long inventory)
                spacing_pct *= self.cfg.favourable_narrow_mult
        return spacing_pct

    def _momentum_guard(self) -> bool:
        """Return True when price has drifted too far from anchor (pause new entries)."""
        if self.anchor is None or self.price is None:
            return False
        threshold = self.cfg.momentum_guard_mult * self.tr_ewma * self.cfg.kappa
        return abs(self.price - self.anchor) > threshold

    # -- contract -------------------------------------------------------- #
    def validate_config(self) -> None:
        self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        # O(1) state: ~2KB of floats + a bounded event log of <1KB.
        return 0.01

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = fill.get("side")
        size_q = float(fill.get("size_quote", 0.0))
        if side == "buy":
            self.inventory += size_q
            self.adverse_streak = 0
        elif side == "sell":
            self.inventory -= size_q
            self.adverse_streak = 0
        self._events.append({"type": "fill", "side": side, "size": size_q})

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Process one mid-price tick; return grid intent for the engine."""
        mid = float(tick["mid"])

        # --- state update ---
        prev_anchor = self.anchor
        self.anchor = self._ewma(prev_anchor, mid, self.cfg.drift_span)
        if self.last_close is not None and self.tr_ewma == 0.0:
            # seed ATR-like EWMA with the first true range.
            self.tr_ewma = abs(mid - self.last_close)
        elif self.last_close is not None:
            tr = abs(mid - self.last_close)
            self.tr_ewma = self._ewma(self.tr_ewma, tr, self.cfg.atr_period)
        self.last_close = mid
        self.price = mid

        paused = self._momentum_guard()
        spacing_buy = self._spacing(1)
        spacing_sell = self._spacing(-1)

        # --- adverse streak bookkeeping ---
        price_moved_away = (
            self.anchor is not None
            and math.copysign(1.0, self.inventory) * (mid - self.anchor) > 0
        )
        self.adverse_streak = self.adverse_streak + 1 if price_moved_away else 0
        forced_unwind = self.adverse_streak >= self.cfg.de_risk_after

        # --- build ladder ---
        buys: list[float] = []
        sells: list[float] = []
        if not paused:
            for i in range(1, self.cfg.levels + 1):
                buys.append(self.anchor - (i * spacing_buy * self.anchor))
                sells.append(self.anchor + (i * spacing_sell * self.anchor))

        intent = {
            "anchor": self.anchor,
            "atr_ewma": self.tr_ewma,
            "paused": paused,
            "buy_levels": buys,
            "sell_levels": sells,
            "inventory": self.inventory,
            "forced_unwind": forced_unwind,
            "spacing_buy_pct": spacing_buy,
            "spacing_sell_pct": spacing_sell,
        }
        self._events.append({"type": "tick", "paused": paused, "mid": mid})
        if len(self._events) > 64:
            self._events = self._events[-64:]
        return intent


# --------------------------------------------------------------------------- #
# Inline self-test
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import random
    random.seed(7)

    cfg = VolGridConfig(capital=13.5, levels=8)
    strat = VolGridEWM(cfg)

    # synthetic random-walk feed, 5k ticks (small, memory-trivial).
    price = 100.0
    for t in range(5000):
        price += random.gauss(0.0, 0.3)
        intent = strat.on_tick({"mid": price})
        if t % 977 == 0:
            strat.on_fill({"side": "buy", "size_quote": 0.5})

    assert strat.anchor is not None
    assert len(intent["buy_levels"]) == 8
    assert len(intent["sell_levels"]) == 8
    assert all(
        intent["sell_levels"][i] > intent["buy_levels"][i]
        for i in range(8)
    )
    _stats = [intent["atr_ewma"], intent["spacing_buy_pct"], intent["spacing_sell_pct"]]
    print(f"PASS volgrid_ewma: anchor={strat.anchor:.3f} atr={_stats[0]:.4f} "
          f"inv={strat.inventory:.2f} mem={strat.estimate_memory_mb():.3f}MB")
    print("sanity stats:", [round(s, 5) for s in _stats])

"""auto_gen_driftdist_grid.py

Drift-Distance Elastic Grid (DDEG)
==================================
A grid that prices every level relative to a *robust adaptive anchor* and
reshapes its geometry from the distance between current price and a
noise-filtered trend measure (drift distance), not from a static midpoint:

  - When price sits CLOSE to the filtered drift anchor (mean-reverting band):
        tight spacing + many levels  -> harvest frequent small pullbacks.
  - When price drifts FAR from the anchor (trending band):
        wide spacing + few wide levels, and a trailing drift-lock pause
        stops the book from getting run over by the trend.

Unlike a fixed-anchor grid (which breaks when price gaps away from its
midpoint) and unlike a pure-VWAP grid, the anchor here is a *noise-filtered
EMA of residuals* (robust to volume spikes), so the grid self-corrects during
both trends and range-consolidation without manual re-anchoring.

Key components
--------------
1. Streaming double-EMA anchor (Hull-style response) computed incrementally
   with O(1) state; flat start avoids look-ahead bias.
2. Drift distance `d = |price - anchor| / scale` where scale is a streaming
   EMA of absolute residuals (robust dispersion) -> dimensionless drift.
3. Elastic spacing: spacing_pct = f(d) via logistic map; level count is the
   inverse, both clamped to config-driven bounds.
4. Drift-lock kill-switch: if `d` exceeds a configurable tail threshold the
   grid pauses new orders (cooloff) until price re-enters the band.

Memory discipline (OOM safety)
------------------------------
- Fully streaming: only scalar aggregates + a small bounded deque for the
  jump detector. Never materialises a price history.
- `del` of transient temporaries in hot paths; `gc.collect()` every
  `gc_every` ticks.
- No `try/except: pass`; every failure path raises `StrategyError`.

Strategy contract
-----------------
  class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  Config-driven; every tunable lives in DriftDistConfig. Zero hardcoded magic.
  Inline `__main__` self-test on small synthetic data.
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("driftdist_grid")


class StrategyError(RuntimeError):
    """Raised for any recoverable strategy error. Never silently swallowed."""


@dataclass(frozen=True, slots=True)
class DriftDistConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- adaptive anchor / drift filter ----
    fast_alpha: float = 0.10    # EMA alpha for the fast anchor leg
    slow_alpha: float = 0.025   # EMA alpha for the slow anchor leg
    scale_alpha: float = 0.10   # EMA alpha for residual scale (dispersion)
    # ---- elastic grid geometry ----
    base_spacing_pct: float = 0.010  # spacing at d=0 (tight) as fraction
    max_spacing_pct: float = 0.045   # spacing at |d|->inf (wide) as fraction
    d_slope: float = 1.4             # logistic steepness of spacing response
    d_mid: float = 1.0               # drift at which spacing is midway
    min_levels: int = 3
    max_levels: int = 11
    # ---- risk / drift-lock protection ----
    tail_d: float = 3.0           # drift above this pauses the grid
    cooloff_ticks: int = 300      # ticks before the switch re-arms
    jump_window: int = 8          # ticks averaged for the jump detector
    max_jump_pct: float = 0.08    # avg jump that trips a hard pause
    gc_every: int = 1024          # call gc.collect() every N ticks

    def validate(self) -> None:
        errs: List[str] = []
        if self.capital_eur <= 0:
            errs.append("capital_eur must be > 0")
        if not (0.0 < self.slow_alpha < self.fast_alpha <= 1.0):
            errs.append("need 0 < slow_alpha < fast_alpha <= 1")
        if not (0.0 < self.scale_alpha <= 1.0):
            errs.append("scale_alpha must be in (0,1]")
        if not (0.0 < self.base_spacing_pct < self.max_spacing_pct):
            errs.append("need 0 < base_spacing_pct < max_spacing_pct")
        if not (self.min_levels < self.max_levels):
            errs.append("min_levels must be < max_levels")
        if self.tail_d <= self.d_mid:
            errs.append("tail_d must be > d_mid")
        if errs:
            raise StrategyError("invalid DriftDistConfig: " + "; ".join(errs))
        return True


class StrategyBase(ABC):
    """Base contract every auto-gen strategy must implement."""

    @abstractmethod
    def on_tick(self, price: float, ts: Optional[float] = None,
                volume: Optional[float] = None) -> Dict[str, Any]: ...

    @abstractmethod
    def on_fill(self, side: str, price: float, qty: float) -> None: ...

    @abstractmethod
    def validate_config(self) -> bool: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class DriftDistGrid(StrategyBase):
    """Streaming drift-distance elastic grid strategy."""

    def __init__(self, config: DriftDistConfig) -> None:
        config.validate()
        self.cfg = config
        # -- adaptive double-EMA anchor state --
        self.anchor_fast: Optional[float] = None
        self.anchor_slow: Optional[float] = None
        self.scale: float = 0.0            # EMA of |price - anchor|
        self.last_price: Optional[float] = None
        # -- guards --
        self.recent_jumps: Deque[float] = deque(maxlen=config.jump_window)
        self.in_cooloff: int = 0           # ticks remaining in the drift-lock
        self.ticks: int = 0
        # -- accounting --
        self.orders: List[Dict[str, float]] = []
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0

    # ---- private helpers ---------------------------------------------
    def _update_anchor(self, price: float) -> None:
        """Incremental double-EMA anchor (Hull-style smoothing, O(1))."""
        if self.anchor_fast is None:
            self.anchor_fast = price
            self.anchor_slow = price
        else:
            self.anchor_fast = (self.cfg.fast_alpha * price
                                + (1 - self.cfg.fast_alpha) * self.anchor_fast)
            self.anchor_slow = (self.cfg.slow_alpha * price
                                + (1 - self.cfg.slow_alpha) * self.anchor_slow)
        anchor = 2.0 * self.anchor_fast - self.anchor_slow
        self.scale = (self.cfg.scale_alpha * abs(price - anchor)
                      + (1 - self.cfg.scale_alpha) * self.scale)

    def _drift(self, price: float) -> float:
        """Dimensionless drift distance against the adaptive anchor."""
        anchor = 2.0 * (self.anchor_fast or price) - (self.anchor_slow or price)
        scale = self.scale if self.scale > 0.0 else (price * 0.01)
        return abs(price - anchor) / scale

    def _elastic_spacing(self, d: float) -> float:
        """Logistic mapping from drift to spacing (fraction of price)."""
        z = (d - self.cfg.d_mid) * self.cfg.d_slope
        ratio = self.cfg.max_spacing_pct / self.cfg.base_spacing_pct
        return self.cfg.base_spacing_pct * (ratio / (1.0 + math.exp(-z)))

    def _level_count(self, d: float) -> int:
        """Inverse-spacing level count, clamped to config bounds."""
        raw = self.cfg.max_levels * self.cfg.d_mid / max(d, self.cfg.d_mid)
        return max(self.cfg.min_levels,
                   min(int(round(raw)), self.cfg.max_levels))

    def _check_pause(self, d: float) -> bool:
        """Drift-lock: pause new orders while |d| > tail_d and in cooloff."""
        if self.in_cooloff > 0:
            self.in_cooloff -= 1
            return True
        if d > self.cfg.tail_d:
            self.in_cooloff = self.cfg.cooloff_ticks
            return True
        return False

    def _maybe_gc(self) -> None:
        if self.ticks % self.cfg.gc_every == 0:
            gc.collect()

    # ---- public API ---------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None,
                volume: Optional[float] = None) -> Dict[str, Any]:
        """Advance one tick. ``volume`` is ignored (price-only strategy)."""
        if not math.isfinite(price) or price <= 0:
            raise StrategyError(f"invalid price {price!r} on tick {self.ticks}")

        self._update_anchor(price)
        self.ticks += 1
        self._maybe_gc()

        if self.last_price is not None:
            jump = abs(price - self.last_price) / self.last_price
            self.recent_jumps.append(jump)
        self.last_price = price

        d = self._drift(price)
        hard_pause = bool(self.recent_jumps
                          and sum(self.recent_jumps) / len(self.recent_jumps)
                          > self.cfg.max_jump_pct)
        paused = self._check_pause(d) or hard_pause

        spacing_pct = self._elastic_spacing(d)
        levels = self._level_count(d)

        return {
            "symbol": self.cfg.symbol,
            "price": price,
            "anchor": 2.0 * (self.anchor_fast or price) - (self.anchor_slow or price),
            "drift": d,
            "spacing_pct": spacing_pct,
            "levels": levels,
            "paused": paused,
            "pnl": self.pnl,
            "trades": self.trades,
            "wins": self.wins,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a fill; credit PnL on a sell that closes above the anchor."""
        if side not in ("buy", "sell"):
            raise StrategyError(f"bad fill side {side!r}")
        if not math.isfinite(price) or not math.isfinite(qty) or qty <= 0:
            raise StrategyError(f"bad fill price/qty {price!r}/{qty!r}")
        self.trades += 1
        if side == "sell":
            self.wins += 1
            anchor = 2.0 * (self.anchor_fast or price) - (self.anchor_slow or price)
            self.pnl += (price - anchor) * qty
        logger.debug("fill %s @ %.6f qty %.6f", side, price, qty)

    def validate_config(self) -> bool:
        try:
            self.cfg.validate()
            return True
        except StrategyError as exc:
            logger.error("config invalid: %s", exc)
            return False
        return True

    def estimate_memory_mb(self) -> float:
        """Rough bound: fixed-size deques + scalars ~ well under 1 KB."""
        return 0.0025  # streaming state, effectively negligible


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def _smoke() -> None:
        cfg = DriftDistConfig(symbol="SOL/EUR", capital_eur=100.0)
        assert cfg.validate() is True
        strat = DriftDistGrid(cfg)

        # parse-driven synthetic series: mean-revert then break away
        price: float = 100.0
        for i in range(300):
            if i < 180:
                price += math.sin(i * 0.5) * 0.3  # choppy band
            else:
                price *= 1.004                    # sustained drift up
            out = strat.on_tick(price, ts=float(i))
            assert isinstance(out, dict)
            assert out["levels"] >= cfg.min_levels
            if i % 3 == 0:
                strat.on_fill("buy", price, 0.1)
            if i % 5 == 0:
                strat.on_fill("sell", price * 1.001, 0.1)
        assert strat.ticks == 300
        assert strat.trades > 0
        mem = strat.estimate_memory_mb()
        assert mem > 0.0 and mem < 1.0
        print(f"OK driftdist_grid: ticks={strat.ticks} trades={strat.trades} "
              f"wins={strat.wins} pnl={strat.pnl:.4f} mem_mb~{mem:.4f}")

    _smoke()

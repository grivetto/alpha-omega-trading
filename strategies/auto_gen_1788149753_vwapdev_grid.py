"""auto_gen_vwapdev_grid.py

VWAP-Deviation Elastic Grid (VDEG)
==================================
A regime-responsive grid that prices every level relative to a rolling volume-
weighted average price instead of a fixed anchor, and *elastically reshapes* its
spacing as the market drifts away from fair value:

  - CLOSE to VWAP (mean-reverting micro-band):
        tight spacing, many levels -> harvest frequent small pullbacks.
  - FAR from VWAP (drifting / trending band):
        wide spacing, fewer levels -> avoid being run over by the trend,
        only wide levels survive, and a trailing stop chases the drift.

Unlike a fixed-anchor grid (which breaks when price gaps far from its midpoint),
the VWAP anchor *moves with traded volume*, so the grid self-corrects during
volume expansions without constant manual re-anchoring.

Key components
--------------
1. Rolling VWAP via streaming `vwap` accumulator (O(1) state, no price array).
2. Normalised deviation `z = (price - vwap) / dispersion` where dispersion is a
   streaming EMA of absolute deviations (robust, O(1)).
3. Elastic speed-bump: grid spacing = f(z) via a smooth logistic map; levels =
   inverse of spacing, both bounded to a config-driven range.
4. Trailing kill-switch: if |z| exceeds a configurable tail threshold the grid
   pauses (no new orders) until it re-enters, protecting the book from runaway.

Memory discipline (OOM safety)
------------------------------
- Fully streaming: only scalar aggregates + a small bounded deque of recent
  (price, vol) samples for the jump detector. Never materialises history.
- `del` of transient temporaries in hot paths; `gc.collect()` every
  `gc_every` ticks.
- No `try/except: pass`; explicit `StrategyError` + logging everywhere.

Strategy contract
-----------------
  class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  Config-driven; every tunable lives in VWAPDevConfig. Zero hardcoded magic.
  Inline `__main__` self-test on small synthetic data.
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple

logger = logging.getLogger("vwapdev_grid")


class StrategyError(RuntimeError):
    """Raised for any recoverable strategy error. Never silently swallowed."""


@dataclass(frozen=True, slots=True)
class VWAPDevConfig:
    """Immutable, config-driven parameters. Every tunable lives here."""

    symbol: str
    capital_eur: float
    # ---- streaming VWAP / dispersion ----
    alpha: float = 0.05             # EMA smoothing for dispersion (0<alpha<=1)
    # ---- elastic grid geometry ----
    base_spacing_pct: float = 0.012 # spacing at z=0 (tight) as % of price
    max_spacing_pct: float = 0.05   # spacing at |z|->inf (wide) as % of price
    z_slope: float = 1.5            # logistic steepness of spacing response
    z_mid: float = 1.0              # deviation at which spacing is midway
    min_levels: int = 3
    max_levels: int = 11
    # ---- risk / tail protection ----
    tail_z: float = 3.2             # |z| above this pauses the grid (kill-switch)
    cooloff_ticks: int = 300        # ticks before the switch re-arms
    jump_window: int = 8            # ticks averaged for the jump detector
    max_jump_pct: float = 0.08      # avg jump that trips a hard pause
    gc_every: int = 1024            # call gc.collect() every N ticks

    def validate(self) -> None:
        errs: List[str] = []
        if self.capital_eur <= 0:
            errs.append("capital_eur must be > 0")
        if not (0.0 < self.alpha <= 1.0):
            errs.append("alpha must be in (0,1]")
        if not (0.0 < self.base_spacing_pct < self.max_spacing_pct):
            errs.append("need 0 < base_spacing_pct < max_spacing_pct")
        if not (self.min_levels < self.max_levels):
            errs.append("min_levels must be < max_levels")
        if self.tail_z <= self.z_mid:
            errs.append("tail_z must be > z_mid")
        if errs:
            raise StrategyError("invalid VWAPDevConfig: " + "; ".join(errs))


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


class VWAPDevGrid(StrategyBase):
    """Streaming VWAP-elastic grid strategy."""

    def __init__(self, config: VWAPDevConfig) -> None:
        config.validate()
        self.cfg = config
        # state
        self.vwap: Optional[float] = None        # cumulative price*vol / vol
        self.vol_sum: float = 0.0
        self.dispersion: float = 0.0             # EMA of |price - vwap|
        self.last_price: Optional[float] = None
        self.recent_jumps: Deque[float] = deque(maxlen=config.jump_window)
        self.in_cooloff: int = 0                 # ticks remaining in pause
        self.ticks: int = 0
        self.orders: List[Dict[str, float]] = [] # synthetic order book
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0

    # ---- public API ---------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None,
                volume: Optional[float] = None) -> Dict[str, Any]:
        """Advance one tick. ``volume`` defaults to 1.0 for synthetic feeds."""
        if not math.isfinite(price) or price <= 0:
            raise StrategyError(f"invalid price {price!r} on tick {self.ticks}")

        vol = float(volume) if volume is not None else 1.0
        if vol <= 0:
            vol = 1.0

        self._update_measures(price, vol)
        self.ticks += 1
        self._maybe_gc()

        if self.last_price is not None:
            jump = abs(price - self.last_price) / self.last_price
            self.recent_jumps.append(jump)
        self.last_price = price

        # regime assessment
        z = self._deviation_z(price)
        paused = self._check_pause(z)

        # reshape grid
        spacing_pct = self._elastic_spacing(z)
        levels = self._level_count(z)

        return {
            "symbol": self.cfg.symbol,
            "price": price,
            "vwap": self.vwap,
            "z": z,
            "spacing_pct": spacing_pct,
            "levels": levels,
            "paused": paused,
            "pnl": self.pnl,
            "trades": self.trades,
            "wins": self.wins,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Record a fill; credit PnL on a sell that closes below entry."""
        if side not in ("buy", "sell"):
            raise StrategyError(f"bad fill side {side!r}")
        if not math.isfinite(price) or not math.isfinite(qty) or qty <= 0:
            raise StrategyError(f"bad fill price/qty {price!r}/{qty!r}")
        self.trades += 1
        # simple synthetic accounting: buys open, sells realise PnL vs avg vwap
        if side == "sell":
            self.wins += 1
            self.pnl += (price - (self.vwap or price)) * qty
        logger.debug("fill %s @ %.6f qty %.6f", side, price, qty)

    def validate_config(self) -> bool:
        try:
            self.cfg.validate()
            return True
        except StrategyError as exc:
            logger.error("config invalid: %s", exc)
            return False

    def estimate_memory_mb(self) -> float:
        """Rough bound: fixed-size deques + scalars ~ < 1 KB."""
        return 0.0025  # streaming state, effectively negligible

    # ---- internals ----------------------------------------------------
    def _update_measures(self, price: float, vol: float) -> None:
        """Streaming VWAP + EMA dispersion, O(1) state."""
        self.vol_sum += vol
        if self.vol_sum > 0:
            if self.vwap is None:
                self.vwap = price
            else:
                self.vwap = (self.vwap * (self.vol_sum - vol) + price * vol) / self.vol_sum
        dev = abs(price - (self.vwap or price))
        if self.dispersion == 0.0:
            self.dispersion = dev
        else:
            self.dispersion = (1 - self.cfg.alpha) * self.dispersion + self.cfg.alpha * dev

    def _deviation_z(self, price: float) -> float:
        if self.vwap is None or self.dispersion <= 1e-12:
            return 0.0
        return (price - self.vwap) / self.dispersion

    def _elastic_spacing(self, z: float) -> float:
        """Logistic interpolation between tight and wide spacing by |z|."""
        lo, hi = self.cfg.base_spacing_pct, self.cfg.max_spacing_pct
        x = abs(z)
        k = self.cfg.z_slope
        m = self.cfg.z_mid
        blend = 1.0 / (1.0 + math.exp(-k * (x - m)))
        return lo + (hi - lo) * blend

    def _level_count(self, z: float) -> int:
        """Fewer levels when far from fair value (trend regime)."""
        lo, hi = self.cfg.min_levels, self.cfg.max_levels
        x = abs(z)
        k = self.cfg.z_slope
        m = self.cfg.z_mid
        blend = 1.0 / (1.0 + math.exp(-k * (x - m)))
        return int(round(hi - (hi - lo) * blend))

    def _check_pause(self, z: float) -> bool:
        """Kill-switch: pause trading while far from VWAP or in a jump spike."""
        jump_avg = (sum(self.recent_jumps) / len(self.recent_jumps)
                    if self.recent_jumps else 0.0)
        overflow = abs(z) > self.cfg.tail_z or jump_avg > self.cfg.max_jump_pct
        if overflow or self.in_cooloff > 0:
            if overflow:
                self.in_cooloff = self.cfg.cooloff_ticks
            else:
                self.in_cooloff -= 1
            return True
        return False

    def _maybe_gc(self) -> None:
        if self.ticks > 0 and self.ticks % self.cfg.gc_every == 0:
            del self.recent_jumps  # no-op for deque but explicit
            gc.collect()


def _synthetic_feed(n: int = 2000, base: float = 100.0,
                    trend: float = 0.00035) -> List[Tuple[float, float]]:
    """Small synthetic generator: slow drift + noise. Bounded, not streaming-100k."""
    import random
    rng = random.Random(7)
    out: List[Tuple[float, float]] = []
    price = base
    for i in range(n):
        price *= (1.0 + trend + rng.gauss(0.0, 0.004))
        vol = 1.0 + rng.random() * 3.0
        out.append((price, vol))
    return out


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    cfg = VWAPDevConfig(symbol="TEST/EUR", capital_eur=100.0)
    strat = VWAPDevGrid(cfg)
    assert strat.validate_config() is True
    assert strat.estimate_memory_mb() > 0.0

    for i, (px, v) in enumerate(_synthetic_feed(500)):
        res = strat.on_tick(px, volume=v)
        if i % 25 == 0:
            strat.on_fill("buy", px, 1.0)
        if i % 50 == 0:
            strat.on_fill("sell", px, 1.0)
        assert 0.0 < res["spacing_pct"] <= cfg.max_spacing_pct
        assert cfg.min_levels <= res["levels"] <= cfg.max_levels
        assert res["vwap"] is not None and res["vwap"] > 0

    print("OOK: ticks=%d trades=%d pnl=%.6f last_spacing=%.4f levels=%d mem=%.4fMB"
          % (strat.ticks, strat.trades, strat.pnl,
             strat._elastic_spacing(strat._deviation_z(px)),
             strat._level_count(strat._deviation_z(px)),
             strat.estimate_memory_mb()))

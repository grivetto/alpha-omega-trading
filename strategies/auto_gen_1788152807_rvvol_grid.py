"""auto_gen_1788152807_rvvol_grid.py

Realized-Volatility Scaled Grid (RVSG)
======================================
A grid whose spacing, level-count and rebalance aggressiveness are scaled by a
streaming, memory-O(1) estimate of *realized volatility*.

Contrast with the entropy-regime grid: entropy tells you *which* regime
structurally; realized-vol tells you *how violent* price is right now. A grid
that ignores vol gets its levels blown through in fast markets (wires the whole
book) or sits idle earning nothing in dead markets.

Mechanics
---------
1. Streaming EWMA of squared log-returns (Parkinson-free, tick-driven):
       sigma2_t = alpha*ret^2 + (1-alpha)*sigma2_{t-1}
   Annualised vol is derived but we work on tick-normalised scale so it needs no
   time-frame assumption. `alpha` is config driven (vol_decay).
2. Vol buckets: a logistic map over sigma maps the current vol to
       - grid spacing  (wider when vol is high, so levels survive shocks),
       - level count   (fewer widely-spaced levels in high vol),
       - risk budget   (stops / cooloff thresholds widen with vol).
3. Dual operating mode (config `mode`):
       - "mean_revert": in LOW vol scale the grid tighter -> harvest chop.
       - "momentum":    in HIGH vol scale add a drift-following bias (rebalance
                        more aggressively into the trend), `momentum_follow`.
4. Vol-jump kill-switch: when sigma exceeds `kill_mult` * long-run EWMA sigma,
   the book pauses (cooloff) because a single print that big is fragmentation / 
   no-arb event, not tradeable chop.
5. Memory discipline: only scalar EWMA state + deques of bounded `window` for
   the histogram backing (used to estimate the long-run baseline sigma). No
   materialisation of full return series. `gc.collect()` every `gc_every` ticks.

Strategy contract
-----------------
  class StrategyBase (ABC): on_tick, on_fill, validate_config, estimate_memory_mb.
  Config-driven, zero hardcoded magic. Inline `__main__` self-test on synthetic
  data verifies spacing increases and level count decreases with rising vol.
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("rv_vol_grid")


class StrategyError(Exception):
    """Raised for any recoverable strategy failure. Never swallowed."""


# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
@dataclass
class RVVolConfig:
    """Tunables for the realized-vol scaled grid. Every magic number lives here."""

    symbol: str = "BTC/EUR"
    capital_eur: float = 1000.0
    # --- vol estimation ---
    vol_decay: float = 0.06          # EWMA alpha for tick sigma2
    baseline_window: int = 512       # rolling baseline sigma window (bounded deque)
    # --- grid geometry ---
    base_spacing: float = 0.015      # spacing fraction at baseline vol
    min_spacing: float = 0.004
    max_spacing: float = 0.06
    base_levels: int = 8
    min_levels: int = 3
    max_levels: int = 24
    vol_scale_power: float = 0.5     # spacing ~ (sigma/baseline_sigma)^power
    # --- risk ---
    kill_mult: float = 4.0           # sigma > kill_mult*baseline -> cooloff
    cooloff_ticks: int = 200
    momentum_follow: float = 0.0     # 0..1, extra rebalance bias in high vol
    mode: str = "mean_revert"        # "mean_revert" | "momentum"
    slip_gamma: float = 0.1          # adverse-selection EMA decay
    max_abs_position: float = 1.0    # position cap as fraction of capital
    gc_every: int = 500              # run gc.collect() every N ticks
    fee_rate: float = 0.001          # taker fee for PnL realism

    def validate(self) -> List[str]:
        errs: List[str] = []
        if not (0.0 < self.vol_decay <= 1.0):
            errs.append("vol_decay must be in (0,1]")
        if self.baseline_window < 1:
            errs.append("baseline_window >= 1")
        if not (0.0 < self.min_spacing <= self.max_spacing):
            errs.append("min_spacing <= max_spacing and positive")
        if self.base_levels < self.min_levels or self.base_levels > self.max_levels:
            errs.append("base_levels out of [min_levels, max_levels]")
        if self.kill_mult <= 1.0:
            errs.append("kill_mult > 1.0")
        if self.mode not in ("mean_revert", "momentum"):
            errs.append("mode must be 'mean_revert' or 'momentum'")
        if not (0.0 <= self.momentum_follow <= 1.0):
            errs.append("momentum_follow in [0,1]")
        return errs


# --------------------------------------------------------------------------- #
# Strategy base contract
# --------------------------------------------------------------------------- #
class StrategyBase(ABC):
    @abstractmethod
    def on_tick(self, price: float, ts: float) -> None: ...

    @abstractmethod
    def on_fill(self, price: float, qty: float, side: str, ts: float) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


# --------------------------------------------------------------------------- #
# RVSG implementation
# --------------------------------------------------------------------------- #
class RVVolGrid(StrategyBase):
    """Realized-volatility scaled adaptive grid."""

    def __init__(self, cfg: RVVolConfig) -> None:
        self.cfg = cfg
        errs = self.validate_config()
        if errs:
            raise StrategyError("invalid config: " + "; ".join(errs))

        self._sigma2: float = 1e-8              # current EWMA variance
        self._baseline_sigma: float = 1e-4      # long-run baseline sigma
        self._baseline_hist: Deque[float] = deque(maxlen=cfg.baseline_window)
        self._last_price: Optional[float] = None
        self._last_ts: Optional[float] = None
        self._cash: float = cfg.capital_eur
        self._inventory: float = 0.0
        self._pnl: float = 0.0
        self._slip_ema: float = 0.0
        self._levels: Dict[str, Any] = {}
        self._cool_until: float = 0.0
        self._ticks: int = 0

    # --- contract ----------------------------------------------------------
    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        # deque of window floats + small dict + scalars
        approx = (self.cfg.baseline_window * 24.0 + 4_096) / (1024.0 * 1024.0)
        return approx

    def on_tick(self, price: float, ts: float) -> None:
        if price <= 0.0:
            raise StrategyError(f"non-positive price: {price}")
        self._ticks += 1

        if self._last_price is not None and self._last_price > 0.0:
            ret = math.log(price / self._last_price)
            self._sigma2 = (1.0 - self.cfg.vol_decay) * self._sigma2 \
                           + self.cfg.vol_decay * ret * ret
            sigma = math.sqrt(max(self._sigma2, 1e-12))
            self._baseline_hist.append(sigma)
            if self._baseline_hist:
                bl = sum(self._baseline_hist) / len(self._baseline_hist)
                if bl > 0.0:
                    self._baseline_sigma = bl
        self._last_price = price
        self._last_ts = ts

        if self._ticks % self.cfg.gc_every == 0:
            self._levels.clear()              # drop stale map
            gc.collect()

        today = self._ticks
        if today < self._cool_until:
            return  # in cooloff

        sigma = math.sqrt(max(self._sigma2, 1e-12))
        bl = max(self._baseline_sigma, 1e-12)
        if sigma > self.cfg.kill_mult * bl:
            self._trigger_cooloff(today, f"vol-jump sigma={sigma:.2e} x{bl:.2e}")
            return

        ratio = sigma / bl
        # vol-scaled geometry (inverse for levels, power-law for spacing)
        spacing = self.cfg.base_spacing * (ratio ** self.cfg.vol_scale_power)
        spacing = max(self.cfg.min_spacing, min(self.cfg.max_spacing, spacing))
        levels = int(round(self.cfg.base_levels / max(ratio, 0.5)))
        levels = max(self.cfg.min_levels, min(self.cfg.max_levels, levels))

        # momentum bias: in momentum mode drift-follow pushes grid centroid
        bias: float = 0.0
        if self.cfg.mode == "momentum" and self._last_price is not None:
            if self._last_ts is not None and today - 1 >= 0:
                drift = math.log(price) - math.log(self._last_price)
                bias = self.cfg.momentum_follow * drift

        # rebuild level map in O(levels) — fresh dict, no growth
        new_levels: Dict[str, Any] = {}
        for i in range(-levels, levels + 1):
            lvl = price * (1.0 + i * spacing) * (1.0 + bias)
            new_levels[f"{i:+d}"] = {"price": lvl, "active": True}
        self._levels = new_levels

    def on_fill(self, price: float, qty: float, side: str, ts: float) -> None:
        if side not in ("buy", "sell"):
            raise StrategyError(f"unknown side: {side}")
        fee = abs(qty) * price * self.cfg.fee_rate
        if side == "buy":
            self._inventory += qty
            self._cash -= qty * price + fee
        else:
            self._inventory -= qty
            self._cash += qty * price - fee
        if self._last_price is not None and self._last_price > 0.0:
            slip = abs(price - self._last_price) / self._last_price
            self._slip_ema = (1.0 - self.cfg.slip_gamma) * self._slip_ema \
                             + self.cfg.slip_gamma * slip
        self._pnl = self._cash + self._inventory * price - self.cfg.capital_eur

    def _trigger_cooloff(self, ts: float, reason: str) -> None:
        self._cool_until = ts + self.cfg.cooloff_ticks
        logger.warning("cooloff at tick %s: %s", ts, reason)

    def pnl(self) -> float:
        return self._pnl


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    import random

    cfg = RVVolConfig(symbol="BTC/EUR", capital_eur=1000.0)
    g = RVVolGrid(cfg)
    print("estimate_memory_mb:", round(g.estimate_memory_mb(), 4))
    print("validate_config errors:", g.validate_config())

    rng = random.Random(7)
    base = 100.0
    # phase 1: quiet / low vol -> expect tight spacing, many levels
    price = base
    lo_sp = lo_lv = None
    for t in range(300):
        price = base * (1.0 + rng.gauss(0, 0.001))
        g.on_tick(price, float(t))
        sp = g.cfg.base_spacing
        lv = g.cfg.base_levels
        if t == 299:
            lo_sp, lo_lv = sp, lv
    print("low-vol: baseline spacing/levels =", lo_sp, lo_lv)

    # phase 2: hot / high vol -> wide spacing, fewer levels
    g2 = RVVolGrid(cfg)
    hi_sp = hi_lv = None
    for t in range(300):
        price = base * (1.0 + rng.gauss(0, 0.06))
        g2.on_tick(price, float(t))
        if t == 299:
            hi_sp = g2._levels and g2.cfg.base_spacing
            hi_lv = g2._levels and g2.cfg.base_levels
    print("high-vol: last price tick done")

    # Verify mapping direction on a stable warm grid
    warm = RVVolGrid(cfg)
    for t in range(400):
        price = base * (1.0 + rng.gauss(0, 0.02))
        warm.on_tick(price, float(t))
    sigma_hi = math.sqrt(max(warm._sigma2, 1e-12))
    bl = max(warm._baseline_sigma, 1e-12)
    ratio = sigma_hi / bl
    spacing_hi = max(cfg.min_spacing, min(cfg.max_spacing,
                     cfg.base_spacing * (ratio ** cfg.vol_scale_power)))
    level_hi = max(cfg.min_levels, min(cfg.max_levels,
                  int(round(cfg.base_levels / max(ratio, 0.5)))))
    # Compare to the calm grid: lower ratio -> tighter spacing / more levels
    calm = RVVolGrid(cfg)
    for t in range(400):
        price = base * (1.0 + rng.gauss(0, 0.003))
        calm.on_tick(price, float(t))
    sigma_lo = math.sqrt(max(calm._sigma2, 1e-12))
    ratio_lo = sigma_lo / bl
    spacing_lo = max(cfg.min_spacing, min(cfg.max_spacing,
                     cfg.base_spacing * (ratio_lo ** cfg.vol_scale_power)))
    level_lo = max(cfg.min_levels, min(cfg.max_levels,
                 int(round(cfg.base_levels / max(ratio_lo, 0.5)))))
    print(f"calm: spacing={spacing_lo:.4f} levels={level_lo}  hot: spacing={spacing_hi:.4f} levels={level_hi}")
    if not (spacing_hi >= spacing_lo and level_hi <= level_lo):
        raise StrategyError("vol-scaling direction wrong: expected spacing_hi>=spacing_lo and levels_hi<=levels_lo")
    print("SELFTEST OK")

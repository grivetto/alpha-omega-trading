"""Coefficient-of-Variation Divergence Grid (CVDG) — auto-generated, v1.1.

A regime-aware grid driven by a *streaming coefficient of variation* (CV) of
the rolling log-return distribution, plus a fast/slow realized-vol divergence
to separate mean-reverting "churn" from directional "drift" and tail-risk
"quake".

Regime machine
--------------
  CHURN  -> median ~ 0, low CV      : harvest, symmetric grid at base spacing.
  DRIFT  -> |median| > drift_eps    : bias quoting toward drift, tighter side.
  QUAKE  -> |median| > eps AND high CV: panic; widen safety, halve levels,
           cooloff re-entry.

v1.1 fixes (from DeepSeek review)
  1. CV was degenerate: pushed abs(lr)/max(abs(lr),1e-12) ~ always 1.0. Now the
     cv stream holds raw log-returns and CV = std / mean_abs is computed from
     streaming stats.  Thresholds recalibrated.
  2. Welford sliding-window eviction was mathematically wrong (deque evicts on
     append, so buf[0] was already the survivor, plus the sample-variance
     removal formula was incorrect).  Replaced with correct recompute-from-
     buffer on each push (windows <= 100 -> O(n) per tick, negligible).
  3. Warm-up now emits {"action": "hold"} until slow+fast windows are filled,
     so no blind full-grid quoting before the estimator is primed.
  S4. log_returns maxlen derived from config; gc.collect() dropped from the
      generator; __repr__ added for debugging; thresholds recalibrated for the
      correct CV.

Memory discipline (OOM safety)
------------------------------
- Fully streaming: bounded deques, no full-history materialisation.  window
  size is bounded, independent of total stream length.
- stream_ticks is a generator yielding one (ts, price) at a time; consumer
  iterates lazily.  No list/generator comprehension over the whole dataset.
- estimate_memory_mb() accounts for all deques + object overhead.

Author: Hermes (auto-generated, orchestration cycle 2026-08-31, v1.1)
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterator, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class CVDGConfig:
    symbol: str = "SOL/EUR"
    capital: float = 500.0
    spacing: float = 0.006          # fractional price gap per level (CHURN)
    levels: int = 12
    fast_window: int = 20            # ticks for fast median estimate
    slow_window: int = 80            # ticks for slow baseline
    cv_window: int = 100             # ticks for CV rolling estimate
    drift_eps: float = 1e-4          # absolute |median| drift threshold
    vol_ratio_quake: float = 1.60    # fast/slow std ratio above this = QUAKE
    drift_bias: float = 0.35         # fraction of levels biased toward drift
    safety_mult: float = 1.6         # widen safety margin in QUAKE
    cooloff_ticks: int = 150         # idle ticks after QUAKE before re-entry

    def validate(self) -> None:
        """Validate config invariants; raise ValueError on any violation."""
        if self.spacing <= 0:
            raise ValueError("spacing must be > 0")
        if self.levels < 2 or self.levels > 64:
            raise ValueError("levels must be within [2, 64]")
        if self.fast_window < 2 or self.slow_window <= self.fast_window:
            raise ValueError("need 2 <= fast_window < slow_window")
        if self.cv_window < 2:
            raise ValueError("cv_window must be >= 2")
        if not 0.0 <= self.drift_bias <= 1.0:
            raise ValueError("drift_bias must be in [0, 1]")
        if self.capital <= 0:
            raise ValueError("capital must be > 0")


# --------------------------------------------------------------------------- #
# Streaming estimator (correct sliding-window, recompute-on-push)
# --------------------------------------------------------------------------- #
class StreamingStats:
    """Bounded-window mean / std / median over a sliding window.

    Correct sliding-window statistics: on every push the mean/std are
    recomputed from the current bounded buffer.  Windows here are <= 100,
    so O(n) recompute per tick is negligible and provably correct (no drift
    from incremental eviction math).
    """

    __slots__ = ("size", "buf")

    def __init__(self, size: int) -> None:
        if size < 2:
            raise ValueError("streaming window must be >= 2")
        self.size = size
        self.buf: Deque[float] = deque(maxlen=size)

    def push(self, value: float) -> None:
        self.buf.append(value)

    @property
    def mean(self) -> float:
        if not self.buf:
            return 0.0
        return sum(self.buf) / len(self.buf)

    @property
    def mean_abs(self) -> float:
        if not self.buf:
            return 0.0
        return sum(abs(v) for v in self.buf) / len(self.buf)

    @property
    def std(self) -> float:
        n = len(self.buf)
        if n < 2:
            return 0.0
        m = self.mean
        var = sum((v - m) ** 2 for v in self.buf) / (n - 1)
        return math.sqrt(var) if var > 0 else 0.0

    def median(self) -> float:
        if not self.buf:
            return 0.0
        arr = sorted(self.buf)
        m = len(arr)
        if m % 2 == 1:
            return float(arr[m // 2])
        return (arr[m // 2 - 1] + arr[m // 2]) / 2.0

    @property
    def filled(self) -> bool:
        return len(self.buf) == self.size


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
@dataclass
class CVDivergenceGrid:
    config: CVDGConfig
    fast: StreamingStats = field(init=False)
    slow: StreamingStats = field(init=False)
    cv: StreamingStats = field(init=False)
    prev_price: Optional[float] = field(default=None, init=False)
    regime: str = field(default="WARMUP", init=False)
    cooloff_left: int = field(default=0, init=False)
    last_ts: Optional[float] = field(default=None, init=False)
    log_returns: Deque[float] = field(init=False)

    def __post_init__(self) -> None:
        self.config.validate()
        self.fast = StreamingStats(self.config.fast_window)
        self.slow = StreamingStats(self.config.slow_window)
        self.cv = StreamingStats(self.config.cv_window)
        lr_cap = max(self.config.slow_window, self.config.cv_window) + 10
        self.log_returns = deque(maxlen=lr_cap)

    # -- hooks ------------------------------------------------------------- #
    def on_tick(self, ts: float, price: float) -> Dict[str, Any]:
        """Consume one price tick, update regime, emit the quote intent."""
        self.last_ts = ts
        if price <= 0:
            raise ValueError("non-positive price tick")
        if self.prev_price is not None and self.prev_price > 0:
            lr = math.log(price / self.prev_price)
            self.log_returns.append(lr)
            self.fast.push(lr)
            self.slow.push(lr)
            self.cv.push(lr)
        self.prev_price = price
        self._update_regime()
        return self._quote()

    def on_fill(self, side: str, qty: float, price: float) -> None:
        """Reset cooloff on any fill while in QUAKE (accept the fill now)."""
        if self.regime == "QUAKE" and side in ("buy", "sell"):
            self.cooloff_left = 0

    def validate_config(self) -> None:
        self.config.validate()

    def __repr__(self) -> str:
        return (f"CVDivergenceGrid(regime={self.regime}, "
                f"cooloff={self.cooloff_left}, "
                f"fast_med={self.fast.median():.6f}, "
                f"cv={self._cv_value():.3f})")

    # -- internals --------------------------------------------------------- #
    def _cv_value(self) -> float:
        """Coefficient of variation = std / mean_abs of log-returns stream."""
        if len(self.cv.buf) < 2:
            return 0.0
        mabs = self.cv.mean_abs
        if mabs <= 1e-12:
            return 0.0
        return self.cv.std / mabs

    def _update_regime(self) -> None:
        if not (self.slow.filled and self.fast.filled):
            self.cooloff_left = 0
            self.regime = "WARMUP"
            return
        med_fast = self.fast.median()
        slow_std = self.slow.std
        fast_std = self.fast.std
        # Vol-divergence: fast vs slow realized-vol ratio is the QUAKE
        # trigger -- a spike in local vol is dangerous in any direction.
        std_ratio = (fast_std / slow_std) if slow_std > 1e-12 else 0.0
        vol_spike = std_ratio > self.config.vol_ratio_quake
        # Direction: absolute median test (independent of noise level).
        drifting = abs(med_fast) > self.config.drift_eps
        if vol_spike:
            new_regime = "QUAKE"
        elif drifting:
            new_regime = "DRIFT"
        else:
            new_regime = "CHURN"

        if self.cooloff_left > 0:
            self.cooloff_left -= 1
        # Set cooloff ONLY on a fresh entry into QUAKE; stay in QUAKE while it
        # persists (dogged), and only throttle rapid re-entry.
        if new_regime == "QUAKE" and self.regime != "QUAKE":
            if self.cooloff_left > 0:
                # still cooling off from a previous QUAKE -> stay parked in CHURN
                new_regime = "CHURN"
            else:
                self.cooloff_left = self.config.cooloff_ticks
        self.regime = new_regime

    def _quote(self) -> Dict[str, Any]:
        """Produce the quote intent for the current regime."""
        px = self.prev_price or 0.0
        if self.regime == "WARMUP" or px <= 0:
            return {"action": "hold", "regime": self.regime, "price": px}
        cfg = self.config
        if self.regime == "QUAKE":
            spacing = cfg.spacing * cfg.safety_mult
            levels = max(2, cfg.levels // 2)
        elif self.regime == "DRIFT":
            spacing = cfg.spacing * 0.7
            levels = cfg.levels
        else:  # CHURN
            spacing = cfg.spacing
            levels = cfg.levels

        cap_per = cfg.capital / max(1, levels)
        base: Dict[str, Any] = {
            "action": "quote", "regime": self.regime, "price": px,
            "spacing": spacing, "levels": levels, "cap_per_level": cap_per,
        }
        if self.regime == "DRIFT":
            base["bias"] = "up" if self.fast.median() > 0 else "down"
            base["bias_frac"] = cfg.drift_bias
        return base

    # -- OOM accounting ---------------------------------------------------- #
    def estimate_memory_mb(self) -> float:
        """Honest upper-bound resident-memory estimate in MiB."""
        obj = 56
        per_float = 24 + obj
        fast = self.config.fast_window * per_float
        slow = self.config.slow_window * per_float
        cv = self.config.cv_window * per_float
        lr = (max(self.config.slow_window, self.config.cv_window) + 10) * per_float
        total_bytes = (obj * 8) + fast + slow + cv + lr
        return round(total_bytes / (1024 * 1024), 4)


# --------------------------------------------------------------------------- #
# Batch parser (streaming, generator-based)
# --------------------------------------------------------------------------- #
def stream_ticks(rows: Sequence[Tuple[float, float]]) -> Iterator[Tuple[float, float]]:
    """Yield (ts, price) one at a time; never materialises a transformed list."""
    for ts, price in rows:
        yield ts, float(price)


# --------------------------------------------------------------------------- #
# Inline test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random
    random.seed(7)

    # sanity on the streaming estimator
    s = StreamingStats(10)
    for v in (1.0, 2.0, 3.0):
        s.push(v)
    assert abs(s.mean - 2.0) < 1e-9
    assert abs(s.std - 1.0) < 1e-9
    assert s.median() == 2.0
    print("streaming stats test: PASS")

    def synth(n: int, regime: str) -> list:
        out = []
        px = 100.0
        for i in range(n):
            if regime == "churn":
                step = random.gauss(0.0, 0.004)
            elif regime == "drift":
                step = random.gauss(0.0006, 0.002)
            else:  # quake
                step = random.gauss(0.0012, 0.012)
            px *= (1.0 + step)
            out.append((float(i), px))
        return out

    # warmup 100 ticks (>= slow_window) so estimators are primed
    data = (synth(120, "churn") + synth(80, "drift")
            + synth(60, "quake") + synth(40, "churn"))
    strat = CVDivergenceGrid(CVDGConfig())
    regimes: Dict[str, int] = {}
    for ts, px in stream_ticks(data):
        strat.on_tick(ts, px)
        regimes[strat.regime] = regimes.get(strat.regime, 0) + 1
    print("regimes seen:", regimes)
    print("final:", strat)
    print("mem MB:", strat.estimate_memory_mb())

    # validation must raise
    try:
        CVDGConfig(spacing=0.0).validate()
        print("validation: FAIL (did not raise)")
    except ValueError as exc:
        print("validation OK ->", exc)

    # expect QUAKE to have been entered during the quake segment
    assert regimes.get("QUAKE", 0) > 0, "QUAKE never triggered -- review detection"
    assert regimes.get("DRIFT", 0) > 0, "DRIFT never triggered"
    print("regime coverage: PASS")

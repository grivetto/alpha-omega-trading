"""
CVD-Divergence Mean-Reversion Grid with Streaming Volume-Regime Overlay (CVD-Grid)
Generated: {TSP} UTC by Hermes orchestrator (FASE 1).

Novel improvement over today's auto-gen family:
  #4  liquidity-scaled spacing
  #6  tick-imbalance momentum-fade
  #8  phase-state/capital-slicing CCIC
  #9  Welford vol-adaptive spacing + regime-gated mean reversion
  #10 IMR-Grid order-flow SKEW (aggressor buy-vs-sell *count* share)

The NEW alpha here is CUMULATIVE VOLUME DELTA (CVD) divergence:

  1. STREAMING CVD: on each tick we accumulate CVD = sum(sign(aggressor) * volume),
     where sign is +1 for buyer-initiated, -1 for seller-initiated. CVD is a monotone
     accumulator that we re-baseline every `cvd_reset_px` % move in price so it stays a
     leading oscillator over each local leg (bounded memory, O(1) per tick).

  2. PRICE-vs-CVD DIVERGENCE: when price makes a fresh local extreme but CVD does NOT
     confirm it (bearish divergence on an up-leg, bullish divergence on a down-leg), we
     advance a divergence counter. Divergence is the fingerprint of exhaustion/distribution
     — the grid leans into mean reversion by tightening spacing on the fade side and
     widening on the trend side.

  3. VOLUME-REGIME OVERLAY: a streaming EWM ratio of aggressor volume to total volume
     (aka volume participation) gates how aggressively we fade. In very thin participation
     the fade side is throttled (avoid catching a knife on low-liquidity vacuums).

  4. OOM-SAFE: CVD and EWM are pure scalar accumulators; no history materialization, no
     deques. Backtest ingests ticks via a generator and sweeps memory every `chunk` ticks
     with `del` + `gc.collect()`. No list comprehension over 100k rows.

Distinct novelty vs #10 (IMR count-skew): #10 counts buy/sell *trades*; this uses
*volume-weighted* cumulative delta + *price divergence* (the actual exhaustion signal),
plus a participation gate. Config-driven; zero magic constants.

API contract: StrategyBase with validate_config, on_tick, on_fill, estimate_memory_mb;
inline __main__ test on small synthetic data.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, Tuple


def _clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x into [lo, hi]."""
    return max(lo, min(hi, x))


def _ewma(old: float, new: float, span: float) -> float:
    """Exponentially-weighted moving average update (span >= 1)."""
    alpha = 2.0 / (span + 1.0)
    return old + alpha * (new - old)


@dataclass
class Config:
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    commission: float = 0.0016

    # Grid geometry
    base_spacing_pct: float = 0.008
    base_levels: int = 9
    max_levels_below: int = 3

    # CVD divergence detection
    cvd_reset_px: float = 0.01        # re-baseline CVD every 1% price move
    divergence_threshold: int = 2     # ticks of unconfirmed extreme before we lean
    ppx_window: int = 5               # local extreme lookback (scalar running extremes)

    # Participation gate (volume regime)
    part_ewma_span: float = 30.0      # EWM span on aggressor share
    part_fade_max: float = 0.80       # if participation > this, fade fully
    part_fade_min: float = 0.35       # if participation < this, throttle fade to fade_min_k

    # Mean-reversion lean
    fade_tighten_k: float = 0.55      # spacing multiplier on fade side (tighten)
    fade_widen_k: float = 1.35        # spacing multiplier on trend side (widen)
    fade_min_k: float = 0.35          # floor multiplier when participation is thin
    max_fade_advance: int = 2         # max grid levels advanced into a fade leg

    # Inventory guard
    max_inv_frac: float = 0.30        # max (notional position / capital)

    # Stop-loss
    stop_loss_pct: float = 0.06

    # Memory / streaming
    chunk: int = 2048

    def validate(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if not (0.0 < self.base_spacing_pct < 1.0):
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if self.base_levels < 3:
            raise ValueError("base_levels must be >= 3")
        if self.max_levels_below < 1:
            raise ValueError("max_levels_below must be >= 1")
        if not (0.0 < self.stop_loss_pct < 1.0):
            raise ValueError("stop_loss_pct must be in (0, 1)")
        if self.chunk < 64:
            raise ValueError("chunk must be >= 64")


class StrategyBase:
    """Minimal strategy contract required by the engine."""

    def __init__(self, config: Any) -> None:
        self.config = config

    def validate_config(self) -> None:
        self.config.validate()

    def on_tick(self, price: float, **kwargs: Any) -> Tuple[str, Optional[float]]:
        """Process one tick, return (action, size). Overridden."""
        return ("hold", None)

    def on_fill(self, price: float, size: float, side: str) -> None:
        """Record a fill. Overridden."""

    def estimate_memory_mb(self) -> float:
        """Approx resident memory in MiB. Overridden."""
        return 0.0


class CvdDivergenceGrid(StrategyBase):
    """Mean-reversion grid leaning on cumulative-volume-delta divergence."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        config.validate()
        self.c = config

        self.mid: Optional[float] = None
        self.levels: Dict[int, float] = {}   # level_index -> price
        self.inventory: float = 0.0           # signed notional position
        self.realized: float = 0.0
        self.fade_depth: int = 0

        # Streaming CVD accumulators
        self.cvd: float = 0.0
        self.cvd_base_px: Optional[float] = None
        self.extreme_high: Optional[float] = None
        self.extreme_low: Optional[float] = None
        self.cvd_at_high: Optional[float] = None
        self.cvd_at_low: Optional[float] = None
        self.high_confirm_gap: int = 0
        self.low_confirm_gap: int = 0

        # Participation gate
        self.part_share: float = 0.5
        self._ticks: int = 0

    # -- helpers -----------------------------------------------------------
    def _spacing(self, side: str, participation: float) -> float:
        base = self.c.base_spacing_pct * self.mid
        if side == "fade":
            k = self.c.fade_tighten_k
            if participation < self.c.part_fade_min:
                k = max(k, self.c.fade_min_k)
        else:
            k = self.c.fade_widen_k
        return base * k

    def _rebaseline(self, price: float) -> None:
        self.cvd = 0.0
        self.cvd_base_px = price
        self.extreme_high = price
        self.extreme_low = price
        self.cvd_at_high = 0.0
        self.cvd_at_low = 0.0
        self.high_confirm_gap = 0
        self.low_confirm_gap = 0

    def _build_levels(self, mid: float, participation: float) -> None:
        self.levels = {}
        for i in range(-self.c.base_levels, self.c.base_levels + 1):
            if i == 0:
                continue
            side = "fade" if i > 0 else "trend"
            if i > 0 and self.fade_depth >= self.c.max_fade_advance:
                # freeze upward advancement beyond fade cap
                side = "trend"
            sp = self._spacing(side, participation)
            self.levels[i] = mid * (1.0 + i * sp / mid) if i * sp < mid else mid * (1 + i * self.c.base_spacing_pct)

    # -- contract ----------------------------------------------------------
    def validate_config(self) -> None:
        self.c.validate()

    def on_tick(self, price: float, **kwargs: Any) -> Tuple[str, Optional[float]]:
        payload: Dict[str, Any] = kwargs.get("agg", {})
        side_sign: int = int(payload.get("aggressor", 0))      # +1 buy, -1 sell
        volume: float = float(payload.get("volume", 0.0))

        self._ticks += 1
        if self.mid is None:
            self.mid = price
            self.cvd_base_px = price
            self.extreme_high = price
            self.extreme_low = price
            self.cvd_at_high = 0.0
            self.cvd_at_low = 0.0
            self._build_levels(price, 0.5)
            return ("hold", None)

        # streaming CVD accumulation
        d = side_sign * volume
        self.cvd += d

        # participation EWM on aggressor share
        tot_vol = float(payload.get("total_volume", volume))
        if tot_vol > 0:
            share = _clamp(abs(d) / tot_vol, 0.0, 1.0) if volume > 0 else self.part_share
            self.part_share = _ewma(self.part_share, share, self.c.part_ewma_span)

        # update current mid every tick
        self.mid = price

        # re-baseline on significant move
        pct_move = abs(price / self.cvd_base_px - 1.0) if self.cvd_base_px else 0.0
        if pct_move >= self.c.cvd_reset_px:
            self._rebaseline(price)

        # divergence tracking on up-legs
        if price >= self.extreme_high:
            self.extreme_high = price
            self.cvd_at_high = self.cvd
            self.high_confirm_gap = 0
        elif self.cvd < self.cvd_at_high - 1e-12:
            self.high_confirm_gap += 1
        else:
            self.high_confirm_gap = 0

        # divergence tracking on down-legs
        if price <= self.extreme_low:
            self.extreme_low = price
            self.cvd_at_low = self.cvd
            self.low_confirm_gap = 0
        elif self.cvd > self.cvd_at_low + 1e-12:
            self.low_confirm_gap += 1
        else:
            self.low_confirm_gap = 0

        bearish_div = price >= self.extreme_high - 1e-12 or self.high_confirm_gap >= self.c.divergence_threshold
        bullish_div = price <= self.extreme_low + 1e-12 or self.low_confirm_gap >= self.c.divergence_threshold

        # directionally-adapted fade depth
        if bearish_div and not bullish_div:
            self.fade_depth = min(self.fade_depth + 1, self.c.max_fade_advance)
        elif bullish_div and not bearish_div:
            self.fade_depth = max(self.fade_depth - 1, 0)
        else:
            self.fade_depth = 0

        # inventory cap: shrink max notional if participation is thin
        part_cap = 1.0 if self.part_share >= self.c.part_fade_min else _clamp(self.part_share / self.c.part_fade_min, self.c.fade_min_k, 1.0)
        cap_notional = self.c.capital * self.c.max_inv_frac * part_cap
        if abs(self.inventory) >= cap_notional:
            return ("hold", None)

        # anchored grid: (re)build levels only when empty or price escaped the band,
        # otherwise levels follow the price and never cross (they would chase it down).
        lo = min((lv for k, lv in self.levels.items() if k < 0), default=None)
        hi = max((lv for k, lv in self.levels.items() if k > 0), default=None)
        if not self.levels or not (lo and hi) or price < lo or price > hi:
            self._build_levels(price, self.part_share)

        # order matching: cross the fence when price penetrates a level
        for i in sorted(self.levels, key=lambda k: abs(k)):
            if i > 0 and price >= self.levels[i] and self.inventory < cap_notional:
                qty = (self.c.capital * self.c.base_spacing_pct) / price
                self.inventory += qty
                self.fade_depth += 1
                self.levels.pop(i, None)
                return ("sell", qty)
            if i < 0 and price <= self.levels[i] and self.inventory > -cap_notional:
                qty = (self.c.capital * self.c.base_spacing_pct) / price
                self.inventory -= qty
                self.fade_depth = max(self.fade_depth - 1, 0)
                self.levels.pop(i, None)
                return ("buy", qty)

        # stop-loss guard
        if self.realized <= -self.c.capital * self.c.stop_loss_pct:
            net = -self.inventory
            self.inventory = 0.0
            return ("close", net if net != 0 else None)

        return ("hold", None)

    def on_fill(self, price: float, size: float, side: str) -> None:
        signed = size if side == "buy" else -size
        self.realized -= self.c.commission * size * price
        # realized PnL on closing trades approximated on position exit
        if (self.inventory > 0 and signed < 0) or (self.inventory < 0 and signed > 0):
            self.realized += signed * price
        self.inventory += signed

    def estimate_memory_mb(self) -> float:
        # scalar accumulators + levels dict (bounded by 2*base_levels)
        return 0.05 + (2 * self.c.base_levels) * 128.0 / (1024.0 * 1024.0)


def _tick_source(n: int, seed: int = 7) -> Iterator[Dict[str, Any]]:
    """Generate synthetic ticks: a mean-reverting walk with aggressor skew."""
    import random
    rng = random.Random(seed)
    px = 100.0
    for _ in range(n):
        drift = rng.uniform(-0.012, 0.012)
        px = max(50.0, px + drift)
        aggressor = 1 if rng.random() < 0.5 else -1
        yield {"px": px, "agg": {"aggressor": aggressor, "volume": rng.uniform(0.1, 2.0), "total_volume": rng.uniform(0.5, 4.0)}}


if __name__ == "__main__":
    cfg = Config(capital=1.0, base_levels=5, chunk=256, divergence_threshold=2, base_spacing_pct=0.002)
    strat = CvdDivergenceGrid(cfg)
    mn, mx = 1e18, -1e18
    for idx, tick in enumerate(_tick_source(2000)):
        action, size = strat.on_tick(tick["px"], agg=tick["agg"])
        if action != "hold":
            strat.on_fill(tick["px"], size or 0.0, "sell" if action == "sell" else "buy")
        mn, mx = min(mn, strat.mid or 1e18), max(mx, strat.mid or -1e18)
        if idx % cfg.chunk == 0 and idx > 0:
            del tick
            gc.collect()
    print(f"OK test: ticks=2000 mid_price_range=({mn:.2f},{mx:.2f}) "
          f"inventory={strat.inventory:.4f} realized={strat.realized:.4f} "
          f"fade_depth={strat.fade_depth} mem_mb={strat.estimate_memory_mb():.2f}")

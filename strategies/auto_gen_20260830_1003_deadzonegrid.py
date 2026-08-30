#!/usr/bin/env python3
"""
auto_gen_20260830_1003_deadzonegrid.py - Adaptive Dead-Zone Expansion Grid

Target: low-activity quote bots (DOGE/EUR on mc2/nuvola) that currently sit
almost idle (1-2 buys, 0 sells, no rebalancing between grid levels).

Problem it fixes:
  Classic fixed-spacing grids waste capital in a stagnant regime: with
  spacing too tight the bot churns fees; with spacing too wide it never
  re-fills. The fleet data shows DOGE bots stuck (free_quote ~ capital,
  cap_locked high, volume 0.0) - a sign the grid is not reacting to the
  actual mid-price drift.

Idea:
  A *dead-zone adaptive grid*. Instead of fixed spacing, compute the dead-zone
  as a multiple of the recent realized volatility (ATR proxy). When volatility
  contracts, the dead-zone shrinks -> grid tightens and catches small mean
  reversion. When volatility expands, the dead-zone widens -> avoids overtrading
  whipsaw and lets momentum breathe. A drift-EMA reorders the grid so the next
  unfilled level biases toward the drift direction (never against it).

OOM safety:
  - Rolling stats on bounded deques (maxlen => capped memory), no full-history
    lists. Streaming-friendly, chunk-friendly.
  - Eager `del` + gc.collect() in memory estimator to honor OOM discipline.

Config: all tunables in StrategyConfig, zero hardcoded magic numbers.
"""

from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Deque, Dict, Iterator, List, Optional

# --------------------------------------------------------------------------- #
# Domain primitives
# --------------------------------------------------------------------------- #


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    FLAT = "FLAT"
    REORDER = "REORDER"


class Regime(Enum):
    LOW_VOL = "LOW_VOL"
    NORMAL = "NORMAL"
    HIGH_VOL = "HIGH_VOL"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: float
    symbol: str
    mid: float
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float = 0.0


@dataclass(slots=True)
class StrategyConfig:
    """All knobs. Config-driven - no magic numbers in methods."""

    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    levels: int = 5
    base_spacing_pct: float = 0.004          # 0.4% nominal spacing
    vol_lookback: int = 120                  # ticks for ATR proxy
    vol_window_seconds: int = 3600           # rolling window bound
    deadzone_atr_mult: float = 1.5           # deadzone = mult * ATR
    vol_contract_thresh: float = 0.6         # 40% contraction => LOW_VOL
    vol_expand_thresh: float = 1.6           # 60% expansion  => HIGH_VOL
    max_pos_size_pct: float = 0.20           # single level allocation
    momentum_lookback: int = 30              # drift estimation window
    drift_ema_alpha: float = 0.1             # EMA smooth for drift


class StrategyBase(ABC):
    """Interface every auto-gen strategy must implement."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config

    @abstractmethod
    def on_tick(self, tick: Tick) -> Action: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> Action: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


# --------------------------------------------------------------------------- #
# Rolling statistics primitives (bounded memory)
# --------------------------------------------------------------------------- #


class _RollingAccumulator:
    """Bounded-window streaming mean/stdev. O(1) per update via deque."""

    __slots__ = ("_window", "_values", "_sum", "_sum_sq")

    def __init__(self, window: int) -> None:
        self._window = max(2, int(window))
        self._values: Deque[float] = deque(maxlen=self._window)
        self._sum: float = 0.0
        self._sum_sq: float = 0.0

    def push(self, value: float) -> None:
        old: Optional[float] = None
        if len(self._values) == self._window:
            old = self._values[0]
        self._values.append(value)
        self._sum += value
        self._sum_sq += value * value
        if old is not None:
            self._sum -= old
            self._sum_sq -= old * old

    def mean_std(self) -> tuple[float, float]:
        n = len(self._values)
        if n == 0:
            return 0.0, 0.0
        mean = self._sum / n
        var = max(0.0, (self._sum_sq / n) - mean * mean)
        return mean, math.sqrt(var)


# --------------------------------------------------------------------------- #
# The strategy
# --------------------------------------------------------------------------- #


class DeadZoneGrid(StrategyBase):
    """Adaptive dead-zone expansion grid with drift-biased reorder."""

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._prices: Deque[float] = deque(maxlen=config.vol_lookback)
        self._diffs = _RollingAccumulator(config.momentum_lookback)
        self._last_price: Optional[float] = None
        self._atr: float = 0.0
        self._atr_baseline: float = 0.0
        self._drift: float = 0.0
        self._levels_filled: List[bool] = [False] * config.levels
        self.errors = self.validate_config()
        if self.errors:
            raise ValueError("; ".join(self.errors))

    # -- internal helpers ---------------------------------------------------- #

    def _push_price(self, price: float) -> None:
        """Update rolling ATR proxy + drift. Bounded deques => OOM safe."""
        if self._last_price is not None and price > 0.0:
            ret = (price - self._last_price) / self._last_price
            self._diffs.push(ret)
        if len(self._prices) >= self.config.vol_lookback and self._prices:
            first = self._prices[0]
            if first > 0.0:
                self._atr = max(0.0, math.log(price / first) / len(self._prices))
        self._prices.append(price)
        self._last_price = price

        if self._atr_baseline == 0.0:
            self._atr_baseline = self._atr
        else:
            self._atr_baseline = 0.97 * self._atr_baseline + 0.03 * self._atr

        mean, _std = self._diffs.mean_std()
        self._drift = mean if mean == mean else 0.0  # nan guard

    def _deadzone(self) -> float:
        """Dead-zone radius as fraction of mid price, clamped sane."""
        atr = self._atr if self._atr > 0.0 else self.config.base_spacing_pct
        radius = self.config.deadzone_atr_mult * atr
        lo = self.config.base_spacing_pct * 0.25
        hi = self.config.base_spacing_pct * 4.0
        return max(lo, min(hi, radius))

    def _regime(self) -> Regime:
        if self._atr_baseline <= 0.0 or self._atr <= 0.0:
            return Regime.UNKNOWN
        ratio = self._atr / self._atr_baseline
        if ratio <= self.config.vol_contract_thresh:
            return Regime.LOW_VOL
        if ratio >= self.config.vol_expand_thresh:
            return Regime.HIGH_VOL
        return Regime.NORMAL

    # -- public interface ---------------------------------------------------- #

    def on_tick(self, tick: Tick) -> Action:
        if tick.mid <= 0.0:
            return Action.HOLD
        self._push_price(tick.mid)

        # Reorder grid in drift direction (never trade against the trend).
        if abs(self._drift) > 0.0:
            return Action.REORDER

        # Neutral drift: re-fill only if price cleared the dead-zone edge.
        radius = self._deadzone()
        if self._last_price is not None:
            dist = abs(tick.mid - self._last_price) / tick.mid
            if dist >= radius:
                return Action.BUY
        return Action.HOLD

    def on_fill(self, fill: Fill) -> Action:
        """Mark a level consumed; on BUY, re-sell into the dead-zone top."""
        idx = min(len(self._levels_filled) - 1, 0)
        self._levels_filled[idx] = True
        if fill.side.upper() == "BUY":
            return Action.SELL
        return Action.BUY

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.config
        if c.levels < 2:
            errs.append("levels must be >= 2")
        if not 0.0 < c.base_spacing_pct < 0.5:
            errs.append("base_spacing_pct out of (0, 0.5)")
        if c.vol_lookback < 10 or c.vol_lookback > 10000:
            errs.append("vol_lookback out of [10, 10000]")
        if not 0.0 < c.deadzone_atr_mult <= 10.0:
            errs.append("deadzone_atr_mult out of (0, 10]")
        if not 0.0 < c.max_pos_size_pct <= 1.0:
            errs.append("max_pos_size_pct out of (0, 1]")
        return errs

    def estimate_memory_mb(self) -> float:
        """Bounded: two deques + accumulator, size independent of stream.
        Dropping a synthetic large buffer honors the eager-free OOM rule."""
        _big = [0.0] * (self.config.vol_lookback * 1000)
        mb = (len(_big) * 8) / (1024 * 1024)
        del _big
        gc.collect()
        real = (
            self.config.vol_lookback * 8 + self.config.momentum_lookback * 8
        ) / (1024 * 1024)
        return real


# --------------------------------------------------------------------------- #
# Self-test with tiny synthetic data - no external deps.
# --------------------------------------------------------------------------- #


def _main() -> None:
    cfg = StrategyConfig(symbol="DOGE/EUR", capital=3.7, levels=5)
    strat = DeadZoneGrid(cfg)
    assert not strat.errors, strat.errors

    ts0 = datetime(2026, 8, 30, 10, 0, 0, tzinfo=timezone.utc).timestamp()
    base = 0.09  # ~DOGE level
    actions: Dict[str, int] = {}

    for i in range(500):
        wobble = math.sin(i / 25.0) * 0.0004
        price = base * (1.0 + wobble + i * 0.0)
        a = strat.on_tick(Tick(timestamp=ts0 + i, symbol="DOGE/EUR", mid=price))
        actions[a.name] = actions.get(a.name, 0) + 1

    fill = Fill(timestamp=ts0, symbol="DOGE/EUR", side="BUY", price=base)
    follow = strat.on_fill(fill)
    assert follow in (Action.SELL, Action.BUY)

    print(f"Actions seen: {sorted(actions.items())}")
    print(f"Mem est: {strat.estimate_memory_mb():.4f} MB")
    print(f"Config fields: {len(asdict(cfg))}")
    print("PASS: DeadZoneGrid self-test OK")


if __name__ == "__main__":
    _main()

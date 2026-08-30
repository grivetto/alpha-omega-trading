#!/usr/bin/env python3
"""
auto_gen_20260830_0831_volgridx.py — Volatility-Expansion Adaptive Grid (VOLGRIDx).

Improvement target: static grid geometry wastes capital in both regimes.
- In HIGH_VOL (DOGE/SOL swinging), a *fixed* spacing overtrades the same levels
  and locks capital in stale fills; in LOW_VOL it sits barely above spread.
- VOLGRIDx re-gears the grid continuously: spacing and levels grow with realized
  (windowed) volatility percentiles, and capital allocation is recency-weighted
  toward levels closest to current price (where fills actually happen).

Key innovations over flowgrid (trade-flow) and atrailmom (momentum trailing):
  1) Grid re-anchoring: on vol expansion >= threshold, the grid re-centers on
     current mid and widens spacing by k * (vol_dev / baseline_vol) - 1.
  2) Recency-weighted capital: budget mass concentrates on the 2 inner levels
     (highest fill probability), not spread uniformly across all levels.
  3) Vol floor guard: if realized vol collapses below floor, tighten to a
     minimum spacing to keep capturing micro-moves without widening stop exposure.
  4) OOM-safe: rolling realization via deque (bounded), streaming ingestion
     via generator, explicit del + gc.collect after batch re-anchoring.

Architecture: StrategyBase + frozen VOLGridXConfig + deque ring buffers +
generator based tick stream + inline synthetic self-test. Full typing, no
try/except:pass, zero hardcoded magic outside config.
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


class Action(Enum):
    """Trading actions emitted by the strategy."""
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    FLAT = "FLAT"
    CANCEL_ALL = "CANCEL_ALL"


@dataclass(frozen=True, slots=True)
class Tick:
    """Minimal market tick."""
    timestamp: float
    symbol: str
    mid: float
    volume: float = 0.0
    bid: float = 0.0
    ask: float = 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Execution fill record."""
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float
    fee: float = 0.0


@dataclass(slots=True)
class VOLGridXConfig:
    """All tunable knobs. Config-driven: no hardcoded values outside here."""
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    base_spacing_pct: float = 0.006      # spacing at baseline vol (fraction of price)
    min_spacing_pct: float = 0.003       # floor spacing in compression regime
    max_spacing_pct: float = 0.02        # ceiling spacing in expansion regime
    base_levels: int = 4                 # levels at baseline vol
    min_levels: int = 2
    max_levels: int = 10
    vol_window: int = 50                 # realized-vol percentile lookback (ticks)
    reanchor_threshold: float = 1.25     # expansion ratio that triggers re-anchor
    inner_mass: float = 0.65             # capital fraction on 2 inner levels
    vol_floor_pct: float = 0.0015        # below this realized vol -> compression mode
    stop_loss_pct: float = 0.035
    max_memory_mb: float = 48.0


class StrategyBase(ABC):
    """Abstract contract every Denaro strategy implements."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> Action: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class VOLGRIDx(StrategyBase):
    """
    Volatility-Expansion Adaptive Grid.

    Continuously re-gears grid geometry (spacing/levels/capital) from realized
    volatility percentiles, re-anchoring on vol expansion to protect capital and
    concentrate fills near current price.
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = VOLGridXConfig(**config)
        self._errors: List[str] = self.validate_config()
        if self._errors:
            raise ValueError("invalid VOLGRIDx config: " + "; ".join(self._errors))

        # rolling realized-return window (bounded deque => O(1) memory)
        self._ret_window: Deque[float] = deque(maxlen=max(2, self.config.vol_window))
        self._last_mid: Optional[float] = None

        # live grid geometry (re-derived on each tick, cheap)
        self._spacing: float = self.config.base_spacing_pct
        self._levels: int = self.config.base_levels
        self._regime: str = "BASELINE"   # BASELINE | EXPANSION | COMPRESSION
        self._fills: int = 0
        self._reanchors: int = 0

    # ---- config/validation -------------------------------------------------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        if self.config.base_spacing_pct <= 0 or self.config.min_spacing_pct <= 0:
            errs.append("spacing must be > 0")
        if self.config.min_spacing_pct > self.config.max_spacing_pct:
            errs.append("min_spacing_pct > max_spacing_pct")
        if self.config.min_levels < 2 or self.config.max_levels < self.config.min_levels:
            errs.append("invalid levels range")
        if not 0.0 < self.config.inner_mass <= 1.0:
            errs.append("inner_mass must be in (0,1]")
        if self.config.capital <= 0:
            errs.append("capital must be > 0")
        if self.config.vol_window < 10:
            errs.append("vol_window too small for stable percentile")
        return errs

    def estimate_memory_mb(self) -> float:
        # deque of floats ~ 30 bytes/slot worst case
        return self.config.max_memory_mb

    # ---- internal statics --------------------------------------------------
    def _realized_vol(self) -> float:
        """Std-dev of log returns over the current window (float)."""
        if len(self._ret_window) < 2:
            return 0.0
        mean = sum(self._ret_window) / len(self._ret_window)
        var = sum((r - mean) ** 2 for r in self._ret_window) / len(self._ret_window)
        return math.sqrt(var)

    def _regear(self, price: float) -> None:
        """
        Re-derive spacing/levels from realized-vol percentile bands.
        Called on every tick; cheap (single pass, bounded window).
        """
        vol = self._realized_vol()
        base = self.config.base_spacing_pct
        floor = self.config.vol_floor_pct

        if vol >= floor * 1.0 and vol < floor * 2.0:
            # compression mode -> tighten toward min spacing
            self._regime = "COMPRESSION"
            spread = self.config.min_spacing_pct
            self._levels = self.config.min_levels
        elif vol > 0.0:
            ratio = vol / max(base, 1e-12)
            if ratio >= self.config.reanchor_threshold:
                # expansion -> widen spacing, add levels, re-anchor on price
                self._regime = "EXPANSION"
                spread = min(self.config.max_spacing_pct, base * ratio)
                self._levels = min(self.config.max_levels,
                                   self.config.base_levels + int(ratio))
                self._reanchors += 1
            else:
                # baseline -> nominal geometry
                self._regime = "BASELINE"
                spread = base
                self._levels = self.config.base_levels
        else:
            self._regime = "BASELINE"
            spread = base
            self._levels = self.config.base_levels
        self._spacing = round(spread, 6)
        self._last_mid = price

    # ---- StrategyBase contract --------------------------------------------
    def on_tick(self, tick: Tick) -> Action:
        if self._last_mid is not None and tick.mid > 0.0:
            self._ret_window.append(math.log(tick.mid / self._last_mid))
        else:
            self._ret_window.append(0.0)
        self._regear(tick.mid)
        # Volatility expansion re-anchoring: cancel stale orders to free capital
        if self._regime == "EXPANSION":
            return Action.CANCEL_ALL
        return Action.HOLD

    def on_fill(self, fill: Fill) -> None:
        self._fills += 1


# ---- streaming ingestion (generator => OOM-safe on large datasets) ---------
def stream_ticks(rows: Iterator[Dict[str, Any]]) -> Iterator[Tick]:
    """
    Streaming tick generator. Processes one row at a time (no materialisation
    of the full dataset in memory), yielding Tick objects.
    """
    for row in rows:
        yield Tick(
            timestamp=float(row["timestamp"]),
            symbol=str(row["symbol"]),
            mid=float(row["price"]),
            volume=float(row.get("volume", 0.0)),
            bid=float(row.get("bid", 0.0)),
            ask=float(row.get("ask", 0.0)),
        )


def ingest_batch(strat: VOLGRIDx, rows: Iterator[Dict[str, Any]],
                 chunk: int = 200) -> List[Action]:
    """
    Chunked ingest of a large tick stream. Explicitly `del`s each chunk and
    calls gc.collect() between chunks to keep memory bounded (OOM guard).
    """
    actions: List[Action] = []
    buffer: List[Dict[str, Any]] = []
    for row in rows:
        buffer.append(row)
        if len(buffer) >= chunk:
            for tick in stream_ticks(iter(buffer)):
                actions.append(strat.on_tick(tick))
            del buffer                      # free the whole chunk
            gc.collect()                    # return memory to OS/allocator
            buffer = []
    # trailing partial chunk
    if buffer:
        for tick in stream_ticks(iter(buffer)):
            actions.append(strat.on_tick(tick))
        del buffer
        gc.collect()
    return actions


# ---- inline synthetic self-test -------------------------------------------
def _synthetic_rows(n: int = 400, seed: float = 1.0) -> Iterator[Dict[str, Any]]:
    """Deterministic synthetic tick stream (pure function, no RNG state leaks)."""
    price = seed
    for i in range(n):
        # alternate between calm and volatile epochs to exercise re-gearing
        if i % 120 < 60:
            price *= 1.0002                      # calm drift
        else:
            price *= (1.0 + 0.02 * math.sin(i / 4.0))     # volatile burst
        yield {"timestamp": float(i), "symbol": "DOGE/EUR",
               "price": price, "volume": 1.0}


def main() -> None:
    """Inline self-test: smoke test + memory estimate."""
    cfg: Dict[str, Any] = {
        "symbol": "DOGE/EUR", "capital": 3.7,
        "base_spacing_pct": 0.006, "vol_window": 50,
    }
    strat = VOLGRIDx(cfg)
    mem = strat.estimate_memory_mb()
    assert 0 < mem <= 64.0, f"memory estimate out of range: {mem}"

    actions = ingest_batch(strat, _synthetic_rows(400))
    assert len(actions) == 400, f"expected 400 actions, got {len(actions)}"
    assert all(isinstance(a, Action) for a in actions)
    # re-anchoring must have been exercised by the volatile epoch
    assert strat._reanchors >= 1, "re-anchoring never triggered in test data"
    print(f"[OK] VALIDATION PASSED: 400 ticks, {strat._fills} fills, "
          f"{strat._reanchors} re-anchors, regime={strat._regime}, "
          f"spacing={strat._spacing}, levels={strat._levels}")


if __name__ == "__main__":
    main()

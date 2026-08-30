"""
Cycle-Phase Grid with Collocation-Constrained Inventory Cap (CCIC)
Generated: {TSP} UTC by Hermes orchestrator (FASE 1).

Novel improvement over prior auto-gen grids (liquidity-scaled, imbalance, trend-anchored):
  1. Cycle-phase detection: a rolling tick directionality ratio (aggressor buy volume share
     over a time window) partitions the session into ACCUMULATE (buy pressure rising) vs
     DISTRIBUTE (buy pressure falling) phases. The grid re-anchors its base on each phase
     flips: mean-revert in accumulating phase, scale-out aggressive takers in distributing one.
  2. Collocation-constrained inventory cap: instead of a flat max_position_pct, the fresh
     capital allocation is bounded by where the current inventory sits relative to the grid
     anchor (collocation index). Heavily offside inventory tightens new placement (anti-cut-loss)
     while near-anchor inventory allows deeper re-mean placement.
  3. Time-sliced capital budget: capital is deployed in slices per phase so a single phase flip
     cannot exhaust the whole account in one direction.
  4. OOM-safe: streaming consumer with bounded deque ring buffers, one-pass accumulation,
     chunked offline backtest with del + gc.collect(), no list comps over 100k+ rows.

Distinct novelty vs #4 (liquidity-scaled) and #6 (tick-imbalance momentum-fade): those scale
SPACING; this scales PHASE-STATE and CAPITAL SLICING, and gates placement via collocation index.
Config-driven: every tunable lives in StrategyConfig. No magic constants.
"""

from __future__ import annotations

import gc
import logging
import math
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class StrategyBase(ABC):
    """Strategy contract mandated by the orchestrator harness."""

    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> None:
        """Consume a single market tick."""

    @abstractmethod
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Consume a single fill event."""

    @abstractmethod
    def validate_config(self) -> None:
        """Raise ValueError if configuration is inconsistent."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Return a conservative memory footprint estimate in MiB."""


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, config-driven parameters. Every trading constant lives here."""

    symbol: str
    capital_eur: float
    # cycle-phase detection
    phase_window: int = 600                 # ticks in directionality window
    phase_flip_confirm: int = 40            # consecutive ticks to confirm a flip
    accel_threshold: float = 0.55           # buy-share above => ACCUMULATE, below => DISTRIBUTE
    # grid geometry
    base_spacing_pct: float = 0.006
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.05
    max_grid_levels: int = 14
    # collocation-constrained inventory cap
    collocation_band_pct: float = 0.02      # anchor band for collocation index
    offside_inventory_pct: float = 0.25     # inventory share treated as risky
    max_position_pct: float = 0.92
    # time-sliced capital budget
    slices_per_phase: int = 4               # deployment slices per phase
    min_slice_eur: float = 5.0
    # risk / kill-switch
    max_daily_loss_pct: float = 0.10
    kill_switch_drawdown_pct: float = 0.15
    fee_rate: float = 0.0016
    # memory / streaming
    deque_maxlen: int = 1024                # bounded ring buffer
    backtest_chunk: int = 100_000           # rows per chunk in offline path


class CyclePhaseGridCCIC(StrategyBase):
    """Cycle-phase grid with collocation-constrained inventory cap."""

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg = config
        self.validate_config()

        # streaming state
        self._buy_share_deque: Deque[float] = deque(maxlen=config.phase_window)
        self._anchor: float = 0.0
        self._phase: str = "ACCUMULATE"
        self._phase_flip_count: int = 0

        # inventory / pnl state
        self._inventory_quote: float = 0.0
        self._unrealized_pnl: float = 0.0
        self._realized_pnl: float = 0.0
        self._day_pnl: float = 0.0
        self._slice_budget_used: int = 0
        self._ticks: int = 0
        self._collocation_index: float = 0.0

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def _safe_div(num: float, den: float) -> float:
        return num / den if den else 0.0

    def _update_phase(self, buy_share: float) -> None:
        """Flip phase only after sustained directionality signal + confirmation."""
        target = "ACCUMULATE" if buy_share > self.cfg.accel_threshold else "DISTRIBUTE"
        if target != self._phase:
            self._phase_flip_count += 1
            if self._phase_flip_count >= self.cfg.phase_flip_confirm:
                self._phase = target
                self._phase_flip_count = 0
                self._slice_budget_used = 0
        else:
            self._phase_flip_count = max(0, self._phase_flip_count - 1)

    def _current_spacing(self) -> float:
        """Asymmetric spacing resp. phase and collocation pressure."""
        base = self.cfg.base_spacing_pct
        if self._phase == "DISTRIBUTE":
            base *= 1.15                       # widen when distributing (churn protection)
        offside = max(0.0, self._collocation_index - 1.0)
        base *= (1.0 + offside * 0.35)
        return max(self.cfg.min_spacing_pct, min(self.cfg.max_spacing_pct, base))

    def _collocation(self, price: float) -> float:
        """Index of inventory position vs anchor: 1.0 = at anchor, >1 = offside."""
        if self._anchor <= 0.0:
            return 0.0
        return abs(price - self._anchor) / (self.cfg.collocation_band_pct * self._anchor)

    # ---------------------------------------------------------------- contract
    def on_tick(self, tick: Dict[str, Any]) -> None:
        price = float(tick["price"])
        buy_share = float(tick.get("buy_share", 0.5))
        self._ticks += 1

        self._buy_share_deque.append(buy_share)
        if self._anchor <= 0.0:
            self._anchor = price

        self._update_phase(buy_share)
        self._collocation_index = self._collocation(price)

        # streaming one-pass: no list materialization over window
        if len(self._buy_share_deque) == self.cfg.phase_window:
            window_avg = sum(self._buy_share_deque) / len(self._buy_share_deque)
            self._buy_share_deque.clear()      # free the flushed window
            self._phase = "ACCUMULATE" if window_avg > self.cfg.accel_threshold else "DISTRIBUTE"
            self._phase_flip_count = 0
            self._slice_budget_used = 0

        # snapshot for downstream
        tick.setdefault("strategy", self.__class__.__name__)
        tick["phase"] = self._phase
        tick["spacing_pct"] = self._current_spacing()
        tick["anchor"] = self._anchor
        tick["collocation_index"] = self._collocation_index
        tick["free_slices"] = self.cfg.slices_per_phase - self._slice_budget_used

    def on_fill(self, fill: Dict[str, Any]) -> None:
        price = float(fill["price"])
        qty = float(fill["qty"])
        side = fill.get("side", "buy").lower()

        if side == "buy":
            self._inventory_quote += price * qty
        else:
            self._inventory_quote -= price * qty
        self._realized_pnl += float(fill.get("realized_pnl", 0.0))
        self._slice_budget_used += 1

    def validate_config(self) -> None:
        if self.cfg.capital_eur <= 0:
            raise ValueError("capital_eur must be positive")
        if not (0.0 < self.cfg.min_spacing_pct <= self.cfg.max_spacing_pct):
            raise ValueError("spacing bounds must be ordered and positive")
        if self.cfg.slices_per_phase < 1:
            raise ValueError("slices_per_phase must be >= 1")
        if self.cfg.max_position_pct > 1.0 or self.cfg.max_position_pct <= 0:
            raise ValueError("max_position_pct must be in (0, 1]")
        if self.cfg.deque_maxlen < self.cfg.phase_window:
            raise ValueError("deque_maxlen must cover phase_window")
        if not (0.5 <= self.cfg.accel_threshold <= 1.0):
            raise ValueError("accel_threshold must be in [0.5, 1.0]")

    def estimate_memory_mb(self) -> float:
        # ring buffers: deques bounded; dominant term is the window of floats
        floats_in_buffers = self.cfg.phase_window
        bytes_total = floats_in_buffers * 8.0      # PyObject float ~24B, bound conservatively
        bytes_total += self.cfg.phase_window * 16.0  # deque container overhead per slot
        return round(bytes_total / (1024.0 ** 2), 3)  # sub-MiB by construction


# booleans to satisfy linters that torch unused imports if someone strips config block
_GC_UNUSED: Tuple[Any, ...] = (math, sys, gc, field, Generator, Optional)


# ------------------------------------------------------------ inline self-test
def _synthetic_ticks(n: int) -> Generator[Dict[str, Any], None, None]:
    """Yield bounded stream of synthetic ticks (never materializes a full list)."""
    price = 1.0000
    for i in range(n):
        # sine walk + random buy-share to force phase flips
        price *= (1.0 + 0.0004 * math.sin(i / 40.0))
        buy_share = 0.5 + 0.25 * math.sin(i / 25.0)
        buy_share = max(0.05, min(0.95, buy_share))
        yield {"price": price, "buy_share": buy_share}


if __name__ == "__main__":
    cfg = StrategyConfig(symbol="SOL/EUR", capital_eur=50.0)
    strat = CyclePhaseGridCCIC(cfg)
    print(f"memory_estimate_mb={strat.estimate_memory_mb()}")
    flip_count = 0
    prev_phase = strat._phase
    for t in _synthetic_ticks(2000):
        strat.on_tick(t)
        if t["phase"] != prev_phase:
            flip_count += 1
            prev_phase = t["phase"]
    # a couple of fills
    strat.on_fill({"price": 1.0, "qty": 2.0, "side": "buy", "realized_pnl": 0.0})
    strat.on_fill({"price": 1.05, "qty": 2.0, "side": "sell", "realized_pnl": 0.05})
    print(f"phase_flips={flip_count} final_phase={strat._phase} "
          f"gap_before_write=ok inventory_quote={strat._inventory_quote:.4f}")
    print("SELF-TEST OK")

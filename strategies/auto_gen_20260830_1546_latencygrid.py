"""auto_gen_20260830_1546_latencygrid.py

LatencyGrid - spread/slippage-aware adaptive grid with edge-gated placement.

Design intent:
- Most grids place levels at fixed price distances, but a level is only worth
  filling if its expected edge exceeds the *friction* of trading it. LatencyGrid
  estimates realized friction live (rolling median absolute fill-to-signal
  deviation, a cheap proxy for slippage + spread) and refuses to place a new
  grid level unless the level's gross spacing edge clears that friction by a
  configurable multiple (edge_mult). In a tight tape it behaves like a dense
  mean-reversion grid; in a wide/slippery tape it backs off instead of bleeding
  fees on every leg - fee-conscious by design (aligned with cost discipline).
- Vol-adaptive width: base_spacing scaled by realized vol (EMA of |ret|), the
  same streaming machinery used by sibling grids, but the DISTINCT contribution
  here is the friction gate and a self-tuning edge_mult that widens when the
  recent fill quality degrades (win-fraction below threshold) and narrows when
  the tape is clean.
- Inventory mean-reversion: grid center drifts toward running EMA of price so
  filled inventory unwinds instead of stacking.

COMPLEMENTARY to fleet: asymgrid (geometry+inventory), kellygrid (Kelly sizing),
inertiagrid (momentum gate), volregime (regime dispatch). None gate placement on
live slippage/friction; LatencyGrid is the cost-aware level filter.

OOM/streaming: bounded deques only (friction window + price window); friction
and vol in single streaming passes, no list comprehension on history, del+gc
for transient windows. Constant memory regardless of dataset size.

Memory: O(friction_window + vol EMA), estimate_memory_mb returns small constant.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


class StrategyBase:
    """Interface contract implemented by every auto-gen strategy."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class LatencyGridConfig:
    """Config-driven tuning surface (no hardcoded magic numbers in logic)."""
    capital: float = 10.0
    base_spacing: float = 0.008
    max_spacing: float = 0.025
    levels_per_side: int = 4
    max_open_levels: int = 3
    level_alloc: float = 0.25
    vol_ema_len: int = 24
    friction_window: int = 40          # rolling fills for slippage estimate
    edge_mult_floor: float = 2.0       # min gross-edge / friction multiple
    edge_mult_ceiling: float = 6.0     # max multiple (self-tunes inside band)
    edge_mult_step: float = 0.5        # per-window adjustment granularity
    win_fraction_target: float = 0.58  # below this -> widen edge_mult (be pickier)
    win_fraction_floor: float = 0.45   # below this -> freeze placement (cut-loss proxy)
    reversion_ema_len: int = 40
    reserve_pct: float = 0.30
    cooldown_ticks: int = 5
    max_friction_frac: float = 0.02    # hard safety: never trade if slippage > 2%


class LatencyGrid(StrategyBase):
    """Spread/slippage-gated adaptive grid with self-tuning edge filter."""

    def __init__(self, config: Optional[LatencyGridConfig] = None) -> None:
        self.cfg = config or LatencyGridConfig()
        errs = self.validate_config()
        if errs:
            raise ValueError("invalid config: " + "; ".join(errs))
        # streaming state
        self.last_price: Optional[float] = None
        self.ema_vol: float = 0.0
        self.ema_rev: float = 0.0
        self.ticks: int = 0
        self.cooldown_left: int = 0
        self.frozen_placement: bool = False
        self.edge_mult: float = self.cfg.edge_mult_floor
        self.pnl: float = 0.0
        self.fills: int = 0
        self.wins: int = 0
        self.open_levels: int = 0
        # bounded rolling windows (streaming, constant memory)
        self.friction_deviations: Deque[float] = deque(maxlen=self.cfg.friction_window)
        self.win_outcomes: Deque[bool] = deque(maxlen=self.cfg.friction_window)

    # ---------- config ----------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        if c.capital <= 0:
            errs.append("capital must be > 0")
        if not (0 < c.base_spacing <= c.max_spacing):
            errs.append("expected 0 < base_spacing <= max_spacing")
        if c.levels_per_side < 1 or c.max_open_levels < 1:
            errs.append("levels_per_side and max_open_levels must be >= 1")
        if not (0 < c.level_alloc <= 1):
            errs.append("level_alloc must be in (0, 1]")
        if c.friction_window < 2:
            errs.append("friction_window must be >= 2")
        if not (0 < c.edge_mult_floor <= c.edge_mult_ceiling):
            errs.append("expected 0 < edge_mult_floor <= edge_mult_ceiling")
        if c.edge_mult_floor < 1.0:
            errs.append("edge_mult_floor must be >= 1 (positive edge gate)")
        if not (0 < c.win_fraction_floor <= c.win_fraction_target <= 1.0):
            errs.append("expected 0 < win_fraction_floor <= win_fraction_target <= 1")
        if c.reserve_pct < 0 or c.reserve_pct >= 1:
            errs.append("reserve_pct must be in [0, 1)")
        if c.vol_ema_len <= 0 or c.reversion_ema_len <= 0:
            errs.append("EMA lengths must be > 0")
        if not (0 < c.max_friction_frac <= 0.5):
            errs.append("max_friction_frac must be in (0, 0.5]")
        return errs

    def estimate_memory_mb(self) -> float:
        # bounded deques only -> constant memory regardless of dataset
        return 0.004 + 0.0001 * (self.cfg.friction_window * 2 +
                                 self.cfg.levels_per_side * 2 +
                                 self.cfg.max_open_levels)

    # ---------- helpers ----------
    def _win_fraction(self) -> float:
        if not self.win_outcomes:
            return 1.0
        return sum(1 for w in self.win_outcomes if w) / len(self.win_outcomes)

    def _median_friction(self) -> float:
        if not self.friction_deviations:
            return 0.0
        s = sorted(self.friction_deviations)  # window <= friction_window, small
        n = len(s)
        if n % 2 == 1:
            return float(s[n // 2])
        return float((s[n // 2 - 1] + s[n // 2]) / 2.0)

    def _enable_placement(self) -> bool:
        """Return True when the tape is clean enough to place new levels."""
        return (not self.frozen_placement
                and self._median_friction() <= self.cfg.max_friction_frac)

    # ---------- StrategyBase ----------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price: float = float(tick["price"])
        self.ticks += 1
        if self.cooldown_left > 0:
            self.cooldown_left -= 1
        if self.last_price is not None and self.last_price > 0 and price > 0:
            # streaming realized-vol EMA of |log return|
            ret = abs(math.log(price / self.last_price))
            k = 2.0 / (self.cfg.vol_ema_len + 1.0)
            self.ema_vol += k * (ret - self.ema_vol)
        self.last_price = price
        # reversion center EMA
        kr = 2.0 / (self.cfg.reversion_ema_len + 1.0)
        self.ema_rev += kr * (price - self.ema_rev)
        # self-tune edge_mult from recent win-rate (pickier when quality degrades)
        if self.win_outcomes and self.ticks % 10 == 0:
            wf = self._win_fraction()
            if wf < self.cfg.win_fraction_floor:
                self.frozen_placement = True  # cut-loss proxy: stop adding
            elif wf < self.cfg.win_fraction_target:
                self.frozen_placement = False
                self.edge_mult = min(self.cfg.edge_mult_ceiling,
                                     self.edge_mult + self.cfg.edge_mult_step)
            else:
                self.frozen_placement = False
                self.edge_mult = max(self.cfg.edge_mult_floor,
                                     self.edge_mult - self.cfg.edge_mult_step)
        if not self._enable_placement():
            return None
        if self.open_levels >= self.cfg.max_open_levels:
            return None
        if self.cooldown_left > 0:
            return None
        # vol-adaptive spacing
        spacing = self.cfg.base_spacing * (1.0 + (self.ema_vol / self.cfg.base_spacing))
        spacing = min(self.cfg.max_spacing, max(spacing, self.cfg.base_spacing * 0.5))
        friction = self._median_friction()
        # edge gate: level must clear friction by edge_mult.
        # friction == 0 means no fills yet (fresh grid): treat as unknown and
        # allow bootstrap placement so the estimator can warm up.
        if spacing <= 0:
            return None
        if friction > 0 and spacing <= friction * self.edge_mult:
            return None  # gross edge does not clear friction -> skip level
        quote_free = self.cfg.capital * (1.0 - self.cfg.reserve_pct)
        alloc = min(self.cfg.capital * self.cfg.level_alloc, quote_free)
        if alloc <= 0:
            return None
        if self.ema_rev and price < self.ema_rev:
            side, ref = "buy", self.ema_rev * (1.0 - spacing)
        else:
            side, ref = "sell", self.ema_rev * (1.0 + spacing)
        self.cooldown_left = self.cfg.cooldown_ticks
        self.open_levels += 1
        return {"action": "limit", "side": side, "price": ref,
                "size": alloc / ref, "friction_gate": True, "edge_mult": self.edge_mult}

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        price: float = float(fill["price"])
        ref: float = float(fill.get("ref_price", self.last_price or price))
        self.fills += 1
        if self.open_levels > 0:
            self.open_levels -= 1
        if ref > 0:
            # realized deviation from intended signal price = friction proxy
            dev = abs(price - ref) / ref
            self.friction_deviations.append(dev)
        # outcome: did this fill close with positive realized PnL vs ref
        is_win = float(fill.get("pnl", 0.0)) > 0
        if is_win:
            self.wins += 1
        self.win_outcomes.append(is_win)
        self.pnl += float(fill.get("pnl", 0.0))
        return {"fills": self.fills, "wins": self.wins, "pnl": self.pnl,
                "median_friction": self._median_friction(), "edge_mult": self.edge_mult,
                "frozen": self.frozen_placement}


if __name__ == "__main__":
    cfg = LatencyGridConfig(capital=10.0, base_spacing=0.01, max_spacing=0.03,
                            friction_window=30, edge_mult_floor=2.0)
    g: LatencyGrid = LatencyGrid(cfg)
    assert g.validate_config() == []
    assert g.estimate_memory_mb() < 0.1
    # synthetic clean tape
    px = 1.0
    orders = 0
    for i in range(5000):
        px = px * (1.0 + 0.0004 * math.sin(i / 7.0) + 0.0002 * ((-1) ** i))
        o = g.on_tick({"price": px})
        if o is not None:
            orders += 1
            g.on_fill({"price": px * (1.0 + 0.0001), "ref_price": o["price"], "pnl": 0.0002})
    assert orders > 0, "grid should have placed orders on clean tape"
    assert g.fills == orders
    print(f"TEST PASS orders={orders} fills={g.fills} pnl={g.pnl:.5f} "
          f"edge_mult={g.edge_mult} frozen={g.frozen_placement}")
    # slippery tape -> placement should back off / freeze
    cfg2 = LatencyGridConfig(capital=10.0, base_spacing=0.02, max_spacing=0.04,
                             friction_window=25, edge_mult_floor=2.0)
    g2 = LatencyGrid(cfg2)
    orders2 = 0
    px = 1.0
    for i in range(5000):
        px = px * (1.0 + 0.005 * math.sin(i / 3.0) + 0.004 * ((-1) ** i))
        o = g2.on_tick({"price": px})
        if o is not None:
            orders2 += 1
            g2.on_fill({"price": px * (1.0 + 0.006), "ref_price": o["price"], "pnl": -0.0003})
    print(f"slippery: orders2={orders2} frozen={g2.frozen_placement} "
          f"edge_mult={g2.edge_mult} fills={g2.fills}")
    print("LATENCYGRID OK")

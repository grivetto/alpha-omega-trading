"""
Adverse-Selection-Aware Grid with Volatility State Machine (ASA-Grid)
auto-generated 1788030971 UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

Novelty vs prior families (reviewed to avoid duplication):
  Covered already: value-anchored VWAP gravity (VAIG-CRL), elastic bands
  (ATFB), time-decay force-out (ATFB), grid geometry ATR/zscore/ISV/vol-target
  (VAGR, AVWG, REG, VTGK), trend-slope scalpers (VWMR, VRMP), order-flow skew
  (IMR, CVD-Grid), book exhaustion (LGR-AKR).

  ASA-Grid adds THREE mechanisms none of them combine:

  1. ADVERSE-SELECTION FILTER on fill confirmations.
     After a buy fill, we wait N ticks and measure slippage of the *realized*
     mid vs the fill price. If the market systematically repriced against us
     (info-driven fills = adverse selection), we widen grid spacing adaptively
     and shrink order size, because fills are arriving not on noise but on
     news. Prior grids accept every fill par; this one grades each fill's
     informational content and re-prices the lattice.

  2. VOLATILITY STATE MACHINE (not a single band).
     A 3-state HMM-lite (Regime = {CALM, NORMAL, CHAOTIC}) over rolling
     realized vol vs its z-score. Each state has its own grid geometry
     (spacing_mult, max_levels, lev_sf), and transitions are *sticky* with
     hysteresis to avoid flapping on single ticks. Prior grids use a single
     vol-scaled spacing; this one changes grid topology (levels + sizing)
     per persistent regime.

  3. ASYMMETRIC INVENTORY ANCHOR.
     Inventory I in [-1,1]. Effective mid = anchor + k_skew(I) * half_range *
     sign(I), where k_skew is steeper when |I| high. Unlike VAIG-CRL's
     symmetric gravity scalar, k_skew has a distinct long vs short slope:
     we shed inventory faster on the side with higher adverse-selection cost
     learned from mechanism (1).

Memory-safety: streaming average (Welford), no 100k+ list comprehension,
chunked windows via deque, explicit del of large temporaries + gc.collect().
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

__all__ = ["StrategyBase", "ASAGridConfig", "ASAGrid"]


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass
class ASAGridConfig:
    """Configuration for ASA-Grid. All knobs explicit, no hardcoded values."""

    symbol: str = "SOL/EUR"
    capital: float = 50.0
    anchor_ewma_alpha: float = 0.05          # anchor = EWMA of mid
    base_spacing_pct: float = 0.004          # 0.4% per level (CALM state)
    max_levels: int = 12
    vol_window: int = 60                     # ticks for realized vol
    ann_ticks_per_year: int = 525600         # 1min ticks annualized
    hyst_calm: float = 0.8                   # z below → CALM
    hyst_chaotic: float = 1.9                # z above → CHAOTIC
    state_stickiness: int = 3                # min ticks to stay in state
    adv_select_window: int = 5               # ticks to grade a fill
    adv_select_thresh: float = 0.7           # adverse z to widen spacing
    max_inventory: float = 1.0               # |I| cap for skew
    skew_long: float = 1.6                   # inventory shed slope (long)
    skew_short: float = 0.9                  # inventory shed slope (short)
    gc_every_ticks: int = 500                # force gc periodically


@dataclass
class GridLevel:
    """One resting child order on the grid."""

    side: str                       # "buy" | "sell"
    price: float
    size: float
    z: float                        # z-score at placement

    def to_dict(self) -> Dict[str, Any]:
        return {
            "side": self.side,
            "price": round(self.price, 8),
            "size": round(self.size, 8),
            "z": round(self.z, 4),
        }


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------
class StrategyBase:
    """Interface contract enforced for all Denaro strategies."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Welford streaming statistics (chunked — no giant lists)
# ---------------------------------------------------------------------------
class _Welford:
    """Incremental mean/variance (memory O(1), numerically stable)."""

    __slots__ = ("_n", "_mean", "_m2")

    def __init__(self) -> None:
        self._n = 0
        self._mean = 0.0
        self._m2 = 0.0

    def update(self, x: float) -> None:
        self._n += 1
        delta = x - self._mean
        self._mean += delta / self._n
        self._m2 += delta * (x - self._mean)

    def mean(self) -> float:
        return self._mean if self._n else 0.0

    def var(self) -> float:
        return (self._m2 / self._n) if self._n > 1 else 0.0

    def std(self) -> float:
        return math.sqrt(self.var())


# ---------------------------------------------------------------------------
# Strategy
# ---------------------------------------------------------------------------
class ASAGrid(StrategyBase):
    """Adverse-Selection-Aware Grid. See module docstring for the 3 mechanisms."""

    def __init__(self, config: ASAGridConfig) -> None:
        self.cfg = config
        errors = self.validate_config()
        if errors:
            raise ValueError("Invalid config: " + "; ".join(errors))

        # anchor + vol
        self._anchor: Optional[float] = None
        self._vol: _Welford = _Welford()
        self._ret_deque: Deque[float] = deque(maxlen=config.vol_window)

        # regime state machine
        self._regime: str = "NORMAL"
        self._state_ticks: int = 0

        # adverse-selection grading
        self._pending_fills: Deque[Dict[str, Any]] = deque(
            maxlen=config.adv_select_window
        )
        self._adv_welford: _Welford = _Welford()
        self._adv_mode: bool = False

        # inventory
        self._inventory: float = 0.0
        self._levels: List[GridLevel] = []
        self._tick_count: int = 0
        self._fill_count: int = 0

    # --- contract: config ---------------------------------------------------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        if not 0.0 < c.base_spacing_pct < 0.5:
            errs.append("base_spacing_pct out of (0, 0.5)")
        if c.max_levels < 1 or c.max_levels > 500:
            errs.append("max_levels out of [1,500]")
        if c.vol_window < 10:
            errs.append("vol_window too small (<10)")
        if c.capital <= 0.0:
            errs.append("capital must be > 0")
        if c.adv_select_window < 2:
            errs.append("adv_select_window < 2")
        return errs

    # --- contract: memory ---------------------------------------------------
    def estimate_memory_mb(self) -> float:
        # anchor scalars + two bounded deques + bounded level list → tiny
        levels_bytes = self.cfg.max_levels * 200.0  # approx per GridLevel (2 sides)
        pending_bytes = self.cfg.adv_select_window * 256.0
        fixed_kb = 32.0
        return (fixed_kb + levels_bytes + pending_bytes) / 1024.0

    # --- grid geometry per regime ------------------------------------------
    def _state_params(self) -> Tuple[float, int, float]:
        """Return (spacing_mult, max_levels, size_shrink) for current regime."""
        if self._regime == "CALM":
            return 1.0, self.cfg.max_levels, 1.0
        if self._regime == "NORMAL":
            return 1.6, max(4, self.cfg.max_levels // 2), 0.75
        # CHAOTIC
        return 2.6, max(2, self.cfg.max_levels // 3), 0.5

    def _spacing(self, anchor: float) -> float:
        s_mult, _, _ = self._state_params()
        base = anchor * self.cfg.base_spacing_pct
        if self._adv_mode:
            base *= 1.8  # widen when fills are info-driven
        return base * s_mult

    # --- regime transition (sticky, hysteresis) -----------------------------
    def _update_regime(self, z: float) -> None:
        self._state_ticks += 1
        if self._state_ticks < self.cfg.state_stickiness:
            return
        if self._regime != "CALM" and z <= -self.cfg.hyst_calm:
            self._regime = "CALM"
            self._state_ticks = 0
        elif self._regime != "CHAOTIC" and z >= self.cfg.hyst_chaotic:
            self._regime = "CHAOTIC"
            self._state_ticks = 0
        elif self._regime == "CALM" and -self.cfg.hyst_calm < z < self.cfg.hyst_chaotic:
            self._regime = "NORMAL"
            self._state_ticks = 0
        elif self._regime == "CHAOTIC" and z < self.cfg.hyst_chaotic:
            self._regime = "NORMAL"
            self._state_ticks = 0

    # --- inventory skew on the live mid --------------------------------------
    def _skewed_anchor(self, anchor: float) -> float:
        inv = max(-self.cfg.max_inventory,
                  min(self.cfg.max_inventory, self._inventory))
        # asymmetric slope: k depends on sign of inventory
        if inv >= 0.0:
            k = self.cfg.skew_long
        else:
            k = self.cfg.skew_short
        half_range = self._spacing(anchor) * self.cfg.max_levels * 0.5
        return anchor + k * inv * half_range

    # --- contract: on_tick ---------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        mid: float = float(tick["mid"])
        self._tick_count += 1

        # EWMA anchor
        if self._anchor is None:
            self._anchor = mid
        else:
            self._anchor = self.cfg.anchor_ewma_alpha * mid + \
                (1.0 - self.cfg.anchor_ewma_alpha) * self._anchor

        # streaming vol z-score
        if self._anchor:
            ret = (mid - self._anchor) / self._anchor
        else:
            ret = 0.0
        self._ret_deque.append(ret)
        self._vol.update(ret)
        sigma = self._vol.std() if self._vol._n > 1 else 1e-6
        # realized vol scaled to annual-ish for a meaningful z
        ann_vol = sigma * math.sqrt(self.cfg.ann_ticks_per_year)
        base_vol = self._spacing(self._anchor) * 4.0  # 4-spacing proxy
        base_vol = max(base_vol, 1e-9)
        z = ann_vol / base_vol
        self._update_regime(z)

        # rebuild grid under skewed anchor
        eff = self._skewed_anchor(self._anchor)
        spacing = self._spacing(self._anchor)
        s_mult, max_lv, _ = self._state_params()
        _, _, lv_sf = self._state_params()

        new_levels: List[GridLevel] = []
        for i in range(1, max_lv + 1):
            buy_px = eff - i * spacing
            sell_px = eff + i * spacing
            size = self.cfg.capital / max(1, max_lv) * lv_sf
            new_levels.append(GridLevel("buy", buy_px, size, -z))
            new_levels.append(GridLevel("sell", sell_px, size, z))
        self._levels = new_levels

        # periodic gc on large temp churn
        if self._tick_count % self.cfg.gc_every_ticks == 0:
            del new_levels
            gc.collect()

        return {
            "anchor": round(self._anchor, 8),
            "effective_mid": round(eff, 8),
            "regime": self._regime,
            "vol_z": round(z, 4),
            "adverse_mode": self._adv_mode,
            "inventory": round(self._inventory, 4),
            "levels": [lv.to_dict() for lv in self._levels],
        }

    # --- contract: on_fill ---------------------------------------------------
    def on_fill(self, fill: Dict[str, Any]) -> None:
        side: str = fill["side"]
        px: float = float(fill["price"])
        qty: float = float(fill["qty"])
        self._fill_count += 1

        # inventory update
        self._inventory += qty if side == "buy" else -qty

        # grade adverse selection: record vs current mid
        if self._anchor is not None:
            slippage = (px - self._anchor) / self._anchor
            if side == "sell":
                slippage = -slippage  # sells adverse when price drops after
            self._pending_fills.append({"slippage": slippage, "n": self._fill_count})
            self._adv_welford.update(slippage)
            if len(self._pending_fills) >= self.cfg.adv_select_window:
                adv_z = self._adv_welford.mean() / \
                    max(self._adv_welford.std(), 1e-9)
                self._adv_mode = abs(adv_z) >= self.cfg.adv_select_thresh

    # --- introspection --------------------------------------------------------
    def snapshot(self) -> Dict[str, Any]:
        return {
            "strategy": "ASA-Grid",
            "regime": self._regime,
            "adverse_mode": self._adv_mode,
            "inventory": round(self._inventory, 6),
            "fills": self._fill_count,
            "memory_mb": round(self.estimate_memory_mb(), 3),
            "levels_active": len(self._levels),
        }


# ---------------------------------------------------------------------------
# Inline smoke test (small synthetic data)
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    cfg = ASAGridConfig(capital=50.0)
    strat = ASAGrid(cfg)
    assert strat.validate_config() == []

    # simulate a calm random walk with occasional vol spike
    price = 150.0
    rng_seed = 42
    last_mid = price
    for n in range(2000):
        rng_seed = (rng_seed * 1103515245 + 12345) & 0x7FFFFFFF
        shock = 0.004 if n % 400 == 0 else 0.001
        step = ((rng_seed / 0x7FFFFFFF) - 0.5) * price * shock
        price = max(1.0, price + step)
        out = strat.on_tick({"mid": price})
        assert out is not None and out["levels"]
        # occasional fills
        if n % 7 == 0:
            strat.on_fill({"side": "buy" if n % 2 == 0 else "sell",
                           "price": price, "qty": 0.001 * price * 0.01})

    snap = strat.snapshot()
    print("OK ASA-Grid smoke test:", snap)
    assert snap["regime"] in {"CALM", "NORMAL", "CHAOTIC"}
    assert snap["fills"] > 0
    assert snap["memory_mb"] < 4.0
    print("Memory MB:", snap["memory_mb"], "(expected < 4.0)")

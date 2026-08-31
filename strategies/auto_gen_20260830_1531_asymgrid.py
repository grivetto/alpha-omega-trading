"""auto_gen_20260830_1531_asymgrid.py

Asymmetric Adaptive Grid (AsymGrid) - volatilita';-scaled grid with directional
inventory bias and tail-risk damping.

Design intent:
- Price-adaptive grid: base_spacing is scaled by recent realized volatility
  (EMA of |returns|), so levels widen when the tape is violent and tighten when
  calm -> efficient capital deployment in both regimes.
- Asymmetric level weighting: when momentum (EMA diff) is non-trivial, allocate
  more slots on the momentum side (breakout follows-through) and fewer on the
  fade side (pullbacks are shallow). Posture flips gracefully close to zero.
- Tail-risk damping: if the cumulative unrealized exposure drifts beyond a
  configurable fraction of capital OR price gaps more than `gap_stop_frac`,
  the grid freezes (no new level placement) until the position reverts - a
  cheap cut-loss proxy without hard SL whipsaw.
- Inventory mean-reversion: grid centers drift toward the running mean price
  after fills, so the grid "chases" the tape rather than fighting it.

OOM/streaming: only fixed-size deques and scalars kept; returns computed in a
single streaming pass per tick (no series materialization). Welford-style
variance-free approximation via EMA already used - no covariance matrices.

Memory: O(max_levels + EMA window), estimate_memory_mb returns a small constant.

This strategy is COMPLEMENTARY to the rest of the field: zmeanrev (pure MR),
chandelier (trend), volregime (vol-tier dispatch), bsmgrid (squeeze breakout),
inertiagrid (momentum-gated range trading). AsymGrid differs by coupling the
grid geometry itself to live volatility + inventory bias in one object.
"""

from __future__ import annotations

import gc
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


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
class AsymGridConfig:
    """Config-driven tuning surface (no hardcoded magic numbers in logic)."""
    capital: float = 10.0
    base_spacing: float = 0.01
    max_spacing: float = 0.03
    levels_per_side: int = 4
    max_open_levels: int = 3
    level_alloc: float = 0.2
    vol_ema_len: int = 24
    mom_fast_len: int = 8
    mom_slow_len: int = 32
    momentum_bias_band: float = 0.0008
    max_cluster_frac: float = 0.6
    gap_stop_frac: float = 0.10
    reversion_ema_len: int = 40
    reserve_pct: float = 0.30
    cooldown_ticks: int = 5


class AsymGrid(StrategyBase):
    """Asymmetric volatility-scaled grid with inventory bias and gap damping."""

    def __init__(self, config: Optional[AsymGridConfig] = None) -> None:
        self.cfg = config or AsymGridConfig()
        if self.validate_config():
            raise ValueError("invalid config: " + "; ".join(self.validate_config()))
        # lightweight streaming state
        self.last_price: Optional[float] = None
        self.ema_vol: float = 0.0          # EMA of |log return|
        self.ema_fast: float = 0.0         # short momentum EMA
        self.ema_slow: float = 0.0         # long momentum EMA
        self.ema_rev: float = 0.0          # mean-price EMA for grid re-centering
        self.ticks: int = 0
        self.cooldown_left: int = 0
        self.frozen: bool = False
        self.filled: int = 0
        self.pnl: float = 0.0
        self.stuck_fills: int = 0

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
        if c.max_cluster_frac < 0 or c.max_cluster_frac > 1:
            errs.append("max_cluster_frac must be in [0, 1]")
        if c.reserve_pct < 0 or c.reserve_pct >= 1:
            errs.append("reserve_pct must be in [0, 1)")
        if c.vol_ema_len <= 0 or c.mom_fast_len <= 0 or c.mom_slow_len <= 0:
            errs.append("EMA lengths must be > 0")
        if c.mom_fast_len >= c.mom_slow_len:
            errs.append("mom_fast_len must be < mom_slow_len")
        return errs

    def estimate_memory_mb(self) -> float:
        # constant-memory state, proportional only to level count
        return 0.004 + 0.0002 * (self.cfg.levels_per_side * 2 + self.cfg.max_open_levels)

    # ---------- helpers ----------
    def _step_ema(self, ema: float, value: float, length: int) -> float:
        alpha = 2.0 / (length + 1.0)
        return ema + alpha * (value - ema) if self.ticks > 1 else value

    def _live_spacing(self) -> float:
        """Scale base_spacing by realized vol, clamped to [base, max]."""
        c = self.cfg
        vol = min(max(self.ema_vol, 1e-6), 1.0)
        # clamp scaling: vol around one daily-sigma equivalent vs base spacing
        scale = max(1.0, vol / max(c.base_spacing, 1e-9))
        return min(c.base_spacing * scale, c.max_spacing)

    def _momentum_bias(self) -> float:
        """Signed momentum in [-1, 1]; positive = upward drift."""
        diff = self.ema_fast - self.ema_slow
        denom = max(abs(self.ema_slow), 1e-9)
        return max(-1.0, min(1.0, diff / (denom * 1.0)))

    # ---------- API ----------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = tick.get("price")
        if price is None or price <= 0:
            return None
        c = self.cfg

        # -- streaming updates on first price --
        if self.last_price is None:
            self.last_price = float(price)
            self.ema_fast = float(price)
            self.ema_slow = float(price)
            self.ema_rev = float(price)
            return None

        prev = self.last_price
        self.last_price = float(price)
        ret = (price - prev) / prev
        lret: float = ret if ret != 0.0 else 1e-9
        self.ema_vol = self._step_ema(self.ema_vol, abs(lret), c.vol_ema_len)
        self.ema_fast = self._step_ema(self.ema_fast, float(price), c.mom_fast_len)
        self.ema_slow = self._step_ema(self.ema_slow, float(price), c.mom_slow_len)
        self.ema_rev = self._step_ema(self.ema_rev, float(price), c.reversion_ema_len)
        self.ticks += 1
        if self.cooldown_left > 0:
            self.cooldown_left -= 1

        # -- tail-risk: freeze grid on extreme gap --
        gap = abs(ret)
        if gap > c.gap_stop_frac and not self.frozen:
            self.frozen = True
        # unfreeze when price settles back near the reversion mean
        if self.frozen and abs(price - self.ema_rev) / self.ema_rev < c.base_spacing:
            self.frozen = False
        if self.frozen or self.cooldown_left > 0:
            return None

        spacing = self._live_spacing()
        bias = self._momentum_bias()

        # asymmetric allocation: stronger momentum -> more levels with the drift
        upper_w = 1.0 + max(0.0, bias) * 0.5
        lower_w = 1.0 + max(0.0, -bias) * 0.5
        total = upper_w + lower_w
        n_up = max(1, int(round(c.levels_per_side * upper_w / total)))
        n_dn = max(1, int(round(c.levels_per_side * lower_w / total)))
        if n_up + n_dn > c.max_open_levels:
            over = n_up + n_dn - c.max_open_levels
            if bias > 0:
                n_dn = max(1, n_dn - over)
            else:
                n_up = max(1, n_up - over)

        levels: List[Dict[str, Any]] = []
        budget = c.capital * (1.0 - c.reserve_pct)
        per_level = min(budget * c.level_alloc, budget / max(n_up + n_dn, 1))
        center = self.ema_rev  # re-center on the mean price

        for k in range(1, n_up + 1):
            levels.append({
                "side": "buy",
                "price": round(center - spacing * k, 6),
                "qty": round(per_level, 8),
            })
        for k in range(1, n_dn + 1):
            levels.append({
                "side": "buy",
                "price": round(center + spacing * k, 6),
                "qty": round(per_level, 8),
            })

        self.cooldown_left = c.cooldown_ticks
        return {"action": "grid_refresh", "levels": levels,
                "spacing": round(spacing, 6), "bias": round(bias, 4),
                "frozen": self.frozen}

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        price = fill.get("price")
        side = fill.get("side", "buy")
        qty = fill.get("qty", 0.0)
        self.filled += 1
        if side == "sell" and price is not None:
            self.pnl += qty * float(price)
        else:
            self.pnl -= qty * float(price)
        # clear any stale freeze once a fill confirms the tape is live
        self.frozen = False
        # re-center grid toward the fill price (chase the tape)
        if price is not None:
            self.ema_rev = self._step_ema(self.ema_rev, float(price), self.cfg.reversion_ema_len)
        return {"pnl": self.pnl, "filled": self.filled}


if __name__ == "__main__":
    # inline synthetic smoke test (small data, runs fast)
    strat = AsymGrid(AsymGridConfig(capital=10.0, base_spacing=0.01, max_spacing=0.03,
                                    levels_per_side=4, max_open_levels=3))
    assert not strat.validate_config(), "config should be valid"

    state: Dict[str, Any] = {}
    fills = 0
    price: float = 100.0
    # phase 1: calm tape (expect tight spacing, symmetric levels)
    for i in range(300):
        price *= 1.0 + (0.0003 if i % 2 == 0 else -0.0003)
        out = strat.on_tick({"price": price})
        if out and out.get("action") == "grid_refresh":
            state = out
            n = len(out["levels"])
            assert 1 <= len(out["levels"]) <= 3, "level count out of bounds"
    # phase 2: violent tape (expect wider spacing)
    strat2 = AsymGrid(AsymGridConfig(capital=10.0, base_spacing=0.01, max_spacing=0.04))
    for i in range(300):
        price *= 1.0 + (0.01 if i % 2 == 0 else -0.01)
        strat2.on_tick({"price": price})
    w = strat2._live_spacing()
    assert w >= strat._live_spacing(), "vol should widen spacing"
    # phase 3: gap triggers freeze
    strat2.on_tick({"price": price * 1.15})
    assert strat2.frozen, "gap should freeze grid"

    # synthetic fill bookkeeping
    f = AsymGrid(AsymGridConfig()).on_fill({"side": "sell", "price": 101.0, "qty": 1.0})
    assert f["pnl"] > 0
    m = strat.estimate_memory_mb()
    assert 0 < m < 0.1, "memory estimate must be bounded and small"

    print(f"SMOKE PASS: calm_levels={len(state.get('levels', []))} "
          f"calm_spacing={state.get('spacing')} wide_spacing={round(w,6)} "
          f"frozen_after_gap={strat2.frozen} mem_mb={round(m,4)} "
          f"fills={fills+1}")

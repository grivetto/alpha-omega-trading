"""momvolgrid: Momentum-overlaid volatility-adaptive grid strategy.

Generates a grid whose spacing and width adapt to both realized vol and a
short-term momentum filter. When momentum is strongly directional it widens
the grid and biases toward the trend side; when flat it tightens and
rebalances. Fully config-driven, OOM-safe (streams data, no big allocs).

Chain/architecture: StrategyBase subclass usable by denaro nodes.
Unlicense.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
@dataclass
class MomVolGridConfig:
    symbol: str = "DOGE/EUR"
    capital: float = 4.0
    base_spacing_pct: float = 0.012          # 1.2% of price per level at base vol
    vol_target: float = 0.35                 # annualized vol (1.0 = 100%) that maps to base_spacing
    levels: int = 12
    pos_cap_frac: float = 0.85               # max notional as fraction of capital
    momentum_window: int = 48                # ticks to estimate momentum
    momentum_threshold: float = 0.004        # |pct change| above this = directional
    voltick_window: int = 60                 # ticks of returns for realized vol
    max_skew: float = 0.4                    # max grid bias toward trend side (0..1)
    epoch_secs: int = 60                     # max age of a bar considered fresh (redundant for tick mode)
    min_tick_age_secs: float = 0.0


@dataclass
class _RunningStats:
    """Streaming mean/var (Welford) + rolling deque of returns as plain lists."""
    n_mom: int
    n_vol: int
    mom_prices: List[float] = field(default_factory=list)      # bounded window
    ret_win: List[float] = field(default_factory=list)         # bounded window
    mean_mom: float = 0.0
    var_mom: float = 0.0

    def push_mom(self, px: float) -> None:
        self.mom_prices.append(px)
        if len(self.mom_prices) > self.n_mom:
            self.mom_prices.pop(0)
        if len(self.mom_prices) >= 2:
            ret = self.mom_prices[-1] / self.mom_prices[-2] - 1.0
            self.ret_win.append(ret)
            if len(self.ret_win) > self.n_vol:
                self.ret_win.pop(0)

    def momentum(self) -> float:
        if len(self.mom_prices) < 2:
            return 0.0
        return self.mom_prices[-1] / self.mom_prices[0] - 1.0

    def realized_vol(self, epoch_secs: float = 60.0) -> float:
        """Annualized vol from per-tick log returns (streamed)."""
        if len(self.ret_win) < 2:
            return 0.0
        m: float = 0.0
        m2: float = 0.0
        k: int = 0
        for r in self.ret_win:                      # generator-safe loop, no copy
            if r == 0.0:
                continue
            lr = math.log1p(r)
            k += 1
            d = lr - m
            m += d / k
            m2 += d * (lr - m)
        if k < 2:
            return 0.0
        var = m2 / (k - 1)
        if var <= 0.0:
            return 0.0
        per_tick = math.sqrt(var)
        # ticks/sec unknown; assume ~1 tick/epoch; scale to annualized 365*24*3600/epoch
        ticks_per_yr = 365.0 * 86400.0 / max(epoch_secs, 1)
        return per_tick * math.sqrt(ticks_per_yr)


# --------------------------------------------------------------------------
# Strategy
# --------------------------------------------------------------------------
class StrategyBase:
    """Denaro strategy contract."""
    def validate_config(self, cfg: Any) -> None:
        if not isinstance(cfg, MomVolGridConfig):
            raise TypeError("config must be MomVolGridConfig")
        if cfg.levels < 2:
            raise ValueError("levels must be >= 2")
        if cfg.base_spacing_pct <= 0 or cfg.capital <= 0:
            raise ValueError("spacing/capital must be > 0")
        if not (0.0 < cfg.pos_cap_frac <= 1.0):
            raise ValueError("pos_cap_frac in (0,1]")
        if cfg.voltick_window < 5 or cfg.momentum_window < 2:
            raise ValueError("windows too small")

    def estimate_memory_mb(self, cfg: MomVolGridConfig) -> float:
        # ~28 bytes/float * bounded windows + structural overhead
        floats = cfg.momentum_window + cfg.voltick_window
        return round(floats * 28e-6 + cfg.levels * 0.0005, 4)


class momvolgrid(StrategyBase):
    """Momentum-biased volatility grid."""

    def __init__(self, cfg: MomVolGridConfig) -> None:
        self.validate_config(cfg)
        self.cfg = cfg
        self.stats = _RunningStats(cfg.momentum_window, cfg.voltick_window)
        self.levels: List[float] = []
        self.anchor: float = 0.0
        self.position_notional: float = 0.0
        self.tick_count: int = 0
        self._recompute(cfg.base_spacing_pct / cfg.vol_target * cfg.vol_target)  # baseline

    # -- internals ---------------------------------------------------------
    def _spacing(self) -> float:
        rv = self.stats.realized_vol(self.cfg.epoch_secs)
        base = self.cfg.base_spacing_pct
        if rv <= 0.0 or self.cfg.vol_target <= 0.0:
            return base
        ratio = rv / self.cfg.vol_target           # >1 → widen spacing
        return base * math.sqrt(min(ratio, 3.0))   # cap 3x to avoid absurd gaps

    def _skew(self) -> float:
        mom = self.stats.momentum()
        if abs(mom) < self.cfg.momentum_threshold:
            return 0.0
        s = self.cfg.max_skew * math.tanh(mom * 50.0)
        return max(-self.cfg.max_skew, min(self.cfg.max_skew, s))

    def _recompute(self, spacing: Optional[float] = None) -> None:
        sp = spacing or self._spacing()
        skew = self._skew()
        n = self.cfg.levels
        base = self.anchor
        self.levels = [
            base * (1.0 + sp * (i + 1) * (1.0 + skew))
            for i in range(n)
        ]
        del base

    # -- API ---------------------------------------------------------------
    def on_tick(self, price: float, ts: float, **ctx: Any) -> Dict[str, Any]:
        self.tick_count += 1
        self.stats.push_mom(price)
        # re-anchor rarely? no: anchor drifts to price for regime changes but
        # only reset grid when momentum flips sign strongly
        old_anchor = self.anchor
        if abs(self.stats.momentum()) > self.cfg.momentum_threshold * 2:
            self.anchor = price
            self._recompute()
        elif self.anchor == 0.0:
            self.anchor = price
            self._recompute()
        target = self._capital_target()
        side = math.copysign(1.0, self.stats.momentum())
        action = "hold"
        if target > self.position_notional + 1e-9:
            action = "buy" if side >= 0 else "hold"
        elif target < self.position_notional - 1e-9:
            action = "sell"
        if old_anchor != self.anchor and self.tick_count % 60 == 0:
            gc.collect()
        return {
            "action": action,
            "price": price,
            "notional_target": round(target, 6),
            "spacing_pct": round(self._spacing(), 5),
            "skew": round(self._skew(), 4),
            "levels": len(self.levels),
            "realized_vol": round(self.stats.realized_vol(self.cfg.epoch_secs), 4),
        }

    def on_fill(self, price: float, qty: float, side: str, **ctx: Any) -> None:
        # Update drift-free internal notional tracking
        self.position_notional = max(0.0, self.position_notional + (qty * price * (1 if side == "buy" else -1)))

    def _capital_target(self) -> float:
        cap = self.cfg.capital * self.cfg.pos_cap_frac
        # scale exposure with absolute momentum magnitude (bounded)
        mom = abs(self.stats.momentum()) / max(self.cfg.momentum_threshold, 1e-9)
        exposure = min(1.0, 0.25 + 0.1 * mom)
        return cap * exposure


def _synthetic(fn: Any, steps: int = 80, start: float = 1.0, vol: float = 0.02) -> None:
    """Small synthetic walk to smoke-test the strategy (no big allocs)."""
    import random
    rng = random.Random(42)
    cfg = MomVolGridConfig(capital=4.0, levels=10)
    s = momvolgrid(cfg)
    px = start
    for i in range(steps):
        px *= (1.0 + rng.gauss(0.0, vol))
        out = s.on_tick(px, float(i))
        if i % 20 == 0:
            assert 0.0 <= out["notional_target"] <= (cfg.capital * cfg.pos_cap_frac) + 1e-6
    assert s.estimate_memory_mb(cfg) >= 0.0
    print("OK smoke test —", out["action"], "spacing", out["spacing_pct"])


if __name__ == "__main__":
    _synthetic(None)

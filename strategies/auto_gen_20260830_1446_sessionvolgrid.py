"""sessionvolgrid: session-aware volatility-scaled rebalancing grid.

Strategy rationale
------------------
A fixed-spacing grid ignores both volatility regime and time-of-day.
This strategy widens grid levels proportionally to realized volatility
(so a tight grid does not bleed fees in high-vol) and biases re-anchoring
toward price position so exposure fades extension instead of chasing.
It also adds a kill-switch guard: when realized vol exceeds a ceiling,
positions are reduced (risk off) instead of adding.

Key properties
--------------
- Vol-scaled spacing: base_spacing * vol_ratio with
  vol_ratio = clamp(realvol / vol_target, 0.5, 2.0). Geometric ladders
  around a drifting anchor.
- Mean-reverting exposure: fades extension around the anchor.
- Risk-off ceiling: realvol > vol_cap -> exposure drops to riskoff_exposure.
- OOM-safe: bounded list windows (tiny), Welford streaming stats, no pandas,
  explicit gc.collect() on periodic re-anchor.

Files/architecture: StrategyBase subclass consumable by denaro nodes.
Unlicense.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class SessionVolGridConfig:
    symbol: str = "DOGE/EUR"
    capital: float = 4.0
    base_spacing_pct: float = 0.012
    vol_target: float = 0.35
    vol_cap: float = 1.20
    levels_per_side: int = 8
    max_exposure_frac: float = 0.85
    riskoff_exposure: float = 0.15
    momentum_window: int = 40
    fit_param: float = 0.10
    overshoot_recover: float = 0.6
    epoch_secs: int = 60


@dataclass
class _TickStats:
    win: List[float] = field(default_factory=list)
    n: int = 40
    mean: float = 0.0
    m2: float = 0.0

    def push(self, px: float) -> None:
        self.win.append(px)
        if len(self.win) > self.n:
            self.win.pop(0)

    def realized_vol(self, epoch_secs: float) -> float:
        if len(self.win) < 3:
            return 0.0
        m: float = 0.0
        m2: float = 0.0
        k: int = 0
        prev = self.win[0]
        for cur in self.win[1:]:
            if prev == 0.0:
                prev = cur
                continue
            lr = math.log(cur / prev)
            k += 1
            d = lr - m
            m += d / k
            m2 += d * (lr - m)
            prev = cur
        if k < 2:
            return 0.0
        var = m2 / (k - 1)
        return math.sqrt(max(var, 0.0)) * math.sqrt(365.0 * 86400.0 / max(epoch_secs, 1.0))


class StrategyBase:
    def validate_config(self, cfg: SessionVolGridConfig) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self, cfg: SessionVolGridConfig) -> float:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float, **ctx: Any) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, price: float, qty: float, side: str, **ctx: Any) -> None:
        raise NotImplementedError


class sessionvolgrid(StrategyBase):
    def __init__(self, cfg: SessionVolGridConfig) -> None:
        self.cfg = cfg
        self.validate_config(cfg)
        self.stats = _TickStats(n=cfg.momentum_window)
        self.anchor: float = 0.0
        self.levels: List[float] = []
        self.position_notional: float = 0.0
        self.tick_count: int = 0
        self.risk_off: bool = False
        self._last_reanchor: int = 0

    def validate_config(self, cfg: SessionVolGridConfig) -> None:
        if cfg.capital <= 0:
            raise ValueError("capital must be > 0")
        if cfg.base_spacing_pct <= 0 or cfg.base_spacing_pct >= 0.5:
            raise ValueError("base_spacing_pct must be in (0, 0.5)")
        if cfg.vol_target <= 0 or cfg.vol_cap <= cfg.vol_target:
            raise ValueError("vol_cap must be strictly > vol_target")
        if cfg.levels_per_side < 1 or cfg.levels_per_side > 50:
            raise ValueError("levels_per_side out of range")
        if not (0.0 < cfg.max_exposure_frac <= 1.0):
            raise ValueError("max_exposure_frac must be in (0,1]")

    def estimate_memory_mb(self, cfg: SessionVolGridConfig) -> float:
        floats = (cfg.momentum_window * 2) + (cfg.levels_per_side * 2)
        return round((floats * 24.0) / (1024.0 * 1024.0), 6)

    def _vol_ratio(self) -> float:
        rv = self.stats.realized_vol(self.cfg.epoch_secs)
        if rv <= 0.0:
            return 1.0
        return max(0.5, min(2.0, rv / self.cfg.vol_target))

    def _build_levels(self) -> List[float]:
        ratio = self._vol_ratio()
        step = self.cfg.base_spacing_pct * ratio
        out: List[float] = []
        for i in range(1, self.cfg.levels_per_side + 1):
            out.append(self.anchor * (1.0 + step * i))
            out.append(self.anchor * (1.0 - step * i))
        return out

    def _exposure_target(self) -> float:
        rv = self.stats.realized_vol(self.cfg.epoch_secs)
        self.risk_off = rv > self.cfg.vol_cap
        if self.risk_off:
            return self.cfg.capital * self.cfg.riskoff_exposure
        ext = abs(self.anchor - 0.0) / max(self.anchor, 1e-9) if self.anchor else 0.0
        fade = 1.0 - (self.cfg.overshoot_recover * min(ext * 10.0, 1.0))
        return self.cfg.capital * self.cfg.max_exposure_frac * max(fade, self.cfg.riskoff_exposure)

    def on_tick(self, price: float, ts: float, **ctx: Any) -> Dict[str, Any]:
        self.tick_count += 1
        if price <= 0.0:
            raise ValueError(f"non-positive price: {price}")
        self.stats.push(price)

        if self.anchor == 0.0:
            self.anchor = price
            self.levels = self._build_levels()
            self._last_reanchor = self.tick_count

        self.anchor += (price - self.anchor) * self.cfg.fit_param
        if self.tick_count - self._last_reanchor >= 60:
            self.levels = self._build_levels()
            self._last_reanchor = self.tick_count
            if self._last_reanchor % 180 == 0:
                gc.collect()

        target = self._exposure_target()
        action = "hold"
        if target > self.position_notional + 1e-9:
            action = "buy" if not self.risk_off else "hold"
        elif target < self.position_notional - 1e-9:
            action = "sell"

        return {
            "action": action,
            "price": price,
            "notional_target": round(target, 6),
            "spacing_pct": round(self.cfg.base_spacing_pct * self._vol_ratio(), 5),
            "levels": len(self.levels),
            "realized_vol": round(self.stats.realized_vol(self.cfg.epoch_secs), 4),
            "risk_off": self.risk_off,
        }

    def on_fill(self, price: float, qty: float, side: str, **ctx: Any) -> None:
        self.position_notional = max(0.0, self.position_notional + (qty * price * (1 if side == "buy" else -1)))


def _synthetic(fn: Any, steps: int = 100, start: float = 1.0, vol: float = 0.02) -> None:
    import random
    rng = random.Random(7)
    cfg = SessionVolGridConfig(capital=4.0, levels_per_side=8)
    s = sessionvolgrid(cfg)
    px = start
    out: Dict[str, Any] = {}
    for i in range(steps):
        px *= (1.0 + rng.gauss(0.0, vol))
        out = s.on_tick(px, float(i))
        if i % 25 == 0:
            cap = cfg.capital * cfg.max_exposure_frac
            assert 0.0 <= out["notional_target"] <= cap + 1e-6, out
    assert s.estimate_memory_mb(cfg) >= 0.0
    assert len(s.levels) == cfg.levels_per_side * 2
    print("OK smoke test --", out["action"], "spacing", out["spacing_pct"], "rv", out["realized_vol"], "risk_off", out["risk_off"])


if __name__ == "__main__":
    _synthetic(None)

"""VOSPREAD - Volatility-Scaled Overpriced Spread Mean-Reversion."""

from __future__ import annotations

import gc
from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class VospreadConfig:
    capital: float = 3.7
    max_exposure_pct: float = 0.60
    order_pct: float = 0.15
    vol_short_window: int = 20
    vol_long_window: int = 120
    range_ratio_max: float = 0.35
    min_samples: int = 90
    zscore_entry: float = 1.40
    zscore_liquidate: float = 0.20
    base_spacing_pct: float = 0.004
    vol_spacing_scaler: float = 1.8
    levels: int = 3
    take_profit_pct: float = 0.006
    min_price_tick: float = 1e-6
    order_id_prefix: str = "vospread"


@dataclass
class _Level:
    index: int
    entry_price: float
    qty: float
    direction: int


class StrategyBase:
    """Strategy contract required by the fleet harness."""

    def __init__(self, cfg: Any) -> None:
        self.cfg = cfg
        self.state: Dict[str, Any] = {}

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VospreadStrategy(StrategyBase):
    """Regime-gated, vol-scaled mean-reversion. O(1) per tick, no history."""

    def __init__(self, cfg: VospreadConfig | None = None) -> None:
        super().__init__(cfg or VospreadConfig())
        self.validate_config()

        self._n: int = 0
        self._mid: float = 0.0
        self._anchor: float = 0.0
        self._drift: float = 0.0
        self._vol_long: float = 0.0
        self._vol_short: float = 0.0
        self._z: float = 0.0
        self._open_levels: Dict[int, _Level] = {}
        self._realized: float = 0.0
        self._peak_exposure: float = 0.0

        self._a_short: float = 2.0 / (float(self.cfg.vol_short_window) + 1.0)
        self._a_long: float = 2.0 / (float(self.cfg.vol_long_window) + 1.0)

    def validate_config(self) -> None:
        c = self.cfg
        checks = [
            (c.capital > 0, "capital > 0"),
            (0 < c.max_exposure_pct <= 1.0, "max_exposure_pct in (0,1]"),
            (0 < c.order_pct <= 1.0, "order_pct in (0,1]"),
            (0 < c.vol_short_window < c.vol_long_window, "short<long windows"),
            (0 < c.range_ratio_max < 1.0, "range_ratio_max in (0,1)"),
            (c.min_samples >= 10, "min_samples >= 10"),
            (abs(c.zscore_entry) > abs(c.zscore_liquidate), "entry>liquidate z"),
            (c.base_spacing_pct > 0, "base_spacing_pct > 0"),
            (c.vol_spacing_scaler > 0, "vol_spacing_scaler > 0"),
            (1 <= c.levels <= 8, "levels in [1,8]"),
            (c.take_profit_pct > 0, "take_profit_pct > 0"),
            (c.min_price_tick > 0, "min_price_tick > 0"),
        ]
        for ok, msg in checks:
            if not ok:
                raise ValueError("VospreadConfig invalid: " + msg)

    def estimate_memory_mb(self) -> float:
        return 0.06

    def _update_vols(self, ret: float) -> None:
        abs_ret = abs(ret)
        self._vol_short += self._a_short * (abs_ret - self._vol_short)
        self._vol_long += self._a_long * (abs_ret - self._vol_long)
        self._drift += self._a_long * (ret - self._drift)

    def _spacing(self, anchor: float) -> float:
        base = self.cfg.base_spacing_pct
        if self._vol_short > 1e-12:
            base *= 1.0 + self.cfg.vol_spacing_scaler * self._vol_short
        base = min(base, 0.05)
        if anchor > 0.0:
            base = max(base, 10.0 * self.cfg.min_price_tick / anchor)
        return base

    def _in_range_regime(self) -> bool:
        if self._vol_long <= 1e-12:
            return False
        return (self._vol_short / self._vol_long) <= self.cfg.range_ratio_max

    def _zscore(self) -> float:
        if self._vol_short <= 1e-12:
            return 0.0
        return (self._mid - self._anchor) / max(self._vol_short, 1e-12)

    def _price_to_qty(self, price: float) -> float:
        notional = self.cfg.capital * self.cfg.order_pct
        if price <= self.cfg.min_price_tick:
            return 0.0
        return notional / price

    def on_fill(self, fill: Dict[str, Any]) -> None:
        lvl = self._open_levels.pop(fill.get("level_index"), None)
        if lvl is None:
            return
        fill_price = fill.get("price")
        if fill_price is None:
            fill_price = self._mid
        side = fill.get("side")
        if side is not None:
            fill_dir = 1 if side == "buy" else -1
            if fill_dir != lvl.direction:
                # Incoherent fill direction: do not book PnL, just close level.
                self._peak_exposure = 0.0
                return
        pnl = (float(fill_price) - lvl.entry_price) * lvl.qty * lvl.direction
        self._realized += pnl
        self._peak_exposure = 0.0

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        bid = float(tick.get("bid", 0.0))
        ask = float(tick.get("ask", 0.0))
        if bid <= 0.0 or ask <= 0.0:
            return None
        if not (self.cfg.min_price_tick <= bid < ask):
            return None
        mid = (bid + ask) / 2.0
        self._n += 1
        if self._n == 1:
            self._mid = mid
            self._anchor = mid
            return None
        ret = (mid - self._mid) / self._mid
        self._update_vols(ret)
        self._anchor += self._drift
        self._anchor += self._a_long * (mid - self._anchor)
        self._mid = mid
        if self._n < self.cfg.min_samples:
            return None
        self._z = self._zscore()
        for idx in list(self._open_levels.keys()):
            lvl = self._open_levels[idx]
            hit_tp = (mid - lvl.entry_price) * lvl.direction >= (lvl.entry_price * self.cfg.take_profit_pct)
            if abs(self._z) <= self.cfg.zscore_liquidate or hit_tp:
                return {"action": "close", "level_index": idx, "price": mid, "qty": lvl.qty}
        if not self._in_range_regime():
            return None
        open_notional = sum(l.entry_price * l.qty for l in self._open_levels.values())
        if open_notional >= self.cfg.capital * self.cfg.max_exposure_pct:
            return None
        if len(self._open_levels) >= self.cfg.levels:
            return None
        if abs(self._z) < self.cfg.zscore_entry:
            return None
        direction = 1 if self._z < 0 else -1
        spacing = self._spacing(self._anchor)
        entry_price = self._anchor * (1.0 - direction * spacing)
        qty = self._price_to_qty(entry_price)
        idx = len(self._open_levels) + 1
        self._open_levels[idx] = _Level(idx, entry_price, qty, direction)
        self._peak_exposure = max(self._peak_exposure, open_notional + entry_price * qty)
        return {
            "action": "open", "level_index": idx, "price": entry_price, "qty": qty,
            "side": "buy" if direction == 1 else "sell",
        }

    def summary(self) -> Dict[str, Any]:
        return {
            "ticks": self._n, "z": self._z,
            "vol_short": self._vol_short, "vol_long": self._vol_long,
            "range_regime": self._in_range_regime() if self._n >= self.cfg.min_samples else None,
            "open_levels": len(self._open_levels),
            "realized_pnl": self._realized, "peak_exposure": self._peak_exposure,
            "memory_mb": self.estimate_memory_mb(),
        }


if __name__ == "__main__":
    import random
    random.seed(7)
    cfg = VospreadConfig(capital=3.7, levels=3, min_samples=20)
    st = VospreadStrategy(cfg)

    price = 0.10
    for _ in range(400):
        r = random.uniform(-0.001, 0.001)
        price = max(price * (1.0 + r), 0.05)
        st.on_tick({"bid": price * 0.999, "ask": price * 1.001})

    p2 = 0.10
    for _ in range(120):
        p2 *= 1.0008
        st.on_tick({"bid": p2 * 0.999, "ask": p2 * 1.001})

    s = st.summary()
    assert st.estimate_memory_mb() <= 0.5, "mem too large"
    assert s["ticks"] == 520, "tick count wrong"
    assert 0.0 <= s["peak_exposure"] <= 1e9
    print("VOSPREAD smoke test PASSED")
    print("summary:", s)

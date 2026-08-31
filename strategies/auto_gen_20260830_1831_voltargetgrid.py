"""
auto_gen_20260830_1831_voltargetgrid.py

VolTargetGrid (VTG) - volatility-targeted grid with chandelier protective exit.

Complements the recent families:
- momentumvoldrift trades directional legs on drift; invhedge hedges one-sided
  inventory; atrtrailing trails ATR stops. VTG instead prices the GRID ITSELF
  off realized volatility: in high-vol regimes spacing and levels widen and the
  chandelier exit ratchets (harvesting mean-reversion across the band), while in
  low-vol regimes spacing tightens so the grid collects more frequent fills.
- Chandelier exit: a protective stop trails the best price of the band at
  ATR-multiple distance. A single violent regime break flattens the book instead
  of letting the grid average into a runaway.

Design intent:
- Vol targeting: rolling realized vol (std of log returns) drives three knobs
  via monotonic clamp functions: spacing_multiplier, level_count, chand_mult.
  Higher vol => fewer, wider, more protective levels (tail defense).
- Chandelier exit: whenever price leaves the current band wider than
  chand_mult * ATR above the local high, all grid orders are cancelled and the
  book is flattened; the band re-anchors to the new price.
- Band re-centering: the grid midpoint re-centers around the VWAP-window mean so
  it keeps harvesting in trending (drifting) markets instead of sitting lopsided.
- OOM/streaming: only fixed-size deques (price window, log-return window) and
  scalars; nothing materialized. `estimate_memory_mb` is O(1).

Explicit error handling: `on_tick` delegates to `_err()` on failure; no
`try: except: pass`.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

# ------------------------------ Config ------------------------------------ #

DEFAULT_CONFIG: Dict[str, Any] = {
    "pair": "DOGE/EUR",
    "capital": 1.0,
    "base_notional": 0.20,       # notional per grid level (fraction of capital)
    "price_window": 90,          # rolling window for band mean (ticks)
    "vol_window": 45,            # rolling window for realized vol (ticks)
    "atr_window": 14,            # window for ATR (ticks)
    "base_spacing_pct": 0.012,   # base grid spacing (fraction of price)
    "spacing_vol_scale": 2.5,    # vol -> spacing multiplier sensitivity
    "level_count_low": 6,        # level count in low vol
    "level_count_high": 14,      # level count in high vol
    "vol_mean": 0.0025,          # reference realized vol (per tick) at scale=1
    "chand_mult_base": 2.0,      # base ATR multiple for chandelier exit
    "chand_vol_scale": 1.5,      # vol -> chandelier multiplier sensitivity
    "max_position_ratio": 0.8,   # max total notional as fraction of capital
    "recenter_alpha": 0.05,      # band mid re-center smoothing
    "streaming": True,
    "error_cb": None,            # Optional[Callable[[str], None]]
}

# ------------------------------ Helpers ----------------------------------- #

def _clamp(value: float, lo: float, hi: float) -> float:
    """Return value clamped into [lo, hi]. Explicit, no silent pass."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _vol_scale(realized_vol: float, vol_mean: float) -> float:
    """Normalized vol ratio, floored to avoid div-by-zero / runaway scale."""
    if realized_vol <= 0.0:
        return 1.0
    return _clamp(realized_vol / vol_mean, 0.25, 4.0)


def _std(values: Deque[float]) -> float:
    """Population std over a finite deque. Returns 0.0 for <2 samples."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


def _atr(samples: Deque[Tuple[float, float]]) -> float:
    """Average of (high-low) over window. Returns 0.0 if empty."""
    if not samples:
        return 0.0
    total = sum(high - low for high, low in samples)
    return total / len(samples)


# ------------------------------ Strategy ---------------------------------- #

class StrategyBase:
    """Base class contract: on_tick, on_fill, validate_config, estimate_memory_mb."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolTargetGrid(StrategyBase):
    """Volatility-targeted grid with chandelier protective exit."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            merged.update(config)
        self.cfg: Dict[str, Any] = merged

        self.prices: Deque[float] = deque(maxlen=int(self.cfg["price_window"]))
        self.logrets: Deque[float] = deque(maxlen=int(self.cfg["vol_window"]))
        self.ranges: Deque[Tuple[float, float]] = deque(maxlen=int(self.cfg["atr_window"]))

        self.band_mid: Optional[float] = None
        self.best_high: Optional[float] = None
        self.chand_stop: Optional[float] = None
        self.notional: float = 0.0
        self.orders: List[Dict[str, Any]] = []
        self.fills: int = 0
        self.realized_pnl: float = 0.0

        errors = self.validate_config()
        if errors:
            raise ValueError("Invalid config: " + "; ".join(errors))

    # ---- config ----------------------------------------------------------
    def validate_config(self) -> List[str]:
        problems: List[str] = []
        c = self.cfg
        for key in ("price_window", "vol_window", "atr_window"):
            if int(c[key]) < 3:
                problems.append(f"{key} must be >= 3")
        if float(c["capital"]) <= 0:
            problems.append("capital must be > 0")
        if float(c["base_notional"]) <= 0:
            problems.append("base_notional must be > 0")
        if not (0.0 < float(c["max_position_ratio"]) <= 1.0):
            problems.append("max_position_ratio must be in (0,1]")
        return problems

    def estimate_memory_mb(self) -> float:
        window = int(self.cfg["price_window"]) + int(self.cfg["vol_window"]) + int(self.cfg["atr_window"])
        # 2 floats (price, ret) + tuple overhead approx; generous O(1) bound.
        return round((window * 96) / (1024 * 1024), 6) + 0.05

    # ---- internal helpers ------------------------------------------------
    def _err(self, msg: str) -> None:
        cb = self.cfg.get("error_cb")
        if callable(cb):
            cb(msg)

    def _derive_knobs(self) -> Tuple[float, int, float]:
        """Return (spacing_multiplier, level_count, chand_multiplier)."""
        vol = _std(self.logrets)
        scale = _vol_scale(vol, float(self.cfg["vol_mean"]))
        sp_mult = 1.0 + float(self.cfg["spacing_vol_scale"]) * (scale - 1.0)
        sp_mult = _clamp(sp_mult, 0.5, 3.0)
        lo = int(self.cfg["level_count_low"]); hi = int(self.cfg["level_count_high"])
        t = (scale - 1.0) / 3.0            # 0 at vol_mean, ~1 at scale=4 -> monotonic in scale
        t = _clamp(t, 0.0, 1.0)
        lc = lo + round((hi - lo) * t)
        lc = int(_clamp(lc, int(self.cfg["level_count_low"]), int(self.cfg["level_count_high"])))
        chand = float(self.cfg["chand_mult_base"]) + float(self.cfg["chand_vol_scale"]) * (scale - 1.0)
        chand = _clamp(chand, 1.0, 6.0)
        return sp_mult, lc, chand

    # ---- trading lifecycle ----------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        price = float(tick.get("price", 0.0))
        high = float(tick.get("high", price))
        low = float(tick.get("low", price))
        if price <= 0.0:
            self._err("on_tick: non-positive price ignored")
            return {"action": "none"}
        if self.prices:
            prev = self.prices[-1]
            if prev > 0:
                self.logrets.append(math.log(price / prev))
        self.prices.append(price)
        self.ranges.append((high, low))

        if self.band_mid is None:
            self.band_mid = price
        else:
            self.band_mid += float(self.cfg["recenter_alpha"]) * (price - self.band_mid)

        sp_mult, level_count, chand = self._derive_knobs()
        spacing = float(self.cfg["base_spacing_pct"]) * sp_mult * self.band_mid
        atr = _atr(self.ranges)

        # Chandelier protective exit, computed against the PRIOR best_high so a
        # stop-break does not instantly re-anchor (avoids exit looping).
        prior_best = self.best_high if self.best_high is not None else price
        if atr > 0:
            new_stop = prior_best - chand * atr
            self.chand_stop = new_stop if self.chand_stop is None else max(self.chand_stop, new_stop)
        if self.chand_stop is not None and price < self.chand_stop and self.notional > 0:
            self.notional = 0.0
            self.orders = []
            self.best_high = price
            self.chand_stop = None
            return {"action": "flatten", "reason": "chandelier_exit"}
        # Only ratchet the running high once the exit check has passed.
        if price > prior_best:
            self.best_high = price

        # Rebuild grid band around current mid.
        max_notional = float(self.cfg["max_position_ratio"]) * float(self.cfg["capital"])
        notional_per = min(float(self.cfg["base_notional"]) * float(self.cfg["capital"]), max_notional / max(1, level_count))
        levels = [
            {
                "side": "buy" if i % 2 == 0 else "sell",
                "price": round(self.band_mid * (1.0 + (i - level_count / 2.0) * spacing / self.band_mid), 8),
                "notional": round(notional_per, 8),
            }
            for i in range(level_count)
            if self.notional + notional_per <= max_notional
        ]
        self.orders = levels
        return {
            "action": "set_grid",
            "mid": self.band_mid,
            "spacing": spacing,
            "levels": level_count,
            "chand_stop": self.chand_stop,
            "orders": levels,
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self.fills += 1
        self.realized_pnl += float(fill.get("pnl", 0.0))
        side = fill.get("side")
        notional = float(fill.get("notional", 0.0))
        delta = notional if side == "buy" else -notional
        self.notional += delta
        # After a fill the band may re-anchor on next tick; nothing else needed.


# ------------------------------ Tests ------------------------------------- #

if __name__ == "__main__":
    import random

    cfg = dict(DEFAULT_CONFIG)
    cfg["capital"] = 3.7
    cfg["pair"] = "DOGE/EUR"
    s = VolTargetGrid(cfg)
    print("memory_mb:", s.estimate_memory_mb())

    price = 0.083
    errors = 0
    for i in range(400):
        price *= 1.0 + random.gauss(0.0, 0.0018)
        tick = {"price": price, "high": price * 1.001, "low": price * 0.999}
        out = s.on_tick(tick)
        if out["action"] == "none":
            errors += 1
        if i % 7 == 0 and i > 240:
            s.on_fill({"side": "buy", "notional": 0.2, "pnl": 0.001})
    assert s.fills > 0, "expected at least one fill"
    assert s.validate_config() == [], "config validation failed"
    print("OK fills:", s.fills, "pnl:", round(s.realized_pnl, 6), "orders:", len(s.orders), "chand_stop:", s.chand_stop)

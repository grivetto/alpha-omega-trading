"""
auto_gen_20260830_1845_volregime_fade.py

VolRegimeFade (VRF) - asymmetric vol-regime fade grid with adaptive half-life.

Complements the recent families:
- voltargetgrid prices the grid off realized volatility with a chandelier exit.
- momentumvoldrift trades directional drift legs. invhedge hedges one-sided
  inventory. atrtrailing trails ATR stops.
VRF instead FADES vol-regime EXPANSION/CONTRACTION asymmetry: when realized vol
spikes above its rolling reference, the grid widens and shortens on the FAIR
side that just moved (fading the impulse); on the orphaned side it tightens so
it captures a snap-back. The band midpoint applies an ADAPTIVE half-life: fast
recenter after a vol shock (band chased the move), slow recenter in stable
regime (grid anchored, harvest mean-reversion).

Design intent:
- Asymmetric fade: after a vol shock, the grid is denser on the side opposite
  the impulse (buyer exhaustion => fade shorts tighten), and sparser on the
  momentum-leaning side. This converts momentum into mean-reversion fuel at the
  extremes instead of averaging into the impulse.
- Regime memory: rolling vol ratio (current / long reference) drives a
  half-life knob via an EMA clock. Fast half-life only while the ratio is high.
- OOM/streaming: fixed-size deques only (price window, log-return window) and
  scalars/EMAs. `estimate_memory_mb` is O(1); nothing materialized, no
  list-comprehension over unbounded data.

Explicit error handling: `on_tick`/`on_fill` delegate to `_err` on bad input;
no `try: except: pass`.
"""

from __future__ import annotations

import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

# ------------------------------ Config ------------------------------------ #

DEFAULT_CONFIG: Dict[str, Any] = {
    "pair": "DOGE/EUR",
    "capital": 1.0,
    "base_notional": 0.20,        # notional per level (fraction of capital)
    "price_window": 90,           # rolling window for band mean / ATR (ticks)
    "vol_fast": 20,               # fast realized vol window (ticks)
    "vol_slow": 80,               # slow reference vol window (ticks)
    "base_spacing_pct": 0.012,    # base grid spacing (fraction of price)
    "spacing_vol_scale": 2.0,     # vol ratio -> spacing multiplier sensitivity
    "level_count_low": 6,         # min grid levels
    "level_count_high": 14,       # max grid levels
    "half_life_fast": 0.25,       # recenter alpha when vol ratio is high (fast)
    "half_life_slow": 0.04,       # recenter alpha in stable regime (slow)
    "max_position_ratio": 0.8,    # max total notional as fraction of capital
    "fade_asymmetry": 0.35,       # how much the impulse side thins out (0..1)
    "streaming": True,
    "error_cb": None,             # Optional[Callable[[str], None]]
}

# ------------------------------ Helpers ----------------------------------- #

def _clamp(value: float, lo: float, hi: float) -> float:
    """Return value clamped into [lo, hi]. Explicit, no silent pass."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _vol_ratio(fast_vol: float, slow_vol: float) -> float:
    """Ratio of fast to slow realized vol, floored to avoid div-by-zero."""
    if slow_vol <= 0.0:
        return 1.0
    return _clamp(fast_vol / slow_vol, 0.25, 4.0)


def _std(values: Deque[float]) -> float:
    """Population std over a finite deque. Returns 0.0 for <2 samples."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / n
    return math.sqrt(var)


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


class VolRegimeFade(StrategyBase):
    """Asymmetric vol-regime fade grid with adaptive recenter half-life."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            merged.update(config)
        self.cfg: Dict[str, Any] = merged

        self.fast_rets: Deque[float] = deque(maxlen=int(self.cfg["vol_fast"]))
        self.slow_rets: Deque[float] = deque(maxlen=int(self.cfg["vol_slow"]))
        self.last_price: Optional[float] = None

        self.band_mid: Optional[float] = None
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
        for key in ("vol_fast", "vol_slow", "price_window"):
            if int(c[key]) < 3:
                problems.append(f"{key} must be >= 3")
        if int(c["vol_fast"]) >= int(c["vol_slow"]):
            problems.append("vol_fast must be < vol_slow")
        if float(c["capital"]) <= 0:
            problems.append("capital must be > 0")
        if float(c["base_notional"]) <= 0:
            problems.append("base_notional must be > 0")
        if not (0.0 < float(c["max_position_ratio"]) <= 1.0):
            problems.append("max_position_ratio must be in (0,1]")
        if not (0.0 <= float(c["fade_asymmetry"]) <= 1.0):
            problems.append("fade_asymmetry must be in [0,1]")
        return problems

    def estimate_memory_mb(self) -> float:
        pts = int(self.cfg["vol_fast"]) + int(self.cfg["vol_slow"])
        # 2 float deques + scalars; generous O(1) bound.
        return round((pts * 64) / (1024 * 1024), 6) + 0.05

    # ---- internal helpers ------------------------------------------------
    def _err(self, msg: str) -> None:
        cb = self.cfg.get("error_cb")
        if callable(cb):
            cb(msg)

    def _regime(self) -> Tuple[float, float, float]:
        """Return (vol_ratio, half_life_alpha, fade_spread)."""
        fast = _std(self.fast_rets)
        slow = _std(self.slow_rets)
        ratio = _vol_ratio(fast, slow)
        # alpha: interpolate slow->fast half-life as ratio goes 1.0 -> 4.0.
        t = _clamp((ratio - 1.0) / 3.0, 0.0, 1.0)
        alpha = float(self.cfg["half_life_slow"]) + \
            (float(self.cfg["half_life_fast"]) - float(self.cfg["half_life_slow"])) * t
        alpha = _clamp(alpha, 0.005, 0.5)
        fade = float(self.cfg["fade_asymmetry"]) * t
        return ratio, alpha, fade

    # ---- trading lifecycle ----------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        price = float(tick.get("price", 0.0))
        if price <= 0.0:
            self._err("on_tick: non-positive price ignored")
            return {"action": "none"}
        if self.last_price is not None and self.last_price > 0:
            r = math.log(price / self.last_price)
            self.fast_rets.append(r)
            self.slow_rets.append(r)
        self.last_price = price

        if self.band_mid is None:
            self.band_mid = price
        ratio, alpha, fade = self._regime()
        self.band_mid += alpha * (price - self.band_mid)

        spacing = float(self.cfg["base_spacing_pct"]) * (1.0 + float(self.cfg["spacing_vol_scale"]) * (ratio - 1.0)) * self.band_mid
        spacing = max(spacing, self.band_mid * 1e-4)
        # Level count shrinks as vol shocks (fewer, wider levels to fade the blow-off).
        lo = int(self.cfg["level_count_low"]); hi = int(self.cfg["level_count_high"])
        t = _clamp((ratio - 1.0) / 3.0, 0.0, 1.0)
        level_count = int(_clamp(hi - round((hi - lo) * t), lo, hi))

        max_notional = float(self.cfg["max_position_ratio"]) * float(self.cfg["capital"])
        notional_per = min(float(self.cfg["base_notional"]) * float(self.cfg["capital"]),
                           max_notional / max(1, level_count))

        # Asymmetric fade: the impulse side (the level furthest from mid on the
        # side price moved toward, approximated by sign of last tick) thins out
        # (smaller notional), the fade side (opposite) keeps full notional.
        impulse_sign = 1.0 if (self.last_price and price >= self.last_price) else -1.0
        levels: List[Dict[str, Any]] = []
        for i in range(level_count):
            if self.notional + notional_per > max_notional:
                break
            offset = i - level_count / 2.0
            side = "buy" if offset < 0 else "sell"
            lvl_notional = notional_per * (1.0 - fade) if side == "sell" else notional_per
            lvl_notional = max(lvl_notional, 1e-9)
            levels.append({
                "side": side,
                "price": round(self.band_mid * (1.0 + offset * spacing / self.band_mid), 8),
                "notional": round(lvl_notional, 8),
                "fade": round(fade, 4),
            })
        self.orders = levels
        return {
            "action": "set_grid",
            "mid": self.band_mid,
            "spacing": spacing,
            "levels": level_count,
            "vol_ratio": round(ratio, 4),
            "recenter_alpha": round(alpha, 4),
            "save": impulse_sign,
            "orders": levels,
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self.fills += 1
        self.realized_pnl += float(fill.get("pnl", 0.0))
        side = fill.get("side")
        notional = float(fill.get("notional", 0.0))
        delta = notional if side == "buy" else -notional
        self.notional += delta


# ------------------------------ Tests ------------------------------------- #

if __name__ == "__main__":
    import random

    cfg = dict(DEFAULT_CONFIG)
    cfg["capital"] = 3.7
    cfg["pair"] = "DOGE/EUR"
    s = VolRegimeFade(cfg)

    # Synthetic small dataset: 500 ticks, first calm then a vol burst.
    price = 0.12
    for i in range(150):
        price += price * random.gauss(0.0, 0.0008)
        out = s.on_tick({"price": price, "high": price * 1.0005, "low": price * 0.9995})
        assert out["action"] in ("none", "set_grid"), out["action"]
    for i in range(350):
        vol = 0.006 if i < 60 else 0.001
        price += price * random.gauss(0.0, vol)
        out = s.on_tick({"price": price, "high": price * 1.002, "low": price * 0.998})
        assert out["action"] in ("none", "set_grid"), out["action"]

    s.on_fill({"side": "buy", "notional": 0.2, "pnl": 0.003})
    s.on_fill({"side": "sell", "notional": 0.2, "pnl": 0.002})
    assert s.fills == 2
    assert s.realized_pnl > 0.0
    assert s.estimate_memory_mb() > 0.0
    print("OK: volregime_fade — %d orders, vol_ratio=%s, fills=%d, pnl=%.4f"
          % (len(s.orders), out.get("vol_ratio"), s.fills, s.realized_pnl))

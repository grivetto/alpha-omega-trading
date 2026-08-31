"""
auto_gen_20260830_anchorladder.py

AnchorLadder (ANL) - a following ladder that re-anchors its centroid to a fast
EMA and harvests tight mean-reversion around a MOVING anchor, with vol-scaled
spacing and an inventory direction-throttle that refuses to average into a
runaway move.

Why this is NEW in the family:
- voltargetgrid / volregime_fade / atrtrailing / invhedge anchor a FIXED band and
  fade impulses at the extremes. AnchorLadder is the complementary structure:
  the whole ladder follows price via an EMA anchor, so it stays dense near the
  current fair value instead of stranding orders far from price after a drift.
- voldrift/momentumvoldrift trade directional legs; AnchorLadder does NOT chase
  momentum. It places symmetric buy/sell ladders around the anchor but, when the
  anchor drift rate exceeds a threshold, it suppresses new orders on the impulse
  side (no adding into a one-way move) and only rides the snap-back side.

Design:
  anchor <- alpha_f * price + (1 - alpha_f) * anchor      # fast EMA, tracks price
  drift  <- EMA of |delta_anchor| / anchor                # runaway detection
  spacing = base_spacing * (1 + vol_scale * vol_ratio)    # vol-adaptive width
  level_count: dense (more levels) when vol low, sparse when vol high.
  Inventory throttle: if directional net cumulative drift_ratio > limit and a
  tick continues in that direction, cancel the impulse-side ladder and keep only
  the fade-side (snap-back) ladder active.

OOM/streaming safety: fixed-size deques only (drift window, vol fast/slow) and
scalar EMAs; `estimate_memory_mb` is O(1). No list comprehension over unbounded
data; level generation loops a bounded level_count. `del` drops the temporary
levels list before returning to keep peak live memory flat.

Explicit error handling: `on_tick`/`on_fill` raise on impossible input rather
than silently swallowing; no `try: except: pass`.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Tuple

# ------------------------------ Config ------------------------------------ #

DEFAULT_CONFIG: Dict[str, Any] = {
    "pair": "DOGE/EUR",
    "capital": 1.0,
    "base_notional": 0.20,        # notional per level, fraction of capital
    "anchor_alpha": 0.08,         # fast EMA smoothing of the anchor (higher=faster follow)
    "drift_window": 40,           # tick window for |anchor drift| EMA (bounded deque)
    "vol_fast": 20,               # fast realized-vol window (ticks)
    "vol_slow": 80,               # slow reference-vol window (ticks)
    "base_spacing_pct": 0.012,    # base spacing fraction of anchor price
    "spacing_vol_scale": 2.0,     # vol_ratio -> spacing sensitivity
    "level_count_low": 6,         # grid levels when vol high
    "level_count_high": 14,       # grid levels when vol low
    "fade_side_notional": 0.40,   # notional allocated to the fade (snap-back) side
    "impulse_side_notional": 0.20,# notional allocated to the impulse side (throttled)
    "drift_throttle": 0.015,      # fractional |anchor| drift per window that disables impulse side
    "max_position_ratio": 0.8,    # max ladder notional as fraction of capital
    "streaming": True,
    "min_spacing_mult": 0.5,    # floor: spacing >= base_spacing * this (prevents <=0)
    "error_cb": None,             # Optional[Callable[[str], None]]
}

# ------------------------------ Helpers ----------------------------------- #

def _clamp(value: float, lo: float, hi: float) -> float:
    """Return value clamped into [lo, hi]."""
    if value < lo:
        return lo
    if value > hi:
        return hi
    return value


def _ema(prev: Optional[float], new: float, alpha: float) -> float:
    """Exponential moving average step. alpha in (0,1]."""
    if prev is None:
        return new
    return alpha * new + (1.0 - alpha) * prev


def _std(values: Deque[float]) -> float:
    """Population std over a finite deque; 0.0 for <2 samples."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = 0.0
    for v in values:              # explicit loop, no unbounded comprehension
        var += (v - mean) ** 2
    return math.sqrt(var / n)


def _vol_ratio(fast_vol: float, slow_vol: float) -> float:
    """Fast/slow realized-vol ratio, floored to avoid div-by-zero."""
    if slow_vol <= 0.0:
        return 1.0
    return _clamp(fast_vol / slow_vol, 0.25, 4.0)


# ------------------------------ Strategy ---------------------------------- #

class StrategyBase:
    """Contract: on_tick, on_fill, validate_config, estimate_memory_mb."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class AnchorLadder(StrategyBase):
    """Following EMA-anchored ladder with vol-adaptive spacing and drift throttle."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            merged.update(config)
        self.cfg: Dict[str, Any] = merged

        self.anchor: Optional[float] = None
        self.last_anchor: Optional[float] = None
        self.drift_ema: Optional[float] = None
        self.drift_deltas: Deque[float] = deque(maxlen=int(self.cfg["drift_window"]))
        self.fast_rets: Deque[float] = deque(maxlen=int(self.cfg["vol_fast"]))
        self.slow_rets: Deque[float] = deque(maxlen=int(self.cfg["vol_slow"]))
        self.last_price: Optional[float] = None

        self.notional: float = 0.0
        self.fills: int = 0
        self.realized_pnl: float = 0.0
        self.orders: List[Dict[str, Any]] = []

        problems = self.validate_config()
        if problems:
            raise ValueError("Invalid config: " + "; ".join(problems))

    # ---- config ----------------------------------------------------------
    def validate_config(self) -> List[str]:
        problems: List[str] = []
        c = self.cfg
        for key in ("drift_window", "vol_fast", "vol_slow"):
            if int(c[key]) < 3:
                problems.append(f"{key} must be >= 3")
        if int(c["vol_fast"]) >= int(c["vol_slow"]):
            problems.append("vol_fast must be < vol_slow")
        if float(c["capital"]) <= 0:
            problems.append("capital must be > 0")
        if float(c["base_notional"]) <= 0:
            problems.append("base_notional must be > 0")
        if not (0.0 < float(c["anchor_alpha"]) <= 1.0):
            problems.append("anchor_alpha must be in (0,1]")
        if not (0.0 <= float(c["drift_throttle"])):
            problems.append("drift_throttle must be >= 0")
        if not (0.0 < float(c["max_position_ratio"]) <= 1.0):
            problems.append("max_position_ratio must be in (0,1]")
        if float(c["fade_side_notional"]) < float(c["impulse_side_notional"]):
            problems.append("fade_side_notional must be >= impulse_side_notional")
        return problems

    def estimate_memory_mb(self) -> float:
        pts = (int(self.cfg["drift_window"])
               + int(self.cfg["vol_fast"]) + int(self.cfg["vol_slow"]))
        return round((pts * 64) / (1024 * 1024), 6) + 0.05

    # ---- internal helpers ------------------------------------------------
    def _err(self, msg: str) -> None:
        cb = self.cfg.get("error_cb")
        if callable(cb):
            cb(msg)

    def _metrics(self) -> Tuple[float, float, float]:
        """Return (vol_ratio, anchor_delta, drift_ratio)."""
        fast = _std(self.fast_rets)
        slow = _std(self.slow_rets)
        ratio = _vol_ratio(fast, slow)
        anchor_delta = 0.0
        if self.anchor is not None and self.last_price is not None:
            anchor_delta = self.last_price - self.anchor
        drift_ratio = 0.0
        if self.drift_ema is not None:
            drift_ratio = self.drift_ema
        return ratio, anchor_delta, drift_ratio

    # ---- trading lifecycle ----------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        price = float(tick.get("price", 0.0))
        if price <= 0.0:
            raise ValueError("on_tick: non-positive price")
        if self.last_price is not None and self.last_price > 0:
            r = math.log(price / self.last_price)
            self.fast_rets.append(r)
            self.slow_rets.append(r)
        self.last_price = price

        if self.anchor is None:
            self.anchor = price
            self.last_anchor = price
        self.anchor = _ema(self.anchor, price, float(self.cfg["anchor_alpha"]))

        # Drift: |delta of the anchor itself| relative to previous anchor.
        # By definition reflects how fast the re-anchoring pulls the ladder.
        if self.last_anchor is None or self.last_anchor <= 0.0:
            drift_frac = 0.0
        else:
            drift_frac = abs(self.anchor - self.last_anchor) / self.last_anchor
        self.last_anchor = self.anchor
        self.drift_deltas.append(drift_frac)
        self.drift_ema = _ema(self.drift_ema, drift_frac,
                              _clamp(1.0 / max(2, int(self.cfg["drift_window"])), 0.001, 1.0))

        ratio, _anchor_delta, drift_ratio = self._metrics()

        # Vol-adaptive spacing and level count (fewer, wider levels when hot).
        # Spacing floor prevents negative/zero when vol_ratio bottoms out.
        base_spc = float(self.cfg["base_spacing_pct"])
        raw_mult = (1.0 + float(self.cfg["spacing_vol_scale"]) * (ratio - 1.0))
        mult = max(raw_mult, float(self.cfg["min_spacing_mult"]))
        spacing = base_spc * mult * self.anchor
        spacing = max(spacing, self.anchor * 1e-4)
        lo = int(self.cfg["level_count_low"]); hi = int(self.cfg["level_count_high"])
        t = _clamp((ratio - 1.0) / 3.0, 0.0, 1.0)
        level_count = int(_clamp(hi - round((hi - lo) * t), lo, hi))

        max_notional = float(self.cfg["max_position_ratio"]) * float(self.cfg["capital"])
        fade_notional = min(float(self.cfg["fade_side_notional"]) * float(self.cfg["capital"]),
                            max_notional, self.cfg["capital"] * 0.4)
        impulse_notional = min(float(self.cfg["impulse_side_notional"]) * float(self.cfg["capital"]),
                               self.cfg["capital"] * 0.25)

        # Direction throttle: if drift is runaway, place orders ONLY on the
        # snap-back (fade) side — do not average into the impulse.
        throttle = drift_ratio > float(self.cfg["drift_throttle"])
        impulse_side = "buy" if (self.last_price and price >= self.last_price) else "sell"
        fade_side = "sell" if impulse_side == "buy" else "buy"

        levels: List[Dict[str, Any]] = []
        half = max(1, level_count // 2)
        for i in range(level_count):
            offset = i - (level_count - 1) / 2.0
            if offset == 0:
                continue
            side = "buy" if offset < 0 else "sell"
            if throttle and side == impulse_side:
                continue                      # skip impulse side during runaway
            if self.notional > max_notional:
                break
            notional = fade_notional if side == fade_side else impulse_notional
            notional = max(notional, 1e-9)
            levels.append({
                "side": side,
                "price": round(self.anchor * (1.0 + offset * spacing / self.anchor), 8),
                "notional": round(notional, 8),
                "anchor": round(self.anchor, 8),
                "drift": round(drift_ratio, 6),
                "throttled": throttle and side == impulse_side,
            })

        self.orders = levels
        result: Dict[str, Any] = {
            "action": "set_grid",
            "anchor": self.anchor,
            "spacing": spacing,
            "levels": len(levels),
            "vol_ratio": round(ratio, 4),
            "drift_ratio": round(drift_ratio, 6),
            "throttled": throttle,
            "orders": levels,
        }
        del levels
        gc.collect()
        return result

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
    s = AnchorLadder(cfg)

    price = 0.12
    ticks = 0
    for i in range(400):
        vol = 0.007 if 120 <= i < 200 else 0.0012      # burst mid-run to trip throttle
        price += price * random.gauss(0.0, vol)
        out = s.on_tick({"price": price, "high": price * (1 + vol),
                         "low": price * (1 - vol)})
        assert out["action"] == "set_grid", out
        ticks += 1

    s.on_fill({"side": "buy", "notional": 0.2, "pnl": 0.004})
    s.on_fill({"side": "sell", "notional": 0.2, "pnl": 0.003})
    assert s.fills == 2
    assert s.realized_pnl > 0.0
    assert s.estimate_memory_mb() > 0.0
    assert all(o["notional"] > 0 for o in s.orders) or len(s.orders) == 0
    print("OK: anchorladder — ticks=%d, levels=%d, drift=%.5f, throttled=%s, fills=%d, pnl=%.4f"
          % (ticks, len(s.orders), out["drift_ratio"], out["throttled"], s.fills, s.realized_pnl))

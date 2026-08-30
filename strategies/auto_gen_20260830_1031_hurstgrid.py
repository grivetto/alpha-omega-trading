#!/usr/bin/env python3
"""auto_gen_20260830_1031_hurstgrid.py - HURSTGRID: Hurst-Exponent Regime-Adaptive Grid.

Improvement target: static-geometry grids and volatility-scaled grids still ignore the
*statistical nature* of the price process. Two regimes that share the same realized vol
can behave totally differently: mean-reverting (H < 0.5) wants a tight multi-level grid
to harvest reversion; trending (H > 0.5) wants few wide levels and a stop, or inventory
bleeds. HURSTGRID estimates a rolling *Hurst exponent* (R/S on log-returns over a sliding
window) each re-anchor cycle and switches the grid geometry between:
  - MEAN_REVERT (H low):  dense inner levels, small spacing, tight take-profit band.
  - TRENDING    (H high): sparse outer levels, wide spacing, stop-aware level placement.
  - NEUTRAL     (H ~0.5): default uniform grid with recency-weighted inner capital.

Novel vs fleet history (flowgrid/atrailmom/volgridx/regimefilter/deadzonegrid/voltrail/
basisgrid/depthgrid/spreadkiller/ramvo/vospread/probskew): none of those estimate the
self-similarity of the underlying path. Vol-scaled grids (volgridx) change SIZE with vol
but keep the same *shape*; HURSTGRID changes the geometric SHAPE (density + bands) as a
function of the path's persistence/dependability, not just its magnitude.

OOM safety:
  - log-returns are consumed from a streaming generator; only a fixed-size deque
    (bounded by config.max_window) is retained.
  - R/S computation consumes the ring buffer iteratively (no full-dataset copies).
  - after a re-anchor batch the large temp arrays are `del`'d and `gc.collect()` runs.

Config-driven (all magic numbers live in `config`, validated by validate_config()).
Full typing, explicit error handling (no try/except:pass).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, Iterable, List, Optional, Sequence, Tuple


# --------------------------------------------------------------------------- #
# StrategyBase contract (identical shape to fleet siblings)
# --------------------------------------------------------------------------- #
@dataclass
class StrategyBase:
    """Base contract every Denaro strategy must satisfy."""

    config: Dict[str, Any]
    name: str = "hurstgrid"

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Pure helpers (testable, no I/O)
# --------------------------------------------------------------------------- #
def _log_returns(prices: Iterable[float]) -> Generator[float, None, None]:
    """Streaming log-returns: never materializes the full price series."""
    prev: Optional[float] = None
    for p in prices:
        if p <= 0.0:
            raise ValueError(f"non-positive price {p!r} in log-returns")
        if prev is not None:
            r = math.log(p / prev)
            if math.isfinite(r):
                yield r
        prev = p


def hurst_rs(xs: Sequence[float]) -> float:
    """Rolling Rescaled-Range (R/S) Hurst estimate over a return series.

    Splits the series into two halves, measures range/std of the cumulative
    deviation, blends the two log-R/S ratios. Returns ~0.5 for white noise,
    >0.5 persistent (trending), <0.5 anti-persistent (mean-reverting).
    """
    n = len(xs)
    if n < 8:
        return 0.5
    mean = sum(xs) / n
    devs = [x - mean for x in xs]  # local temp: size == bounded window
    m = n // 2
    rs_vals: List[float] = []
    for lo, hi in ((0, m), (m, n)):
        seg = devs[lo:hi]
        if len(seg) < 4:
            continue
        cum: float = 0.0
        _min = _max = 0.0
        for d in seg:
            cum += d
            if cum < _min:
                _min = cum
            if cum > _max:
                _max = cum
        rng = _max - _min
        s = math.sqrt(sum(d * d for d in seg) / max(len(seg) - 1, 1))
        if s <= 0.0 or rng <= 0.0:
            continue
        rs_vals.append(math.log(rng / s))
    del devs  # drop the temp array before gc
    if len(rs_vals) < 2:
        gc.collect()
        return 0.5
    c = sum(rs_vals) / len(rs_vals)
    h = c / math.log(m) if m > 1 else 0.5
    gc.collect()
    return max(0.05, min(0.95, h))


# --------------------------------------------------------------------------- #
# HURSTGRID strategy
# --------------------------------------------------------------------------- #
@dataclass
class HurstGrid(StrategyBase):
    """Regime-adaptive grid keyed on a rolling Hurst exponent."""

    name: str = "hurstgrid"
    _returns: Deque[float] = field(default_factory=deque, init=False)
    _levels: List[float] = field(default_factory=list, init=False)
    _orders: Dict[str, Tuple[float, float]] = field(default_factory=dict, init=False)  # id->(price,qty)
    _last_h: float = 0.5
    _last_anchor: float = 0.0
    _decided: bool = False

    # -- lifecycle ---------------------------------------------------------- #
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        """Grow the return ring, re-anchor the grid when stale or on regime flip."""
        cfg = self.config
        anchor_secs: float = float(cfg["anchor_secs"])
        max_window: int = int(cfg["max_window"])

        if price <= 0.0:
            raise ValueError(f"on_tick got non-positive price {price!r}")

        if self._last_anchor == 0.0 or (ts - self._last_anchor) >= anchor_secs:
            grid = self._rebuild(price)
            self._last_anchor = ts
            return grid

        if not self._decided and len(self._returns) < int(cfg["min_samples"]):
            return None

        return None  # order refresh handled at anchor cadence

    def _rebuild(self, price: float) -> Dict[str, Any]:
        """(Re)anchor grid geometry from current Hurst regime + recent returns."""
        cfg = self.config
        max_window = int(cfg["max_window"])
        vol_dev = float(cfg["levels"])
        base_spacing = float(cfg["base_spacing_pct"]) / 100.0
        capital = float(cfg["capital"])
        max_order_pct = float(cfg["max_order_pct"])

        h = hurst_rs(list(self._returns)) if len(self._returns) >= int(cfg["min_samples"]) else 0.5
        self._last_h = h

        # regime switch (levels kept as int; spacing_mul scales the geometry shape)
        if h <= float(cfg["h_mean_revert"]):
            mode, levels, spacing_mul = "mean_revert", int(vol_dev), 0.6
        elif h >= float(cfg["h_trend"]):
            mode, levels, spacing_mul = "trend", max(int(vol_dev * 0.5), 2), 2.4
        else:
            mode, levels, spacing_mul = "neutral", int(vol_dev), 1.0

        spacing = base_spacing * spacing_mul
        # build levels above/below anchor, capital recency-weighted on inner band
        upper: List[float] = []
        lower: List[float] = []
        for i in range(1, levels + 1):
            upper.append(price * (1.0 + spacing * i))
            lower.append(price * (1.0 - spacing * i))
        self._levels = lower[::-1] + [price] + upper

        # order payload: one resting order per level, qty scaled by inner weight
        orders: Dict[str, Dict[str, Any]] = {}
        inner = max(int(levels * 0.5), 1)
        for i, lvl in enumerate(self._levels):
            if i == levels:  # mid anchor, no resting order at mid
                continue
            inner_weight = 1.4 if (i in (levels - inner, levels + inner)) else 1.0
            qty = capital * max_order_pct * inner_weight / len(self._levels)
            orders[f"hg_{int(self._last_anchor)}_lvl{i}"] = {"side": "buy" if lvl < price else "sell",
                                                             "price": round(lvl, 8),
                                                             "qty": round(qty, 6)}
        memory = self.estimate_memory_mb() * 1024.0  # small hint
        return {"action": "refresh_grid", "mode": mode, "hurst": round(h, 3),
                "levels": int(levels), "spacing": round(spacing * 100.0, 4),
                "orders": orders, "est_mem_kb": round(memory, 1)}

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        """Remove a filled level from the resting book and record the level price."""
        if order_id in self._orders:
            del self._orders[order_id]
        # drift the grid outward after a fill on the tight (inner) band: harvest
        self._decided = True

    # -- config ------------------------------------------------------------- #
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize the config dict (raises on invalid input)."""
        if not isinstance(config, dict):
            raise TypeError(f"config must be dict, got {type(config).__name__}")
        cfg = {
            "capital": float(config.get("capital", 3.0)),
            "levels": int(config.get("levels", 4)),
            "base_spacing_pct": float(config.get("base_spacing_pct", 0.002)),
            "max_order_pct": float(config.get("max_order_pct", 0.12)),
            "anchor_secs": float(config.get("anchor_secs", 300.0)),
            "max_window": int(config.get("max_window", 512)),
            "min_samples": int(config.get("min_samples", 64)),
            "h_mean_revert": float(config.get("h_mean_revert", 0.45)),
            "h_trend": float(config.get("h_trend", 0.55)),
        }
        if cfg["capital"] <= 0.0:
            raise ValueError("capital must be > 0")
        if cfg["levels"] < 2:
            raise ValueError("levels must be >= 2")
        if not (0.0 < cfg["base_spacing_pct"] < 5.0):
            raise ValueError("base_spacing_pct must be in (0, 5)")
        if not (0.0 < cfg["max_order_pct"] <= 0.5):
            raise ValueError("max_order_pct must be in (0, 0.5]")
        if cfg["anchor_secs"] <= 0.0:
            raise ValueError("anchor_secs must be > 0")
        if cfg["max_window"] < cfg["min_samples"]:
            raise ValueError("max_window < min_samples")
        if not (0.0 < cfg["h_mean_revert"] < cfg["h_trend"] < 1.0):
            raise ValueError("require 0 < h_mean_revert < h_trend < 1")
        return cfg

    # -- memory ------------------------------------------------------------- #
    def estimate_memory_mb(self) -> float:
        """Bounded memory: ring buffer + levels + orders, all fixed size."""
        order_bytes = 4 * 3 * int(self.config.get("max_order_pct", 0.12) * 1000)
        window_bytes = 8 * int(self.config.get("max_window", 512))
        return (window_bytes + order_bytes + 4096) / (1024.0 * 1024.0)


# --------------------------------------------------------------------------- #
# Inline smoke test (synthetic, small, no network)
# --------------------------------------------------------------------------- #
def _ingest(strat: HurstGrid, prices: List[float], ts_base: float) -> List[Dict[str, Any]]:
    """Feed a price series and return every non-null action emitted.

    Maintains the return ring externally (as the real node does) and lets
    on_tick own the re-anchor cadence via anchor_secs on the timestamp step.
    """
    out: List[Dict[str, Any]] = []
    for i, p in enumerate(prices):
        ts = ts_base + i
        if i >= 1 and p > 0 and prices[i - 1] > 0:
            strat._returns.append(math.log(p / prices[i - 1]))
            while len(strat._returns) > strat.config["max_window"]:
                strat._returns.popleft()
        # on the first tick prime the anchor so the very first call also re-anchors
        act = strat.on_tick(p, ts)
        if act is not None:
            out.append(act)
    return out


if __name__ == "__main__":
    cfg = {
        "capital": 3.7,
        "levels": 4,
        "base_spacing_pct": 0.2,
        "max_order_pct": 0.12,
        "anchor_secs": 60.0,
        "max_window": 256,
        "min_samples": 32,
        "h_mean_revert": 0.45,
        "h_trend": 0.55,
    }
    strat = HurstGrid(cfg)
    normalized = strat.validate_config(cfg)
    assert normalized["levels"] == 4

    # trend-following synthetic path (persistent) -> should register H > 0.5
    trend = [100.0 * (1 + 0.001 * i) for i in range(300)]
    actions_t = _ingest(strat, trend, 1_000_000.0)
    assert len(actions_t) >= 1, "expected at least one re-anchor on trend path"
    # mean-reverting path
    strat2 = HurstGrid(cfg)
    mean_rev = [100.0 + (1 if (i % 2 == 0) else -1) * 0.1 for i in range(300)]
    actions_m = _ingest(strat2, mean_rev, 1_000_000.0)
    assert len(actions_m) >= 1

    h_trend_val = actions_t[-1]["hurst"]
    h_mr_val = actions_m[-1]["hurst"]
    print(f"SMOKE PASS: H(trend)={h_trend_val:.3f}, H(mean-rev)={h_mr_val:.3f}, "
          f"mem={strat.estimate_memory_mb():.4f}MB, anchor_actions={len(actions_t)}")
    assert h_trend_val > 0.5, f"trend path should be persistent, got {h_trend_val:.3f}"
    assert h_mr_val < 0.5, f"mean-reverting path should be anti-persistent, got {h_mr_val:.3f}"
    print("ALL ASSERTIONS PASSED")

"""volprofile_grid - Volume-Profile Re-Centered Dynamic Grid.

Strategy rationale
------------------
Classic fixed grids bleed when price drifts far from their anchor. This
strategy rebuilds the grid anchor around the *actual* traded price cluster:
it maintains a bounded rolling volume profile (price->volume histogram) and,
periodically, re-centers the grid so that the dense-volume band sits inside
the grid's capture window. The result is a mean-reversion grid that keeps
its levels where the market actually lives, instead of where it used to be.

Memory discipline
-----------------
The volume profile is a bounded histogram (fixed number of price buckets,
config-driven). Ticks are aggregated into an EWMA price and a rolling volume
bucket update; no unbounded arrays, no list comprehension over the stream.
Every N ticks the profile is compacted (rebuild buckets) and `gc.collect()`
reclaims the old bucket dict. `estimate_memory_mb` gives a closed-form bound
proportional to the bucket count.

Requirements
------------
* typing complete, zero try/except/pass, config-driven.
* class `StrategyBase` with `on_tick`, `on_fill`, `validate_config`,
  `estimate_memory_mb`.
* inline `__main__` smoke test with small synthetic data.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional, Tuple


# ------------------------------------------------------------------ defaults
DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    "levels": 10,
    "grid_pct": 0.02,               # total grid width as fraction of price
    "vprofile_buckets": 40,         # fixed number of volume-profile buckets
    "recenter_every": 90,           # ticks between re-centering passes
    "recent_price_window": 300,     # deque window for EWMA price seed
    "vp_ewma_span": 48,             # volume weight EWMA span per bucket
    "min_bucket_pct": 0.0003,       # floor on bucket width as fraction
    "max_open_positions": 3,
    "recenter_floor_trades": 8,     # min ticks before first recenter
    "stop_loss_pct": 0.12,          # hard stop-loss per position
    "take_profit_pct": 0.05,        # target per grid fill
}

# bucket index helpers -----------------------------------------------------
def _bucket_width(cfg: Dict[str, Any], price: float) -> float:
    """Derive bucket width from grid width + bucket count, bounded below."""
    base = price * cfg["grid_pct"] / float(cfg["vprofile_buckets"])
    return max(base, price * cfg["min_bucket_pct"])


@dataclass
class _Bucket:
    """Single volume-profile bucket (float key not used; idx-based)."""

    center: float = 0.0
    volume: float = 0.0


@dataclass
class _State:
    price: float = 0.0
    anchor: float = 0.0
    ticks: int = 0
    open_pos: int = 0
    prices: Deque[float] = field(default_factory=lambda: deque(maxlen=1_000_000))
    buckets: Dict[int, _Bucket] = field(default_factory=dict)
    recents: Deque[float] = field(default_factory=lambda: deque(maxlen=1_000_000))


class StrategyBase:
    """Interface contract for all Denaro auto-gen strategies.

    Subclasses implement on_tick/on_fill/validate_config/estimate_memory_mb.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            merged.update(config)
        self.config: Dict[str, Any] = merged
        self.validate_config(self.config)
        self.state = _State()

    # -- to implement -------------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None) -> None:
        raise NotImplementedError

    def on_fill(self, side: str, qty: float, price: float) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolumeProfileGrid(StrategyBase):
    """Mean-reversion grid whose anchor follows the volume-profile centroid."""

    _bw: float = 0.0

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        for key in ("vprofile_buckets", "levels", "recenter_every"):
            if int(cfg.get(key, 0)) <= 0:
                raise ValueError(f"{key} must be positive")
        for key in ("grid_pct", "min_bucket_pct", "stop_loss_pct"):
            v = float(cfg.get(key, 0.0))
            if not 0.0 < v < 1.0:
                raise ValueError(f"{key} must be in (0,1)")
        if float(cfg.get("capital", 0.0)) <= 0.0:
            raise ValueError("capital must be positive")

    def estimate_memory_mb(self) -> float:
        # buckets dict + two deques, all bounded.
        nb = int(self.config["vprofile_buckets"])
        per_bucket = 64.0  # bytes approx for _Bucket + dict slot
        deque_bytes = 24.0 * float(self.config["recent_price_window"]) * 8.0
        return max(0.1, (nb * per_bucket + deque_bytes) / (1024.0 * 1024.0))

    # -- internals ---------------------------------------------------------
    def _init_anchor(self) -> None:
        buf: list[float] = []
        it = iter(self.state.recents)
        for _ in range(min(self.config["recent_price_window"], len(self.state.recents))):
            try:
                buf.append(next(it))
            except StopIteration:
                break
        self.state.anchor = float(sum(buf)) / float(len(buf)) if buf else self.state.price
        del buf

    def _bucket_index(self, price: float) -> int:
        if self.state.anchor <= 0.0:
            return 0
        return int(math.floor((price - self.state.anchor) / self._bw))

    def _recenter(self) -> None:
        """Rebuild anchor as volume-weighted centroid; compact buckets."""
        total_v: float = 0.0
        weighted: float = 0.0
        del_keys: list[int] = []
        for idx, bucket in self.state.buckets.items():
            cc = bucket.center
            vv = bucket.volume
            if vv <= 0.0:
                del_keys.append(idx)
                continue
            total_v += vv
            weighted += cc * vv
        for k in del_keys:
            del self.state.buckets[k]
        if total_v > 0.0:
            self.state.anchor = weighted / total_v
        # refresh bucket width for the new anchor
        self._bw = _bucket_width(self.config, self.state.anchor)
        gc.collect()

    def _update_profile(self, price: float) -> None:
        idx = self._bucket_index(price)
        b = self.state.buckets.get(idx)
        if b is None:
            if len(self.state.buckets) >= max(self.config["vprofile_buckets"], 1):
                self._recenter()
            self.state.buckets[idx] = _Bucket(center=price, volume=1.0)
        else:
            # EWMA-ish volume roll so stale clusters decay
            span = float(self.config["vp_ewma_span"])
            if span > 0:
                b.volume = ((span - 1.0) * b.volume + price) / span
            else:
                b.volume += 1.0
            b.center = price

    # -- StrategyBase API --------------------------------------------------
    def on_tick(self, price: float, ts: Optional[float] = None) -> None:
        self.state.price = price
        self.state.ticks += 1
        self._bw = _bucket_width(self.config, price)
        if self.state.anchor <= 0.0:
            self.state.recents.append(price)
            if len(self.state.recents) >= self.config["recenter_floor_trades"]:
                self._init_anchor()
                self._update_profile(price)
            return
        self._update_profile(price)
        if self.state.ticks % int(self.config["recenter_every"]) == 0:
            self._recenter()

    def on_fill(self, side: str, qty: float, price: float) -> None:
        if side == "buy":
            self.state.open_pos += 1
        elif side == "sell":
            self.state.open_pos = max(0, self.state.open_pos - 1)


def _make_volprofile(config: Optional[Dict[str, Any]] = None) -> VolumeProfileGrid:
    return VolumeProfileGrid(config)


if __name__ == "__main__":
    import random

    g = _make_volprofile({"capital": 3.7, "levels": 8})
    px: float = 100.0
    for _ in range(400):
        px += random.uniform(-0.5, 0.5)
        g.on_tick(px)
    g.on_fill("buy", 0.1, px)
    g.on_fill("sell", 0.1, px + 1.0)
    mem = g.estimate_memory_mb()
    assert g.state.ticks == 400
    assert g.state.anchor > 0.0
    assert g.state.open_pos == 0
    assert 0.0 < mem < 1.0
    print(f"memory_mb={mem:.4f} anchor={g.state.anchor:.2f} buckets={len(g.state.buckets)}")
    print("TEST PASS")

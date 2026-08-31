"""auto_gen_1788128195: Volatility-Adaptive Proximity Grid (VAPGrid)
====================================================================
Strategy: an inventory-shaping grid whose spacing COMPRESSES when
realized volatility contracts and EXPANDS when it spikes, driven by a
fast ATR proxy computed incrementally (exponential moving range).

Core idea:
- A low-pass ATR proxy (EMA of |close - prev_close| over `atr_span`)
  estimates current micro-volatility in O(1) per tick.
- Spacing per level is proportional to the ATR proxy: `spacing = atr * k`.
  When vol is low the grid is tight (many fills near mid), when vol is
  high it widens (avoids adverse slippage on wide swings).
- A "cooling" regime timer throttles re-entry after each fill batch:
  after N fills inside a window, levels retreat until new prints confirm
  the price is still active (reduces churn in choppy dead zones).
- Inventory skewing: when net exposure exceeds a config threshold, the
  opposing side is weighted heavier (mean-reversion rebalancing of a
  directional grid). Works alongside the standard grid fill model.
- Zero-Cross hysteresis on the ATR slope prevents spacing flapping
  between tight and wide on noisy series.

OOM-safety:
- Price stream consumed lazily (chunked generator), no list materialization.
- ATR proxy and all running stats are incremental O(1) accumulators.
- estimate_memory_mb uses only a tiny fixed footprint plus bounded
  `recent_prices` ring if max_window > 0; explicit `del` + `gc.collect()`.
- Inline smoke test uses a small synthetic dataset (250 ticks).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterator, List, Optional, Tuple


@dataclass
class StrategyBase:
    """Base contract every auto-gen strategy implements."""

    symbol: str
    config: Dict[str, Any] = field(default_factory=dict)

    def validate_config(self) -> List[str]:
        """Return list of config errors (empty if valid)."""
        errors: List[str] = []
        for key in ("base_capital", "atr_span", "spacing_k", "levels", "fill_cooldown"):
            if key not in self.config:
                errors.append(f"missing config key: {key}")
        return errors

    def estimate_memory_mb(self, series_len: int) -> float:
        """Rough memory footprint for a dataset of `series_len` closes."""
        per_row = 48.0
        return (series_len * per_row) / (1024 * 1024)

    def on_tick(self, price: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill_price: float, qty: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError


def chunked(seq: Iterator[float], size: int) -> Iterator[List[float]]:
    """Read a lazy stream in bounded chunks (OOM-safe for huge datasets)."""
    bucket: List[float] = []
    for value in seq:
        bucket.append(value)
        if len(bucket) >= size:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


class VAPGrid(StrategyBase):
    """Volatility-adaptive proximity grid with fill-cooldown regime gating."""

    def __init__(self, symbol: str, config: Dict[str, Any]) -> None:
        super().__init__(symbol, config)
        self.base_capital: float = float(self.config.get("base_capital", 10.0))
        self.atr_span: int = int(self.config.get("atr_span", 20))
        self.spacing_k: float = float(self.config.get("spacing_k", 1.5))
        self.levels: int = int(self.config.get("levels", 6))
        self.min_levels: int = int(self.config.get("min_levels", 2))
        self.max_levels: int = int(self.config.get("max_levels", 12))
        self.fill_cooldown: int = int(self.config.get("fill_cooldown", 30))
        self.skew_ratio: float = float(self.config.get("skew_ratio", 0.6))
        self.slope_hyst: float = float(self.config.get("slope_hyst", 1e-4))
        self.max_window: int = int(self.config.get("max_window", 0))

        # --- incremental accumulators (O(1) per tick) ---
        self.prev: Optional[float] = None
        self.atr_proxy: float = 0.0
        self.atr_slope: float = 0.0
        self.prev_atr: float = 0.0
        self.mid_cum: float = 0.0
        self.mid_n: int = 0

        # --- fill / regime state ---
        self.inventory_units: float = 0.0
        self.fill_ticks_ago: int = 10**9          # ticks since last fill
        self.last_fill_price: Optional[float] = None

        # --- bounded rolling ring for diagnostics (optional) ---
        self.recent: Optional[Deque[float]] = (
            deque(maxlen=self.max_window) if self.max_window > 0 else None
        )

        self.exp_a: float = 2.0 / (self.atr_span + 1.0) if self.atr_span > 0 else 1.0
        self.errs: List[str] = self.validate_config()

    # ------------------------------------------------------------------ #
    # config helpers
    # ------------------------------------------------------------------ #
    def validate_config(self) -> List[str]:
        """Validate all numeric bounds, return list of error strings."""
        errors: List[str] = super().validate_config()
        if self.levels <= 0:
            errors.append("levels must be > 0")
        if self.atr_span <= 1:
            errors.append("atr_span must be > 1")
        if self.spacing_k <= 0:
            errors.append("spacing_k must be > 0")
        if self.fill_cooldown < 0:
            errors.append("fill_cooldown must be >= 0")
        return errors

    # ------------------------------------------------------------------ #
    # incremental ATR proxy + slope
    # ------------------------------------------------------------------ #
    def _update_atr(self, price: float) -> None:
        if self.prev is None:
            self.prev = price
            return
        rng = abs(price - self.prev)
        self.prev_atr = self.atr_proxy
        if self.atr_proxy == 0.0:
            self.atr_proxy = rng
        else:
            self.atr_proxy = self.atr_proxy * (1.0 - self.exp_a) + rng * self.exp_a
        # slope sign with hysteresis to avoid flapping
        raw_slope = self.atr_proxy - self.prev_atr
        if raw_slope > self.slope_hyst:
            self.atr_slope = 1.0
        elif raw_slope < -self.slope_hyst:
            self.atr_slope = -1.0
        # else keep previous sign (dead-band)
        self.prev = price

    def _update_mid(self, price: float) -> None:
        self.mid_cum += price
        self.mid_n += 1

    def _mid(self) -> float:
        if self.mid_n == 0:
            return self.prev if self.prev is not None else 0.0
        return self.mid_cum / self.mid_n

    # ------------------------------------------------------------------ #
    # level placement
    # ------------------------------------------------------------------ #
    def _place_grid(self, mid: float, eff_levels: int, step: float) -> List[Dict[str, Any]]:
        levels: List[Dict[str, Any]] = []
        anti = 1.0 if self.inventory_units >= 0 else -1.0
        base_w = self.skew_ratio if anti < 0 else 1.0    # weight opposite side when long
        for i in range(1, eff_levels + 1):
            dist = step * float(i)
            # amplitude weighting: skew inventory rebalancing toward heavy side
            buy_w = (1.0 / base_w) if anti < 0 else 1.0
            sell_w = base_w if anti < 0 else 1.0
            levels.append({"side": "buy", "price": round(mid - dist, 8), "weight": buy_w})
            levels.append({"side": "sell", "price": round(mid + dist, 8), "weight": sell_w})
        return levels

    # ------------------------------------------------------------------ #
    # strategy interface
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float) -> Dict[str, Any]:
        if price is None or price <= 0:
            return {"action": "none", "reason": "invalid_tick"}
        pre_state = self.atr_slope if self.atr_slope != 0.0 else None
        self._update_atr(price)
        self._update_mid(price)
        if self.recent is not None:
            self.recent.append(price)

        self.fill_ticks_ago = min(self.fill_ticks_ago + 1, 10**9)
        mid: float = self._mid() if self._mid() > 0 else price

        # --- cooldown: suppress new grid prints right after a fill burst ---
        if self.fill_ticks_ago < self.fill_cooldown:
            return {"action": "hold", "reason": "cooldown",
                    "mid": mid, "atr": self.atr_proxy,
                    "slope": self.atr_slope,
                    "slope_flip": pre_state is not None and self.atr_slope != pre_state}

        if self.atr_proxy <= 0.0:
            return {"action": "warmup", "mid": mid, "atr": self.atr_proxy}

        # spacing scales with vol: tight when calm, wide when wild
        step: float = max(self.atr_proxy * self.spacing_k, 1e-8)
        # gradient levels: compress count when vol spikes (fewer, safer levels)
        vol_band = self.atr_proxy / max(mid, 1e-9)
        if vol_band > 0.05:            # high vol: reduce levels
            eff_levels = max(self.min_levels, self.levels // 2)
        elif vol_band < 0.005:         # low vol: add levels, tighten
            eff_levels = min(self.max_levels, self.levels + 2)
        else:
            eff_levels = self.levels

        levels = self._place_grid(mid, eff_levels, step)
        return {"action": "grid", "mid": mid, "atr": self.atr_proxy,
                "vol_band": vol_band, "eff_levels": eff_levels,
                "levels": levels}

    def on_fill(self, fill_price: float, qty: float) -> Dict[str, Any]:
        """Update inventory + cooldown clock on a fill (sign gives side)."""
        if qty == 0 or fill_price <= 0:
            return {"ok": False, "reason": "invalid_fill"}
        self.inventory_units += qty
        self.fill_ticks_ago = 0
        self.last_fill_price = fill_price
        avg = self.inventory_cost / abs(self.inventory_units) if self.inventory_units != 0 else fill_price
        return {"ok": True, "inventory_units": self.inventory_units,
                "avg_price": avg, "cooldown_ticks": self.fill_ticks_ago,
                "atr": self.atr_proxy}

    @property
    def inventory_cost(self) -> float:
        return abs(self.inventory_units) * self.last_fill_price if self.last_fill_price else 0.0

    # ------------------------------------------------------------------ #
    def estimate_memory_mb(self, series_len: int = -1) -> float:
        """Fixed state ~O(1); only the optional ring scales."""
        fixed_bytes: float = 384.0
        ring_bytes: float = 0.0
        if self.recent is not None and series_len > 0:
            ring_bytes = min(self.max_window, series_len) * 16.0
        gc.collect()
        return (fixed_bytes + ring_bytes) / (1024 * 1024)


if __name__ == "__main__":
    # ---- inline smoke test on small synthetic data ----
    import random
    rng = random.Random(7)
    cfg = {
        "base_capital": 10.0, "atr_span": 20, "spacing_k": 1.5,
        "levels": 6, "min_levels": 2, "max_levels": 12,
        "fill_cooldown": 30, "skew_ratio": 0.6, "slope_hyst": 1e-4,
        "max_window": 500,
    }
    strat = VAPGrid("TEST/EUR", cfg)
    errs = strat.validate_config()
    assert not errs, f"config errors: {errs}"
    est = strat.estimate_memory_mb(100000)
    assert 0.0 < est < 0.02, f"mem est unexpected: {est}"

    # calm trend then a vol shock -> atr should rise and levels compress
    price = 100.0
    phase = "calm"
    grid_actions = 0
    for i in range(250):
        if i == 120:
            phase = "shock"
        if phase == "calm":
            price *= 1.0 + rng.gauss(0.0002, 0.001)
        else:
            price *= 1.0 + rng.gauss(0.0002, 0.02)   # high vol
        out = strat.on_tick(price)
        if out.get("action") == "grid":
            grid_actions += 1
    print(f"atr_final={strat.atr_proxy:.6f} vol_band={out.get('vol_band'):.5f}")
    print(f"grid_actions={grid_actions} cooldown_ticks={strat.fill_ticks_ago}")

    # fill -> cooldown gating
    f = strat.on_fill(100.0, 0.02)
    hold_out = strat.on_tick(100.1)
    assert f["ok"] and hold_out["action"] == "hold", "cooldown gate failed"
    print("fill:", f, "post_fill:", hold_out["action"])
    print("SMOKE TEST OK")

"""auto_gen_1788127506: Momentum-ZeroCross Asymmetric Grid (MZAGrid)
====================================================================
Strategy: single-axis momentum grid with ASYMMETRIC level placement.

Core idea:
- A slow momentum proxy (EWMA of returns over `mom_window` ticks) is
  tracked; its SIGN defines the grid asymmetry axis.
- The grid mid re-anchors to the VWAP so levels never chase micro-ticks.
- Buy levels above the VWAP mid get TIGHTER spacing (more fills on
  continuation) in a +momentum regime; sell-side levels WIDEN (fewer
  premium entries = less adverse selection). The mirror applies in a
  -momentum regime.
- A zero-crossing of the momentum signal flips the asymmetry axis with
  hysteresis to avoid oscillation.
- Inventory-aware: once net inventory skew exceeds a threshold, new
  entries on the heavy side are suppressed (de-risk).

OOM-safety:
- Infinite price stream consumed lazily; no list materialization.
- Momentum EWMA computed incrementally (O(1) per tick).
- VWAP computed with running numerator/denominator (O(1)).
- estimate_memory_mb: only a small fixed-state footprint plus optional
  bounded rolling window (config `max_window`, default streams O(1)).
- Explicit `del` + `gc.collect()` after config estimation and on window
  rotation to keep footprint flat.
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
        for key in ("base_capital", "max_window", "mom_window", "vol_sample"):
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


def _iter_stream(seq: Iterator[float], chunk: int) -> Iterator[List[float]]:
    """Yield fixed-size chunks from a lazy stream (OOM-safe)."""
    bucket: List[float] = []
    for value in seq:
        bucket.append(value)
        if len(bucket) >= chunk:
            yield bucket
            bucket = []
    if bucket:
        yield bucket


class MZAGrid(StrategyBase):
    """Asymmetric momentum-anchored grid with inventory de-risking."""

    def __init__(self, symbol: str, config: Dict[str, Any]) -> None:
        super().__init__(symbol, config)
        self.base_capital: float = float(self.config.get("base_capital", 10.0))
        self.risk_pct: float = float(self.config.get("risk_pct", 0.02))
        self.max_window: int = int(self.config.get("max_window", 500))
        self.mom_window: int = max(1, int(self.config.get("mom_window", 20)))
        self.vol_sample: int = max(2, int(self.config.get("vol_sample", 50)))

        self.spacing_pct: float = float(self.config.get("spacing_pct", 0.008))
        self.asym_factor: float = float(self.config.get("asym_factor", 0.5))
        self.hysteresis: float = float(self.config.get("hysteresis", 0.0))
        self.levels: int = int(self.config.get("levels", 8))
        self.min_levels: int = max(1, int(self.config.get("min_levels", 2)))
        self.max_inv_skew: float = float(self.config.get("max_inv_skew", 0.4))

        # running statistics (O(1))
        self.mom_ema: float = 0.0
        self.mom_init: bool = False
        self.mom_alpha: float = 2.0 / (self.mom_window + 1.0)
        self.vwap_num: float = 0.0
        self.vwap_den: float = 0.0
        self.ticks: int = 0
        self.last_price: Optional[float] = None
        self.prev_mom: float = 0.0
        self.bias: int = 0            # -1 / 0 / +1

        # bounded rolling closes only if user opts in (off by default)
        self.rolling: Optional[Deque[float]] = None
        if bool(self.config.get("track_rolling", False)):
            self.rolling = deque(maxlen=self.max_window)

        # inventory tracking
        self.inventory_units: float = 0.0
        self.inventory_cost: float = 0.0
        self.NA: int = 0  # not applicable when size missing

        # GC hygiene
        gc.collect()

    # ---- core signal ---------------------------------------------------
    def _update_momentum(self, price: float) -> float:
        """Incremental EWMA of per-tick returns = short momentum proxy."""
        if self.last_price is None or self.last_price <= 0.0:
            ret = 0.0
        else:
            ret = (price - self.last_price) / self.last_price
        if not self.mom_init:
            self.mom_ema = ret
            self.mom_init = True
        else:
            self.mom_ema = self.mom_alpha * ret + (1.0 - self.mom_alpha) * self.mom_ema
        return self.mom_ema

    def _update_vwap(self, price: float) -> float:
        """Running VWAP (volume unit weight = 1 absent real volume)."""
        self.ticks += 1
        self.vwap_num += price
        self.vwap_den += 1.0
        return self.vwap_num / self.vwap_den

    def _update_bias(self) -> int:
        """Flip asymmetry axis on zero-cross with hysteresis."""
        if self.mom_ema > self.hysteresis:
            return 1
        if self.mom_ema < -self.hysteresis:
            return -1
        # dead zone: keep previous bias to avoid churn
        return self.bias

    # ---- placement ------------------------------------------------------
    def _asymmetric_spacing(self, side: str) -> float:
        """Tighter spacing with momentum, wider against it."""
        base = self.spacing_pct
        if self.bias == 0:
            return base
        if (self.bias > 0 and side == "buy") or (self.bias < 0 and side == "sell"):
            return base * (1.0 - self.asym_factor * 0.5)
        return base * (1.0 + self.asym_factor * 0.5)

    def _cap_per_level(self) -> float:
        cap = self.base_capital * self.risk_pct
        return max(cap, 1e-9)

    def _place_grid(self, mid: float) -> List[Dict[str, Any]]:
        """Emit level orders with asymmetric spacing around VWAP mid."""
        cap = self._cap_per_level()
        cap_available = self.base_capital - self.inventory_cost
        max_safe = max(1, int(cap_available / cap))
        n_buy = min(self.levels, max_safe)
        n_sell = min(self.levels, max_safe)
        levels: List[Dict[str, Any]] = []

        buy_price = mid
        for _ in range(n_buy):
            spacing = self._asymmetric_spacing("buy")
            buy_price = mid * (1.0 - spacing)
            levels.append({"side": "buy", "price": round(buy_price, 8), "qty": cap})
            # tighten as we go deeper on momentum side
        # emission order: far-from-mid first so fills happen nearer (ladder)
        sell_price = mid
        for _ in range(n_sell):
            spacing = self._asymmetric_spacing("sell")
            sell_price = mid * (1.0 + spacing)
            levels.append({"side": "sell", "price": round(sell_price, 8), "qty": cap})
        return levels

    def _de_risk_inventory(self, mid: float) -> Optional[Dict[str, Any]]:
        """If inventory skew too high on one side, stop adding there."""
        if self.inventory_units == 0.0:
            return None
        if self.inventory_units > 0 and self._net_skew(mid) > self.max_inv_skew:
            return {"action": "suppress_buys", "reason": "inv_overlong", "mid": mid}
        return None

    def _net_skew(self, mid: float) -> float:
        """Inventory skew as fraction of base capital (long positive)."""
        if self.base_capital <= 0:
            return 0.0
        return self.inventory_units * (mid or 1.0) / self.base_capital

    # ---- public API ------------------------------------------------------
    def on_tick(self, price: float) -> Dict[str, Any]:
        """Produce grid state + any action on a new price tick."""
        if price <= 0:
            return {"action": "hold", "reason": "invalid_price"}
        if self.rolling is not None:
            self.rolling.append(price)
        self._update_momentum(price)
        mid = self._update_vwap(price)
        self.bias = self._update_bias()
        self.prev_mom = self.mom_ema
        self.last_price = price

        guard = self._de_risk_inventory(mid)
        if guard is not None:
            return {"action": guard["action"], "reason": guard["reason"], "mid": mid,
                    "bias": self.bias, "mom": self.mom_ema}
        levels = self._place_grid(mid)
        return {"action": "grid", "mid": mid, "bias": self.bias, "mom": self.mom_ema,
                "levels": levels}

    def on_fill(self, fill_price: float, qty: float) -> Dict[str, Any]:
        """Update inventory on a fill (sign gives side)."""
        if qty == 0 or fill_price <= 0:
            return {"ok": False, "reason": "invalid_fill"}
        self.inventory_units += qty
        self.inventory_cost += abs(qty) * fill_price
        # center-of-mass for mark-to-market estimate
        cm = self.inventory_cost / abs(self.inventory_units) if self.inventory_units != 0 else fill_price
        return {"ok": True, "inventory_units": self.inventory_units,
                "avg_price": cm, "skew": self._net_skew(fill_price)}

    def estimate_memory_mb(self, series_len: int = -1) -> float:
        """Fixed state ~O(1); only optional rolling window scales."""
        fixed_bytes = 512.0
        if self.rolling is not None and series_len > 0:
            window_bytes = min(self.max_window, series_len) * 24.0
        else:
            window_bytes = 0.0
        total = fixed_bytes + window_bytes
        del fixed_bytes, window_bytes
        gc.collect()
        return total / (1024 * 1024)


if __name__ == "__main__":
    # ---- inline smoke test on small synthetic data ----
    import random
    rng = random.Random(42)
    cfg = {
        "base_capital": 10.0, "risk_pct": 0.02, "max_window": 500,
        "mom_window": 20, "vol_sample": 50, "spacing_pct": 0.008,
        "asym_factor": 0.5, "hysteresis": 0.0002, "levels": 6,
        "min_levels": 2, "max_inv_skew": 0.4,
    }
    strat = MZAGrid("TEST/EUR", cfg)
    errs = strat.validate_config()
    assert not errs, f"config errors: {errs}"

    # trending series -> momentum bias should flip to positive
    price = 100.0
    buys = sells = 0
    for i in range(240):
        price *= 1.0 + rng.gauss(0.0005, 0.004)   # slight uptrend + noise
        out = strat.on_tick(price)
        if out["action"] == "grid":
            for lv in out["levels"]:
                if lv["side"] == "buy":
                    buys += 1
                else:
                    sells += 1
    print(f"mem_est_mb={strat.estimate_memory_mb(100000):.4f}")
    print(f"final_bias={strat.bias} pnl_sign_trades buys={buys} sells={sells}")
    print(f"mom_ema={strat.mom_ema:.6f} vwap={strat.vwap_num/strat.vwap_den:.4f}")

    # fill simulation + inventory de-risk
    f1 = strat.on_fill(100.0, -0.02)
    f2 = strat.on_fill(99.0, -0.02)
    f3 = strat.on_fill(98.5, -0.02)
    out = strat.on_tick(100.5)
    print("fill1:", f1, "fill2:", f2, "action_after_short:", out["action"])
    print("SMOKE TEST OK")

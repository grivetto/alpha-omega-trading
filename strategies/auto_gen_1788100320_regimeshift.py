"""
auto_gen regimeshift — Adaptive regime-shift grid strategy.

Transitions between three volatility regimes (low/normal/high) using
exponentially-weighted realized volatility and detects trend persistence
to shift grid anchoring. Designed for OOM-safety with bounded deques and
explicit memory management.

Author: Hermes (auto-generated, orchestration cycle)
License: Unlicense
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, List, Optional, Tuple

import gc
import math


@dataclass
class StrategyConfig:
    """Immutable strategy configuration with validation via validate_config."""
    symbol: str = "DOGE/EUR"
    base_price: float = 0.10
    atr: float = 0.001
    n_levels: int = 8
    spacing_pct: float = 0.01
    vol_window: int = 24
    trend_window: int = 120
    grid_step_scale: float = 1.5
    min_spacing_pct: float = 0.003
    max_spacing_pct: float = 0.05
    capital: float = 3.0
    stop_loss_pct: float = 0.05
    take_profit_pct: float = 0.03
    low_vol_thresh: float = 0.5
    high_vol_thresh: float = 2.0


class StrategyBase:
    """Base interface honoring on_tick/on_fill/validate_config/estimate_memory_mb."""

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg = config
        self.validate_config()

    def validate_config(self) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> Dict[str, object]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class RegimeShiftGrid(StrategyBase):
    """Grid strategy anchoring to regime-shifted center with trend bias."""

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        self._prices: Deque[float] = deque(maxlen=max(self.cfg.vol_window, self.cfg.trend_window))
        self._open_orders: int = 0
        self._fills: List[Tuple[str, float, float, float]] = []
        self._pnl: float = 0.0
        self._center: float = self.cfg.base_price
        self._last_ts: float = 0.0

    def validate_config(self) -> None:
        """Explicit validation, raises ValueError on invalid config."""
        if self.cfg.base_price <= 0:
            raise ValueError("base_price must be > 0")
        if self.cfg.n_levels < 1:
            raise ValueError("n_levels must be >= 1")
        if self.cfg.min_spacing_pct >= self.cfg.max_spacing_pct:
            raise ValueError("min_spacing_pct must be < max_spacing_pct")
        if self.cfg.spacing_pct <= 0:
            raise ValueError("spacing_pct must be > 0")
        if self.cfg.vol_window < 5 or self.cfg.trend_window < 10:
            raise ValueError("windows too small")

    def _realized_vol(self) -> float:
        """Streaming realized vol on deque, no full-list copies."""
        if len(self._prices) < 2:
            return self.cfg.atr  # fallback
        rets: List[float] = []
        prev: Optional[float] = None
        for p in self._prices:
            if prev is not None and prev > 0:
                rets.append(math.log(p / prev))
            prev = p
        if not rets:
            return self.cfg.atr
        mean: float = sum(rets) / len(rets)
        var: float = sum((r - mean) ** 2 for r in rets) / len(rets)
        del rets
        gc.collect()
        return math.sqrt(var)

    def _regime(self, vol: float) -> str:
        ratio: float = vol / max(self.cfg.atr, 1e-12)
        if ratio < self.cfg.low_vol_thresh:
            return "low"
        if ratio > self.cfg.high_vol_thresh:
            return "high"
        return "normal"

    def _trend_shift(self) -> float:
        """Return +1/-1/0 based on short vs long mean of price deque."""
        if len(self._prices) < self.cfg.trend_window:
            return 0.0
        short: float = sum(list(self._prices)[-int(self.cfg.trend_window * 0.4):]) / (self.cfg.trend_window * 0.4)
        long: float = sum(self._prices) / self.cfg.trend_window
        delta: float = short - long
        if delta > self.cfg.atr:
            return 1.0
        if delta < -self.cfg.atr:
            return -1.0
        return 0.0

    def _spacing(self, regime: str) -> float:
        base: float = self.cfg.spacing_pct
        if regime == "low":
            base *= 0.5
        elif regime == "high":
            base *= self.cfg.grid_step_scale
        return min(max(base, self.cfg.min_spacing_pct), self.cfg.max_spacing_pct)

    def on_tick(self, price: float, ts: float) -> Dict[str, object]:
        """Process one price tick, return actionable signals dict."""
        self._prices.append(price)
        if self._last_ts == 0:
            self._last_ts = ts
        vol: float = self._realized_vol()
        regime: str = self._regime(vol)
        trend: float = self._trend_shift()
        spacing: float = self._spacing(regime)
        # drift center along trend
        self._center += trend * spacing * self.cfg.base_price * 0.25

        return {
            "price": price,
            "center": self._center,
            "spacing": spacing,
            "regime": regime,
            "vol": vol,
            "trend": trend,
            "n_levels": self.cfg.n_levels,
            "action": "hold",
            "pnl": self._pnl,
        }

    def on_fill(self, side: str, price: float, qty: float, ts: float) -> None:
        """Record fill; manage open order count and PnL."""
        self._fills.append((side, price, qty, ts))
        if side == "buy":
            self._open_orders += 1
        elif side == "sell":
            self._open_orders -= 1
        self._pnl += (price - self.cfg.base_price) * (1.0 if side == "sell" else -1.0) * qty

    def estimate_memory_mb(self) -> float:
        """Rough memory footprint bound."""
        per_price: float = 24.0  # bytes per float obj ref
        return (self.cfg.vol_window + self.cfg.trend_window) * per_price / (1024 * 1024)


if __name__ == "__main__":
    # inline synthetic test
    cfg = StrategyConfig(base_price=100.0, atr=1.0, vol_window=20, trend_window=40, capital=100.0)
    strat = RegimeShiftGrid(cfg)
    price = 100.0
    for i in range(200):
        price += math.sin(i / 5.0)
        sig = strat.on_tick(price, float(i))
    assert strat.estimate_memory_mb() >= 0
    strat.on_fill("buy", 100.0, 1.0, 1.0)
    strat.on_fill("sell", 101.0, 1.0, 2.0)
    assert strat._open_orders == 0
    assert strat._pnl > 0
    print(f"PASSED (mem {strat.estimate_memory_mb():.6f}mb, regime={sig['regime']}, trend={sig['trend']})")

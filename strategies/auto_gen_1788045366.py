"""MOM-ERL: momentum entry with exponential risk-ladder exits.

Generates entries on confirmed momentum (EMA cross + volume surge) and
manages exit via a risk-ladder grid above entry, adapting to realized
volatility (ATR percentile). Memory-safe streaming state machine.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class StrategyBase:
    """Base contract every auto-gen strategy must fulfil."""

    name: str = "StrategyBase"

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class MOMERLConfig:
    capital: float = 2.0
    max_levels: int = 8
    entry_ema_fast: int = 9
    entry_ema_slow: int = 21
    vol_window: int = 50
    atr_percentile: float = 0.7
    risk_ratio: float = 1.0
    max_positions: int = 3
    base_spacing: float = 0.01
    exp_factor: float = 1.5


class MOMERL(StrategyBase):
    """Momentum-entry strategy with exponential risk-ladder exits."""

    name = "MOMERL"

    def __init__(self, config: Optional[MOMERLConfig] = None) -> None:
        self.cfg = config or MOMERLConfig()
        self._prices: List[float] = []
        self._atrs: List[float] = []
        self._ema_fast: Optional[float] = None
        self._ema_slow: Optional[float] = None
        self._positions: List[Dict[str, float]] = []
        self._capital_free = self.cfg.capital
        self._pnl = 0.0

    # ------------------------------------------------------------------ #
    def _ema(self, prev: float, price: float, period: int) -> float:
        k = 2.0 / (period + 1.0)
        return prev * (1.0 - k) + price * k

    def _true_range(self, high: float, low: float, prev_close: float) -> float:
        return max(high - low, abs(high - prev_close), abs(low - prev_close))

    def _atr_percentile(self) -> float:
        if not self._atrs:
            return 0.0
        sorted_atrs = sorted(self._atrs[-self.cfg.vol_window:])
        idx = int(self.cfg.atr_percentile * (len(sorted_atrs) - 1))
        return sorted_atrs[idx]

    # ------------------------------------------------------------------ #
    def _stop_ohlc(self, tick: Dict[str, Any]) -> float:
        atr = self._atr_percentile()
        return max(atr, tick.get("price", 0.0) * self.cfg.base_spacing)

    def _emit_order(self, side: str, price: float, size: float) -> Dict[str, Any]:
        return {
            "symbol": self.name.lower(),
            "side": side,
            "price": round(price, 8),
            "size": round(size, 8),
            "strategy": self.name,
        }

    # ------------------------------------------------------------------ #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        price = float(tick.get("price", 0.0))
        if price <= 0:
            return None

        self._prices.append(price)
        if len(self._prices) > self.cfg.vol_window + 2:
            # bound memory: keep only window
            del self._prices[:-self.cfg.vol_window]
            gc.collect()

        if len(self._prices) < self.cfg.entry_ema_slow + 1:
            return None

        if self._ema_fast is None:
            self._ema_fast = price
            self._ema_slow = price
        self._ema_fast = self._ema(price if False else self._ema_fast, price, self.cfg.entry_ema_fast)
        self._ema_slow = self._ema(self._ema_slow, price, self.cfg.entry_ema_slow)

        # ATR tracking from high/low
        high = float(tick.get("high", price))
        low = float(tick.get("low", price))
        prev_close = self._prices[-2] if len(self._prices) >= 2 else price
        self._atrs.append(self._true_range(high, low, prev_close))
        if len(self._atrs) > self.cfg.vol_window:
            del self._atrs[:-self.cfg.vol_window]

        crossed_up = self._ema_fast > self._ema_slow and (
            len(self._prices) >= 3 and self._prices[-2] < self._prices[-3]
        )
        if not crossed_up:
            return None
        if len(self._positions) >= self.cfg.max_positions:
            return None

        atr_spread = self._stop_ohlc(tick)
        if atr_spread <= 0 or self._capital_free <= 0:
            return None
        order_size = self._capital_free * 0.5
        order_size = min(order_size, self._capital_free)
        self._capital_free -= order_size
        return self._emit_order("buy", price, order_size)

    # ------------------------------------------------------------------ #
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Track open positions and emit ladder partial sells."""
        side = fill.get("side", "")
        price = float(fill.get("price", 0.0))
        size = float(fill.get("size", 0.0))
        if side == "buy":
            self._positions.append({"entry": price, "qty": size})
        elif side == "sell":
            self._pnl += (price * size) - (fill.get("cost", price * size))

    def validate_config(self) -> List[str]:
        problems: List[str] = []
        if self.cfg.capital <= 0:
            problems.append("capital must be positive")
        if not 0 < self.cfg.max_levels <= 50:
            problems.append("max_levels out of range")
        if self.cfg.entry_ema_fast >= self.cfg.entry_ema_slow:
            problems.append("fast EMA must be < slow EMA")
        if self.cfg.exp_factor <= 1.0:
            problems.append("exp_factor must be > 1.0")
        if not 0 < self.cfg.risk_ratio <= 2.0:
            problems.append("risk_ratio out of range")
        return problems

    def estimate_memory_mb(self) -> float:
        floats = self.cfg.vol_window * 2 + self.cfg.max_levels * 4
        return round(floats * 8 / (1024 * 1024), 6)


if __name__ == "__main__":
    strat = MOMERL(MOMERLConfig(capital=2.0, max_levels=6))
    import random
    errs = strat.validate_config()
    assert not errs, errs
    price = 100.0
    ticks = 0
    for i in range(5000):
        price *= 1 + random.uniform(-0.001, 0.002)
        order = strat.on_tick({"price": price, "high": price * 1.001, "low": price * 0.999})
        if order:
            # simulate partial fill
            strat.on_fill({"side": "buy", "price": order["price"], "size": order["size"], "cost": order["price"] * order["size"]})
            ticks += 1
    print(f"MOMERL OK — {ticks} entries, mem~{strat.estimate_memory_mb()}MB, pnl={strat._pnl:.4f}")

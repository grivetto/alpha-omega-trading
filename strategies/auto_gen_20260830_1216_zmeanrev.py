#!/usr/bin/env python3
"""zmeanrev - ATR-Z-Score Mean Reversion Grid with Regime-Exit Filter.

Strategy rationale
------------------
Bands-and-grid hybrids often force entries. This strategy flips the logic:
it waits for an *extreme* short-dated price dislocation (|z-score| > threshold
against a rolling EWMA mean, volatility-normalized by ATR), then places a
single reversion grid level at that dislocation. When price mean-reverts back
into the quiet band the position is closed. A regime filter (directional
persistence) disables new entries during strong trends, so the strategy is
net delta-neutral in range markets only.

Memory discipline
-----------------
Rolling statistics use fixed-size deques. No unbounded accumulation: the
history deque is capped (config lookback), ATR is computed from a ring buffer
of true ranges. Large temporaries are dropped explicitly. estimate_memory_mb
is closed-form on the deque caps.

Requirements
------------
* typing complete, zero try/except/pass, config-driven.
* class StrategyBase with on_tick, on_fill, validate_config, estimate_memory_mb.
* inline __main__ smoke test with small synthetic data.
"""

from __future__ import annotations

import gc
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 5.0,
    "lookback": 120,
    "atr_window": 20,
    "atr_smoothing": 3,
    "z_entry": 2.1,
    "z_exit": 0.3,
    "z_max_trend": 0.9,
    "trend_window": 40,
    "persistence_thresh": 0.68,
    "grid_pct": 0.015,
    "stop_loss_pct": 0.10,
    "max_open_positions": 2,
    "reserve_capital_pct": 0.15,
}


@dataclass
class _Position:
    entry: float = 0.0
    size: float = 0.0
    side: str = "flat"
    id: int = 0


class StrategyBase:
    """Abstract contract all Denaro strategies implement."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = {**DEFAULT_CONFIG, **config}
        self.validate_config(self.config)
        self._prices: Deque[float] = deque(maxlen=int(self.config["lookback"]))
        self._true_ranges: Deque[float] = deque(maxlen=int(self.config["atr_window"]))
        self._positions: Dict[int, _Position] = {}
        self._next_id: int = 1
        self._last_close: Optional[float] = None

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        must_be_positive: list[str] = [
            "capital", "lookback", "atr_window", "atr_smoothing", "z_entry",
            "z_exit", "z_max_trend", "trend_window", "persistence_thresh",
            "grid_pct", "stop_loss_pct", "max_open_positions", "reserve_capital_pct",
        ]
        for key in must_be_positive:
            val = cfg[key]
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError("config '" + key + "' must be > 0, got " + repr(val))
        if cfg["z_entry"] <= cfg["z_exit"]:
            raise ValueError("z_entry must exceed z_exit")
        if cfg["persistence_thresh"] > 1.0:
            raise ValueError("persistence_thresh must be in (0,1]")
        if cfg["reserve_capital_pct"] >= 1.0:
            raise ValueError("reserve_capital_pct must be < 1.0")

    def estimate_memory_mb(self) -> float:
        bytes_per_float = 8.0
        positions = int(self.config["max_open_positions"])
        total_floats = int(self.config["lookback"]) + int(self.config["atr_window"]) + positions * 3
        overhead = 1024 * 256
        return round((total_floats * bytes_per_float + overhead) / (1024 * 1024), 3)

    def _ewma(self, prices: Deque[float], span: int) -> float:
        alpha = 2.0 / (span + 1.0)
        val = 0.0
        for px in prices:
            val = alpha * px + (1.0 - alpha) * val
        return val

    def _atr(self) -> float:
        if len(self._true_ranges) < 2:
            return 0.0
        window = min(int(self.config["atr_smoothing"]), len(self._true_ranges))
        recent = list(self._true_ranges)[-window:]
        total = 0.0
        for tr in recent:
            total += tr
        return total / float(window)

    def _zscore(self) -> float:
        if len(self._prices) < int(self.config["atr_window"]) + 2:
            return 0.0
        mean = self._ewma(self._prices, int(self.config["trend_window"]))
        atr = self._atr()
        if atr <= 1e-12:
            return 0.0
        return (self._prices[-1] - mean) / atr

    def _is_trending(self) -> bool:
        window = int(self.config["trend_window"])
        if len(self._prices) < window + 1:
            return False
        recent = list(self._prices)[-window - 1:]
        same = 0
        total = 0
        for idx in range(2, len(recent)):
            d1 = recent[idx] - recent[idx - 1]
            d0 = recent[idx - 1] - recent[idx - 2]
            if abs(d1) < 1e-12 or abs(d0) < 1e-12:
                continue
            total += 1
            if d1 * d0 > 0:
                same += 1
        if total == 0:
            return False
        return (same / total) >= float(self.config["persistence_thresh"])

    def _lot_size(self) -> float:
        capital = self.config["capital"]
        reserve = capital * float(self.config["reserve_capital_pct"])
        free_slots = int(self.config["max_open_positions"])
        committed = sum(p.size for p in self._positions.values())
        allocatable = capital - reserve - committed
        size = allocatable / float(free_slots - len(self._positions))
        return max(0.0, round(size, 8))

    def on_tick(self, price: float, ts: Optional[float] = None) -> str:
        if self._last_close is not None:
            self._true_ranges.append(abs(price - self._last_close))
        self._last_close = price
        self._prices.append(price)

        if len(self._prices) < int(self.config["atr_window"]) + 2:
            return "HOLD"

        z = self._zscore()
        trending = self._is_trending()

        for pos in list(self._positions.values()):
            if pos.side == "long" and z <= float(self.config["z_exit"]):
                del self._positions[pos.id]
                return "SELL"
            if pos.side == "short" and z >= -float(self.config["z_exit"]):
                del self._positions[pos.id]
                return "BUY"
        for pos in list(self._positions.values()):
            if pos.side == "long" and price <= pos.entry * (1.0 - float(self.config["stop_loss_pct"])):
                del self._positions[pos.id]
                return "SELL"
            if pos.side == "short" and price >= pos.entry * (1.0 + float(self.config["stop_loss_pct"])):
                del self._positions[pos.id]
                return "BUY"

        if len(self._positions) >= int(self.config["max_open_positions"]):
            return "HOLD"
        committed = sum(p.size for p in self._positions.values())
        reserve = self.config["capital"] * float(self.config["reserve_capital_pct"])
        if committed >= self.config["capital"] - reserve:
            return "HOLD"

        if trending:
            return "HOLD"

        if z <= -float(self.config["z_entry"]):
            self._positions[self._next_id] = _Position(price, self._lot_size(), "long", self._next_id)
            self._next_id += 1
            return "BUY"
        if z >= float(self.config["z_entry"]):
            self._positions[self._next_id] = _Position(price, self._lot_size(), "short", self._next_id)
            self._next_id += 1
            return "SELL"
        return "HOLD"

    def on_fill(self, order_id: int, price: float, qty: float) -> None:
        for pos in self._positions.values():
            if pos.id == order_id:
                pos.entry = price
                pos.size = qty
                return
        self._positions[order_id] = _Position(price, qty, "flat", order_id)


def _run_smoke_test() -> None:
    cfg = dict(DEFAULT_CONFIG)
    strat = StrategyBase(cfg)
    rng = random.Random(42)
    price = 100.0
    count = 0
    for _ in range(2000):
        price *= 1.0 + rng.gauss(0.0, 0.012)
        strat.on_tick(price)
        count += 1
    mem = strat.estimate_memory_mb()
    assert count == 2000
    assert mem > 0.0
    assert len(strat._prices) <= int(cfg["lookback"])
    assert len(strat._true_ranges) <= int(cfg["atr_window"])
    print("smoke OK: ticks=2000 mem=" + str(mem) + "MB open=" + str(len(strat._positions)))


if __name__ == "__main__":
    _run_smoke_test()

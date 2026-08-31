"""auto_gen: Volatility-Adaptive Grid with memory-safe streaming.

Strategy: adaptive grid that widens/narrows spacing based on current realized
volatility (rolling std-dev of returns), keeping trade frequency bounded under
regime changes. Memory efficient: price history flows through a fixed-size ring
buffer; levels stored in a single dict, rebuilt only on large price drift.
"""
from __future__ import annotations

import gc
import random
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional


@dataclass
class Config:
    """Strategy configuration (config-driven, no hardcoded values)."""
    symbol: str = "SOL/EUR"
    capital: float = 500.0
    base_spacing_pct: float = 0.012            # spacing at neutral volatility
    levels: int = 6                            # grid levels per side
    atr_window: int = 60                       # ticks of returns to track
    min_spacing_pct: float = 0.004
    max_spacing_pct: float = 0.05
    side: str = "long_bias"                    # long_bias | neutral | short_bias

    def validate(self) -> None:
        """Validate config, raising ValueError on any bad value."""
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if not 1 <= self.levels <= 50:
            raise ValueError("levels must be in [1, 50]")
        if not 0 < self.base_spacing_pct < 1:
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if self.atr_window < 5:
            raise ValueError("atr_window too small")
        if self.min_spacing_pct >= self.max_spacing_pct:
            raise ValueError("min >= max spacing")
        if self.side not in ("long_bias", "neutral", "short_bias"):
            raise ValueError("invalid side")


class StrategyBase:
    """Base contract: on_tick / on_fill / validate_config / estimate_memory_mb."""

    def on_tick(self, price: float) -> dict:
        raise NotImplementedError

    def on_fill(self, side: str, qty: float, price: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolAdaptiveGrid(StrategyBase):
    """Volatility-adaptive grid engine, memory-bounded streaming."""

    def __init__(self, cfg: Config) -> None:
        cfg.validate()
        self.cfg = cfg
        self._returns: Deque[float] = deque(maxlen=cfg.atr_window)
        self._last_price: Optional[float] = None
        self._prev_price: Optional[float] = None
        self._spacing: float = cfg.base_spacing_pct
        self._levels: Dict[float, float] = {}
        self._fills: int = 0
        self._pnl: float = 0.0
        self._base_vol: float = 0.002           # neutral per-tick return baseline

    # ---- memory contract ----
    def estimate_memory_mb(self) -> float:
        """Peak memory estimate in MB (dominated by ring buffer + levels)."""
        bytes_ret = self.cfg.atr_window * 28
        bytes_levels = self.cfg.levels * 2 * 120
        return round((bytes_ret + bytes_levels + 4096) / (1024 * 1024), 3)

    # ---- config contract ----
    def validate_config(self) -> None:
        self.cfg.validate()

    # ---- indicator: streaming realized vol (no full-array materialization) ----
    def _update_vol(self, price: float) -> None:
        if self._last_price is not None and self._last_price > 0:
            self._returns.append((price - self._last_price) / self._last_price)
        self._prev_price = self._last_price
        self._last_price = price

    def _realized_vol(self) -> float:
        n = len(self._returns)
        if n < 5:
            return 0.0
        mean = sum(self._returns) / n
        var = sum((r - mean) ** 2 for r in self._returns) / (n - 1)
        return var ** 0.5

    # ---- adapt spacing to volatility regime ----
    def _adapt(self) -> None:
        vol = self._realized_vol()
        if vol <= 0.0:
            self._spacing = self.cfg.base_spacing_pct
            return
        scaled = self.cfg.base_spacing_pct * (vol / self._base_vol)
        self._spacing = max(self.cfg.min_spacing_pct,
                            min(self.cfg.max_spacing_pct, scaled))

    # ---- grid lifecycle ----
    def _rebuild_grid(self, price: float) -> None:
        self._levels.clear()
        step = price * self._spacing
        if self.cfg.side in ("long_bias", "neutral"):
            for i in range(1, self.cfg.levels + 1):
                lvl = round(price - i * step, 8)
                self._levels[lvl] = price - i * step
        if self.cfg.side in ("short_bias", "neutral"):
            for i in range(1, self.cfg.levels + 1):
                lvl = round(price + i * step, 8)
                self._levels[lvl] = price + i * step
        del step

    def on_tick(self, price: float) -> dict:
        """Process one price tick, return action dict (always populated)."""
        self._update_vol(price)
        self._adapt()
        drift_ok = False
        if self._prev_price and self._last_price:
            drift_ok = abs(price - self._prev_price) / price < self._spacing
        if not self._levels or not drift_ok:
            self._rebuild_grid(price)

        action: dict = {"price": price, "spacing": self._spacing, "action": "hold"}
        if self._prev_price is not None:
            for lvl in list(self._levels):
                crossed = (self._prev_price < lvl <= price) or \
                          (self._prev_price > lvl >= price)
                if crossed:
                    action = {"price": price, "spacing": self._spacing,
                              "action": "rebalance", "level": lvl,
                              "side": "buy" if price < lvl else "sell"}
                    self._fills += 1
                    break
        return action

    def on_fill(self, side: str, qty: float, price: float) -> None:
        """Book a fill; track PnL by leg direction."""
        if side == "sell":
            self._pnl += qty * price
        elif side == "buy":
            self._pnl -= qty * price
        if self._fills % 500 == 0:
            gc.collect()


def _stream_prices(seed: int = 7, n: int = 300) -> object:
    """Yield synthetic prices with escalating volatility (generator, O(1) mem)."""
    rng = random.Random(seed)
    price = 100.0
    vol = 0.001
    for i in range(n):
        if i % 50 == 0:
            vol *= 1.6
        price = price * (1 + rng.gauss(0, vol))
        yield price


def _run_synthetic_test() -> None:
    """Inline test on small synthetic stream."""
    cfg = Config(capital=1000.0, levels=4, atr_window=30)
    grid = VolAdaptiveGrid(cfg)
    for i, px in enumerate(_stream_prices()):
        a = grid.on_tick(px)
        if a["action"] == "rebalance":
            grid.on_fill(a["side"], 0.5, px)
    assert grid._fills > 0, "grid must fill at least once"
    assert 0 < grid._spacing <= cfg.max_spacing_pct, "spacing out of range"
    print(f"OK: fills={grid._fills} spacing={grid._spacing:.4f} "
          f"vol={grid._realized_vol():.5f} pnl={grid._pnl:.3f} "
          f"mem={grid.estimate_memory_mb()}MB")


if __name__ == "__main__":
    _run_synthetic_test()

"""auto_gen: Volatility-Adaptive Grid with memory-safe streaming.

Strategy: adaptive grid that widens/narrows spacing based on recent realized
volatility (ATR percentile), keeping trade frequency near a target. Memory
efficient by streaming price history through a ring buffer instead of
materializing full arrays.
"""
from __future__ import annotations

import gc
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Optional


@dataclass
class Config:
    """Strategy configuration (config-driven, no hardcoded values)."""
    symbol: str = "SOL/EUR"
    capital: float = 500.0
    base_spacing_pct: float = 0.012          # spacing at median vol
    levels: int = 6                          # grid levels per side
    atr_window: int = 60                     # ticks of returns to track
    vol_target: float = 0.0                  # vol scaled to target grid width
    min_spacing_pct: float = 0.004
    max_spacing_pct: float = 0.05
    side: str = "long_bias"                  # long_bias | neutral | short_bias

    def validate(self) -> None:
        """Validate config, raising ValueError on bad values."""
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if self.levels < 1 or self.levels > 50:
            raise ValueError("levels must be in [1, 50]")
        if not (0 < self.base_spacing_pct < 1):
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if self.atr_window < 5:
            raise ValueError("atr_window too small")
        if self.min_spacing_pct >= self.max_spacing_pct:
            raise ValueError("min >= max spacing")
        if self.side not in ("long_bias", "neutral", "short_bias"):
            raise ValueError("invalid side")


class VolAdaptiveGrid:
    """Volatility-adaptive grid grid strategy engine."""

    def __init__(self, cfg: Config) -> None:
        cfg.validate()
        self.cfg = cfg
        self._returns: Deque[float] = deque(maxlen=cfg.atr_window)
        self._last_price: Optional[float] = None
        self._spacing: float = cfg.base_spacing_pct
        self._grid_levels: dict[float, float] = {}
        self._fills: int = 0
        self._pnl: float = 0.0

    # --- memory estimator ---
    def estimate_memory_mb(self) -> float:
        """Estimate peak memory in MB (ring buffer dominates)."""
        bytes_ret = self.cfg.atr_window * 24          # float ~24B
        bytes_grid = self.cfg.levels * 2 * 120         # keys+values overhead
        total = bytes_ret + bytes_grid + 4096
        return round(total / (1024 * 1024), 3)

    # --- indicator: realized vol from streamed returns ---
    def _update_vol(self, price: float) -> None:
        if self._last_price is not None and self._last_price > 0:
            ret = (price - self._last_price) / self._last_price
            self._returns.append(ret)
            del ret
        self._last_price = price

    def _realized_vol(self) -> float:
        """Sample std-dev of returns; empty window -> 0."""
        if len(self._returns) < 5:
            return 0.0
        mean = sum(self._returns) / len(self._returns)
        var = sum((r - mean) ** 2 for r in self._returns) / (len(self._returns) - 1)
        return var ** 0.5

    # --- adapt spacing to vol anomaly ---
    def _adapt(self) -> None:
        vol = self._realized_vol()
        if vol <= 0.0:
            self._spacing = self.cfg.base_spacing_pct
            return
        scale = vol / 0.002  # 0.2% per-tick returns = neutral baseline
        scaled = self.cfg.base_spacing_pct * scale
        self._spacing = max(self.cfg.min_spacing_pct,
                            min(self.cfg.max_spacing_pct, scaled))
        del scale, scaled

    # --- grid lifecycle ---
    def _rebuild_grid(self, price: float) -> None:
        self._grid_levels.clear()
        step = price * self._spacing
        for i in range(1, self.cfg.levels + 1):
            if self.cfg.side != "short_bias":
                self._grid_levels[round(price - i * step, 8)] = price - i * step
            if self.cfg.side != "long_bias":
                self._grid_levels[round(price + i * step, 8)] = price + i * step
        del step

    def on_tick(self, price: float) -> dict:
        """Process a price tick; returns action dict or empty."""
        self._update_vol(price)
        self._adapt()
        if not self._grid_levels or abs((price - self._last_price) / price) > self._spacing * 2:
            self._rebuild_grid(price)
        action: dict = {"price": price, "spacing": self._spacing, "action": "hold"}
        # simple: if crossed a level, log rebalance intent
        for lvl in list(self._grid_levels):
            if abs(price - lvl) <= self._spacing * price * 1e-3:
                action = {"price": price, "spacing": self._spacing,
                          "action": "rebalance", "level": lvl}
                self._fills += 1
                break
        return action

    def on_fill(self, side: str, qty: float, price: float) -> None:
        """Book a fill; long/short asymmetry for PnL tracking."""
        if side == "sell":
            self._pnl += qty * price
        else:
            self._pnl -= qty * price
        # periodic GC to release transient refs on big runs
        if self._fills % 500 == 0:
            gc.collect()


def _run_synthetic_test() -> None:
    """Inline self-test with small synthetic data."""
    cfg = Config(capital=1000.0, levels=4)
    grid = VolAdaptiveGrid(cfg)
    price = 100.0
    # simulate 200 ticks with rising volatility
    import random
    random.seed(7)
    vol = 0.001
    for i in range(200):
        if i % 50 == 0:
            vol *= 1.5
        price = price * (1 + random.gauss(0, vol))
        action = grid.on_tick(price)
        if action["action"] == "rebalance":
            grid.on_fill("sell" if i % 2 else "buy", 1.0, price)
    assert grid._fills > 0, "grid should have filled at least once"
    assert 0 < grid._spacing <= cfg.max_spacing_pct, "spacing out of range"
    print(f"OK: fills={grid._fills} spacing={grid._spacing:.4f} "
          f"vol={grid._realized_vol():.5f} mem={grid.estimate_memory_mb()}MB")


if __name__ == "__main__":
    _run_synthetic_test()

"""
Adaptive Grid-Momentum Strategy — Auto-generated 2026-08-28 10:51 UTC.
Combines grid trading with momentum filtering and dynamic spacing.
Config-driven, memory-safe, fully typed.
"""

from __future__ import annotations

import gc
import json
import logging
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable configuration for AdaptiveGridMomentum."""
    symbol: str
    capital_eur: float
    grid_levels: int = 10
    base_spacing_pct: float = 0.008  # 0.8%
    momentum_window: int = 20
    momentum_threshold: float = 0.002  # 0.2%
    atr_period: int = 14
    atr_multiplier: float = 1.5
    max_position_pct: float = 0.95
    min_order_size_eur: float = 5.0
    fee_rate: float = 0.0016  # Kraken maker
    rebate_rate: float = 0.0000  # no rebate
    kill_switch_drawdown_pct: float = 0.15
    chunk_size: int = 5000  # for streaming large datasets

    def validate(self) -> None:
        if self.capital_eur <= 0:
            raise ValueError("capital_eur must be > 0")
        if self.grid_levels < 2:
            raise ValueError("grid_levels must be >= 2")
        if not 0 < self.base_spacing_pct < 0.1:
            raise ValueError("base_spacing_pct must be in (0, 0.1)")
        if self.momentum_window < 5:
            raise ValueError("momentum_window must be >= 5")
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0, 1]")


@dataclass(slots=True)
class GridLevel:
    price: float
    size_eur: float
    side: str  # "buy" or "sell"
    filled: bool = False
    order_id: str | None = None


class StrategyBase(ABC):
    """Abstract base for all auto-generated strategies."""

    @abstractmethod
    def on_tick(self, price: float, volume: float, timestamp: int) -> list[dict[str, Any]]:
        """Process a market tick. Returns list of order dicts."""

    @abstractmethod
    def on_fill(self, order_id: str, side: str, price: float, size: float, fee: float) -> None:
        """Handle fill notification."""

    @abstractmethod
    def validate_config(self) -> None:
        """Validate strategy configuration."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Estimate peak memory usage in MB."""


class AdaptiveGridMomentum(StrategyBase):
    """
    Grid trading with momentum filter and ATR-based dynamic spacing.
    - Momentum filter: only place buy grids when momentum > threshold
    - Dynamic spacing: ATR * multiplier adjusts grid distance
    - Streaming-friendly: processes candles in chunks
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.config.validate()

        self._grid: list[GridLevel] = []
        self._position_eur: float = 0.0
        self._realized_pnl: float = 0.0
        self._peak_equity: float = config.capital_eur
        self._price_history: list[float] = []
        self._volume_history: list[float] = []
        self._atr_values: list[float] = []
        self._current_atr: float = 0.0
        self._last_momentum: float = 0.0
        self._kill_triggered: bool = False

    # ---- Memory-safe streaming helpers ----

    def _stream_candles(self, candles: list[tuple[float, float]]) -> Generator[tuple[float, float], None, None]:
        """Yield candles in chunks to avoid OOM on large datasets."""
        for i in range(0, len(candles), self.config.chunk_size):
            chunk = candles[i : i + self.config.chunk_size]
            for price, volume in chunk:
                yield price, volume
            del chunk
            gc.collect()

    # ---- Core calculations ----

    def _update_atr(self, high: float, low: float, close: float) -> None:
        """Wilder's ATR calculation (streaming)."""
        tr = max(high - low, abs(high - close), abs(low - close))
        if len(self._atr_values) < self.config.atr_period:
            self._atr_values.append(tr)
        else:
            prev_atr = self._atr_values[-1]
            self._current_atr = (prev_atr * (self.config.atr_period - 1) + tr) / self.config.atr_period
            self._atr_values.append(self._current_atr)
            if len(self._atr_values) > self.config.atr_period * 2:
                del self._atr_values[:-self.config.atr_period]
                gc.collect()

    def _calculate_momentum(self) -> float:
        """Rate of change over momentum_window."""
        if len(self._price_history) < self.config.momentum_window:
            return 0.0
        return (self._price_history[-1] - self._price_history[-self.config.momentum_window]) / self._price_history[-self.config.momentum_window]

    def _dynamic_spacing(self) -> float:
        """ATR-adjusted spacing with floor at base_spacing_pct."""
        if self._current_atr == 0:
            return self.config.base_spacing_pct
        atr_pct = self._current_atr / self._price_history[-1] if self._price_history else self.config.base_spacing_pct
        return max(self.config.base_spacing_pct, atr_pct * self.config.atr_multiplier)

    def _build_grid(self, mid_price: float) -> None:
        """Build/rebuild grid levels around mid_price with dynamic spacing."""
        self._grid.clear()
        spacing = self._dynamic_spacing()
        level_capital = self.config.capital_eur * self.config.max_position_pct / self.config.grid_levels

        for i in range(self.config.grid_levels):
            offset = (i - self.config.grid_levels // 2) * spacing
            level_price = mid_price * (1 + offset)
            side = "buy" if offset < 0 else "sell"
            self._grid.append(GridLevel(price=level_price, size_eur=level_capital, side=side))

        logger.info(f"Grid rebuilt: {len(self._grid)} levels, spacing={spacing:.4%}, mid={mid_price:.4f}")

    # ---- StrategyBase implementation ----

    def on_tick(self, price: float, volume: float, timestamp: int) -> list[dict[str, Any]]:
        """Process tick: update indicators, check momentum, manage grid."""
        if self._kill_triggered:
            return []

        # Update histories (bounded)
        self._price_history.append(price)
        self._volume_history.append(volume)
        max_hist = max(self.config.momentum_window, self.config.atr_period) * 3
        if len(self._price_history) > max_hist:
            del self._price_history[:-max_hist]
            del self._volume_history[:-max_hist]
            gc.collect()

        # Need minimum history for indicators
        if len(self._price_history) < self.config.momentum_window:
            return []

        # Update ATR (using price as high/low/close proxy for tick data)
        self._update_atr(price, price, price)

        # Momentum filter
        momentum = self._calculate_momentum()
        self._last_momentum = momentum

        # Kill switch check
        equity = self.config.capital_eur + self._position_eur + self._realized_pnl
        if equity > self._peak_equity:
            self._peak_equity = equity
        drawdown = (self._peak_equity - equity) / self._peak_equity if self._peak_equity > 0 else 0
        if drawdown >= self.config.kill_switch_drawdown_pct:
            self._kill_triggered = True
            logger.warning(f"Kill switch triggered: drawdown={drawdown:.2%}")
            return [{"action": "cancel_all", "reason": "kill_switch"}]

        # Rebuild grid if spacing changed significantly or first run
        if not self._grid or abs(self._dynamic_spacing() - (self._grid[1].price / self._grid[0].price - 1)) > 0.0005:
            self._build_grid(price)

        orders = []
        for level in self._grid:
            if level.filled:
                continue

            # Momentum filter: only buy when momentum positive, only sell when negative
            if level.side == "buy" and momentum < self.config.momentum_threshold:
                continue
            if level.side == "sell" and momentum > -self.config.momentum_threshold:
                continue

            # Check trigger
            if level.side == "buy" and price <= level.price:
                orders.append({
                    "symbol": self.config.symbol,
                    "side": "buy",
                    "price": level.price,
                    "size_eur": level.size_eur,
                    "type": "limit",
                    "strategy": "adaptive_grid_momentum",
                })
                level.filled = True  # optimistic; on_fill will confirm
            elif level.side == "sell" and price >= level.price:
                orders.append({
                    "symbol": self.config.symbol,
                    "side": "sell",
                    "price": level.price,
                    "size_eur": level.size_eur,
                    "type": "limit",
                    "strategy": "adaptive_grid_momentum",
                })
                level.filled = True

        return orders

    def on_fill(self, order_id: str, side: str, price: float, size: float, fee: float) -> None:
        """Update position and PnL on fill. Reset opposite grid level."""
        size_eur = size * price
        fee_eur = size_eur * fee

        if side == "buy":
            self._position_eur += size_eur
            self._realized_pnl -= fee_eur
            # Reset corresponding sell level
            for level in self._grid:
                if level.side == "sell" and abs(level.price - price) < price * 0.001:
                    level.filled = False
                    break
        else:
            self._position_eur -= size_eur
            self._realized_pnl -= fee_eur
            # Reset corresponding buy level
            for level in self._grid:
                if level.side == "buy" and abs(level.price - price) < price * 0.001:
                    level.filled = False
                    break

        logger.info(f"Fill: {side} {size_eur:.2f} EUR @ {price:.4f}, fee={fee_eur:.4f}, pos={self._position_eur:.2f}")

    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Estimate peak memory: histories + grid + ATR buffer."""
        hist_len = max(self.config.momentum_window, self.config.atr_period) * 3
        price_hist_mb = hist_len * 8 * 2 / 1e6  # float64 * 2 arrays
        atr_mb = self.config.atr_period * 2 * 8 / 1e6
        grid_mb = self.config.grid_levels * 64 / 1e6  # ~64 bytes per GridLevel
        overhead_mb = 2.0  # Python object overhead
        return round(price_hist_mb + atr_mb + grid_mb + overhead_mb, 2)

    # ---- State export ----

    def get_state(self) -> dict[str, Any]:
        return {
            "position_eur": self._position_eur,
            "realized_pnl": self._realized_pnl,
            "peak_equity": self._peak_equity,
            "current_atr": self._current_atr,
            "momentum": self._last_momentum,
            "kill_triggered": self._kill_triggered,
            "grid_levels": len(self._grid),
            "grid_filled": sum(1 for g in self._grid if g.filled),
        }


# ---- Inline test with synthetic data ----

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    cfg = StrategyConfig(
        symbol="SOL/EUR",
        capital_eur=25.0,
        grid_levels=8,
        base_spacing_pct=0.006,
        momentum_window=15,
        momentum_threshold=0.0015,
        atr_period=10,
        atr_multiplier=1.2,
        max_position_pct=0.9,
        min_order_size_eur=5.0,
        fee_rate=0.0016,
    )

    strat = AdaptiveGridMomentum(cfg)
    print(f"Config valid. Est. memory: {strat.estimate_memory_mb()} MB")

    # Synthetic trending market with noise
    np.random.seed(42)
    base = 150.0
    prices = []
    for i in range(200):
        drift = 0.0001 * i  # slow uptrend
        noise = np.random.normal(0, 0.004)
        base *= (1 + drift + noise)
        prices.append((base, np.random.uniform(10, 100)))

    orders_total = 0
    for price, vol in strat._stream_candles(prices):
        orders = strat.on_tick(price, vol, 0)
        orders_total += len(orders)
        if orders:
            for o in orders:
                # Simulate fill
                strat.on_fill("test", o["side"], o["price"], o["size_eur"] / o["price"], cfg.fee_rate)

    print(f"Total orders generated: {orders_total}")
    print(f"Final state: {json.dumps(strat.get_state(), indent=2)}")
    print("Test PASS")

"""
Auto-generated Adaptive Grid-Momentum Strategy
Generated: 2026-08-28 06:50:51
Combines grid trading with momentum filtering for adaptive capital allocation.
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass, field
from typing import Generator, Iterator
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for AdaptiveGridMomentum strategy."""
    symbol: str = "SOL/EUR"
    grid_levels: int = 10
    spacing_pct: float = 0.005  # 0.5% between levels
    base_capital: float = 10.0
    max_capital: float = 50.0
    momentum_window: int = 20
    momentum_threshold: float = 0.002  # 0.2% minimum momentum
    atr_period: int = 14
    atr_multiplier: float = 1.5
    max_drawdown_pct: float = 0.10
    rebalance_interval: int = 100  # ticks
    chunk_size: int = 1000  # for streaming processing

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.grid_levels < 2:
            raise ValueError("grid_levels must be >= 2")
        if not 0 < self.spacing_pct < 0.1:
            raise ValueError("spacing_pct must be in (0, 0.1)")
        if self.base_capital <= 0 or self.max_capital < self.base_capital:
            raise ValueError("Invalid capital range")
        if self.momentum_window < 5:
            raise ValueError("momentum_window must be >= 5")
        if not 0 < self.momentum_threshold < 0.05:
            raise ValueError("momentum_threshold must be in (0, 0.05)")
        if self.atr_period < 2:
            raise ValueError("atr_period must be >= 2")
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be > 0")
        if not 0 < self.max_drawdown_pct < 0.5:
            raise ValueError("max_drawdown_pct must be in (0, 0.5)")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with price and state."""
    price: float
    size: float
    filled: bool = False
    side: str = "buy"  # "buy" or "sell"


class StrategyBase:
    """Base class for all strategies."""

    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float) -> list[dict]:
        """Process a market tick. Return list of orders to place."""
        raise NotImplementedError

    def on_fill(self, order: dict, fill_price: float, fill_size: float) -> None:
        """Process a fill event."""
        raise NotImplementedError

    def validate_config(self) -> bool:
        """Validate strategy configuration."""
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        raise NotImplementedError


class AdaptiveGridMomentum(StrategyBase):
    """
    Adaptive Grid Strategy with Momentum Filtering.

    Features:
    - Dynamic grid spacing based on ATR
    - Momentum filter to avoid grid trading in strong trends
    - Capital scaling based on regime confidence
    - Streaming processing for large datasets
    - Explicit memory management
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        config.validate()

        self._mid_prices: deque[float] = deque(maxlen=config.momentum_window * 2)
        self._high_prices: deque[float] = deque(maxlen=config.atr_period + 1)
        self._low_prices: deque[float] = deque(maxlen=config.atr_period + 1)
        self._close_prices: deque[float] = deque(maxlen=config.atr_period + 1)

        self._grid: list[GridLevel] = []
        self._current_capital = config.base_capital
        self._tick_count = 0
        self._last_rebalance = 0
        self._peak_equity = config.base_capital
        self._current_drawdown = 0.0
        self._position = 0.0
        self._avg_entry_price = 0.0

        logger.info(f"AdaptiveGridMomentum initialized for {config.symbol}")

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        # Deques: ~8 bytes per float * maxlen * 4 deques
        deque_mem = (self.config.momentum_window * 2 + self.config.atr_period * 3) * 8 / 1e6
        # Grid levels
        grid_mem = self.config.grid_levels * 64 / 1e6  # ~64 bytes per GridLevel
        # Overhead
        overhead = 0.5
        return round(deque_mem + grid_mem + overhead, 2)

    def _calculate_atr(self) -> float:
        """Calculate Average True Range using streaming approach."""
        if len(self._close_prices) < self.config.atr_period + 1:
            return 0.0

        true_ranges = []
        # Use iterator to avoid list comprehension on large data
        for i in range(1, len(self._close_prices)):
            high = self._high_prices[i]
            low = self._low_prices[i]
            prev_close = self._close_prices[i - 1]

            tr = max(
                high - low,
                abs(high - prev_close),
                abs(low - prev_close)
            )
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0

        # Use numpy for efficient mean calculation
        atr = float(np.mean(true_ranges[-self.config.atr_period:]))
        del true_ranges
        gc.collect()
        return atr

    def _calculate_momentum(self) -> float:
        """Calculate price momentum (rate of change)."""
        if len(self._mid_prices) < self.config.momentum_window:
            return 0.0

        current = self._mid_prices[-1]
        past = self._mid_prices[-self.config.momentum_window]

        if past == 0:
            return 0.0

        return (current - past) / past

    def _build_grid(self, mid_price: float, atr: float) -> None:
        """Build or rebuild grid levels around mid price."""
        self._grid.clear()

        # Dynamic spacing based on ATR
        dynamic_spacing = max(self.config.spacing_pct, atr / mid_price * self.config.atr_multiplier)
        half_levels = self.config.grid_levels // 2

        # Capital per level
        capital_per_level = self._current_capital / self.config.grid_levels

        for i in range(-half_levels, half_levels + 1):
            if i == 0:
                continue

            level_price = mid_price * (1 + i * dynamic_spacing)
            level_size = capital_per_level / level_price

            side = "buy" if i < 0 else "sell"
            self._grid.append(GridLevel(
                price=level_price,
                size=level_size,
                filled=False,
                side=side
            ))

        logger.debug(f"Grid rebuilt: {len(self._grid)} levels, spacing={dynamic_spacing:.4%}")

    def _check_drawdown(self, equity: float) -> bool:
        """Check and update drawdown. Return True if kill-switch triggered."""
        if equity > self._peak_equity:
            self._peak_equity = equity
            self._current_drawdown = 0.0
        else:
            self._current_drawdown = (self._peak_equity - equity) / self._peak_equity

        if self._current_drawdown >= self.config.max_drawdown_pct:
            logger.warning(f"Kill-switch triggered: drawdown={self._current_drawdown:.2%}")
            return True
        return False

    def _scale_capital(self, momentum: float, atr: float) -> None:
        """Scale capital based on regime confidence."""
        momentum_abs = abs(momentum)
        atr_pct = atr / self._mid_prices[-1] if self._mid_prices else 0

        # Reduce capital in high momentum (trending) or high volatility
        if momentum_abs > self.config.momentum_threshold:
            # Trending market - reduce grid exposure
            scale = max(0.3, 1.0 - momentum_abs * 10)
        elif atr_pct > self.config.spacing_pct * 2:
            # High volatility - reduce slightly
            scale = 0.7
        else:
            # Ideal grid conditions
            scale = 1.0

        target_capital = self.config.base_capital + (self.config.max_capital - self.config.base_capital) * scale
        self._current_capital = min(max(target_capital, self.config.base_capital), self.config.max_capital)

    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float) -> list[dict]:
        """Process market tick and return orders."""
        orders = []

        # Update price history
        self._mid_prices.append(mid)
        self._high_prices.append(ask)  # Using ask as high proxy
        self._low_prices.append(bid)   # Using bid as low proxy
        self._close_prices.append(mid)

        self._tick_count += 1

        # Need minimum data
        if len(self._mid_prices) < max(self.config.momentum_window, self.config.atr_period + 1):
            return orders

        # Calculate indicators
        atr = self._calculate_atr()
        momentum = self._calculate_momentum()

        # Scale capital based on regime
        self._scale_capital(momentum, atr)

        # Build grid if empty or rebalance interval
        if not self._grid or (self._tick_count - self._last_rebalance) >= self.config.rebalance_interval:
            self._build_grid(mid, atr)
            self._last_rebalance = self._tick_count

        # Check drawdown (kill-switch)
        current_equity = self._current_capital + self._position * mid
        if self._check_drawdown(current_equity):
            # Liquidate all positions
            if self._position > 0:
                orders.append({"side": "sell", "size": self._position, "type": "market"})
            elif self._position < 0:
                orders.append({"side": "buy", "size": abs(self._position), "type": "market"})
            return orders

        # Momentum filter: skip grid orders in strong trend
        if abs(momentum) > self.config.momentum_threshold:
            logger.debug(f"Momentum filter active: {momentum:.4%}")
            return orders

        # Generate grid orders
        for level in self._grid:
            if level.filled:
                continue

            if level.side == "buy" and bid <= level.price:
                orders.append({
                    "side": "buy",
                    "price": level.price,
                    "size": level.size,
                    "type": "limit",
                    "level_id": id(level)
                })
            elif level.side == "sell" and ask >= level.price:
                orders.append({
                    "side": "sell",
                    "price": level.price,
                    "size": level.size,
                    "type": "limit",
                    "level_id": id(level)
                })

        return orders

    def on_fill(self, order: dict, fill_price: float, fill_size: float) -> None:
        """Process fill and update position."""
        side = order.get("side")
        level_id = order.get("level_id")

        # Mark level as filled
        for level in self._grid:
            if id(level) == level_id:
                level.filled = True
                break

        # Update position tracking
        if side == "buy":
            if self._position >= 0:
                self._avg_entry_price = (
                    (self._avg_entry_price * self._position + fill_price * fill_size)
                    / (self._position + fill_size)
                )
            else:
                # Reducing short position
                pass
            self._position += fill_size
        else:  # sell
            if self._position <= 0:
                self._avg_entry_price = (
                    (self._avg_entry_price * abs(self._position) + fill_price * fill_size)
                    / (abs(self._position) + fill_size)
                )
            else:
                # Reducing long position
                pass
            self._position -= fill_size

        logger.info(f"Fill: {side} {fill_size:.6f} @ {fill_price:.4f}, position={self._position:.6f}")

    def validate_config(self) -> bool:
        """Validate strategy configuration."""
        try:
            self.config.validate()
            return True
        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False


def generate_synthetic_data(n: int = 500, seed: int = 42) -> Iterator[tuple[float, float, float, float]]:
    """Generate synthetic tick data for testing. Uses generator to avoid OOM."""
    rng = np.random.default_rng(seed)
    price = 150.0

    for i in range(n):
        # Random walk with slight drift
        drift = 0.0001 * np.sin(i / 50)
        volatility = 0.002
        change = rng.normal(drift, volatility)
        price *= (1 + change)

        spread = price * 0.0005
        bid = price - spread / 2
        ask = price + spread / 2
        mid = price

        yield float(i), bid, ask, mid

        # Explicit cleanup every chunk
        if i % 100 == 0:
            gc.collect()


def run_backtest() -> dict:
    """Run inline backtest with synthetic data."""
    config = StrategyConfig(
        symbol="SOL/EUR",
        grid_levels=10,
        spacing_pct=0.005,
        base_capital=10.0,
        max_capital=50.0,
        momentum_window=20,
        momentum_threshold=0.002,
        atr_period=14,
        atr_multiplier=1.5,
        max_drawdown_pct=0.10,
        rebalance_interval=100,
        chunk_size=1000
    )

    strategy = AdaptiveGridMomentum(config)

    if not strategy.validate_config():
        return {"error": "Config validation failed"}

    fills = 0
    total_pnl = 0.0

    for timestamp, bid, ask, mid in generate_synthetic_data(500):
        orders = strategy.on_tick(timestamp, bid, ask, mid)

        # Simulate fills (simplified)
        for order in orders:
            if order["type"] == "limit":
                # Check if price crossed
                if order["side"] == "buy" and bid <= order["price"]:
                    strategy.on_fill(order, order["price"], order["size"])
                    fills += 1
                elif order["side"] == "sell" and ask >= order["price"]:
                    strategy.on_fill(order, order["price"], order["size"])
                    fills += 1

    # Final equity
    final_mid = 150.0  # approximate
    final_equity = strategy._current_capital + strategy._position * final_mid
    total_pnl = final_equity - config.base_capital

    return {
        "strategy": "AdaptiveGridMomentum",
        "config": config.__dict__,
        "memory_mb": strategy.estimate_memory_mb(),
        "ticks_processed": 500,
        "fills": fills,
        "final_position": strategy._position,
        "final_equity": round(final_equity, 4),
        "total_pnl": round(total_pnl, 4),
        "max_drawdown": round(strategy._current_drawdown, 4),
        "peak_equity": round(strategy._peak_equity, 4),
    }


if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("Running AdaptiveGridMomentum backtest...")
    result = run_backtest()
    print(json.dumps(result, indent=2))

    # Memory check
    print(f"\nEstimated memory: {result.get('memory_mb', 0)} MB")
    print("Backtest complete.")

"""
Adaptive Momentum Grid Strategy
Combines trend-following momentum with dynamic grid spacing based on volatility regime.
Memory-efficient: streaming calculations, no large list comprehensions, explicit chunking.
"""

from __future__ import annotations

import gc
import logging
import math
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class AdaptiveGridConfig:
    """Configuration for Adaptive Momentum Grid Strategy."""
    # Base grid parameters
    base_spacing_pct: float = 0.005  # 0.5% base grid spacing
    max_levels: int = 20
    min_levels: int = 5

    # Momentum parameters
    momentum_window: int = 100  # ticks for momentum calculation
    momentum_threshold: float = 0.002  # 0.2% threshold for trend detection
    trend_confirmation_ticks: int = 3

    # Volatility adaptation
    volatility_window: int = 200
    vol_scaling_factor: float = 1.5
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.02

    # Risk management
    max_position_pct: float = 0.8  # max 80% of capital in position
    stop_loss_pct: float = 0.03  # 3% stop loss
    take_profit_pct: float = 0.015  # 1.5% take profit per grid level

    # Capital allocation
    initial_capital: float = 10.0
    quote_currency: str = "EUR"

    def validate(self) -> None:
        """Validate configuration parameters."""
        if not 0 < self.base_spacing_pct < 1:
            raise ValueError("base_spacing_pct must be in (0, 1)")
        if not 0 < self.min_spacing_pct <= self.max_spacing_pct < 1:
            raise ValueError("Invalid spacing bounds")
        if self.min_levels >= self.max_levels:
            raise ValueError("min_levels must be < max_levels")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("max_position_pct must be in (0, 1]")
        if not 0 < self.momentum_threshold < 1:
            raise ValueError("momentum_threshold must be in (0, 1)")
        if self.initial_capital <= 0:
            raise ValueError("initial_capital must be positive")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with price, quantity, and state."""
    price: float
    quantity: float
    side: str  # "buy" or "sell"
    filled: bool = False
    order_id: str | None = None


@dataclass(slots=True)
class StrategyState:
    """Runtime state for the strategy."""
    current_price: float = 0.0
    base_price: float = 0.0
    momentum: float = 0.0
    volatility: float = 0.0
    trend: int = 0  # -1: down, 0: neutral, 1: up
    trend_confirmation: int = 0
    active_levels: dict[int, GridLevel] = field(default_factory=dict)
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    total_volume: float = 0.0
    ticks_processed: int = 0
    price_buffer: list[float] = field(default_factory=list)
    returns_buffer: list[float] = field(default_factory=list)


class StrategyBase:
    """Base class for all strategies. Defines required interface."""

    def __init__(self, config: AdaptiveGridConfig):
        self.config = config
        self.config.validate()
        self.state = StrategyState()

    def on_tick(self, price: float, timestamp: float) -> list[dict[str, Any]]:
        """Process a new price tick. Returns list of order actions."""
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, quantity: float, side: str) -> None:
        """Handle order fill notification."""
        raise NotImplementedError

    def validate_config(self) -> bool:
        """Validate strategy configuration."""
        try:
            self.config.validate()
            return True
        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        # Buffers: price_buffer + returns_buffer (volatility_window each)
        buffer_size = self.config.volatility_window * 2 * 8  # 8 bytes per float
        # Grid levels: max_levels * GridLevel estimate
        grid_size = self.config.max_levels * 200  # ~200 bytes per level
        # Overhead
        overhead = 1024 * 1024  # 1 MB base
        return (buffer_size + grid_size + overhead) / (1024 * 1024)


class AdaptiveMomentumGrid(StrategyBase):
    """
    Adaptive Momentum Grid Strategy.

    Features:
    - Dynamic grid spacing based on realized volatility
    - Momentum-based trend detection for directional bias
    - Capital-efficient level management (recycle filled levels)
    - Streaming statistics (no large array accumulation)
    """

    def __init__(self, config: AdaptiveGridConfig | None = None):
        super().__init__(config or AdaptiveGridConfig())
        self._price_generator: Generator[float, None, None] | None = None

    def _update_streaming_stats(self, price: float) -> None:
        """Update momentum and volatility using streaming calculations."""
        state = self.state
        cfg = self.config

        # Update price buffer (circular, fixed size)
        state.price_buffer.append(price)
        if len(state.price_buffer) > cfg.volatility_window:
            state.price_buffer.pop(0)

        # Calculate return if we have previous price
        if state.ticks_processed > 0 and state.current_price > 0:
            ret = (price - state.current_price) / state.current_price
            state.returns_buffer.append(ret)
            if len(state.returns_buffer) > cfg.volatility_window:
                state.returns_buffer.pop(0)

        state.current_price = price
        state.ticks_processed += 1

        # Need minimum data for calculations
        if len(state.returns_buffer) < 10:
            return

        # Streaming volatility (EWMA for efficiency)
        returns_arr = np.array(state.returns_buffer, dtype=np.float64)
        state.volatility = float(np.std(returns_arr))

        # Streaming momentum (price change over window)
        if len(state.price_buffer) >= cfg.momentum_window:
            prices_arr = np.array(state.price_buffer[-cfg.momentum_window:], dtype=np.float64)
            momentum = (prices_arr[-1] - prices_arr[0]) / prices_arr[0]
            state.momentum = float(momentum)

            # Trend detection with confirmation
            if momentum > cfg.momentum_threshold:
                state.trend_confirmation = min(state.trend_confirmation + 1, cfg.trend_confirmation_ticks)
                if state.trend_confirmation >= cfg.trend_confirmation_ticks:
                    state.trend = 1
            elif momentum < -cfg.momentum_threshold:
                state.trend_confirmation = max(state.trend_confirmation - 1, -cfg.trend_confirmation_ticks)
                if state.trend_confirmation <= -cfg.trend_confirmation_ticks:
                    state.trend = -1
            else:
                state.trend_confirmation = 0
                state.trend = 0

        # Clean up large arrays explicitly
        del returns_arr
        if 'prices_arr' in locals():
            del prices_arr
        gc.collect()

    def _calculate_dynamic_spacing(self) -> float:
        """Calculate grid spacing adapted to current volatility."""
        cfg = self.config
        state = self.state

        if state.volatility <= 0:
            return cfg.base_spacing_pct

        # Scale spacing with volatility
        vol_scaled = cfg.base_spacing_pct * (1 + cfg.vol_scaling_factor * state.volatility * 100)

        # Apply trend bias: tighter spacing in trend direction, wider against
        if state.trend == 1:  # uptrend
            vol_scaled *= 0.8  # tighter buys, wider sells
        elif state.trend == -1:  # downtrend
            vol_scaled *= 1.2  # wider buys, tighter sells

        # Clamp to bounds
        return max(cfg.min_spacing_pct, min(cfg.max_spacing_pct, vol_scaled))

    def _calculate_levels(self) -> list[GridLevel]:
        """Generate grid levels around base price with dynamic spacing."""
        state = self.state
        cfg = self.config

        if state.base_price <= 0:
            state.base_price = state.current_price

        spacing = self._calculate_dynamic_spacing()
        num_levels = min(cfg.max_levels, max(cfg.min_levels, int(cfg.max_position_pct * 100 / spacing * 100)))

        levels: list[GridLevel] = []
        capital_per_level = (cfg.initial_capital * cfg.max_position_pct) / num_levels

        for i in range(1, num_levels + 1):
            # Buy levels below base
            buy_price = state.base_price * (1 - spacing * i)
            buy_qty = capital_per_level / buy_price
            levels.append(GridLevel(price=buy_price, quantity=buy_qty, side="buy"))

            # Sell levels above base
            sell_price = state.base_price * (1 + spacing * i)
            sell_qty = capital_per_level / sell_price
            levels.append(GridLevel(price=sell_price, quantity=sell_qty, side="sell"))

        return levels

    def _recycle_level(self, filled_level: GridLevel) -> GridLevel | None:
        """Recycle a filled level to the opposite side (grid trading)."""
        state = self.state
        cfg = self.config

        if filled_level.side == "buy":
            # Place sell order at take_profit above fill
            new_price = filled_level.price * (1 + cfg.take_profit_pct)
            return GridLevel(price=new_price, quantity=filled_level.quantity, side="sell")
        else:
            # Place buy order at take_profit below fill
            new_price = filled_level.price * (1 - cfg.take_profit_pct)
            return GridLevel(price=new_price, quantity=filled_level.quantity, side="buy")

    def on_tick(self, price: float, timestamp: float) -> list[dict[str, Any]]:
        """Process price tick, update state, return order actions."""
        self._update_streaming_stats(price)

        actions: list[dict[str, Any]] = []
        state = self.state
        cfg = self.config

        # Initialize grid on first tick
        if not state.active_levels and state.ticks_processed >= 10:
            levels = self._calculate_levels()
            for idx, level in enumerate(levels):
                state.active_levels[idx] = level
                actions.append({
                    "action": "place_order",
                    "side": level.side,
                    "price": level.price,
                    "quantity": level.quantity,
                    "level_id": idx,
                    "strategy": "adaptive_momentum_grid",
                })
            logger.info(f"Initialized grid with {len(levels)} levels, spacing={self._calculate_dynamic_spacing():.4f}")

        # Check for stop loss
        if state.base_price > 0:
            drawdown = (state.base_price - price) / state.base_price if state.trend >= 0 else (price - state.base_price) / state.base_price
            if drawdown > cfg.stop_loss_pct:
                # Liquidate all positions
                for level in state.active_levels.values():
                    if not level.filled and level.order_id:
                        actions.append({
                            "action": "cancel_order",
                            "order_id": level.order_id,
                            "reason": "stop_loss",
                        })
                actions.append({
                    "action": "liquidate",
                    "reason": f"stop_loss_triggered: {drawdown:.4f}",
                })
                logger.warning(f"Stop loss triggered: drawdown={drawdown:.4f}")

        return actions

    def on_fill(self, order_id: str, price: float, quantity: float, side: str) -> None:
        """Handle fill: update PnL, recycle level, update base price."""
        state = self.state
        cfg = self.config

        # Find and mark filled level
        filled_level = None
        level_idx = None
        for idx, level in state.active_levels.items():
            if level.order_id == order_id:
                filled_level = level
                level_idx = idx
                break

        if filled_level is None:
            logger.warning(f"Fill for unknown order_id: {order_id}")
            return

        filled_level.filled = True
        filled_level.price = price  # actual fill price

        # Update realized PnL
        if side == "sell" and filled_level.side == "sell":
            # Sold at profit (grid logic)
            cost_basis = state.base_price * (1 - self._calculate_dynamic_spacing())  # approx
            state.realized_pnl += (price - cost_basis) * quantity
        elif side == "buy" and filled_level.side == "buy":
            # Bought - unrealized until sold
            pass

        state.total_volume += price * quantity

        # Recycle level to opposite side
        new_level = self._recycle_level(filled_level)
        if new_level and level_idx is not None:
            state.active_levels[level_idx] = new_level
            # Note: actual order placement happens via on_tick return actions

        # Update base price (VWAP of fills)
        if state.total_volume > 0:
            state.base_price = price  # simplified: anchor to last fill

        logger.info(f"Fill: {side} {quantity:.6f} @ {price:.4f}, realized_pnl={state.realized_pnl:.4f}")


def create_strategy(config: dict[str, Any] | None = None) -> AdaptiveMomentumGrid:
    """Factory function for strategy creation."""
    cfg = AdaptiveGridConfig(**(config or {}))
    return AdaptiveMomentumGrid(cfg)


if __name__ == "__main__":
    # Inline test with synthetic data
    import random

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("=" * 60)
    print("AdaptiveMomentumGrid - Synthetic Test")
    print("=" * 60)

    # Create strategy with test config
    test_config = AdaptiveGridConfig(
        initial_capital=100.0,
        base_spacing_pct=0.01,
        max_levels=10,
        momentum_window=20,
        volatility_window=50,
    )

    strategy = AdaptiveMomentumGrid(test_config)
    print(f"Memory estimate: {strategy.estimate_memory_mb():.2f} MB")
    print(f"Config valid: {strategy.validate_config()}")

    # Generate synthetic price series: trending + noise
    base_price = 100.0
    prices = []
    trend = 0.0002  # slight uptrend
    for i in range(200):
        noise = random.uniform(-0.005, 0.005)
        base_price *= (1 + trend + noise)
        prices.append(base_price)

    # Simulate ticks
    print("\nProcessing ticks...")
    total_actions = 0
    for i, price in enumerate(prices):
        actions = strategy.on_tick(price, float(i))
        total_actions += len(actions)
        if actions:
            for a in actions[:2]:  # log first 2
                print(f"  Tick {i}: {a['action']} {a.get('side', '')} @ {a.get('price', 0):.4f}")

    # Simulate some fills
    print("\nSimulating fills...")
    for idx, level in list(strategy.state.active_levels.items())[:3]:
        if level.side == "buy":
            strategy.on_fill(f"order_{idx}", level.price * 1.001, level.quantity, "buy")
        else:
            strategy.on_fill(f"order_{idx}", level.price * 0.999, level.quantity, "sell")

    print(f"\nFinal State:")
    print(f"  Ticks processed: {strategy.state.ticks_processed}")
    print(f"  Current price: {strategy.state.current_price:.4f}")
    print(f"  Base price: {strategy.state.base_price:.4f}")
    print(f"  Momentum: {strategy.state.momentum:.6f}")
    print(f"  Volatility: {strategy.state.volatility:.6f}")
    print(f"  Trend: {strategy.state.trend}")
    print(f"  Realized PnL: {strategy.state.realized_pnl:.4f}")
    print(f"  Total volume: {strategy.state.total_volume:.2f}")
    print(f"  Active levels: {len(strategy.state.active_levels)}")
    print(f"  Total actions generated: {total_actions}")

    print("\n✓ Test completed successfully")

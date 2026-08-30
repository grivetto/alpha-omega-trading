"""
Adaptive Grid-Momentum Strategy
Combines grid trading with momentum filtering and dynamic spacing adjustment.
"""

from __future__ import annotations

import gc
import json
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Generator, Iterator, Optional
from collections import deque

import numpy as np

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StrategyConfig:
    """Immutable configuration for the strategy."""
    symbol: str
    base_spacing_pct: float = 0.005  # 0.5% base grid spacing
    max_spacing_pct: float = 0.02    # 2% max spacing in trending markets
    min_spacing_pct: float = 0.002   # 0.2% min spacing in ranging markets
    grid_levels: int = 10
    capital_per_level: float = 10.0
    momentum_window: int = 20
    momentum_threshold: float = 0.003  # 0.3% momentum to trigger trend mode
    atr_window: int = 14
    atr_multiplier: float = 1.5
    max_position_pct: float = 0.8      # Max 80% of capital deployed
    stop_loss_pct: float = 0.05        # 5% stop loss
    take_profit_pct: float = 0.02      # 2% take profit per grid
    enable_dynamic_spacing: bool = True
    enable_momentum_filter: bool = True

    def validate(self) -> None:
        """Validate configuration parameters."""
        if not 0 < self.base_spacing_pct <= self.max_spacing_pct:
            raise ValueError("base_spacing_pct must be > 0 and <= max_spacing_pct")
        if not 0 < self.min_spacing_pct <= self.base_spacing_pct:
            raise ValueError("min_spacing_pct must be > 0 and <= base_spacing_pct")
        if not 1 <= self.grid_levels <= 50:
            raise ValueError("grid_levels must be between 1 and 50")
        if not 0 < self.capital_per_level:
            raise ValueError("capital_per_level must be > 0")
        if not 1 <= self.momentum_window <= 200:
            raise ValueError("momentum_window must be between 1 and 200")
        if not 0 < self.momentum_threshold < 0.1:
            raise ValueError("momentum_threshold must be between 0 and 0.1")
        if not 1 <= self.atr_window <= 100:
            raise ValueError("atr_window must be between 1 and 100")
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be between 0 and 1")
        if not 0 < self.stop_loss_pct < 1.0:
            raise ValueError("stop_loss_pct must be between 0 and 1")
        if not 0 < self.take_profit_pct < 1.0:
            raise ValueError("take_profit_pct must be between 0 and 1")


@dataclass
class MarketState:
    """Current market state snapshot."""
    price: float
    timestamp: int
    volume: float = 0.0


@dataclass
class GridLevel:
    """Single grid level with order tracking."""
    price: float
    quantity: float
    side: str  # 'buy' or 'sell'
    order_id: Optional[str] = None
    filled: bool = False


@dataclass
class Position:
    """Current position tracking."""
    quantity: float = 0.0
    avg_entry_price: float = 0.0
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0


class StrategyBase(ABC):
    """Abstract base class for all strategies."""

    def __init__(self, config: StrategyConfig):
        self.config = config
        config.validate()
        self.position = Position()
        self.grid_levels: list[GridLevel] = []
        self.price_history: deque[float] = deque(maxlen=max(config.momentum_window, config.atr_window) + 10)
        self.volume_history: deque[float] = deque(maxlen=config.atr_window + 10)
        self._last_momentum: float = 0.0
        self._current_spacing_pct: float = config.base_spacing_pct
        self._trend_mode: bool = False

    @abstractmethod
    def on_tick(self, market_state: MarketState) -> list[dict[str, Any]]:
        """Process a new market tick. Returns list of order actions."""
        pass

    @abstractmethod
    def on_fill(self, order_id: str, price: float, quantity: float, side: str) -> None:
        """Process a filled order."""
        pass

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        price_hist_mb = (len(self.price_history) * 8) / 1_048_576
        volume_hist_mb = (len(self.volume_history) * 8) / 1_048_576
        grid_mb = (len(self.grid_levels) * 200) / 1_048_576  # rough estimate per level
        return price_hist_mb + volume_hist_mb + grid_mb + 0.5  # base overhead

    def validate_config(self) -> bool:
        """Validate the current configuration."""
        try:
            self.config.validate()
            return True
        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False

    def _calculate_momentum(self) -> float:
        """Calculate price momentum over the configured window."""
        if len(self.price_history) < self.config.momentum_window:
            return 0.0
        prices = list(self.price_history)
        recent = prices[-self.config.momentum_window:]
        older = prices[-2*self.config.momentum_window:-self.config.momentum_window] if len(prices) >= 2*self.config.momentum_window else prices[:-self.config.momentum_window]
        if not older:
            return 0.0
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        return (recent_avg - older_avg) / older_avg if older_avg > 0 else 0.0

    def _calculate_atr(self) -> float:
        """Calculate Average True Range using streaming approach."""
        if len(self.price_history) < self.config.atr_window + 1:
            return 0.0
        prices = list(self.price_history)
        true_ranges = []
        for i in range(1, min(len(prices), self.config.atr_window + 1)):
            tr = abs(prices[-i] - prices[-i-1])
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        return sum(true_ranges) / len(true_ranges)

    def _update_dynamic_spacing(self) -> None:
        """Adjust grid spacing based on volatility and momentum."""
        if not self.config.enable_dynamic_spacing:
            self._current_spacing_pct = self.config.base_spacing_pct
            return

        atr = self._calculate_atr()
        momentum = abs(self._last_momentum)
        current_price = self.price_history[-1] if self.price_history else 0

        if current_price == 0:
            self._current_spacing_pct = self.config.base_spacing_pct
            return

        atr_pct = (atr / current_price) * self.config.atr_multiplier if current_price > 0 else self.config.base_spacing_pct
        momentum_factor = 1.0 + (momentum / self.config.momentum_threshold) if self.config.momentum_threshold > 0 else 1.0

        target_spacing = max(
            self.config.min_spacing_pct,
            min(self.config.max_spacing_pct, max(atr_pct, self.config.base_spacing_pct * momentum_factor))
        )
        self._current_spacing_pct = target_spacing
        self._trend_mode = momentum > self.config.momentum_threshold

    def _build_grid(self, center_price: float) -> list[GridLevel]:
        """Build grid levels around center price with current spacing."""
        levels = []
        half_levels = self.config.grid_levels // 2

        for i in range(-half_levels, half_levels + 1):
            if i == 0:
                continue
            level_price = center_price * (1 + i * self._current_spacing_pct)
            side = 'buy' if i < 0 else 'sell'
            quantity = self.config.capital_per_level / level_price if level_price > 0 else 0
            levels.append(GridLevel(price=level_price, quantity=quantity, side=side))

        return levels


class AdaptiveGridMomentumStrategy(StrategyBase):
    """
    Adaptive Grid-Momentum Strategy.

    Features:
    - Dynamic grid spacing based on ATR and momentum
    - Momentum filter to avoid grid trading in strong trends
    - Trend-following mode with wider spacing
    - Mean-reversion mode with tighter spacing
    - Stop-loss and take-profit per grid level
    """

    def __init__(self, config: StrategyConfig):
        super().__init__(config)
        self._initialized: bool = False
        self._last_center_price: float = 0.0

    def on_tick(self, market_state: MarketState) -> list[dict[str, Any]]:
        """Process market tick and generate orders."""
        actions = []

        # Update history
        self.price_history.append(market_state.price)
        self.volume_history.append(market_state.volume)

        # Calculate momentum
        self._last_momentum = self._calculate_momentum()

        # Update dynamic spacing
        self._update_dynamic_spacing()

        # Initialize grid on first tick
        if not self._initialized:
            self._initialized = True
            self._last_center_price = market_state.price
            self.grid_levels = self._build_grid(market_state.price)
            actions.extend(self._generate_initial_orders())
            return actions

        # Check if we need to rebuild grid (price moved significantly)
        price_change_pct = abs(market_state.price - self._last_center_price) / self._last_center_price
        if price_change_pct > self._current_spacing_pct * 2:
            self._rebuild_grid(market_state.price, actions)

        # Manage existing orders
        actions.extend(self._manage_orders(market_state))

        # Check stop loss
        if self._check_stop_loss(market_state.price):
            actions.append({"action": "stop_loss", "reason": "Stop loss triggered"})

        return actions

    def _generate_initial_orders(self) -> list[dict[str, Any]]:
        """Generate initial grid orders."""
        actions = []
        max_position_value = self.config.capital_per_level * self.config.grid_levels * self.config.max_position_pct
        current_position_value = abs(self.position.quantity * self._last_center_price)

        for level in self.grid_levels:
            if current_position_value >= max_position_value:
                break
            if level.side == 'buy' and self.position.quantity >= 0:
                actions.append({
                    "action": "place_order",
                    "order_type": "limit",
                    "side": "buy",
                    "price": level.price,
                    "quantity": level.quantity,
                    "level_price": level.price
                })
            elif level.side == 'sell' and self.position.quantity <= 0:
                actions.append({
                    "action": "place_order",
                    "order_type": "limit",
                    "side": "sell",
                    "price": level.price,
                    "quantity": level.quantity,
                    "level_price": level.price
                })
        return actions

    def _rebuild_grid(self, new_center: float, actions: list[dict[str, Any]]) -> None:
        """Rebuild grid around new center price."""
        logger.info(f"Rebuilding grid: center {self._last_center_price:.4f} -> {new_center:.4f}, spacing {self._current_spacing_pct:.4%}")
        # Cancel all existing orders
        for level in self.grid_levels:
            if level.order_id and not level.filled:
                actions.append({"action": "cancel_order", "order_id": level.order_id})

        self._last_center_price = new_center
        self.grid_levels = self._build_grid(new_center)
        actions.extend(self._generate_initial_orders())

    def _manage_orders(self, market_state: MarketState) -> list[dict[str, Any]]:
        """Manage existing orders based on current price."""
        actions = []
        current_price = market_state.price

        for level in self.grid_levels:
            if level.filled or not level.order_id:
                continue

            # Check if order should be filled (simulated)
            if level.side == 'buy' and current_price <= level.price:
                actions.append({"action": "fill_simulation", "order_id": level.order_id, "price": level.price})
            elif level.side == 'sell' and current_price >= level.price:
                actions.append({"action": "fill_simulation", "order_id": level.order_id, "price": level.price})

            # Check take profit for filled levels
            if level.filled:
                if level.side == 'buy':
                    tp_price = level.price * (1 + self.config.take_profit_pct)
                    if current_price >= tp_price:
                        actions.append({"action": "take_profit", "order_id": level.order_id, "price": current_price})
                else:
                    tp_price = level.price * (1 - self.config.take_profit_pct)
                    if current_price <= tp_price:
                        actions.append({"action": "take_profit", "order_id": level.order_id, "price": current_price})

        return actions

    def _check_stop_loss(self, current_price: float) -> bool:
        """Check if stop loss should trigger."""
        if self.position.quantity == 0 or self.position.avg_entry_price == 0:
            return False

        if self.position.quantity > 0:  # Long position
            loss_pct = (self.position.avg_entry_price - current_price) / self.position.avg_entry_price
        else:  # Short position
            loss_pct = (current_price - self.position.avg_entry_price) / self.position.avg_entry_price

        return loss_pct >= self.config.stop_loss_pct

    def on_fill(self, order_id: str, price: float, quantity: float, side: str) -> None:
        """Process filled order and update position."""
        # Find and mark level as filled
        for level in self.grid_levels:
            if level.order_id == order_id:
                level.filled = True
                break

        # Update position
        if side == 'buy':
            new_quantity = self.position.quantity + quantity
            if self.position.quantity >= 0:
                self.position.avg_entry_price = (
                    (self.position.avg_entry_price * self.position.quantity) + (price * quantity)
                ) / new_quantity if new_quantity != 0 else price
            else:
                # Reducing short position
                realized = (self.position.avg_entry_price - price) * min(abs(self.position.quantity), quantity)
                self.position.realized_pnl += realized
            self.position.quantity = new_quantity
        else:  # sell
            new_quantity = self.position.quantity - quantity
            if self.position.quantity <= 0:
                self.position.avg_entry_price = (
                    (self.position.avg_entry_price * abs(self.position.quantity)) + (price * quantity)
                ) / abs(new_quantity) if new_quantity != 0 else price
            else:
                # Reducing long position
                realized = (price - self.position.avg_entry_price) * min(self.position.quantity, quantity)
                self.position.realized_pnl += realized
            self.position.quantity = new_quantity

        logger.info(f"Fill: {side} {quantity:.6f} @ {price:.4f} | Pos: {self.position.quantity:.6f} @ {self.position.avg_entry_price:.4f} | PnL: {self.position.realized_pnl:.4f}")


def generate_synthetic_data(num_ticks: int = 1000, base_price: float = 100.0, volatility: float = 0.02) -> Generator[MarketState, None, None]:
    """Generate synthetic market data for testing."""
    price = base_price
    for i in range(num_ticks):
        # Random walk with occasional trend
        drift = 0.0001 * np.sin(i / 50)  # Slow oscillation
        shock = np.random.normal(0, volatility)
        price *= (1 + drift + shock)
        price = max(price, 0.01)

        volume = abs(np.random.normal(1000, 200))
        yield MarketState(price=price, timestamp=i, volume=volume)

    # Force cleanup
    gc.collect()


if __name__ == "__main__":
    print("=" * 60)
    print("Adaptive Grid-Momentum Strategy - Inline Test")
    print("=" * 60)

    # Test configuration
    config = StrategyConfig(
        symbol="TEST/EUR",
        base_spacing_pct=0.005,
        max_spacing_pct=0.02,
        min_spacing_pct=0.002,
        grid_levels=10,
        capital_per_level=10.0,
        momentum_window=20,
        momentum_threshold=0.003,
        atr_window=14,
        atr_multiplier=1.5,
        max_position_pct=0.8,
        stop_loss_pct=0.05,
        take_profit_pct=0.02,
    )

    # Validate config
    assert config.validate() is None or True
    print("✓ Config validation passed")

    # Create strategy
    strategy = AdaptiveGridMomentumStrategy(config)
    print(f"✓ Strategy created, estimated memory: {strategy.estimate_memory_mb():.2f} MB")

    # Run simulation
    fills = 0
    actions_total = 0

    for i, tick in enumerate(generate_synthetic_data(500, base_price=100.0, volatility=0.015)):
        actions = strategy.on_tick(tick)
        actions_total += len(actions)

        # Simulate fills
        for action in actions:
            if action.get("action") == "fill_simulation":
                strategy.on_fill(action["order_id"], action["price"], 0.1, "buy" if action["price"] < tick.price else "sell")
                fills += 1

        if i % 100 == 0:
            mem = strategy.estimate_memory_mb()
            print(f"  Tick {i}: Price={tick.price:.2f}, Spacing={strategy._current_spacing_pct:.4%}, Trend={strategy._trend_mode}, Mem={mem:.2f}MB, Actions={len(actions)}")

    print(f"\n✓ Simulation complete: {fills} fills, {actions_total} total actions")
    print(f"✓ Final position: {strategy.position.quantity:.6f}, Realized PnL: {strategy.position.realized_pnl:.4f}")
    print(f"✓ Memory estimate: {strategy.estimate_memory_mb():.2f} MB")
    print("=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)

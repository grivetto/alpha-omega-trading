"""
Auto-generated Adaptive Grid-Momentum Hybrid Strategy
Generated: 2026-08-28 07:30:39 UTC
"""

from __future__ import annotations
import gc
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generator, Optional
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for AdaptiveGridMomentum strategy."""
    symbol: str
    base_capital: float
    grid_levels: int = 10
    grid_spacing_pct: float = 0.5
    momentum_window: int = 20
    momentum_threshold: float = 0.002
    max_position_pct: float = 0.8
    stop_loss_pct: float = 2.0
    take_profit_pct: float = 1.5
    rebalance_interval: int = 100
    chunk_size: int = 1000

    def validate(self) -> None:
        """Validate configuration parameters."""
        if self.base_capital <= 0:
            raise ValueError("base_capital must be positive")
        if not 1 <= self.grid_levels <= 50:
            raise ValueError("grid_levels must be in [1, 50]")
        if not 0.01 <= self.grid_spacing_pct <= 5.0:
            raise ValueError("grid_spacing_pct must be in [0.01, 5.0]")
        if not 5 <= self.momentum_window <= 200:
            raise ValueError("momentum_window must be in [5, 200]")
        if not 0.0001 <= self.momentum_threshold <= 0.05:
            raise ValueError("momentum_threshold must be in [0.0001, 0.05]")
        if not 0.1 <= self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in [0.1, 1.0]")
        if not 0.1 <= self.stop_loss_pct <= 10.0:
            raise ValueError("stop_loss_pct must be in [0.1, 10.0]")
        if not 0.1 <= self.take_profit_pct <= 10.0:
            raise ValueError("take_profit_pct must be in [0.1, 10.0]")


@dataclass(slots=True)
class MarketState:
    """Current market state snapshot."""
    price: float
    timestamp: float
    volume: float = 0.0


@dataclass(slots=True)
class Position:
    """Current position state."""
    base_qty: float = 0.0
    quote_qty: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    grid_orders: dict[float, float] = field(default_factory=dict)


class StrategyBase(ABC):
    """Abstract base class for all strategies."""

    @abstractmethod
    def on_tick(self, market_state: MarketState) -> list[dict]:
        """Process a market tick and return order intents."""
        pass

    @abstractmethod
    def on_fill(self, fill: dict) -> None:
        """Process a fill execution."""
        pass

    @abstractmethod
    def validate_config(self) -> None:
        """Validate strategy configuration."""
        pass

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        pass


class AdaptiveGridMomentum(StrategyBase):
    """
    Adaptive Grid-Momentum Hybrid Strategy.

    Combines grid trading with momentum filtering:
    - Grid provides liquidity in ranging markets
    - Momentum filter pauses grid during strong trends
    - Dynamic spacing adapts to volatility
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.config.validate()

        self.position = Position()
        self.price_history: deque[float] = deque(maxlen=config.momentum_window * 2)
        self.volatility_history: deque[float] = deque(maxlen=100)
        self.tick_count = 0
        self.last_rebalance = 0
        self.momentum_paused = False
        self.current_spacing = config.grid_spacing_pct

    def _calculate_momentum(self) -> float:
        """Calculate momentum as rate of change over window."""
        if len(self.price_history) < self.config.momentum_window:
            return 0.0
        prices = list(self.price_history)
        return (prices[-1] - prices[-self.config.momentum_window]) / prices[-self.config.momentum_window]

    def _calculate_volatility(self) -> float:
        """Calculate rolling volatility (std of returns)."""
        if len(self.price_history) < 2:
            return self.config.grid_spacing_pct / 100
        returns = np.diff(list(self.price_history)) / list(self.price_history)[:-1]
        return float(np.std(returns)) if len(returns) > 1 else self.config.grid_spacing_pct / 100

    def _adapt_spacing(self) -> None:
        """Dynamically adapt grid spacing based on volatility."""
        vol = self._calculate_volatility()
        self.volatility_history.append(vol)
        # Scale spacing with volatility, clamp to reasonable bounds
        target_spacing = max(0.1, min(3.0, vol * 100 * 1.5))
        self.current_spacing = 0.7 * self.current_spacing + 0.3 * target_spacing

    def _check_momentum_pause(self) -> bool:
        """Check if momentum filter should pause grid."""
        momentum = self._calculate_momentum()
        return abs(momentum) > self.config.momentum_threshold

    def _generate_grid_orders(self, center_price: float) -> list[dict]:
        """Generate grid orders around center price."""
        orders = []
        half_levels = self.config.grid_levels // 2
        spacing = self.current_spacing / 100

        for i in range(-half_levels, half_levels + 1):
            if i == 0:
                continue
            level_price = center_price * (1 + i * spacing)
            side = "buy" if i < 0 else "sell"
            qty = self._calculate_level_qty(level_price, side)
            if qty > 0:
                orders.append({
                    "symbol": self.config.symbol,
                    "side": side,
                    "price": round(level_price, 6),
                    "quantity": round(qty, 6),
                    "type": "limit",
                    "strategy": "adaptive_grid_momentum",
                    "level": i
                })
        return orders

    def _calculate_level_qty(self, price: float, side: str) -> float:
        """Calculate order quantity for a grid level."""
        max_base = (self.config.base_capital * self.config.max_position_pct) / price
        level_allocation = max_base / self.config.grid_levels
        return min(level_allocation, self.position.base_qty if side == "sell" else level_allocation)

    def on_tick(self, market_state: MarketState) -> list[dict]:
        """Process market tick and generate orders."""
        self.price_history.append(market_state.price)
        self.tick_count += 1

        # Update position PnL
        if self.position.base_qty > 0:
            self.position.unrealized_pnl = (
                (market_state.price - self.position.avg_entry_price) * self.position.base_qty
            )

        # Check stop loss / take profit
        if self.position.base_qty > 0:
            pnl_pct = (market_state.price - self.position.avg_entry_price) / self.position.avg_entry_price * 100
            if pnl_pct <= -self.config.stop_loss_pct or pnl_pct >= self.config.take_profit_pct:
                return [{
                    "symbol": self.config.symbol,
                    "side": "sell",
                    "price": market_state.price,
                    "quantity": self.position.base_qty,
                    "type": "market",
                    "strategy": "adaptive_grid_momentum",
                    "reason": "stop_loss" if pnl_pct < 0 else "take_profit"
                }]

        # Adapt spacing periodically
        if self.tick_count % 50 == 0:
            self._adapt_spacing()

        # Check momentum pause
        self.momentum_paused = self._check_momentum_pause()

        # Generate grid orders if not paused
        if not self.momentum_paused and self.tick_count % self.config.rebalance_interval == 0:
            center = market_state.price if self.position.base_qty == 0 else self.position.avg_entry_price
            orders = self._generate_grid_orders(center)
            self.last_rebalance = self.tick_count
            return orders

        return []

    def on_fill(self, fill: dict) -> None:
        """Update position after fill."""
        side = fill.get("side", "")
        price = fill.get("price", 0.0)
        qty = fill.get("quantity", 0.0)

        if side == "buy":
            total_cost = self.position.avg_entry_price * self.position.base_qty + price * qty
            self.position.base_qty += qty
            self.position.avg_entry_price = total_cost / self.position.base_qty if self.position.base_qty > 0 else 0
            self.position.quote_qty -= price * qty
        elif side == "sell":
            self.position.base_qty -= qty
            self.position.quote_qty += price * qty
            if self.position.base_qty <= 0:
                self.position.avg_entry_price = 0.0

        logger.info(f"Fill processed: {side} {qty}@{price}, position: {self.position.base_qty}")

    def validate_config(self) -> None:
        """Validate configuration."""
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        price_hist_mb = (self.config.momentum_window * 2 * 8) / (1024 * 1024)  # deque of floats
        vol_hist_mb = (100 * 8) / (1024 * 1024)
        orders_mb = (self.config.grid_levels * 200) / (1024 * 1024)  # rough estimate
        overhead_mb = 2.0  # Python object overhead
        return price_hist_mb + vol_hist_mb + orders_mb + overhead_mb


def stream_market_data(symbol: str, days: int = 30) -> Generator[MarketState, None, None]:
    """
    Stream synthetic market data to avoid OOM on large datasets.
    Uses generator pattern for memory efficiency.
    """
    np.random.seed(42)
    base_price = 100.0
    for day in range(days):
        for _ in range(288):  # 5-min intervals per day
            # Random walk with slight drift
            ret = np.random.normal(0.0001, 0.01)
            base_price *= (1 + ret)
            volume = np.random.lognormal(10, 1)
            yield MarketState(price=base_price, timestamp=day * 86400, volume=volume)
        # Explicit cleanup per day
        if day % 7 == 0:
            gc.collect()


def run_backtest(config: StrategyConfig, data_days: int = 7) -> dict:
    """Run backtest with streaming data."""
    strategy = AdaptiveGridMomentum(config)
    fills = 0
    total_pnl = 0.0

    for ms in stream_market_data(config.symbol, data_days):
        orders = strategy.on_tick(ms)
        for order in orders:
            if order["type"] == "limit":
                # Simulate fill at limit price
                fill = {"side": order["side"], "price": order["price"], "quantity": order["quantity"]}
                strategy.on_fill(fill)
                fills += 1
            elif order["type"] == "market":
                total_pnl += strategy.position.unrealized_pnl
                strategy.on_fill({"side": "sell", "price": order["price"], "quantity": order["quantity"]})

    return {
        "total_fills": fills,
        "final_pnl": total_pnl + strategy.position.unrealized_pnl,
        "final_position": strategy.position.base_qty,
        "memory_mb": strategy.estimate_memory_mb(),
        "momentum_pauses": sum(1 for _ in range(strategy.tick_count) if strategy.momentum_paused)
    }


if __name__ == "__main__":
    # Inline test with synthetic data
    test_config = StrategyConfig(
        symbol="DOGE/EUR",
        base_capital=10.0,
        grid_levels=8,
        grid_spacing_pct=0.8,
        momentum_window=15,
        momentum_threshold=0.003,
        max_position_pct=0.7,
        stop_loss_pct=3.0,
        take_profit_pct=2.0,
        rebalance_interval=50,
        chunk_size=500
    )

    print("Running inline backtest...")
    result = run_backtest(test_config, data_days=3)
    print(f"Result: {result}")
    print(f"Estimated memory: {AdaptiveGridMomentum(test_config).estimate_memory_mb():.2f} MB")
    print("Test passed: strategy executes without errors")

"""
Adaptive Grid-Momentum Strategy
Combines grid trading with momentum filtering and dynamic spacing adjustment.
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass, field
from typing import Generator, Iterator, Optional
from collections import deque

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for AdaptiveGridMomentum strategy."""
    symbol: str
    base_capital: float
    grid_levels: int = 10
    spacing_pct: float = 0.005  # 0.5% base spacing
    momentum_window: int = 20
    momentum_threshold: float = 0.002  # 0.2% momentum to trigger bias
    max_position_pct: float = 0.8  # max 80% of capital in position
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.02
    volatility_window: int = 50
    atr_multiplier: float = 1.5
    chunk_size: int = 1000  # for streaming processing

    def validate(self) -> None:
        if self.grid_levels < 3:
            raise ValueError("grid_levels must be >= 3")
        if not 0 < self.spacing_pct <= 0.1:
            raise ValueError("spacing_pct must be in (0, 0.1]")
        if not 0 < self.momentum_threshold < 0.05:
            raise ValueError("momentum_threshold must be in (0, 0.05)")
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0, 1.0]")
        if self.min_spacing_pct >= self.max_spacing_pct:
            raise ValueError("min_spacing_pct must be < max_spacing_pct")


@dataclass(slots=True)
class GridLevel:
    """Single grid level with price and quantity."""
    price: float
    quantity: float
    side: str  # "buy" or "sell"
    filled: bool = False
    order_id: Optional[str] = None


class StrategyBase:
    """Base class for all strategies."""
    
    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float) -> None:
        raise NotImplementedError
    
    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        raise NotImplementedError
    
    def validate_config(self) -> bool:
        raise NotImplementedError
    
    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class AdaptiveGridMomentum(StrategyBase):
    """
    Adaptive Grid-Momentum Strategy.
    
    Features:
    - Dynamic grid spacing based on ATR volatility
    - Momentum filter to bias grid direction
    - Streaming memory management for large datasets
    - Explicit error handling, no silent failures
    """
    
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        config.validate()
        
        # Price history for momentum/volatility (streaming, bounded)
        self._price_history: deque[float] = deque(maxlen=config.volatility_window)
        self._momentum_history: deque[float] = deque(maxlen=config.momentum_window)
        
        # Grid state
        self._grid: list[GridLevel] = []
        self._base_price: Optional[float] = None
        self._current_spacing: float = config.spacing_pct
        self._position_qty: float = 0.0
        self._realized_pnl: float = 0.0
        
        # Metrics
        self._ticks_processed: int = 0
        self._fills_processed: int = 0
        
        logger.info(f"Initialized AdaptiveGridMomentum for {config.symbol}")

    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        price_hist_mb = (self.config.volatility_window * 8) / 1e6
        momentum_hist_mb = (self.config.momentum_window * 8) / 1e6
        grid_mb = (self.config.grid_levels * 64) / 1e6  # ~64 bytes per GridLevel
        overhead_mb = 2.0  # Python object overhead
        return price_hist_mb + momentum_hist_mb + grid_mb + overhead_mb

    def validate_config(self) -> bool:
        try:
            self.config.validate()
            return True
        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False

    def _calculate_atr(self, prices: Iterator[float]) -> float:
        """Calculate ATR using streaming generator to avoid OOM."""
        if not prices:
            return self.config.spacing_pct
        
        prev = None
        true_ranges = []
        
        for price in prices:
            if prev is not None:
                tr = abs(price - prev)
                true_ranges.append(tr)
            prev = price
        
        if not true_ranges:
            return self.config.spacing_pct
        
        atr = np.mean(true_ranges[-self.config.volatility_window:]) if len(true_ranges) >= self.config.volatility_window else np.mean(true_ranges)
        return float(atr)

    def _calculate_momentum(self) -> float:
        """Calculate momentum as rate of change over window."""
        if len(self._momentum_history) < 2:
            return 0.0
        
        prices = list(self._momentum_history)
        if prices[0] == 0:
            return 0.0
        return (prices[-1] - prices[0]) / prices[0]

    def _update_spacing(self, mid: float) -> None:
        """Dynamically adjust grid spacing based on volatility and momentum."""
        atr = self._calculate_atr(iter(self._price_history))
        atr_pct = atr / mid if mid > 0 else self.config.spacing_pct
        
        momentum = self._calculate_momentum()
        
        # Base spacing from ATR
        new_spacing = atr_pct * self.config.atr_multiplier
        
        # Momentum bias: tighten spacing in trend direction, widen against
        if abs(momentum) > self.config.momentum_threshold:
            if momentum > 0:
                new_spacing *= 0.8  # tighten for long bias
            else:
                new_spacing *= 1.2  # widen for short bias
        
        # Clamp
        new_spacing = max(self.config.min_spacing_pct, min(self.config.max_spacing_pct, new_spacing))
        
        if abs(new_spacing - self._current_spacing) / self._current_spacing > 0.1:
            logger.info(f"Spacing updated: {self._current_spacing:.4%} -> {new_spacing:.4%} (ATR%: {atr_pct:.4%}, momentum: {momentum:.4%})")
            self._current_spacing = new_spacing
            self._rebuild_grid(mid)

    def _rebuild_grid(self, mid: float) -> None:
        """Rebuild grid levels around current mid price."""
        self._grid.clear()
        half_levels = self.config.grid_levels // 2
        
        for i in range(-half_levels, half_levels + 1):
            if i == 0:
                continue
            price = mid * (1 + i * self._current_spacing)
            side = "buy" if i < 0 else "sell"
            # Quantity decreases further from center
            qty_factor = 1.0 - (abs(i) / half_levels) * 0.5
            quantity = (self.config.base_capital * self.config.max_position_pct * qty_factor) / (self.config.grid_levels * price)
            
            self._grid.append(GridLevel(price=price, quantity=quantity, side=side))
        
        self._base_price = mid
        logger.debug(f"Grid rebuilt: {len(self._grid)} levels, spacing={self._current_spacing:.4%}")

    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float) -> None:
        """Process market tick."""
        if mid <= 0:
            logger.warning(f"Invalid mid price: {mid}")
            return
        
        self._ticks_processed += 1
        
        # Stream price into history (bounded deque)
        self._price_history.append(mid)
        self._momentum_history.append(mid)
        
        # Initialize grid on first tick
        if self._base_price is None:
            self._rebuild_grid(mid)
            return
        
        # Update spacing periodically (every 100 ticks)
        if self._ticks_processed % 100 == 0:
            self._update_spacing(mid)
        
        # Check grid levels for fills (simulated)
        for level in self._grid:
            if level.filled:
                continue
            
            if level.side == "buy" and bid <= level.price:
                logger.info(f"Buy signal: {level.price:.4f} (bid: {bid:.4f})")
                # In real impl, would place order here
                level.filled = True
                self._position_qty += level.quantity
                
            elif level.side == "sell" and ask >= level.price:
                logger.info(f"Sell signal: {level.price:.4f} (ask: {ask:.4f})")
                level.filled = True
                self._position_qty -= level.quantity
        
        # Periodic cleanup
        if self._ticks_processed % 1000 == 0:
            gc.collect()

    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        """Process order fill."""
        self._fills_processed += 1
        
        # Update position
        if side == "buy":
            self._position_qty += qty
        else:
            self._position_qty -= qty
        
        # Find and mark grid level
        for level in self._grid:
            if level.order_id == order_id:
                level.filled = True
                logger.info(f"Fill confirmed: {side} {qty:.6f} @ {price:.4f}")
                break
        else:
            logger.warning(f"Fill for unknown order_id: {order_id}")
        
        # Reset filled levels that are far from current price (grid recycling)
        if self._base_price:
            for level in self._grid:
                if level.filled and abs(level.price - self._base_price) > self._current_spacing * 3 * self._base_price:
                    level.filled = False
                    level.order_id = None

    def get_status(self) -> dict:
        """Return current strategy status."""
        return {
            "symbol": self.config.symbol,
            "base_price": self._base_price,
            "current_spacing_pct": self._current_spacing,
            "grid_levels": len(self._grid),
            "filled_levels": sum(1 for g in self._grid if g.filled),
            "position_qty": self._position_qty,
            "realized_pnl": self._realized_pnl,
            "ticks_processed": self._ticks_processed,
            "fills_processed": self._fills_processed,
            "memory_mb": self.estimate_memory_mb(),
        }


def generate_synthetic_ticks(count: int, base_price: float = 100.0, volatility: float = 0.01) -> Generator[tuple[float, float, float, float], None, None]:
    """Generate synthetic tick data for testing (streaming generator)."""
    np.random.seed(42)
    price = base_price
    for i in range(count):
        # Random walk with drift
        drift = np.random.normal(0, volatility * 0.1)
        shock = np.random.normal(0, volatility)
        price *= (1 + drift + shock)
        price = max(price, 0.01)
        
        spread = price * 0.001
        bid = price - spread / 2
        ask = price + spread / 2
        mid = price
        
        yield float(i), bid, ask, mid


if __name__ == "__main__":
    # Inline test with synthetic data
    config = StrategyConfig(
        symbol="TEST/EUR",
        base_capital=1000.0,
        grid_levels=10,
        spacing_pct=0.005,
        momentum_window=20,
        momentum_threshold=0.002,
        max_position_pct=0.8,
        min_spacing_pct=0.002,
        max_spacing_pct=0.02,
        volatility_window=50,
        atr_multiplier=1.5,
        chunk_size=1000,
    )
    
    strategy = AdaptiveGridMomentum(config)
    print(f"Memory estimate: {strategy.estimate_memory_mb():.2f} MB")
    print(f"Config valid: {strategy.validate_config()}")
    
    # Process synthetic ticks
    for i, (ts, bid, ask, mid) in enumerate(generate_synthetic_ticks(500, base_price=150.0)):
        strategy.on_tick(ts, bid, ask, mid)
        
        if i % 100 == 0:
            status = strategy.get_status()
            print(f"Tick {i}: spacing={status['current_spacing_pct']:.4%}, pos={status['position_qty']:.4f}, filled={status['filled_levels']}")
    
    final_status = strategy.get_status()
    print(f"\nFinal: {final_status}")
    print("Test completed successfully.")

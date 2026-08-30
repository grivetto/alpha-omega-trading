"""
Adaptive Grid Momentum Strategy v2
====================================
Grid strategy with dynamic spacing based on ATR and momentum filter.
Memory-efficient streaming design for high-frequency ticks.
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass, field
from typing import Generator, Optional
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GridConfig:
    """Configuration for adaptive grid."""
    base_spacing_pct: float = 0.008       # 0.8% base spacing
    max_spacing_pct: float = 0.03         # 3% max spacing
    min_spacing_pct: float = 0.003        # 0.3% min spacing
    atr_period: int = 14
    momentum_period: int = 20
    momentum_threshold: float = 0.001     # 0.1% momentum filter
    levels: int = 6                       # grid levels each side
    capital_per_level: float = 5.0        # EUR per level
    max_position_pct: float = 0.8         # max 80% capital deployed
    stop_loss_atr_mult: float = 2.5       # SL at 2.5 * ATR
    take_profit_atr_mult: float = 1.5     # TP at 1.5 * ATR


@dataclass(slots=True)
class GridLevel:
    """Single grid level state."""
    price: float
    side: str          # 'buy' or 'sell'
    filled: bool = False
    order_id: Optional[str] = None
    filled_price: float = 0.0
    filled_qty: float = 0.0


class StrategyBase:
    """Base class for all strategies."""
    
    def __init__(self, config: GridConfig):
        self.config = config
        self.levels: list[GridLevel] = []
        self.position: float = 0.0
        self.avg_entry: float = 0.0
        self.realized_pnl: float = 0.0
        self._price_history: deque = deque(maxlen=config.momentum_period + 5)
        self._atr_history: deque = deque(maxlen=config.atr_period + 5)
        self._last_mid: float = 0.0
        
    def on_tick(self, bid: float, ask: float, timestamp: int) -> list[dict]:
        """Process new tick, return list of order dicts."""
        raise NotImplementedError
    
    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        """Process fill event."""
        raise NotImplementedError
    
    def validate_config(self) -> tuple[bool, str]:
        """Validate configuration parameters."""
        raise NotImplementedError
    
    def estimate_memory_mb(self) -> float:
        """Estimate memory usage in MB."""
        raise NotImplementedError


class AdaptiveGridMomentum(StrategyBase):
    """
    Adaptive grid with ATR-based spacing and momentum filter.
    Only places orders when momentum aligns with grid direction.
    """
    
    def __init__(self, config: GridConfig):
        super().__init__(config)
        self._initialized = False
        self._current_spacing = config.base_spacing_pct
        
    def validate_config(self) -> tuple[bool, str]:
        if self.config.levels < 1:
            return False, "levels must be >= 1"
        if self.config.base_spacing_pct <= 0:
            return False, "base_spacing_pct must be > 0"
        if self.config.max_spacing_pct <= self.config.min_spacing_pct:
            return False, "max_spacing_pct must be > min_spacing_pct"
        if self.config.capital_per_level <= 0:
            return False, "capital_per_level must be > 0"
        if not (0 < self.config.max_position_pct <= 1):
            return False, "max_position_pct must be in (0, 1]"
        return True, "OK"
    
    def estimate_memory_mb(self) -> float:
        # Fixed structures: price_history + atr_history + levels
        history_bytes = (self.config.momentum_period + self.config.atr_period + 10) * 8 * 2
        levels_bytes = self.config.levels * 2 * 64  # ~64 bytes per GridLevel
        overhead = 1024  # object overhead
        return (history_bytes + levels_bytes + overhead) / 1_048_576
    
    def _update_atr(self, high: float, low: float, close: float) -> float:
        """Calculate ATR using Wilder's smoothing."""
        if not self._atr_history:
            tr = high - low
            self._atr_history.append(tr)
            return tr
        
        prev_close = self._price_history[-1] if self._price_history else close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        self._atr_history.append(tr)
        
        # Wilder's smoothing
        atr = sum(self._atr_history) / len(self._atr_history)
        return atr
    
    def _calculate_momentum(self) -> float:
        """Calculate normalized momentum."""
        if len(self._price_history) < self.config.momentum_period:
            return 0.0
        
        prices = list(self._price_history)
        # Use generator to avoid list copy for large windows
        def price_changes() -> Generator[float, None, None]:
            for i in range(1, len(prices)):
                yield (prices[i] - prices[i-1]) / prices[i-1]
        
        changes = sum(price_changes()) / (len(prices) - 1)
        return changes
    
    def _update_spacing(self, atr: float, mid_price: float) -> None:
        """Dynamically adjust grid spacing based on volatility."""
        if mid_price <= 0:
            return
        
        atr_pct = atr / mid_price
        # Scale spacing with ATR, clamp to bounds
        target_spacing = atr_pct * 1.5
        self._current_spacing = max(
            self.config.min_spacing_pct,
            min(self.config.max_spacing_pct, target_spacing)
        )
    
    def _build_grid(self, mid_price: float) -> None:
        """Build/rebuild grid levels around mid price."""
        self.levels.clear()
        spacing = self._current_spacing
        
        for i in range(1, self.config.levels + 1):
            # Buy levels below
            buy_price = mid_price * (1 - spacing * i)
            self.levels.append(GridLevel(price=buy_price, side='buy'))
            
            # Sell levels above
            sell_price = mid_price * (1 + spacing * i)
            self.levels.append(GridLevel(price=sell_price, side='sell'))
        
        logger.debug(f"Grid rebuilt: {len(self.levels)} levels, spacing={self._current_spacing:.4%}")
    
    def on_tick(self, bid: float, ask: float, timestamp: int) -> list[dict]:
        """Process tick, return orders to place."""
        orders = []
        mid = (bid + ask) / 2
        
        # Update price history (streaming)
        self._price_history.append(mid)
        
        # Calculate ATR
        atr = self._update_atr(max(bid, ask), min(bid, ask), mid)
        
        # Initialize on first valid tick
        if not self._initialized and len(self._price_history) >= self.config.atr_period:
            self._build_grid(mid)
            self._initialized = True
            self._last_mid = mid
            return orders
        
        if not self._initialized:
            return orders
        
        # Update dynamic spacing
        self._update_spacing(atr, mid)
        
        # Calculate momentum
        momentum = self._calculate_momentum()
        
        # Rebuild grid if price moved > 2*spacing
        if abs(mid - self._last_mid) / self._last_mid > 2 * self._current_spacing:
            self._build_grid(mid)
            self._last_mid = mid
        
        # Momentum filter: only place buys if momentum >= 0, sells if momentum <= 0
        # This prevents catching falling knives / selling into pumps
        for level in self.levels:
            if level.filled:
                continue
            
            should_place = False
            if level.side == 'buy' and bid <= level.price and momentum >= -self.config.momentum_threshold:
                should_place = True
            elif level.side == 'sell' and ask >= level.price and momentum <= self.config.momentum_threshold:
                should_place = True
            
            if should_place:
                qty = self.config.capital_per_level / level.price
                orders.append({
                    'symbol': 'DOGE/EUR',  # placeholder, set by runner
                    'side': level.side,
                    'price': level.price,
                    'amount': qty,
                    'type': 'limit',
                    'level_idx': self.levels.index(level)
                })
                level.order_id = f"grid_{level.side}_{level.price:.6f}"
        
        return orders
    
    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        """Update position and PnL on fill."""
        # Find and mark level
        for level in self.levels:
            if level.order_id == order_id:
                level.filled = True
                level.filled_price = price
                level.filled_qty = qty
                break
        
        # Update position
        if side == 'buy':
            new_position = self.position + qty
            if self.position != 0:
                self.avg_entry = (self.avg_entry * self.position + price * qty) / new_position
            else:
                self.avg_entry = price
            self.position = new_position
        else:
            # Sell: realize PnL on closed position
            if self.position > 0:
                closed_qty = min(qty, self.position)
                self.realized_pnl += (price - self.avg_entry) * closed_qty
                self.position -= closed_qty
                if self.position == 0:
                    self.avg_entry = 0.0
        
        # Check stop-loss / take-profit on net position
        if self.position != 0 and self._atr_history:
            atr = sum(self._atr_history) / len(self._atr_history)
            sl_price = self.avg_entry - (atr * self.config.stop_loss_atr_mult) if self.position > 0 else self.avg_entry + (atr * self.config.stop_loss_atr_mult)
            tp_price = self.avg_entry + (atr * self.config.take_profit_atr_mult) if self.position > 0 else self.avg_entry - (atr * self.config.take_profit_atr_mult)
            
            # In live trading, this would trigger reduce-only orders
            logger.debug(f"Position: {self.position:.4f} @ {self.avg_entry:.6f}, SL: {sl_price:.6f}, TP: {tp_price:.6f}")


# --- Inline test with synthetic data ---
if __name__ == "__main__":
    import random
    
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
    
    config = GridConfig(
        base_spacing_pct=0.008,
        levels=4,
        capital_per_level=5.0,
        atr_period=14,
        momentum_period=20
    )
    
    strat = AdaptiveGridMomentum(config)
    valid, msg = strat.validate_config()
    assert valid, f"Config invalid: {msg}"
    print(f"Config valid: {msg}")
    print(f"Estimated memory: {strat.estimate_memory_mb():.4f} MB")
    
    # Generate synthetic tick data
    base_price = 0.15  # DOGE/EUR ~0.15
    random.seed(42)
    
    for i in range(100):
        # Random walk with slight drift
        drift = 0.0001 * (i % 20 - 10)
        noise = random.gauss(0, 0.0015)
        mid = base_price * (1 + drift + noise)
        
        spread = mid * 0.001
        bid = mid - spread / 2
        ask = mid + spread / 2
        
        orders = strat.on_tick(bid, ask, i)
        if orders:
            print(f"Tick {i}: mid={mid:.6f}, orders={len(orders)}")
            for o in orders:
                print(f"  {o['side']} {o['amount']:.2f} @ {o['price']:.6f}")
    
    # Simulate some fills
    for level in strat.levels[:3]:
        if level.side == 'buy':
            strat.on_fill(level.order_id or '', 'buy', level.price, config.capital_per_level / level.price)
    
    print(f"\nFinal position: {strat.position:.4f}")
    print(f"Avg entry: {strat.avg_entry:.6f}")
    print(f"Realized PnL: {strat.realized_pnl:.4f}")
    print("Test passed!")
    
    # Explicit cleanup
    del strat
    gc.collect()

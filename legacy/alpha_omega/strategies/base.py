"""
Base strategy classes for Alpha-Omega Trading System.

All strategies inherit from BaseStrategy and implement generate_signal().
Signal dataclass provides unified output format.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time

from ..core.custom_types import Signal as CoreSignal, Position, Order
from ..core.buffers import OhlcvBuffer

# Re-export for convenience
Signal = CoreSignal


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.
    
    Each strategy must implement generate_signal() which returns
    a Signal or None (hold).
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        **params
    ):
        self.symbol = symbol
        self.exchange = exchange
        self.params = params
        self.name = self.__class__.__name__
        self.last_signal: Optional[Signal] = None
        self.last_signal_ts = 0

    @abstractmethod
    async def generate_signal(
        self,
        ohlcv: OhlcvBuffer,
        current_price: float,
        atr_pct: float,
        adx: float,
        rsi: float,
        regime: str,
        equity: float,
        positions: Dict[str, Position],
        open_orders: Dict[str, Order],
    ) -> Optional[Signal]:
        """
        Generate trading signal based on market data and current state.
        
        Returns:
            Signal with action, side, price, amount, etc.
            None if no action (hold).
        """
        pass

    def get_params(self) -> Dict[str, Any]:
        """Get strategy parameters."""
        return {**self.params, "name": self.name}

    def update_params(self, **params) -> None:
        """Update strategy parameters (hot reload)."""
        self.params.update(params)


class StrategyMixin:
    """Common utility methods for strategies."""

    def _calculate_position_size(
        self,
        equity: float,
        risk_pct: float,
        entry_price: float,
        stop_loss_pct: float,
        max_position_pct: float = 0.25
    ) -> float:
        """Calculate position size based on risk management."""
        risk_amount = equity * risk_pct
        stop_distance = entry_price * stop_loss_pct
        if stop_distance <= 0:
            return 0.0
        size = risk_amount / stop_distance
        max_size = equity * max_position_pct / entry_price
        return min(size, max_size)

    def _calculate_grid_levels(
        self,
        anchor: float,
        spread_pct: float,
        levels: int,
        side: str = "both"
    ) -> List[Dict[str, float]]:
        """Calculate grid price levels."""
        grid = []
        half_spread = spread_pct / 2
        
        if side in ("buy", "both"):
            for i in range(1, levels + 1):
                price = anchor * (1 - half_spread * i)
                grid.append({"side": "buy", "price": price, "level": i})
        
        if side in ("sell", "both"):
            for i in range(1, levels + 1):
                price = anchor * (1 + half_spread * i)
                grid.append({"side": "sell", "price": price, "level": i})
        
        return grid

    def _should_reanchor(self, current_price: float, anchor: float, drift_pct: float) -> bool:
        """Check if grid should be re-anchored."""
        if anchor <= 0:
            return True
        drift = abs(current_price - anchor) / anchor
        return drift >= drift_pct / 100

    def _calculate_atr_spread(self, atr_pct: float, multiplier: float, 
                              min_spread: float, max_spread: float) -> float:
        """Calculate ATR-adaptive spread with bounds."""
        spread = atr_pct * multiplier / 100  # Convert to decimal
        return max(min_spread, min(max_spread, spread))


# Convenience function for creating signals
def create_signal(
    action: str,
    side: str = "",
    order_type: str = "limit",
    price: float = 0.0,
    amount: float = 0.0,
    strategy: str = "",
    confidence: float = 1.0,
    metadata: Dict = None
) -> Signal:
    """Factory function for creating Signal objects."""
    return Signal(
        action=action,
        side=side,
        order_type=order_type,
        price=price,
        amount=amount,
        strategy=strategy,
        confidence=confidence,
        metadata=metadata or {},
        timestamp=int(time.time() * 1000),
    )
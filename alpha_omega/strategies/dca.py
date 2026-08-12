"""
DCA (Dollar-Cost Averaging) Strategy for Alpha-Omega Trading System.

Accumulates position over time with fixed intervals, regardless of price.
Best for transitional markets and accumulation phases.
"""
from __future__ import annotations
import logging
import time
from typing import Optional, Dict, List

from .base import BaseStrategy, Signal, create_signal, StrategyMixin
from ..core.buffers import OhlcvBuffer
from ..core.custom_types import Position, Order

log = logging.getLogger("alpha_omega.strategies.dca")


class DCAStrategy(BaseStrategy, StrategyMixin):
    """
    Dollar-Cost Averaging strategy.
    
    Buys fixed amount at regular intervals regardless of price.
    Sells when take-profit reached or stop-loss triggered.
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        max_entries: int = 5,
        entry_spacing_pct: float = 0.02,  # 2% between entries
        take_profit_pct: float = 0.03,  # 3%
        stop_loss_pct: float = 0.05,  # 5%
        entry_interval_seconds: int = 3600,  # 1 hour between entries
        position_size_pct: float = 0.1,  # 10% of equity per entry
        **kwargs
    ):
        super().__init__(symbol, exchange, **kwargs)
        
        self.max_entries = max_entries
        self.entry_spacing_pct = entry_spacing_pct
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.entry_interval_seconds = entry_interval_seconds
        self.position_size_pct = position_size_pct
        
        # Runtime state
        self.entry_prices: List[float] = []
        self.last_entry_ts = 0
        self.avg_entry_price = 0.0

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
        """Generate DCA signal."""
        
        now = time.time()
        current_position = positions.get(self.symbol)
        
        # Check if we have an open position
        if current_position and current_position.size > 0:
            # Check take profit
            unrealized_pct = (current_price - self.avg_entry_price) / self.avg_entry_price
            if unrealized_pct >= self.take_profit_pct:
                return create_signal(
                    action="sell",
                    side="sell",
                    order_type="limit",
                    price=current_price * (1 + self.take_profit_pct * 0.5),
                    amount=current_position.size,
                    strategy="dca",
                    confidence=0.9,
                    metadata={"reason": "take_profit", "unrealized_pct": unrealized_pct}
                )
            
            # Check stop loss
            if unrealized_pct <= -self.stop_loss_pct:
                return create_signal(
                    action="sell",
                    side="sell",
                    order_type="market",
                    price=current_price,
                    amount=current_position.size,
                    strategy="dca",
                    confidence=1.0,
                    metadata={"reason": "stop_loss", "unrealized_pct": unrealized_pct}
                )
        
        # Check if we can add another entry
        if len(self.entry_prices) >= self.max_entries:
            return None
        
        # Check entry interval
        if now - self.last_entry_ts < self.entry_interval_seconds:
            return None
        
        # Check if price has dropped enough from last entry (or first entry)
        if self.entry_prices:
            last_entry = self.entry_prices[-1]
            if current_price > last_entry * (1 - self.entry_spacing_pct):
                # Price hasn't dropped enough
                return None
        
        # Calculate position size
        capital_per_entry = equity * self.position_size_pct
        amount = capital_per_entry / current_price
        
        if amount <= 0:
            return None
        
        self.entry_prices.append(current_price)
        self.avg_entry_price = sum(self.entry_prices) / len(self.entry_prices)
        self.last_entry_ts = now
        
        return create_signal(
            action="buy",
            side="buy",
            order_type="limit",
            price=current_price * 0.999,  # Slightly below market for maker fee
            amount=amount,
            strategy="dca",
            confidence=0.7,
            metadata={
                "entry_number": len(self.entry_prices),
                "avg_entry_price": self.avg_entry_price,
                "entry_spacing_pct": self.entry_spacing_pct * 100,
            }
        )

    def reset_entries(self) -> None:
        """Reset entry tracking (e.g., after full cycle)."""
        self.entry_prices = []
        self.last_entry_ts = 0
        self.avg_entry_price = 0.0
        log.info("DCA entries reset")
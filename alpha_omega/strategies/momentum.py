"""
Momentum Strategy for Alpha-Omega Trading System.

Trend following strategy that enters on momentum breakouts and exits on reversal signals.
Best for strong trending markets with high ADX.
"""
from __future__ import annotations
import logging
import time
from typing import Optional, Dict

from .base import BaseStrategy, Signal, create_signal, StrategyMixin
from ..core.buffers import OhlcvBuffer
from ..core.types import Position, Order

log = logging.getLogger("alpha_omega.strategies.momentum")


class MomentumStrategy(BaseStrategy, StrategyMixin):
    """
    Momentum/trend following strategy.
    
    Enters when price breaks out with strong momentum.
    Exits on trend reversal or stop-loss.
    Uses Donchian channels + ADX filter.
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        lookback_periods: int = 20,
        entry_threshold: float = 0.02,  # 2% breakout
        exit_threshold: float = 0.01,  # 1% pullback
        stop_loss_pct: float = 0.02,  # 2%
        adx_threshold: float = 25.0,
        max_hold_hours: int = 24,
        position_size_pct: float = 0.2,
        **kwargs
    ):
        super().__init__(symbol, exchange, **kwargs)
        
        self.lookback_periods = lookback_periods
        self.entry_threshold = entry_threshold
        self.exit_threshold = exit_threshold
        self.stop_loss_pct = stop_loss_pct
        self.adx_threshold = adx_threshold
        self.max_hold_hours = max_hold_hours
        self.position_size_pct = position_size_pct
        
        # Runtime state
        self.position_entry_ts = 0
        self.position_entry_price = 0.0
        self.highest_price = 0.0
        self.lowest_price = float('inf')
        self.last_signal_ts = 0
        self.min_signal_interval = 60  # 1 minute between signals

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
        """Generate momentum trading signal."""
        
        now = time.time()
        
        # Rate limiting
        if now - self.last_signal_ts < self.min_signal_interval:
            return None
        
        # Require minimum ADX for momentum strategy
        if adx < self.adx_threshold:
            return None
        
        current_position = positions.get(self.symbol)
        
        # Check existing position for exit
        if current_position and abs(current_position.size) > 1e-8:
            hold_time_hours = (now - self.position_entry_ts) / 3600
            
            if current_position.size > 0:
                # Long position
                unrealized_pct = (current_price - self.position_entry_price) / self.position_entry_price
                self.highest_price = max(self.highest_price, current_price)
                
                # Trailing stop
                trailing_stop = self.highest_price * (1 - self.exit_threshold)
                if current_price <= trailing_stop:
                    self.last_signal_ts = now
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="market",
                        price=current_price,
                        amount=current_position.size,
                        strategy="momentum",
                        confidence=0.9,
                        metadata={"reason": "trailing_stop", "unrealized_pct": unrealized_pct, "highest": self.highest_price}
                    )
                
                # Stop loss
                if unrealized_pct <= -self.stop_loss_pct:
                    self.last_signal_ts = now
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="market",
                        price=current_price,
                        amount=current_position.size,
                        strategy="momentum",
                        confidence=1.0,
                        metadata={"reason": "stop_loss", "unrealized_pct": unrealized_pct}
                    )
                
                # Max hold time
                if hold_time_hours >= self.max_hold_hours:
                    self.last_signal_ts = now
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="market",
                        price=current_price,
                        amount=current_position.size,
                        strategy="momentum",
                        confidence=0.8,
                        metadata={"reason": "max_hold", "hold_hours": hold_time_hours}
                    )
            
            else:
                # Short position
                unrealized_pct = (self.position_entry_price - current_price) / self.position_entry_price
                self.lowest_price = min(self.lowest_price, current_price)
                
                # Trailing stop
                trailing_stop = self.lowest_price * (1 + self.exit_threshold)
                if current_price >= trailing_stop:
                    self.last_signal_ts = now
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="market",
                        price=current_price,
                        amount=abs(current_position.size),
                        strategy="momentum",
                        confidence=0.9,
                        metadata={"reason": "trailing_stop", "unrealized_pct": unrealized_pct, "lowest": self.lowest_price}
                    )
                
                # Stop loss
                if unrealized_pct <= -self.stop_loss_pct:
                    self.last_signal_ts = now
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="market",
                        price=current_price,
                        amount=abs(current_position.size),
                        strategy="momentum",
                        confidence=1.0,
                        metadata={"reason": "stop_loss", "unrealized_pct": unrealized_pct}
                    )
                
                # Max hold time
                if hold_time_hours >= self.max_hold_hours:
                    self.last_signal_ts = now
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="market",
                        price=current_price,
                        amount=abs(current_position.size),
                        strategy="momentum",
                        confidence=0.8,
                        metadata={"reason": "max_hold", "hold_hours": hold_time_hours}
                    )
            
            return None  # Hold position
        
        # No position - look for breakout entry
        if ohlcv.size < self.lookback_periods + 5:
            return None
        
        # Calculate Donchian channels
        highs = [ohlcv.get_high(i) for i in range(ohlcv.size)]
        lows = [ohlcv.get_low(i) for i in range(ohlcv.size)]
        
        upper_channel = max(highs[-self.lookback_periods:])
        lower_channel = min(lows[-self.lookback_periods:])
        
        # Volume check
        volumes = [ohlcv.get_volume(i) for i in range(min(10, ohlcv.size))]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        current_volume = volumes[-1] if volumes else 0
        volume_ok = current_volume >= avg_volume * 1.2 if avg_volume > 0 else True
        
        # Long breakout: price breaks above upper channel
        if current_price > upper_channel * (1 + self.entry_threshold) and volume_ok:
            capital_per_trade = equity * self.position_size_pct
            amount = capital_per_trade / current_price
            
            if amount > 0:
                self.position_entry_ts = now
                self.position_entry_price = current_price
                self.highest_price = current_price
                self.last_signal_ts = now
                
                return create_signal(
                    action="buy",
                    side="buy",
                    order_type="limit",
                    price=current_price * 1.001,
                    amount=amount,
                    strategy="momentum",
                    confidence=0.75,
                    metadata={
                        "breakout": "long",
                        "upper_channel": upper_channel,
                        "adx": adx,
                        "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1,
                    }
                )
        
        # Short breakout: price breaks below lower channel
        if current_price < lower_channel * (1 - self.entry_threshold) and volume_ok:
            capital_per_trade = equity * self.position_size_pct
            amount = capital_per_trade / current_price
            
            if amount > 0:
                self.position_entry_ts = now
                self.position_entry_price = current_price
                self.lowest_price = current_price
                self.last_signal_ts = now
                
                return create_signal(
                    action="sell",
                    side="sell",
                    order_type="limit",
                    price=current_price * 0.999,
                    amount=amount,
                    strategy="momentum",
                    confidence=0.75,
                    metadata={
                        "breakout": "short",
                        "lower_channel": lower_channel,
                        "adx": adx,
                        "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1,
                    }
                )
        
        return None

    def on_position_closed(self) -> None:
        """Called when position is closed."""
        self.position_entry_ts = 0
        self.position_entry_price = 0.0
        self.highest_price = 0.0
        self.lowest_price = float('inf')
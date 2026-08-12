"""
Scalp Strategy for Alpha-Omega Trading System.

Fast scalping for trending markets with tight stops and quick profits.
Best for high ADX, clear trend direction.
"""
from __future__ import annotations
import logging
import time
from typing import Optional, Dict

from .base import BaseStrategy, Signal, create_signal, StrategyMixin
from ..core.buffers import OhlcvBuffer
from ..core.custom_types import Position, Order

log = logging.getLogger("alpha_omega.strategies.scalp")


class ScalpStrategy(BaseStrategy, StrategyMixin):
    """
    Scalping strategy for trending markets.
    
    Enters in trend direction, exits quickly with tight take-profit.
    Uses EMA crossover and volume confirmation.
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        take_profit_pct: float = 0.005,  # 0.5%
        stop_loss_pct: float = 0.01,  # 1%
        max_hold_seconds: int = 300,  # 5 minutes max hold
        min_spread_pct: float = 0.001,  # 0.1%
        ema_fast: int = 9,
        ema_slow: int = 21,
        volume_threshold: float = 1.5,  # 1.5x average volume
        **kwargs
    ):
        super().__init__(symbol, exchange, **kwargs)
        
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_seconds = max_hold_seconds
        self.min_spread_pct = min_spread_pct
        self.ema_fast = ema_fast
        self.ema_slow = ema_slow
        self.volume_threshold = volume_threshold
        
        # Runtime state
        self.position_entry_ts = 0
        self.last_signal_ts = 0
        self.min_signal_interval = 30  # 30 seconds between signals

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
        """Generate scalp trading signal."""
        
        now = time.time()
        
        # Rate limiting
        if now - self.last_signal_ts < self.min_signal_interval:
            return None
        
        current_position = positions.get(self.symbol)
        
        # Check existing position for exit
        if current_position and abs(current_position.size) > 1e-8:
            hold_time = now - self.position_entry_ts
            unrealized_pct = 0.0
            
            if current_position.size > 0:
                unrealized_pct = (current_price - current_position.entry_price) / current_position.entry_price
            else:
                unrealized_pct = (current_position.entry_price - current_price) / current_position.entry_price
            
            # Take profit
            if unrealized_pct >= self.take_profit_pct:
                self.last_signal_ts = now
                return create_signal(
                    action="sell" if current_position.size > 0 else "buy",
                    side="sell" if current_position.size > 0 else "buy",
                    order_type="limit",
                    price=current_price * (1 + self.take_profit_pct * 0.5) if current_position.size > 0 else current_price * (1 - self.take_profit_pct * 0.5),
                    amount=abs(current_position.size),
                    strategy="scalp",
                    confidence=0.95,
                    metadata={"reason": "take_profit", "unrealized_pct": unrealized_pct, "hold_time": hold_time}
                )
            
            # Stop loss
            if unrealized_pct <= -self.stop_loss_pct:
                self.last_signal_ts = now
                return create_signal(
                    action="sell" if current_position.size > 0 else "buy",
                    side="sell" if current_position.size > 0 else "buy",
                    order_type="market",
                    price=current_price,
                    amount=abs(current_position.size),
                    strategy="scalp",
                    confidence=1.0,
                    metadata={"reason": "stop_loss", "unrealized_pct": unrealized_pct, "hold_time": hold_time}
                )
            
            # Max hold time
            if hold_time >= self.max_hold_seconds:
                self.last_signal_ts = now
                return create_signal(
                    action="sell" if current_position.size > 0 else "buy",
                    side="sell" if current_position.size > 0 else "buy",
                    order_type="market",
                    price=current_price,
                    amount=abs(current_position.size),
                    strategy="scalp",
                    confidence=0.8,
                    metadata={"reason": "max_hold", "hold_time": hold_time}
                )
            
            return None  # Hold position
        
        # No position - look for entry
        # Need enough data for EMA
        if ohlcv.size < self.ema_slow + 10:
            return None
        
        # Calculate EMAs from close prices
        closes = [ohlcv.get_close(i) for i in range(ohlcv.size)]
        ema_fast = self._ema(closes, self.ema_fast)
        ema_slow = self._ema(closes, self.ema_slow)
        
        if ema_fast is None or ema_slow is None:
            return None
        
        # Volume check
        volumes = [ohlcv.get_volume(i) for i in range(min(20, ohlcv.size))]
        avg_volume = sum(volumes) / len(volumes) if volumes else 0
        current_volume = volumes[-1] if volumes else 0
        
        # Determine trend direction
        trend_bullish = ema_fast > ema_slow and current_price > ema_fast
        trend_bearish = ema_fast < ema_slow and current_price < ema_fast
        
        # Volume confirmation
        volume_ok = current_volume >= avg_volume * self.volume_threshold if avg_volume > 0 else True
        
        if not (trend_bullish or trend_bearish) or not volume_ok:
            return None
        
        # Check spread is acceptable
        if atr_pct < self.min_spread_pct * 100:
            return None  # Spread too tight
        
        # Entry signal
        side = "buy" if trend_bullish else "sell"
        capital_per_trade = equity * 0.15  # 15% per scalp trade
        amount = capital_per_trade / current_price
        
        if amount <= 0:
            return None
        
        self.position_entry_ts = now
        self.last_signal_ts = now
        
        return create_signal(
            action=side,
            side=side,
            order_type="limit",
            price=current_price * (0.999 if side == "buy" else 1.001),
            amount=amount,
            strategy="scalp",
            confidence=0.75,
            metadata={
                "ema_fast": ema_fast,
                "ema_slow": ema_slow,
                "trend": "bullish" if trend_bullish else "bearish",
                "volume_ratio": current_volume / avg_volume if avg_volume > 0 else 1,
                "adx": adx,
            }
        )

    def _ema(self, values: list, period: int) -> Optional[float]:
        """Calculate Exponential Moving Average."""
        if len(values) < period:
            return None
        
        multiplier = 2 / (period + 1)
        ema = sum(values[:period]) / period
        
        for value in values[period:]:
            ema = (value - ema) * multiplier + ema
        
        return ema

    def on_position_closed(self) -> None:
        """Called when position is closed."""
        self.position_entry_ts = 0
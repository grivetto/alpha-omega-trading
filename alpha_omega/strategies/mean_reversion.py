"""
Mean Reversion Strategy for Alpha-Omega Trading System.

Trades overbought/oversold conditions using Bollinger Bands and RSI.
Best for ranging/transitional markets with clear mean-reverting behavior.
"""
from __future__ import annotations
import logging
import time
from typing import Optional, Dict

from .base import BaseStrategy, Signal, create_signal, StrategyMixin
from ..core.buffers import OhlcvBuffer
from ..core.types import Position, Order

log = logging.getLogger("alpha_omega.strategies.mean_reversion")


class MeanReversionStrategy(BaseStrategy, StrategyMixin):
    """
    Mean reversion strategy using Bollinger Bands and RSI.
    
    Buys at lower band (oversold), sells at upper band (overbought).
    Exits at middle band or stop-loss.
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        bb_period: int = 20,
        bb_std: float = 2.0,
        rsi_oversold: int = 30,
        rsi_overbought: int = 70,
        take_profit_pct: float = 0.02,  # 2%
        stop_loss_pct: float = 0.03,  # 3%
        max_hold_hours: int = 12,
        position_size_pct: float = 0.15,
        require_both_signals: bool = True,
        **kwargs
    ):
        super().__init__(symbol, exchange, **kwargs)
        
        self.bb_period = bb_period
        self.bb_std = bb_std
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_hold_hours = max_hold_hours
        self.position_size_pct = position_size_pct
        self.require_both_signals = require_both_signals
        
        # Runtime state
        self.position_entry_ts = 0
        self.position_entry_price = 0.0
        self.last_signal_ts = 0
        self.min_signal_interval = 120  # 2 minutes between signals

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
        """Generate mean reversion trading signal."""
        
        now = time.time()
        
        # Rate limiting
        if now - self.last_signal_ts < self.min_signal_interval:
            return None
        
        # Don't trade in strong trends (ADX > 25)
        if adx > 25:
            return None
        
        current_position = positions.get(self.symbol)
        
        # Check existing position for exit
        if current_position and abs(current_position.size) > 1e-8:
            hold_time_hours = (now - self.position_entry_ts) / 3600
            
            if current_position.size > 0:
                # Long position - exit at middle band or take profit
                unrealized_pct = (current_price - self.position_entry_price) / self.position_entry_price
                
                # Calculate middle band (SMA)
                middle_band = self._calculate_sma(ohlcv, self.bb_period)
                
                # Take profit
                if unrealized_pct >= self.take_profit_pct:
                    self.last_signal_ts = now
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="limit",
                        price=current_price * (1 + self.take_profit_pct * 0.5),
                        amount=current_position.size,
                        strategy="mean_reversion",
                        confidence=0.9,
                        metadata={"reason": "take_profit", "unrealized_pct": unrealized_pct}
                    )
                
                # Exit at middle band (mean reversion target)
                if middle_band and current_price >= middle_band:
                    self.last_signal_ts = now
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="limit",
                        price=middle_band * 0.999,
                        amount=current_position.size,
                        strategy="mean_reversion",
                        confidence=0.85,
                        metadata={"reason": "middle_band", "middle_band": middle_band}
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
                        strategy="mean_reversion",
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
                        strategy="mean_reversion",
                        confidence=0.8,
                        metadata={"reason": "max_hold", "hold_hours": hold_time_hours}
                    )
            
            else:
                # Short position - exit at middle band or take profit
                unrealized_pct = (self.position_entry_price - current_price) / self.position_entry_price
                
                # Calculate middle band (SMA)
                middle_band = self._calculate_sma(ohlcv, self.bb_period)
                
                # Take profit
                if unrealized_pct >= self.take_profit_pct:
                    self.last_signal_ts = now
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="limit",
                        price=current_price * (1 - self.take_profit_pct * 0.5),
                        amount=abs(current_position.size),
                        strategy="mean_reversion",
                        confidence=0.9,
                        metadata={"reason": "take_profit", "unrealized_pct": unrealized_pct}
                    )
                
                # Exit at middle band
                if middle_band and current_price <= middle_band:
                    self.last_signal_ts = now
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="limit",
                        price=middle_band * 1.001,
                        amount=abs(current_position.size),
                        strategy="mean_reversion",
                        confidence=0.85,
                        metadata={"reason": "middle_band", "middle_band": middle_band}
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
                        strategy="mean_reversion",
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
                        strategy="mean_reversion",
                        confidence=0.8,
                        metadata={"reason": "max_hold", "hold_hours": hold_time_hours}
                    )
            
            return None  # Hold position
        
        # No position - look for mean reversion entry
        if ohlcv.size < self.bb_period + 5:
            return None
        
        # Calculate Bollinger Bands
        bb = self._calculate_bollinger_bands(ohlcv, self.bb_period, self.bb_std)
        if not bb:
            return None
        
        upper_band = bb["upper"]
        middle_band = bb["middle"]
        lower_band = bb["lower"]
        
        # Long entry: price at or below lower band + RSI oversold
        long_signal = False
        if current_price <= lower_band * 1.002:  # Near lower band
            if not self.require_both_signals or rsi <= self.rsi_oversold:
                long_signal = True
        
        # Short entry: price at or above upper band + RSI overbought
        short_signal = False
        if current_price >= upper_band * 0.998:  # Near upper band
            if not self.require_both_signals or rsi >= self.rsi_overbought:
                short_signal = True
        
        # Check for conflicting signals
        if long_signal and short_signal:
            return None
        
        if long_signal:
            capital_per_trade = equity * self.position_size_pct
            amount = capital_per_trade / current_price
            
            if amount > 0:
                self.position_entry_ts = now
                self.position_entry_price = current_price
                self.last_signal_ts = now
                
                return create_signal(
                    action="buy",
                    side="buy",
                    order_type="limit",
                    price=current_price * 0.999,
                    amount=amount,
                    strategy="mean_reversion",
                    confidence=0.7,
                    metadata={
                        "entry": "oversold",
                        "lower_band": lower_band,
                        "middle_band": middle_band,
                        "rsi": rsi,
                        "adx": adx,
                    }
                )
        
        elif short_signal:
            capital_per_trade = equity * self.position_size_pct
            amount = capital_per_trade / current_price
            
            if amount > 0:
                self.position_entry_ts = now
                self.position_entry_price = current_price
                self.last_signal_ts = now
                
                return create_signal(
                    action="sell",
                    side="sell",
                    order_type="limit",
                    price=current_price * 1.001,
                    amount=amount,
                    strategy="mean_reversion",
                    confidence=0.7,
                    metadata={
                        "entry": "overbought",
                        "upper_band": upper_band,
                        "middle_band": middle_band,
                        "rsi": rsi,
                        "adx": adx,
                    }
                )
        
        return None

    def _calculate_sma(self, ohlcv: OhlcvBuffer, period: int) -> Optional[float]:
        """Calculate Simple Moving Average."""
        if ohlcv.size < period:
            return None
        
        closes = [ohlcv.get_close(i) for i in range(ohlcv.size - period, ohlcv.size)]
        return sum(closes) / len(closes)

    def _calculate_bollinger_bands(self, ohlcv: OhlcvBuffer, period: int, std_dev: float) -> Optional[Dict[str, float]]:
        """Calculate Bollinger Bands."""
        if ohlcv.size < period:
            return None
        
        closes = [ohlcv.get_close(i) for i in range(ohlcv.size - period, ohlcv.size)]
        
        sma = sum(closes) / len(closes)
        
        # Calculate standard deviation
        variance = sum((c - sma) ** 2 for c in closes) / len(closes)
        std = variance ** 0.5
        
        return {
            "upper": sma + std_dev * std,
            "middle": sma,
            "lower": sma - std_dev * std,
        }

    def on_position_closed(self) -> None:
        """Called when position is closed."""
        self.position_entry_ts = 0
        self.position_entry_price = 0.0
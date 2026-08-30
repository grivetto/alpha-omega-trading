"""
Mean Reversion with Adaptive Bollinger Bands Strategy
Combines mean reversion signals with dynamic Bollinger Band width adjustment
based on volatility regime detection and volume confirmation.
"""

from __future__ import annotations

import gc
import logging
from dataclasses import dataclass, field
from typing import Generator, Iterator, Optional
from collections import deque
from enum import Enum

import numpy as np

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Market volatility regime classification."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass(slots=True)
class StrategyConfig:
    """Configuration for MeanReversionAdaptiveBands strategy."""
    symbol: str
    base_capital: float
    bb_period: int = 20
    bb_std_dev: float = 2.0
    volume_period: int = 20
    volume_threshold_pct: float = 1.5
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    max_position_pct: float = 0.6
    stop_loss_atr_mult: float = 2.0
    take_profit_atr_mult: float = 3.0
    regime_lookback: int = 100
    regime_std_threshold_low: float = 0.5
    regime_std_threshold_high: float = 2.0
    chunk_size: int = 1000

    def validate(self) -> None:
        if self.bb_period < 10:
            raise ValueError("bb_period must be >= 10")
        if not 0.5 <= self.bb_std_dev <= 4.0:
            raise ValueError("bb_std_dev must be in [0.5, 4.0]")
        if not 0 < self.volume_threshold_pct <= 5.0:
            raise ValueError("volume_threshold_pct must be in (0, 5.0]")
        if not 0 < self.rsi_oversold < self.rsi_overbought < 100:
            raise ValueError("Invalid RSI thresholds")
        if not 0 < self.max_position_pct <= 1.0:
            raise ValueError("max_position_pct must be in (0, 1.0]")
        if self.stop_loss_atr_mult <= 0 or self.take_profit_atr_mult <= 0:
            raise ValueError("ATR multipliers must be > 0")
        if self.regime_lookback < 50:
            raise ValueError("regime_lookback must be >= 50")


@dataclass(slots=True)
class Position:
    """Active position tracking."""
    side: str
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    timestamp: float
    order_id: Optional[str] = None


@dataclass(slots=True)
class MarketState:
    """Current market state snapshot."""
    mid: float
    bid: float
    ask: float
    volume: float
    timestamp: float
    bb_upper: float = 0.0
    bb_middle: float = 0.0
    bb_lower: float = 0.0
    bb_width: float = 0.0
    rsi: float = 50.0
    volume_avg: float = 0.0
    atr: float = 0.0
    regime: VolatilityRegime = VolatilityRegime.NORMAL


class StrategyBase:
    """Base class for all strategies."""

    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float, volume: float = 0.0) -> None:
        raise NotImplementedError

    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> bool:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class MeanReversionAdaptiveBands(StrategyBase):
    """
    Mean Reversion with Adaptive Bollinger Bands Strategy.

    Features:
    - Dynamic Bollinger Band width based on volatility regime
    - Volume confirmation for entry signals
    - RSI filter for mean reversion strength
    - ATR-based stop loss and take profit
    - Streaming memory management for large datasets
    - Explicit error handling, no silent failures
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        config.validate()

        self._prices: deque[float] = deque(maxlen=config.regime_lookback)
        self._volumes: deque[float] = deque(maxlen=config.volume_period)
        self._highs: deque[float] = deque(maxlen=config.bb_period)
        self._lows: deque[float] = deque(maxlen=config.bb_period)
        self._closes: deque[float] = deque(maxlen=config.bb_period)

        self._gains: deque[float] = deque(maxlen=config.rsi_period)
        self._losses: deque[float] = deque(maxlen=config.rsi_period)
        self._prev_close: Optional[float] = None

        self._position: Optional[Position] = None
        self._realized_pnl: float = 0.0

        self._ticks_processed: int = 0
        self._fills_processed: int = 0
        self._signals_generated: int = 0
        self._trades_executed: int = 0

        self._current_regime: VolatilityRegime = VolatilityRegime.NORMAL
        self._bb_std_multiplier: float = config.bb_std_dev

        logger.info(f"Initialized MeanReversionAdaptiveBands for {config.symbol}")

    def estimate_memory_mb(self) -> float:
        total_elements = (
            self.config.regime_lookback +
            self.config.volume_period +
            self.config.bb_period * 3 +
            self.config.rsi_period * 2
        )
        data_mb = (total_elements * 8) / 1e6
        overhead_mb = 3.0
        return data_mb + overhead_mb

    def validate_config(self) -> bool:
        try:
            self.config.validate()
            return True
        except ValueError as e:
            logger.error(f"Config validation failed: {e}")
            return False

    def _calculate_rsi(self) -> float:
        if len(self._gains) < self.config.rsi_period or len(self._losses) < self.config.rsi_period:
            return 50.0
        avg_gain = np.mean(self._gains)
        avg_loss = np.mean(self._losses)
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def _calculate_atr(self) -> float:
        if len(self._highs) < 2 or len(self._lows) < 2 or len(self._closes) < 2:
            return 0.0
        highs = list(self._highs)
        lows = list(self._lows)
        closes = list(self._closes)
        true_ranges = []
        for i in range(1, len(closes)):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            true_ranges.append(tr)
        if not true_ranges:
            return 0.0
        return float(np.mean(true_ranges[-self.config.bb_period:]))

    def _calculate_bollinger_bands(self, prices: list[float]) -> tuple[float, float, float, float]:
        if len(prices) < self.config.bb_period:
            return 0.0, 0.0, 0.0, 0.0
        recent = prices[-self.config.bb_period:]
        middle = float(np.mean(recent))
        std = float(np.std(recent))
        upper = middle + (self._bb_std_multiplier * std)
        lower = middle - (self._bb_std_multiplier * std)
        width = (upper - lower) / middle if middle > 0 else 0.0
        return upper, middle, lower, width

    def _detect_regime(self) -> VolatilityRegime:
        if len(self._prices) < self.config.regime_lookback:
            return VolatilityRegime.NORMAL
        prices = list(self._prices)
        returns = np.diff(prices) / prices[:-1]
        rolling_std = np.std(returns)
        if rolling_std < self.config.regime_std_threshold_low * 0.01:
            return VolatilityRegime.LOW
        elif rolling_std > self.config.regime_std_threshold_high * 0.01:
            return VolatilityRegime.HIGH
        elif rolling_std > self.config.regime_std_threshold_high * 0.015:
            return VolatilityRegime.EXTREME
        return VolatilityRegime.NORMAL

    def _update_regime_params(self) -> None:
        regime_multipliers = {
            VolatilityRegime.LOW: 1.5,
            VolatilityRegime.NORMAL: 2.0,
            VolatilityRegime.HIGH: 2.5,
            VolatilityRegime.EXTREME: 3.0,
        }
        self._bb_std_multiplier = regime_multipliers.get(self._current_regime, 2.0)

    def _check_volume_confirmation(self, volume: float) -> bool:
        if len(self._volumes) < self.config.volume_period:
            return True
        avg_volume = np.mean(list(self._volumes))
        return volume >= avg_volume * self.config.volume_threshold_pct

    def _generate_signal(self, state: MarketState) -> Optional[dict]:
        if self._position is not None:
            return None

        at_lower = state.mid <= state.bb_lower * 1.001
        at_upper = state.mid >= state.bb_upper * 0.999

        rsi_oversold = state.rsi <= self.config.rsi_oversold
        rsi_overbought = state.rsi >= self.config.rsi_overbought

        vol_confirmed = self._check_volume_confirmation(state.volume)

        signal = None

        if at_lower and rsi_oversold and vol_confirmed:
            signal = {
                "side": "buy",
                "reason": "mean_reversion_long",
                "price": state.ask,
                "strength": (self.config.rsi_oversold - state.rsi) / self.config.rsi_oversold
            }
        elif at_upper and rsi_overbought and vol_confirmed:
            signal = {
                "side": "sell",
                "reason": "mean_reversion_short",
                "price": state.bid,
                "strength": (state.rsi - self.config.rsi_overbought) / (100 - self.config.rsi_overbought)
            }

        if signal:
            self._signals_generated += 1
            logger.info(f"Signal: {signal['side']} @ {signal['price']:.4f} (RSI: {state.rsi:.1f}, Regime: {state.regime.value})")

        return signal

    def _calculate_position_size(self, price: float, atr: float) -> float:
        if atr <= 0:
            return 0.0
        risk_per_share = atr * self.config.stop_loss_atr_mult
        max_risk = self.config.base_capital * self.config.max_position_pct * 0.02
        qty = max_risk / risk_per_share if risk_per_share > 0 else 0.0
        max_qty = (self.config.base_capital * self.config.max_position_pct) / price
        return min(qty, max_qty)

    def _create_position(self, signal: dict, state: MarketState) -> Position:
        atr = state.atr
        entry = signal["price"]
        qty = self._calculate_position_size(entry, atr)

        if signal["side"] == "buy":
            stop_loss = entry - (atr * self.config.stop_loss_atr_mult)
            take_profit = entry + (atr * self.config.take_profit_atr_mult)
        else:
            stop_loss = entry + (atr * self.config.stop_loss_atr_mult)
            take_profit = entry - (atr * self.config.take_profit_atr_mult)

        return Position(
            side="long" if signal["side"] == "buy" else "short",
            entry_price=entry,
            quantity=qty,
            stop_loss=stop_loss,
            take_profit=take_profit,
            timestamp=state.timestamp
        )

    def _check_exit_conditions(self, state: MarketState) -> Optional[str]:
        if self._position is None:
            return None

        pos = self._position

        if pos.side == "long":
            if state.bid <= pos.stop_loss:
                return "stop_loss"
            if state.ask >= pos.take_profit:
                return "take_profit"
            if state.mid >= state.bb_middle:
                return "mean_reversion"
        else:
            if state.ask >= pos.stop_loss:
                return "stop_loss"
            if state.bid <= pos.take_profit:
                return "take_profit"
            if state.mid <= state.bb_middle:
                return "mean_reversion"

        return None

    def on_tick(self, timestamp: float, bid: float, ask: float, mid: float, volume: float = 0.0) -> None:
        if mid <= 0 or bid <= 0 or ask <= 0:
            logger.warning(f"Invalid prices: bid={bid}, ask={ask}, mid={mid}")
            return

        self._ticks_processed += 1

        self._prices.append(mid)
        self._volumes.append(volume)
        self._highs.append(max(bid, ask))
        self._lows.append(min(bid, ask))
        self._closes.append(mid)

        if self._prev_close is not None:
            change = mid - self._prev_close
            self._gains.append(max(change, 0.0))
            self._losses.append(max(-change, 0.0))
        self._prev_close = mid

        rsi = self._calculate_rsi()
        atr = self._calculate_atr()
        self._current_regime = self._detect_regime()
        self._update_regime_params()

        bb_upper, bb_middle, bb_lower, bb_width = self._calculate_bollinger_bands(list(self._prices))
        volume_avg = np.mean(list(self._volumes)) if self._volumes else 0.0

        state = MarketState(
            mid=mid, bid=bid, ask=ask, volume=volume, timestamp=timestamp,
            bb_upper=bb_upper, bb_middle=bb_middle, bb_lower=bb_lower, bb_width=bb_width,
            rsi=rsi, volume_avg=volume_avg, atr=atr, regime=self._current_regime
        )

        if self._position:
            exit_reason = self._check_exit_conditions(state)
            if exit_reason:
                logger.info(f"Exit signal: {exit_reason} for {self._position.side} @ {mid:.4f}")
                self._realized_pnl += self._calculate_pnl(state.mid)
                self._position = None
                self._trades_executed += 1

        if self._position is None:
            signal = self._generate_signal(state)
            if signal:
                self._position = self._create_position(signal, state)
                logger.info(f"Position opened: {self._position.side} {self._position.quantity:.6f} @ {self._position.entry_price:.4f}")

        if self._ticks_processed % 1000 == 0:
            gc.collect()

    def _calculate_pnl(self, current_price: float) -> float:
        if self._position is None:
            return 0.0
        pos = self._position
        if pos.side == "long":
            return (current_price - pos.entry_price) * pos.quantity
        else:
            return (pos.entry_price - current_price) * pos.quantity

    def on_fill(self, order_id: str, side: str, price: float, qty: float) -> None:
        self._fills_processed += 1
        if self._position and self._position.order_id == order_id:
            logger.info(f"Fill confirmed: {side} {qty:.6f} @ {price:.4f}")
        else:
            logger.warning(f"Fill for unexpected order: {order_id}")

    def get_status(self) -> dict:
        pos_info = None
        if self._position:
            pos_info = {
                "side": self._position.side,
                "entry": self._position.entry_price,
                "qty": self._position.quantity,
                "sl": self._position.stop_loss,
                "tp": self._position.take_profit,
            }
        return {
            "symbol": self.config.symbol,
            "regime": self._current_regime.value,
            "bb_std_mult": self._bb_std_multiplier,
            "rsi": self._calculate_rsi() if self._gains else 50.0,
            "position": pos_info,
            "realized_pnl": self._realized_pnl,
            "ticks_processed": self._ticks_processed,
            "fills_processed": self._fills_processed,
            "signals_generated": self._signals_generated,
            "trades_executed": self._trades_executed,
            "memory_mb": self.estimate_memory_mb(),
        }


def generate_synthetic_ticks(count: int, base_price: float = 100.0, volatility: float = 0.01) -> Generator[tuple[float, float, float, float, float], None, None]:
    np.random.seed(42)
    price = base_price
    for i in range(count):
        drift = np.random.normal(0, volatility * 0.05)
        shock = np.random.normal(0, volatility)
        price *= (1 + drift + shock)
        price = max(price, 0.01)
        spread = price * 0.001
        bid = price - spread / 2
        ask = price + spread / 2
        mid = price
        volume = np.random.lognormal(10, 0.5)
        yield float(i), bid, ask, mid, volume


if __name__ == "__main__":
    config = StrategyConfig(
        symbol="TEST/EUR",
        base_capital=1000.0,
        bb_period=20,
        bb_std_dev=2.0,
        volume_period=20,
        volume_threshold_pct=1.5,
        rsi_period=14,
        rsi_oversold=30.0,
        rsi_overbought=70.0,
        max_position_pct=0.6,
        stop_loss_atr_mult=2.0,
        take_profit_atr_mult=3.0,
        regime_lookback=100,
        regime_std_threshold_low=0.5,
        regime_std_threshold_high=2.0,
        chunk_size=1000,
    )

    strategy = MeanReversionAdaptiveBands(config)
    print(f"Memory estimate: {strategy.estimate_memory_mb():.2f} MB")
    print(f"Config valid: {strategy.validate_config()}")

    for i, (ts, bid, ask, mid, vol) in enumerate(generate_synthetic_ticks(500, base_price=150.0)):
        strategy.on_tick(ts, bid, ask, mid, vol)
        if i % 100 == 0:
            status = strategy.get_status()
            print(f"Tick {i}: regime={status['regime']}, RSI={status['rsi']:.1f}, pos={status['position']}, pnl={status['realized_pnl']:.2f}")

    final_status = strategy.get_status()
    print(f"\nFinal: {final_status}")
    print("Test completed successfully.")

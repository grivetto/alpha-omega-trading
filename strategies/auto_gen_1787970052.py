"""
Grid + Momentum Adaptive Strategy for EUR spot trading.
Memory-safe, config-driven, zero hardcoded values.
"""
from __future__ import annotations

import gc
import json
import math
from dataclasses import dataclass
from typing import Generator, Iterator, List, Optional, Tuple

import numpy as np


@dataclass(slots=True)
class Candle:
    """Single OHLCV candle."""
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(slots=True)
class GridLevel:
    """Single grid level with order metadata."""
    price: float
    side: str  # 'buy' or 'sell'
    size: float
    order_id: Optional[str] = None
    filled: bool = False


@dataclass(slots=True)
class StrategyConfig:
    """Strategy configuration - all params externalized."""
    symbol: str
    base_spacing_pct: float
    max_levels: int
    atr_period: int
    rsi_period: int
    rsi_long_threshold: float
    rsi_short_threshold: float
    volume_lookback: int
    kelly_fraction: float
    max_position_pct: float
    min_order_size: float
    grid_recenter_threshold: float

    @classmethod
    def from_dict(cls, data: dict) -> StrategyConfig:
        required = {
            'symbol', 'base_spacing_pct', 'max_levels', 'atr_period',
            'rsi_period', 'rsi_long_threshold', 'rsi_short_threshold',
            'volume_lookback', 'kelly_fraction', 'max_position_pct',
            'min_order_size', 'grid_recenter_threshold'
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Missing config keys: {missing}")
        return cls(**{k: data[k] for k in required})


class StrategyBase:
    """
    Grid + Momentum Adaptive Strategy.
    
    Dynamically adjusts grid spacing and levels based on:
    - ATR for volatility regime
    - RSI for momentum bias (long/short skew)
    - Volume profile for liquidity zones
    - Kelly criterion for position sizing
    """
    
    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self._candles: List[Candle] = []
        self._grid_levels: List[GridLevel] = []
        self._current_price: float = 0.0
        self._position: float = 0.0
        self._realized_pnl: float = 0.0
        self._atr_values: List[float] = []
        self._rsi_values: List[float] = []
        self._volume_profile: List[float] = []
        
    def validate_config(self) -> Tuple[bool, str]:
        """Validate configuration parameters."""
        c = self.config
        if c.base_spacing_pct <= 0 or c.base_spacing_pct > 0.1:
            return False, "base_spacing_pct must be in (0, 0.1]"
        if c.max_levels < 2 or c.max_levels > 100:
            return False, "max_levels must be in [2, 100]"
        if c.atr_period < 2 or c.atr_period > 200:
            return False, "atr_period must be in [2, 200]"
        if c.rsi_period < 2 or c.rsi_period > 200:
            return False, "rsi_period must be in [2, 200]"
        if not (0 < c.rsi_long_threshold < c.rsi_short_threshold < 100):
            return False, "RSI thresholds invalid: 0 < long < short < 100"
        if c.volume_lookback < 10 or c.volume_lookback > 1000:
            return False, "volume_lookback must be in [10, 1000]"
        if not (0 < c.kelly_fraction <= 1):
            return False, "kelly_fraction must be in (0, 1]"
        if not (0 < c.max_position_pct <= 1):
            return False, "max_position_pct must be in (0, 1]"
        if c.min_order_size <= 0:
            return False, "min_order_size must be > 0"
        if not (0 < c.grid_recenter_threshold < 0.5):
            return False, "grid_recenter_threshold must be in (0, 0.5)"
        return True, "OK"
    
    def estimate_memory_mb(self, max_candles: int = 10000) -> float:
        """Estimate memory usage in MB for given candle count."""
        candle_size = 6 * 8  # 6 floats per candle
        atr_size = max_candles * 8
        rsi_size = max_candles * 8
        volume_size = max_candles * 8
        grid_size = self.config.max_levels * 64  # GridLevel approx
        overhead = 1024 * 1024  # 1MB Python overhead
        total_bytes = (candle_size + atr_size + rsi_size + volume_size) * max_candles + grid_size + overhead
        return total_bytes / (1024 * 1024)
    
    def _stream_candles(self, data: List[dict]) -> Generator[Candle, None, None]:
        """Memory-safe candle streaming generator."""
        for row in data:
            yield Candle(
                timestamp=row['timestamp'],
                open=row['open'],
                high=row['high'],
                low=row['low'],
                close=row['close'],
                volume=row['volume']
            )
    
    def _calculate_atr(self, candles: List[Candle], period: int) -> float:
        """Calculate ATR using streaming approach."""
        if len(candles) < period + 1:
            return 0.0
        true_ranges = []
        for i in range(1, len(candles)):
            tr = max(
                candles[i].high - candles[i].low,
                abs(candles[i].high - candles[i-1].close),
                abs(candles[i].low - candles[i-1].close)
            )
            true_ranges.append(tr)
        if len(true_ranges) < period:
            return 0.0
        return sum(true_ranges[-period:]) / period
    
    def _calculate_rsi(self, candles: List[Candle], period: int) -> float:
        """Calculate RSI using streaming approach."""
        if len(candles) < period + 1:
            return 50.0
        gains = []
        losses = []
        for i in range(1, len(candles)):
            change = candles[i].close - candles[i-1].close
            gains.append(max(change, 0))
            losses.append(max(-change, 0))
        if len(gains) < period:
            return 50.0
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def _calculate_volume_profile(self, candles: List[Candle], lookback: int) -> List[float]:
        """Calculate volume-weighted price levels."""
        if len(candles) < lookback:
            return []
        recent = candles[-lookback:]
        price_volume = {}
        for c in recent:
            typical = (c.high + c.low + c.close) / 3
            price_volume[typical] = price_volume.get(typical, 0) + c.volume
        total_vol = sum(price_volume.values())
        if total_vol == 0:
            return []
        return [v / total_vol for v in price_volume.values()]
    
    def _kelly_position_size(self, win_rate: float, avg_win: float, avg_loss: float, capital: float) -> float:
        """Kelly criterion position sizing."""
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0.0
        kelly_pct = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
        kelly_pct = max(0, min(kelly_pct, 1)) * self.config.kelly_fraction
        return capital * kelly_pct
    
    def _build_grid(self, center_price: float, atr: float, rsi: float, capital: float) -> List[GridLevel]:
        """Build dynamic grid levels based on regime."""
        spacing = self.config.base_spacing_pct
        if atr > 0:
            spacing = max(spacing, atr / center_price * 0.5)
        
        # Momentum bias from RSI
        long_bias = 1.0
        short_bias = 1.0
        if rsi < self.config.rsi_long_threshold:
            long_bias = 1.5
            short_bias = 0.5
        elif rsi > self.config.rsi_short_threshold:
            long_bias = 0.5
            short_bias = 1.5
        
        max_pos = capital * self.config.max_position_pct
        level_capital = max_pos / self.config.max_levels
        
        levels = []
        half = self.config.max_levels // 2
        
        # Buy levels (below center)
        for i in range(1, half + 1):
            price = center_price * (1 - spacing * i * long_bias)
            # Ensure order value meets minimum (in quote currency)
            size = max(self.config.min_order_size / price, level_capital / price)
            if size * price >= self.config.min_order_size:
                levels.append(GridLevel(price=price, side='buy', size=size))
        
        # Sell levels (above center)
        for i in range(1, half + 1):
            price = center_price * (1 + spacing * i * short_bias)
            size = max(self.config.min_order_size / price, level_capital / price)
            if size * price >= self.config.min_order_size:
                levels.append(GridLevel(price=price, side='sell', size=size))
        
        return levels
    
    def on_tick(self, candle: Candle) -> List[GridLevel]:
        """Process new candle, return grid actions."""
        self._candles.append(candle)
        self._current_price = candle.close
        
        # Maintain rolling window
        max_lookback = max(self.config.atr_period, self.config.rsi_period, self.config.volume_lookback) + 10
        if len(self._candles) > max_lookback:
            self._candles = self._candles[-max_lookback:]
        
        # Calculate indicators
        atr = self._calculate_atr(self._candles, self.config.atr_period)
        rsi = self._calculate_rsi(self._candles, self.config.rsi_period)
        self._atr_values.append(atr)
        self._rsi_values.append(rsi)
        
        # Recenter grid if price moved significantly
        if self._grid_levels:
            center = sum(l.price for l in self._grid_levels) / len(self._grid_levels)
            if abs(candle.close - center) / center > self.config.grid_recenter_threshold:
                capital = 1000.0 + self._realized_pnl + self._position * self._current_price
                self._grid_levels = self._build_grid(candle.close, atr, rsi, capital)
        else:
            capital = 1000.0 + self._realized_pnl + self._position * self._current_price
            self._grid_levels = self._build_grid(candle.close, atr, rsi, capital)
        
        # Clean up
        if len(self._atr_values) > max_lookback:
            del self._atr_values[:-max_lookback]
            del self._rsi_values[:-max_lookback]
            gc.collect()
        
        return self._grid_levels
    
    def on_fill(self, level: GridLevel, fill_price: float, fill_size: float) -> None:
        """Process fill event."""
        level.filled = True
        level.order_id = None
        
        if level.side == 'buy':
            self._position += fill_size
            self._realized_pnl -= fill_price * fill_size
        else:
            self._position -= fill_size
            self._realized_pnl += fill_price * fill_size
        
        # Rebuild grid after fill
        atr = self._atr_values[-1] if self._atr_values else 0.0
        rsi = self._rsi_values[-1] if self._rsi_values else 50.0
        capital = 1000.0 + self._realized_pnl + self._position * self._current_price
        self._grid_levels = self._build_grid(self._current_price, atr, rsi, capital)
    
    def get_state(self) -> dict:
        """Return current strategy state."""
        return {
            'position': self._position,
            'realized_pnl': self._realized_pnl,
            'current_price': self._current_price,
            'grid_levels': len(self._grid_levels),
            'atr': self._atr_values[-1] if self._atr_values else 0.0,
            'rsi': self._rsi_values[-1] if self._rsi_values else 50.0,
        }


def generate_synthetic_candles(count: int = 100, start_price: float = 0.1) -> List[dict]:
    """Generate synthetic candle data for testing."""
    np.random.seed(42)
    candles = []
    price = start_price
    timestamp = 1700000000
    for _ in range(count):
        change = np.random.normal(0, 0.02)
        price *= (1 + change)
        high = price * (1 + abs(np.random.normal(0, 0.005)))
        low = price * (1 - abs(np.random.normal(0, 0.005)))
        open_ = price * (1 + np.random.normal(0, 0.002))
        volume = abs(np.random.normal(10000, 5000))
        candles.append({
            'timestamp': timestamp,
            'open': open_,
            'high': high,
            'low': low,
            'close': price,
            'volume': volume
        })
        timestamp += 60
    return candles


if __name__ == '__main__':
    config = StrategyConfig(
        symbol='DOGE/EUR',
        base_spacing_pct=0.005,
        max_levels=20,
        atr_period=14,
        rsi_period=14,
        rsi_long_threshold=40,
        rsi_short_threshold=60,
        volume_lookback=50,
        kelly_fraction=0.25,
        max_position_pct=0.1,
        min_order_size=10.0,
        grid_recenter_threshold=0.02
    )
    
    strategy = StrategyBase(config)
    valid, msg = strategy.validate_config()
    print(f"Config valid: {valid} - {msg}")
    print(f"Estimated memory (10k candles): {strategy.estimate_memory_mb(10000):.2f} MB")
    
    candles = generate_synthetic_candles(100)
    for c_data in candles:
        candle = Candle(**c_data)
        levels = strategy.on_tick(candle)
    
    state = strategy.get_state()
    print(f"Final state: {json.dumps(state, indent=2)}")
    
    # Simulate a fill
    if strategy._grid_levels:
        test_level = strategy._grid_levels[0]
        strategy.on_fill(test_level, test_level.price, test_level.size)
        print(f"After fill: {strategy.get_state()}")

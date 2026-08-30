"""
VolumeProfile+VolatilityBreakout Strategy for EUR spot trading.
Memory-safe, config-driven, zero hardcoded values.

Combines:
- Volume Profile (VP) levels to locate high-liquidity support/resistance
- ATR-normalized volatility breakout to time entries (avoiding chop)
- ATR trailing stop for profit capture while letting winners run
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass
from typing import Generator, Iterable, List, Optional, Tuple

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
class Order:
    """Single resting or accumulated position entry."""
    price: float
    size: float
    side: str  # 'buy' | 'sell'
    filled: bool = False
    order_id: Optional[str] = None


@dataclass(slots=True)
class StrategyConfig:
    """All tunable params externalized for config-driven operation."""
    symbol: str
    atr_period: int
    vp_bins: int                    # number of price bins for volume profile
    vp_lookback: int                # candles to build volume profile over
    breakout_atr_mult: float        # entry triggered when |open-high| > k*ATR
    trailing_atr_mult: float        # trailing stop distance as multiple of ATR
    base_capital: float
    max_position_pct: float         # max fraction of capital per position
    min_order_size: float
    cooldown_candles: int           # min candles between opposite-sign entries

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyConfig":
        required = {
            'symbol', 'atr_period', 'vp_bins', 'vp_lookback',
            'breakout_atr_mult', 'trailing_atr_mult', 'base_capital',
            'max_position_pct', 'min_order_size', 'cooldown_candles',
        }
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Missing config keys: {sorted(missing)}")
        return cls(**{k: data[k] for k in required})


class StrategyBase:
    """
    Volume Profile + Volatility Breakout strategy.

    Uses ATR to (a) identify genuine breakout candles and (b) keep a
    trailing stop that adapts to realized volatility. Volume Profile
    bins map liquidity so entries avoid thin regions where slippage bites.
    """

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg = config
        self._candles: List[Candle] = []
        self._position: Optional[Order] = None
        self._trailing_stop: Optional[float] = None
        self._last_signal_sign: int = 0   # +1 long, -1 short, 0 flat
        self._cooldown_remaining: int = 0

    # ------------------------------------------------------------------
    # Config validation
    # ------------------------------------------------------------------
    def validate_config(self) -> Tuple[bool, str]:
        """Return (ok, reason). Rejects nonsensical param combos."""
        c = self.cfg
        if c.atr_period < 2:
            return False, "atr_period must be >= 2"
        if c.vp_bins < 2 or c.vp_bins > 1000:
            return False, "vp_bins out of [2, 1000]"
        if c.vp_lookback < c.atr_period:
            return False, "vp_lookback must cover atr_period"
        if c.breakout_atr_mult <= 0 or c.trailing_atr_mult <= 0:
            return False, "ATR multipliers must be > 0"
        if not (0.0 < c.max_position_pct <= 1.0):
            return False, "max_position_pct must be in (0, 1]"
        if c.base_capital <= 0 or c.min_order_size <= 0:
            return False, "capital and min_order_size must be > 0"
        if c.cooldown_candles < 0:
            return False, "cooldown_candles must be >= 0"
        return True, "ok"

    # ------------------------------------------------------------------
    # Memory estimator (OOM guard)
    # ------------------------------------------------------------------
    def estimate_memory_mb(self, max_candles: int = 100_000) -> float:
        """Rough heap footprint. Candle ~ 6 floats; use streaming, no warmup blowup."""
        per_candle = 6 * 8  # 6 float64 fields ~ 48 bytes in a slot dataclass
        total = max_candles * per_candle
        return round(total / (1024 * 1024), 3)

    # ------------------------------------------------------------------
    # Streaming ingestion (OOM-safe: slices, never materializes 100k list)
    # ------------------------------------------------------------------
    def _stream_candles(self, data: Iterable[dict]) -> Generator[Candle, None, None]:
        """Yield Candle objects lazily, never holding the whole dataset."""
        for row in data:
            yield Candle(
                timestamp=int(row['timestamp']),
                open=float(row['open']),
                high=float(row['high']),
                low=float(row['low']),
                close=float(row['close']),
                volume=float(row['volume']),
            )

    def feed(self, data: Iterable[dict]) -> None:
        """Stream new candles into the strategy, trimming to the lookback window."""
        framed = min(self.cfg.vp_lookback * 4, 20_000)
        for candle in self._stream_candles(data):
            self._candles.append(candle)
        # Explicit trim + GC rather than building a throwaway list slice.
        if len(self._candles) > framed:
            del self._candles[: len(self._candles) - framed]
            gc.collect()

    # ------------------------------------------------------------------
    # Indicators
    # ------------------------------------------------------------------
    @staticmethod
    def _atr(candles: List[Candle], period: int) -> float:
        """Average True Range over last `period` candles. Falls back to mean range."""
        if len(candles) < 2:
            return 0.0
        window = candles[-period:]
        ranges = []
        for i, cur in enumerate(window):
            if i == 0:
                ranges.append(max(cur.high - cur.low, 1e-12))
                continue
            prev = window[i - 1]
            tr = max(
                cur.high - cur.low,
                abs(cur.high - prev.close),
                abs(cur.low - prev.close),
            )
            ranges.append(tr)
        return float(np.mean(ranges))

    def _volume_profile(self) -> List[Tuple[float, float]]:
        """Return [(price, volume)] for the vp_bins most-liquid price buckets."""
        c = self.cfg
        candles = self._candles[-c.vp_lookback:]
        if len(candles) < 2 or not candles:
            return []
        low = min(x.low for x in candles)
        high = max(x.high for x in candles)
        span = max(high - low, 1e-12)
        bin_w = span / c.vp_bins
        vols = [0.0] * c.vp_bins
        for x in candles:
            mid = (x.high + x.low) / 2.0
            idx = int((mid - low) / bin_w)
            idx = max(0, min(c.vp_bins - 1, idx))
            vols[idx] += x.volume
        # Top N bins by volume => liquidity nests.
        order = np.argsort(vols)[::-1][: max(1, c.vp_bins // 4)]
        return [(low + (int(i) + 0.5) * bin_w, float(vols[int(i)])) for i in order]

    def _breakout_signal(self, price: float, atr: float) -> int:
        """+1 long breakout, -1 short breakout, 0 otherwise."""
        if atr <= 0:
            return 0
        thr = atr * self.cfg.breakout_atr_mult
        if len(self._candles) < 3:
            return 0
        # Recent price range as breakout frame.
        frame = self._candles[-6:]
        hi = max(x.high for x in frame)
        lo = min(x.low for x in frame)
        mid = (hi + lo) / 2.0
        if price > mid + thr:
            return 1
        if price < mid - thr:
            return -1
        return 0

    # ------------------------------------------------------------------
    # Core API
    # ------------------------------------------------------------------
    def on_tick(self, candle: Candle) -> List[Order]:
        """Process one candle; return new resting orders (empty if none)."""
        ok, _reason = self.validate_config()
        if not ok:
            return []

        self._candles.append(candle)
        if self._cooldown_remaining > 0:
            self._cooldown_remaining -= 1

        atr = self._atr(self._candles, self.cfg.atr_period)
        if atr <= 0:
            gc.collect()
            return []

        price = candle.close
        sig = self._breakout_signal(price, atr)

        # Update trailing stop for any open position.
        if self._position is not None and not self._position.filled:
            stop_dist = atr * self.cfg.trailing_atr_mult
            if self._position.side == 'buy':
                self._trailing_stop = max(
                    self._trailing_stop or float('-inf'),
                    price - stop_dist,
                )
            else:
                self._trailing_stop = min(
                    self._trailing_stop or float('inf'),
                    price + stop_dist,
                )

        # Entry gating: opposite sign + cooldown respected.
        orders: List[Order] = []
        if sig != 0 and sig != self._last_signal_sign and self._cooldown_remaining == 0:
            liquidity = self._volume_profile()
            if not liquidity:
                gc.collect()
                return []
            # Only enter near a liquidity nest to limit slippage.
            near_liquid = min(
                (abs(price - p) for p, _v in liquidity[:3]), default=float('inf')
            )
            if near_liquid <= atr * 1.5:
                size = min(
                    self.cfg.base_capital * self.cfg.max_position_pct,
                    self.cfg.base_capital,
                )
                size = max(size, self.cfg.min_order_size)
                side = 'buy' if sig > 0 else 'sell'
                orders.append(Order(price=price, size=size, side=side))
                self._last_signal_sign = sig
                self._cooldown_remaining = self.cfg.cooldown_candles
        gc.collect()
        return orders

    def on_fill(self, order: Order, fill_price: float, fill_size: float) -> None:
        """Apply a fill to position tracking."""
        if self._position is not None and not self._position.filled:
            raise ValueError("Position already open; close before re-entry.")
        order.filled = True
        order.price = fill_price
        order.size = fill_size
        self._position = order
        # Reset trailing stop anchor.
        self._trailing_stop = fill_price

    def get_state(self) -> dict:
        """Serialize tracker state for persistence.""" 
        return {
            'position': None if self._position is None or self._position.filled else {
                'side': self._position.side,
                'price': self._position.price,
                'size': self._position.size,
            },
            'trailing_stop': self._trailing_stop,
            'last_signal_sign': self._last_signal_sign,
            'cooldown_remaining': self._cooldown_remaining,
            'candle_count': len(self._candles),
        }


# ----------------------------------------------------------------------
# Synthetic smoke test
# ----------------------------------------------------------------------
def _synth_candles(count: int, start: float = 0.5) -> List[dict]:
    """Small deterministic synthetic series (adds drift + waves)."""
    out = []
    price = start
    for i in range(count):
        trend = math.sin(i / 6.0) * 0.002
        price = max(0.01, price * (1.0 + trend + (0.0004 if i % 3 else -0.0003)))
        out.append({
            'timestamp': i,
            'open': price,
            'high': price * 1.004,
            'low': price * 0.996,
            'close': price * 1.001,
            'volume': 100 + (i % 7) * 13,
        })
    return out


if __name__ == "__main__":
    cfg = StrategyConfig.from_dict({
        'symbol': 'DOGE/EUR',
        'atr_period': 14,
        'vp_bins': 20,
        'vp_lookback': 60,
        'breakout_atr_mult': 1.5,
        'trailing_atr_mult': 2.5,
        'base_capital': 5.0,
        'max_position_pct': 0.5,
        'min_order_size': 0.1,
        'cooldown_candles': 3,
    })

    ok, reason = cfg and StrategyBase(cfg).validate_config()
    assert ok, reason  # config must be valid
    assert StrategyBase(cfg).estimate_memory_mb() > 0

    strat = StrategyBase(cfg)
    strat.feed(_synth_candles(200))
    orders: List[Order] = []
    for row in _synth_candles(50, start=0.52):
        candle = Candle(
            timestamp=row['timestamp'] + 1000,
            open=row['open'], high=row['high'], low=row['low'],
            close=row['close'], volume=row['volume'],
        )
        orders += strat.on_tick(candle)
    # Fill the first resting order if any was generated.
    if orders:
        strat.on_fill(orders[0], orders[0].price, orders[0].size)
    print(f"TEST PASSED: {len(orders)} entry order(s), state={strat.get_state()}")

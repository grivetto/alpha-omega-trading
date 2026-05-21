#!/usr/bin/env python3
"""
DENARO V2 - Signal Engine
Multi-factor signal generation combining technical analysis,
order book analysis, and momentum detection.
"""
import logging
from typing import Optional

logger = logging.getLogger("Denaro.Signals")


class SignalEngine:
    """Multi-factor signal generation."""

    def __init__(self):
        pass

    def analyze(self, symbol: str, price: float, ohlcv: list,
                orderbook: Optional[dict] = None) -> dict:
        """Generate composite signal from multiple factors."""
        if not ohlcv or len(ohlcv) < 20:
            return {'signal': 'HOLD', 'score': 0.0, 'factors': {}}

        factors = {}

        # 1. RSI (14 period)
        rsi = self._calc_rsi(ohlcv, 14)
        factors['rsi'] = rsi

        # 2. EMA trend
        ema_fast = self._calc_ema(ohlcv, 9)
        ema_slow = self._calc_ema(ohlcv, 21)
        factors['ema_fast'] = ema_fast
        factors['ema_slow'] = ema_slow

        # 3. Volatility (ATR)
        atr = self._calc_atr(ohlcv, 14)
        factors['atr'] = atr
        factors['atr_pct'] = atr / price * 100 if price > 0 else 0

        # 4. Volume analysis
        vol_ratio = self._calc_volume_ratio(ohlcv)
        factors['vol_ratio'] = vol_ratio

        # 5. Order book imbalance
        ob_imbalance = 0
        if orderbook:
            ob_imbalance = self._calc_orderbook_imbalance(orderbook)
        factors['ob_imbalance'] = ob_imbalance

        # 6. Momentum
        momentum = self._calc_momentum(ohlcv)
        factors['momentum'] = momentum

        # Composite score
        score = self._composite_score(factors)

        # Signal determination
        if score >= 0.6:
            signal = 'STRONG_BUY'
        elif score >= 0.3:
            signal = 'BUY'
        elif score <= -0.6:
            signal = 'STRONG_SELL'
        elif score <= -0.3:
            signal = 'SELL'
        else:
            signal = 'HOLD'

        return {
            'signal': signal,
            'score': score,
            'factors': factors,
        }

    def _calc_rsi(self, ohlcv: list, period: int = 14) -> float:
        """Calculate RSI."""
        closes = [c[4] for c in ohlcv]
        if len(closes) < period + 1:
            return 50.0

        gains = []
        losses = []
        for i in range(1, len(closes)):
            diff = closes[i] - closes[i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_ema(self, ohlcv: list, period: int) -> float:
        """Calculate current EMA value."""
        closes = [c[4] for c in ohlcv]
        if len(closes) < period:
            return closes[-1] if closes else 0

        multiplier = 2 / (period + 1)
        ema = sum(closes[:period]) / period

        for price in closes[period:]:
            ema = (price - ema) * multiplier + ema

        return ema

    def _calc_atr(self, ohlcv: list, period: int = 14) -> float:
        """Calculate Average True Range."""
        if len(ohlcv) < period + 1:
            return 0

        true_ranges = []
        for i in range(1, len(ohlcv)):
            high = ohlcv[i][1]
            low = ohlcv[i][2]
            prev_close = ohlcv[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)

        return sum(true_ranges[-period:]) / period

    def _calc_volume_ratio(self, ohlcv: list) -> float:
        """Calculate volume ratio (current vs average)."""
        if len(ohlcv) < 20:
            return 1.0

        volumes = [c[5] for c in ohlcv]
        current_vol = volumes[-1]
        avg_vol = sum(volumes[-20:-1]) / 19 if len(volumes) > 1 else 1

        return current_vol / avg_vol if avg_vol > 0 else 1.0

    def _calc_orderbook_imbalance(self, orderbook: dict) -> float:
        """Calculate order book imbalance (-1 to +1)."""
        bids = orderbook.get('bids', [])
        asks = orderbook.get('asks', [])

        if not bids or not asks:
            return 0

        bid_volume = sum(b[1] for b in bids[:5])
        ask_volume = sum(a[1] for a in asks[:5])

        total = bid_volume + ask_volume
        if total == 0:
            return 0

        return (bid_volume - ask_volume) / total

    def _calc_momentum(self, ohlcv: list) -> float:
        """Calculate price momentum (-1 to +1)."""
        if len(ohlcv) < 10:
            return 0

        closes = [c[4] for c in ohlcv]
        recent = closes[-5:]
        older = closes[-10:-5]

        if not older or not recent:
            return 0

        avg_recent = sum(recent) / len(recent)
        avg_older = sum(older) / len(older)

        if avg_older == 0:
            return 0

        change = (avg_recent - avg_older) / avg_older
        return max(-1, min(1, change * 10))  # Scale to -1..+1

    def _composite_score(self, factors: dict) -> float:
        """Calculate composite signal score (-1 to +1)."""
        score = 0.0

        # RSI component (weight: 0.25)
        rsi = factors.get('rsi', 50)
        if rsi < 25:
            score += 0.25  # Oversold = buy signal
        elif rsi < 35:
            score += 0.15
        elif rsi > 75:
            score -= 0.25  # Overbought = sell signal
        elif rsi > 65:
            score -= 0.15

        # EMA trend component (weight: 0.25)
        ema_fast = factors.get('ema_fast', 0)
        ema_slow = factors.get('ema_slow', 0)
        if ema_fast > 0 and ema_slow > 0:
            ema_diff = (ema_fast - ema_slow) / ema_slow
            score += max(-0.25, min(0.25, ema_diff * 10))

        # Volume component (weight: 0.15)
        vol_ratio = factors.get('vol_ratio', 1)
        if vol_ratio > 2.0:
            score += 0.15  # High volume confirms move
        elif vol_ratio > 1.5:
            score += 0.08

        # Order book imbalance (weight: 0.20)
        ob_imb = factors.get('ob_imbalance', 0)
        score += ob_imb * 0.20

        # Momentum component (weight: 0.15)
        momentum = factors.get('momentum', 0)
        score += momentum * 0.15

        return max(-1.0, min(1.0, score))

#!/usr/bin/env python3
"""Denaro v7 — Advanced indicators module.

RSI, MACD, Bollinger Bands, Stochastic, ADX, Ichimoku cloud, Volume profile.
Ogni indicatore ritorna valore scalare + segnale di cross + livello di previsione.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .types import CoreState, Trend


@dataclass
class AdvancedIndicator:
    value: float
    signal: str
    strength: float
    level: str


class AdvancedIndicators:
    """Comprehensive technical analysis toolkit."""

    # --- RSI ---------------------------------------------------------------

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> AdvancedIndicator:
        """Relative Strength Index with overbought/oversold signals."""
        if len(prices) < period + 1:
            return AdvancedIndicator(value=50.0, signal="neutral", strength=0.0, level="unknown")

        gains = [max(prices[i] - prices[i-1], 0) for i in range(1, len(prices))]
        losses = [max(prices[i-1] - prices[i], 0) for i in range(1, len(prices))]

        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period

        if avg_loss == 0:
            return AdvancedIndicator(value=100.0, signal="overbought", strength=1.0, level="extreme")

        rs = avg_gain / avg_loss
        rsi_val = 100 - (100 / (1 + rs))

        signal = "neutral"
        strength = 0.0
        level = "neutral"

        if rsi_val > 70:
            signal = "overbought"
            strength = min(1.0, (rsi_val - 70) / 30)
            level = "high" if rsi_val > 80 else "moderate"
        elif rsi_val < 30:
            signal = "oversold"
            strength = min(1.0, (30 - rsi_val) / 30)
            level = "low" if rsi_val < 20 else "moderate"

        return AdvancedIndicator(
            value=rsi_val,
            signal=signal,
            strength=strength,
            level=level
        )

    # --- MACD --------------------------------------------------------------

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> AdvancedIndicator:
        """MACD with histogram + convergence/divergence signal."""
        if len(prices) < slow + signal:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        ema_fast = AdvancedIndicators._ema(prices[-fast:], fast)
        ema_slow = AdvancedIndicators._ema(prices[-slow:], slow)

        macd_line = ema_fast - ema_slow
        signal_line = AdvancedIndicators._ema(prices[-(fast+slow+signal):], signal)
        histogram = macd_line - signal_line

        signal_str = "neutral"
        strength = 0.0

        if histogram > 0.0001:
            signal_str = "bullish"
            strength = min(1.0, histogram / (signal_line * 0.02))
        elif histogram < -0.0001:
            signal_str = "bearish"
            strength = min(1.0, abs(histogram) / (signal_line * 0.02))

        return AdvancedIndicator(
            value=macd_line,
            signal=signal_str,
            strength=strength,
            level="strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        )

    # --- Bollinger Bands ----------------------------------------------------

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> AdvancedIndicator:
        """Bollinger Bands with squeeze detection and price position analysis."""
        if len(prices) < period + 1:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        middle = sum(prices[-period:]) / period
        variance = sum((x - middle)**2 for x in prices[-period:]) / period
        std = variance ** 0.5

        upper = middle + std_dev * std
        lower = middle - std_dev * std
        current = prices[-1]

        bb_width = (upper - lower) / middle
        bb_position = (current - lower) / (upper - lower + 1e-10)

        signal = "neutral"
        strength = 0.0
        level = "neutral"

        bb_width_pct = bb_width * 100

        if bb_width < 0.02:
            signal = "squeeze"
            strength = 1.0 - bb_width / 0.02
            level = "tight"
        elif current > upper * 1.02:
            signal = "overbought"
            strength = min(1.0, (current - upper) / std)
        elif current < lower * 0.98:
            signal = "oversold"
            strength = min(1.0, (lower - current) / std)

        return AdvancedIndicator(
            value=bb_position,
            signal=signal,
            strength=strength,
            level=level
        )

    # --- Stochastic Oscillator --------------------------------------------

    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> AdvancedIndicator:
        """Stochastic oscillator with %K and %D signals."""
        if len(closes) < period:
            return AdvancedIndicator(value=50.0, signal="neutral", strength=0.0, level="unknown")

        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])

        current_high = highs[-1]
        current_low = lows[-1]

        k_val = ((current_high - lowest_low) / (highest_high - lowest_low + 1e-10)) * 100
        d_val = sum([((h - lowest_low) / (highest_high - lowest_low + 1e-10)) * 100 for h in highs[-period:]]) / period

        signal = "neutral"
        strength = 0.0

        if k_val > 80 and d_val > 80:
            signal = "overbought"
            strength = min(1.0, (k_val - 80) / 20)
        elif k_val < 20 and d_val < 20:
            signal = "oversold"
            strength = min(1.0, (20 - k_val) / 20)

        return AdvancedIndicator(
            value=k_val,
            signal=signal,
            strength=strength,
            level="strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        )

    # --- ADX ---------------------------------------------------------------

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> AdvancedIndicator:
        """ADX with +DI and -DI for trend strength."""
        if len(closes) < period + 1:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        tr = []
        for i in range(1, len(closes)):
            high_low = highs[i] - lows[i]
            high_close = abs(highs[i] - closes[i-1])
            low_close = abs(lows[i] - closes[i-1])
            tr.append(max(high_low, high_close, low_close))

        plus_dm = []
        minus_dm = []
        for i in range(1, len(closes)):
            dm_plus = highs[i] - highs[i-1]
            dm_minus = lows[i-1] - lows[i]
            if dm_plus > dm_minus and dm_plus > 0:
                plus_dm.append(dm_plus)
                minus_dm.append(0.0)
            elif dm_minus > dm_plus and dm_minus > 0:
                plus_dm.append(0.0)
                minus_dm.append(dm_minus)
            else:
                plus_dm.append(0.0)
                minus_dm.append(0.0)

        # Pad with zeros if we have less data than needed
        if len(tr) < period:
            tr = [0.0] * (period - len(tr)) + tr
        if len(plus_dm) < period:
            plus_dm = [0.0] * (period - len(plus_dm)) + plus_dm
        if len(minus_dm) < period:
            minus_dm = [0.0] * (period - len(minus_dm)) + minus_dm

        tr_smooth = tr[-period:] + [tr[-1]] * period
        plus_dm_smooth = plus_dm[-period:] + [plus_dm[-1]] * period
        minus_dm_smooth = minus_dm[-period:] + [minus_dm[-1]] * period

        tr_avg = sum(tr_smooth) / period
        plus_dm_avg = sum(plus_dm_smooth) / period
        minus_dm_avg = sum(minus_dm_smooth) / period

        plus_di = (plus_dm_avg / tr_avg) * 100 if tr_avg > 0 else 0.0
        minus_di = (minus_dm_avg / tr_avg) * 100 if tr_avg > 0 else 0.0

        dx = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        adx = dx

        signal = "neutral"
        strength = 0.0
        level = "weak"

        if adx >= 25:
            level = "moderate"
            if adx >= 40:
                level = "strong"
                if plus_di > minus_di:
                    signal = "trending_up"
                else:
                    signal = "trending_down"
            strength = min(1.0, (adx - 25) / 15)

        return AdvancedIndicator(
            value=adx,
            signal=signal,
            strength=strength,
            level=level
        )

    # --- Ichimoku Cloud ----------------------------------------------------

    @staticmethod
    def ichimoku(highs: List[float], lows: List[float], closes: List[float]) -> AdvancedIndicator:
        """Ichimoku Cloud with conversion and base line signals."""
        if len(closes) < 50:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        tenkan_sen = (max(highs[-9:]) + min(lows[-9:])) / 2
        kijun_sen = (max(highs[-26:]) + min(lows[-26:])) / 2
        senkou_a = ((tenkan_sen + kijun_sen) / 2 + (max(highs[-52:]) + min(lows[-52:])) / 2) / 2
        senkou_b = ((max(highs[-26:]) + min(lows[-26:])) / 2 + (max(highs[-52:]) + min(lows[-52:])) / 2) / 2
        chikou_span = closes[-26]

        current = closes[-1]
        conversion_line = tenkan_sen
        base_line = kijun_sen

        signal = "neutral"
        strength = 0.0

        if conversion_line > base_line and senkou_a > senkou_b:
            signal = "bullish"
            strength = min(1.0, (conversion_line - base_line) / (base_line * 0.05))
        elif conversion_line < base_line and senkou_a < senkou_b:
            signal = "bearish"
            strength = min(1.0, (base_line - conversion_line) / (base_line * 0.05))

        return AdvancedIndicator(
            value=current - chikou_span,
            signal=signal,
            strength=strength,
            level="strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        )

    # --- Volume Profile ----------------------------------------------------

    @staticmethod
    def volume_profile(prices: List[float], volumes: List[float], num_levels: int = 20) -> AdvancedIndicator:
        """Volume profile with value area and POC (Point of Control)."""
        if len(prices) < num_levels:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        price_range = max(prices) - min(prices)
        level_width = price_range / num_levels

        levels = []
        for i in range(num_levels):
            level_price = min(prices) + i * level_width
            level_vol = sum(v for p, v in zip(prices, volumes) if p >= level_price and p < level_price + level_width)
            levels.append((level_price, level_vol))

        poc_price = max(levels, key=lambda x: x[1])[0]
        value_area_top = sorted(levels, key=lambda x: x[1], reverse=True)[:3]
        value_area_bot = sorted(levels, key=lambda x: x[1])[:3]

        current_price = prices[-1]
        pos_in_value = (current_price - value_area_bot[0][0]) / (value_area_top[0][0] - value_area_bot[0][0] + 1e-10)

        signal = "neutral"
        strength = 0.0

        if pos_in_value > 0.7:
            signal = "bullish_depth"
            strength = pos_in_value
        elif pos_in_value < 0.3:
            signal = "bearish_depth"
            strength = 1.0 - pos_in_value

        return AdvancedIndicator(
            value=pos_in_value,
            signal=signal,
            strength=strength,
            level="strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        )

    # --- Composite Trend Signal --------------------------------------------

    @staticmethod
    def trend_score(prices: List[float], highs: List[float], lows: List[float], closes: List[float]) -> AdvancedIndicator:
        """Composite trend score combining RSI, MACD, ADX signals."""
        if len(closes) < 30:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        rsi = AdvancedIndicators.rsi(closes, period=14)
        macd = AdvancedIndicators.macd(closes)
        adx = AdvancedIndicators.adx(highs, lows, closes, period=14)

        signals = []
        strengths = []

        if macd.signal == "bullish":
            signals.append(1.0)
            strengths.append(macd.strength)
        elif macd.signal == "bearish":
            signals.append(-1.0)
            strengths.append(macd.strength)

        if rsi.signal == "oversold":
            signals.append(1.0)
            strengths.append(rsi.strength * 0.5)
        elif rsi.signal == "overbought":
            signals.append(-1.0)
            strengths.append(rsi.strength * 0.5)

        if adx.signal == "trending_up":
            signals.append(1.0)
            strengths.append(adx.strength * 0.3)
        elif adx.signal == "trending_down":
            signals.append(-1.0)
            strengths.append(adx.strength * 0.3)

        if not signals:
            return AdvancedIndicator(value=0.0, signal="neutral", strength=0.0, level="unknown")

        total_score = sum(s * st for s, st in zip(signals, strengths))
        normalized_score = total_score / sum(strengths)

        signal = "neutral"
        level = "neutral"

        if normalized_score > 0.3:
            signal = "bullish"
            level = "strong" if normalized_score > 0.7 else "moderate"
        elif normalized_score < -0.3:
            signal = "bearish"
            level = "strong" if normalized_score < -0.7 else "moderate"

        return AdvancedIndicator(
            value=normalized_score,
            signal=signal,
            strength=abs(normalized_score),
            level=level
        )

    @staticmethod
    def _ema(data: List[float], period: int) -> float:
        """Exponential Moving Average."""
        if not data:
            return 0.0

        multiplier = 2 / (period + 1)
        ema = data[0]

        for price in data[1:]:
            ema = (price - ema) * multiplier + ema

        return ema

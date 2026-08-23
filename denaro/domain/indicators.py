#!/usr/bin/env python3
"""Denaro — domain indicators (puro Python, zero dipendenze).

Consolida i moduli mancanti/circolari del vecchio layer v6/v7:
- `atr_percent`, `volatility_regime`, `historical_var`, `clamp`
  (importati da risk/core/grid ma mai definiti — ImportError in produzione)
- indicatore avanzati (RSI, MACD, Bollinger, ADX, Ichimoku, Volume Profile,
  trend score) portati da `indicators_advanced.py`
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


# --- helper puri -------------------------------------------------------------

def clamp(value: float, lo: float, hi: float) -> float:
    """Ritaglia `value` nell'intervallo [lo, hi]."""
    return max(lo, min(hi, value))


def atr_percent(ohlcv: Sequence[Sequence[float]], period: int = 14) -> float:
    """Average True Range come percentuale dell'ultimo prezzo.

    `ohlcv`: lista di righe [ts, open, high, low, close, volume].
    Ritorna 0.0 se i dati sono insufficienti (contratto v4).
    """
    if len(ohlcv) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(ohlcv)):
        high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
        trs.append(max(high - low, abs(high - prev_close), abs(low - prev_close)))
    atr = sum(trs[-period:]) / period
    price = ohlcv[-1][4]
    return atr / price if price > 0 else 0.0


def volatility_regime(atr_pct: float) -> str:
    """Classifica il regime di volatilita' (low|normal|high|extreme).

    Soglie calibrate su candle 1h crypto (ATR% ~ 0.1-0.5% in normalita').
    """
    if atr_pct <= 0.001:
        return "low"
    if atr_pct <= 0.004:
        return "normal"
    if atr_pct <= 0.012:
        return "high"
    return "extreme"


def historical_var(prices: Sequence[float]) -> tuple:
    """VaR storica sui rendimenti: (var_95, var_99, cvar_95).

    Ritorna i default di sicurezza (0.02, 0.035, 0.03) con dati insufficienti.
    """
    if len(prices) < 10:
        return (0.02, 0.035, 0.03)
    rets = sorted(
        (prices[i] - prices[i - 1]) / prices[i - 1]
        for i in range(1, len(prices)) if prices[i - 1] > 0
    )
    if len(rets) < 10:
        return (0.02, 0.035, 0.03)
    n = len(rets)
    idx95 = max(0, int(n * 0.05) - 1)
    idx99 = max(0, int(n * 0.01) - 1)
    var95 = abs(rets[idx95])
    var99 = abs(rets[idx99])
    tail = rets[:idx95 + 1]
    cvar95 = abs(sum(tail) / len(tail)) if tail else var95
    return (var95, var99, cvar95)


def _ema(data: Sequence[float], period: int) -> float:
    if not data:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = data[0]
    for price in data[1:]:
        ema = (price - ema) * multiplier + ema
    return ema


# --- Advanced indicators ------------------------------------------------------

@dataclass
class AdvancedIndicator:
    value: float
    signal: str
    strength: float
    level: str


class AdvancedIndicators:
    """Toolkit tecnico: ogni indicatore ritorna valore + segnale + forza."""

    # --- RSI ---------------------------------------------------------------

    @staticmethod
    def rsi(prices: List[float], period: int = 14) -> AdvancedIndicator:
        if len(prices) < period + 1:
            return AdvancedIndicator(50.0, "neutral", 0.0, "unknown")
        gains = [max(prices[i] - prices[i - 1], 0) for i in range(1, len(prices))]
        losses = [max(prices[i - 1] - prices[i], 0) for i in range(1, len(prices))]
        avg_gain = sum(gains[-period:]) / period
        avg_loss = sum(losses[-period:]) / period
        if avg_loss == 0:
            return AdvancedIndicator(100.0, "overbought", 1.0, "extreme")
        rs = avg_gain / avg_loss
        rsi_val = 100 - (100 / (1 + rs))
        signal, strength, level = "neutral", 0.0, "neutral"
        if rsi_val > 70:
            signal, strength = "overbought", min(1.0, (rsi_val - 70) / 30)
            level = "high" if rsi_val > 80 else "moderate"
        elif rsi_val < 30:
            signal, strength = "oversold", min(1.0, (30 - rsi_val) / 30)
            level = "low" if rsi_val < 20 else "moderate"
        return AdvancedIndicator(rsi_val, signal, strength, level)

    # --- MACD --------------------------------------------------------------

    @staticmethod
    def macd(prices: List[float], fast: int = 12, slow: int = 26, signal: int = 9) -> AdvancedIndicator:
        if len(prices) < slow + signal:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        macd_line = _ema(prices[-fast:], fast) - _ema(prices[-slow:], slow)
        signal_line = _ema(prices[-(fast + slow + signal):], signal)
        hist = macd_line - signal_line
        signal_str, strength = "neutral", 0.0
        if hist > 0.0001:
            signal_str, strength = "bullish", min(1.0, hist / (signal_line * 0.02))
        elif hist < -0.0001:
            signal_str, strength = "bearish", min(1.0, abs(hist) / (signal_line * 0.02))
        level = "strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        return AdvancedIndicator(macd_line, signal_str, strength, level)

    # --- Bollinger Bands ----------------------------------------------------

    @staticmethod
    def bollinger_bands(prices: List[float], period: int = 20, std_dev: float = 2.0) -> AdvancedIndicator:
        if len(prices) < period + 1:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        middle = sum(prices[-period:]) / period
        variance = sum((x - middle) ** 2 for x in prices[-period:]) / period
        std = variance ** 0.5
        upper, lower, current = middle + std_dev * std, middle - std_dev * std, prices[-1]
        bb_width = (upper - lower) / middle
        bb_position = (current - lower) / (upper - lower + 1e-10)
        signal, strength, level = "neutral", 0.0, "neutral"
        if bb_width < 0.02:
            signal, strength, level = "squeeze", 1.0 - bb_width / 0.02, "tight"
        elif current > upper * 1.02:
            signal, strength = "overbought", min(1.0, (current - upper) / std)
        elif current < lower * 0.98:
            signal, strength = "oversold", min(1.0, (lower - current) / std)
        return AdvancedIndicator(bb_position, signal, strength, level)

    # --- Stochastic ---------------------------------------------------------

    @staticmethod
    def stochastic(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> AdvancedIndicator:
        if len(closes) < period:
            return AdvancedIndicator(50.0, "neutral", 0.0, "unknown")
        highest_high = max(highs[-period:])
        lowest_low = min(lows[-period:])
        denom = highest_high - lowest_low + 1e-10
        k_val = ((highs[-1] - lowest_low) / denom) * 100
        d_val = sum(((h - lowest_low) / denom) * 100 for h in highs[-period:]) / period
        signal, strength = "neutral", 0.0
        if k_val > 80 and d_val > 80:
            signal, strength = "overbought", min(1.0, (k_val - 80) / 20)
        elif k_val < 20 and d_val < 20:
            signal, strength = "oversold", min(1.0, (20 - k_val) / 20)
        level = "strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        return AdvancedIndicator(k_val, signal, strength, level)

    # --- ADX ---------------------------------------------------------------

    @staticmethod
    def adx(highs: List[float], lows: List[float], closes: List[float], period: int = 14) -> AdvancedIndicator:
        if len(closes) < period + 1:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        tr, plus_dm, minus_dm = [], [], []
        for i in range(1, len(closes)):
            hl = highs[i] - lows[i]
            hc = abs(highs[i] - closes[i - 1])
            lc = abs(lows[i] - closes[i - 1])
            tr.append(max(hl, hc, lc))
            dm_plus = highs[i] - highs[i - 1]
            dm_minus = lows[i - 1] - lows[i]
            if dm_plus > dm_minus and dm_plus > 0:
                plus_dm.append(dm_plus); minus_dm.append(0.0)
            elif dm_minus > dm_plus and dm_minus > 0:
                plus_dm.append(0.0); minus_dm.append(dm_minus)
            else:
                plus_dm.append(0.0); minus_dm.append(0.0)
        if len(tr) < period:
            tr = [0.0] * (period - len(tr)) + tr
        if len(plus_dm) < period:
            plus_dm = [0.0] * (period - len(plus_dm)) + plus_dm
        if len(minus_dm) < period:
            minus_dm = [0.0] * (period - len(minus_dm)) + minus_dm
        tr_avg = sum(tr[-period:] + [tr[-1]] * period) / period
        plus_avg = sum(plus_dm[-period:] + [plus_dm[-1]] * period) / period
        minus_avg = sum(minus_dm[-period:] + [minus_dm[-1]] * period) / period
        plus_di = (plus_avg / tr_avg) * 100 if tr_avg > 0 else 0.0
        minus_di = (minus_avg / tr_avg) * 100 if tr_avg > 0 else 0.0
        adx_val = abs(plus_di - minus_di) / (plus_di + minus_di + 1e-10) * 100
        signal, strength, level = "neutral", 0.0, "weak"
        if adx_val >= 25:
            level = "moderate"
            if adx_val >= 40:
                level = "strong"
                signal = "trending_up" if plus_di > minus_di else "trending_down"
            strength = min(1.0, (adx_val - 25) / 15)
        return AdvancedIndicator(adx_val, signal, strength, level)

    # --- Ichimoku -----------------------------------------------------------

    @staticmethod
    def ichimoku(highs: List[float], lows: List[float], closes: List[float]) -> AdvancedIndicator:
        if len(closes) < 50:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        tenkan = (max(highs[-9:]) + min(lows[-9:])) / 2
        kijun = (max(highs[-26:]) + min(lows[-26:])) / 2
        senkou_a = ((tenkan + kijun) / 2 + (max(highs[-52:]) + min(lows[-52:])) / 2) / 2
        senkou_b = ((max(highs[-26:]) + min(lows[-26:])) / 2 + (max(highs[-52:]) + min(lows[-52:])) / 2) / 2
        chikou = closes[-26]
        current = closes[-1]
        signal, strength = "neutral", 0.0
        if tenkan > kijun and senkou_a > senkou_b:
            signal, strength = "bullish", min(1.0, (tenkan - kijun) / (kijun * 0.05))
        elif tenkan < kijun and senkou_a < senkou_b:
            signal, strength = "bearish", min(1.0, (kijun - tenkan) / (kijun * 0.05))
        level = "strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        return AdvancedIndicator(current - chikou, signal, strength, level)

    # --- Volume Profile -----------------------------------------------------

    @staticmethod
    def volume_profile(prices: List[float], volumes: List[float], num_levels: int = 20) -> AdvancedIndicator:
        if len(prices) < num_levels:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        price_range = max(prices) - min(prices)
        level_width = price_range / num_levels
        levels = []
        for i in range(num_levels):
            lp = min(prices) + i * level_width
            lv = sum(v for p, v in zip(prices, volumes) if lp <= p < lp + level_width)
            levels.append((lp, lv))
        poc = max(levels, key=lambda x: x[1])[0]
        top = sorted(levels, key=lambda x: x[1], reverse=True)[:3]
        bot = sorted(levels, key=lambda x: x[1])[:3]
        pos = (prices[-1] - bot[0][0]) / (top[0][0] - bot[0][0] + 1e-10)
        signal, strength = "neutral", 0.0
        if pos > 0.7:
            signal, strength = "bullish_depth", pos
        elif pos < 0.3:
            signal, strength = "bearish_depth", 1.0 - pos
        level = "strong" if strength > 0.7 else "weak" if strength < 0.3 else "moderate"
        return AdvancedIndicator(pos, signal, strength, level)

    # --- Trend score --------------------------------------------------------

    @staticmethod
    def trend_score(prices: List[float], highs: List[float], lows: List[float], closes: List[float]) -> AdvancedIndicator:
        if len(closes) < 30:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        rsi = AdvancedIndicators.rsi(closes, 14)
        macd = AdvancedIndicators.macd(closes)
        adx = AdvancedIndicators.adx(highs, lows, closes, 14)
        signals, strengths = [], []
        if macd.signal == "bullish":
            signals.append(1.0); strengths.append(macd.strength)
        elif macd.signal == "bearish":
            signals.append(-1.0); strengths.append(macd.strength)
        if rsi.signal == "oversold":
            signals.append(1.0); strengths.append(rsi.strength * 0.5)
        elif rsi.signal == "overbought":
            signals.append(-1.0); strengths.append(rsi.strength * 0.5)
        if adx.signal == "trending_up":
            signals.append(1.0); strengths.append(adx.strength * 0.3)
        elif adx.signal == "trending_down":
            signals.append(-1.0); strengths.append(adx.strength * 0.3)
        if not signals:
            return AdvancedIndicator(0.0, "neutral", 0.0, "unknown")
        total = sum(s * st for s, st in zip(signals, strengths))
        normalized = total / sum(strengths)
        signal, level = "neutral", "neutral"
        if normalized > 0.3:
            signal = "bullish"
            level = "strong" if normalized > 0.7 else "moderate"
        elif normalized < -0.3:
            signal = "bearish"
            level = "strong" if normalized < -0.7 else "moderate"
        return AdvancedIndicator(normalized, signal, abs(normalized), level)

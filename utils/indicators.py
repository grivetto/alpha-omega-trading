"""Indicatori tecnici — Pure Pandas/NumPy implementation.
Niente pandas_ta: RSI, EMA, SMA, ATR, MACD calcolati con pandas/numpy puri.
v3.0: rimossa dipendenza da pandas_ta per compatibilità Python 3.14+.
"""
import pandas as pd
import numpy as np
import statistics
from typing import Optional


# ── Base indicators ────────────────────────────────────────────────

def calculate_rsi(prices, length=14):
    """RSI usando Wilder's smoothing. Return ultimo valore."""
    if len(prices) < length + 1:
        return 50.0
    series = pd.Series(prices, dtype=float)
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)

    avg_gain = gain.rolling(window=length, min_periods=length).mean()[:length+1]
    avg_loss = loss.rolling(window=length, min_periods=length).mean()[:length+1]

    # Wilder smoothing
    for i in range(length+1, len(series)):
        avg_gain.iloc[i] = (avg_gain.iloc[i-1] * (length-1) + gain.iloc[i]) / length
        avg_loss.iloc[i] = (avg_loss.iloc[i-1] * (length-1) + loss.iloc[i]) / length

    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 50.0


def calculate_ema(prices, length=9):
    """Exponential Moving Average — pura pandas."""
    if len(prices) < length:
        return float(prices[-1]) if prices else 0.0
    series = pd.Series(prices, dtype=float)
    ema = series.ewm(span=length, adjust=False).mean()
    return float(ema.iloc[-1])


def calculate_sma(prices, length=20):
    """Simple Moving Average."""
    if len(prices) < length:
        return float(prices[-1]) if prices else 0.0
    return float(sum(prices[-length:]) / length)


def calculate_atr(highs, lows, closes, length=14):
    """Average True Range — pura pandas."""
    if len(highs) < length + 1:
        return 0.0
    df = pd.DataFrame({
        'high': pd.Series(highs, dtype=float),
        'low': pd.Series(lows, dtype=float),
        'close': pd.Series(closes, dtype=float),
    })
    prev_close = df['close'].shift(1)
    tr = pd.concat([
        (df['high'] - df['low']).abs(),
        (df['high'] - prev_close).abs(),
        (df['low'] - prev_close).abs(),
    ], axis=1).max(axis=1)
    atr = tr.rolling(window=length, min_periods=length).mean()
    return float(atr.iloc[-1]) if not atr.empty else 0.0


# ── MACD (Moving Average Convergence Divergence) ───────────────────

def calculate_macd(prices: list, fast=12, slow=26, signal=9) -> dict:
    """MACD usando EMA pura."""
    if len(prices) < slow + signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "histogram_pct": 0.0}

    series = pd.Series(prices, dtype=float)
    ema_fast = series.ewm(span=fast, adjust=False).mean()
    ema_slow = series.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    macd_val = float(macd_line.iloc[-1])
    signal_val = float(signal_line.iloc[-1])
    hist_val = float(histogram.iloc[-1])
    current_price = prices[-1] if prices else 1.0

    return {
        "macd_line": round(macd_val, 4),
        "signal_line": round(signal_val, 4),
        "histogram": round(hist_val, 4),
        "histogram_pct": round((hist_val / current_price) * 100, 3),
    }


# ── VWAP (Volume Weighted Average Price) ──────────────────────────

def calculate_vwap(ohlcv: list) -> Optional[float]:
    """Volume Weighted Average Price da lista OHLCV."""
    if not ohlcv:
        return None
    tp_vol = sum(((c[1] + c[2] + c[3]) / 3) * c[5] for c in ohlcv)
    vol = sum(c[5] for c in ohlcv)
    return tp_vol / vol if vol > 0 else None


# ── Multi-timeframe aggregation ────────────────────────────────────

def aggregate_timeframes(
    ohlcv_short: list,
    ohlcv_long: list,
    short_label: str = "short",
    long_label: str = "long",
) -> dict:
    """Aggrega indicatori da due timeframe in un unico dict strutturato."""
    def _compute(label, ohlcv):
        if not ohlcv:
            return {label: {}, "price": 0.0}
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        vols = [c[5] for c in ohlcv]
        price = closes[-1]

        return {
            "price": price,
            "rsi": round(calculate_rsi(closes), 1),
            "ema9": round(calculate_ema(closes, 9), 2),
            "sma20": round(calculate_sma(closes, 20), 2),
            "sma50": round(calculate_sma(closes, 50), 2) if len(closes) >= 50 else None,
            "macd": calculate_macd(closes),
            "vwap": round(calculate_vwap(ohlcv), 2) if calculate_vwap(ohlcv) else None,
            "atr_pct": round(
                calculate_atr(highs, lows, closes) / price * 100, 3
            ) if len(closes) >= 14 else None,
            "volume_ratio": round(
                vols[-1] / statistics.mean(vols[-20:]), 2
            ) if len(vols) >= 20 else None,
        }

    short_data = _compute(short_label, ohlcv_short)
    long_data = _compute(long_label, ohlcv_long)

    # Divergence detection: short RSI diverging from long trend
    divergence = "neutral"
    if (short_data.get("rsi", 50) < 35 and
        long_data.get("price", 0) > long_data.get("sma20", 0)):
        divergence = "bullish"
    elif (short_data.get("rsi", 50) > 65 and
          long_data.get("price", 0) < long_data.get("sma20", 0)):
        divergence = "bearish"

    return {
        short_label: short_data,
        long_label: long_data,
        "divergence": divergence,
    }

import pandas as pd
import pandas_ta as ta
import statistics
from typing import Optional


# ── Base indicators ────────────────────────────────────────────────

def calculate_rsi(prices, length=14):
    """Calculates RSI using pandas_ta. Returns the last value."""
    if len(prices) < length:
        return 50.0
    series = pd.Series(prices)
    rsi = ta.rsi(series, length=length)
    return float(rsi.iloc[-1]) if not rsi.empty else 50.0

def calculate_ema(prices, length=9):
    """Calculates EMA using pandas_ta. Returns the last value."""
    if len(prices) < length:
        return prices[-1] if prices else 0.0
    series = pd.Series(prices)
    ema = ta.ema(series, length=length)
    return float(ema.iloc[-1]) if not ema.empty else prices[-1]

def calculate_sma(prices, length=20):
    """Simple Moving Average."""
    if len(prices) < length:
        return prices[-1] if prices else 0.0
    return sum(prices[-length:]) / length

def calculate_atr(highs, lows, closes, length=14):
    """Calculates ATR using pandas_ta. Returns the last value."""
    if len(highs) < length:
        return 0.0
    df = pd.DataFrame({
        'high': highs,
        'low': lows,
        'close': closes
    })
    atr = ta.atr(df['high'], df['low'], df['close'], length=length)
    return float(atr.iloc[-1]) if not atr.empty else 0.0


# ── MACD (Moving Average Convergence Divergence) ───────────────────
# Aggiunto da video Alpha Arena: usato come indicatore principale
# per trend momentum e divergenze.

def calculate_macd(prices: list, fast=12, slow=26, signal=9) -> dict:
    """
    Calcola MACD.

    Returns:
        dict con:
          - macd_line: MACD (EMA fast - EMA slow)
          - signal_line: EMA della macd_line (periodo signal)
          - histogram: macd_line - signal_line (positivo = bullish momentum)
          - histogram_pct: istogramma normalizzato sul prezzo corrente (%)
    """
    if len(prices) < slow + signal:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "histogram_pct": 0.0}

    series = pd.Series(prices)
    macd_result = ta.macd(series, fast=fast, slow=slow, signal=signal)
    if macd_result is None or macd_result.empty:
        return {"macd_line": 0.0, "signal_line": 0.0, "histogram": 0.0, "histogram_pct": 0.0}

    last = macd_result.iloc[-1]
    macd_val = float(last.get(f"MACD_{fast}_{slow}_{signal}", 0))
    signal_val = float(last.get(f"MACDs_{fast}_{slow}_{signal}", 0))
    hist_val = float(last.get(f"MACDh_{fast}_{slow}_{signal}", 0))
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
# Pattern chiave dal video Alpha Arena: ogni decisione considera
# TWO timeframe: short-term (~4h di 5min candles) + long-term (~3gg).

def aggregate_timeframes(
    ohlcv_short: list,
    ohlcv_long: list,
    short_label: str = "short",
    long_label: str = "long",
) -> dict:
    """
    Aggrega indicatori da due timeframe in un unico dict strutturato.

    Args:
        ohlcv_short: Candele timeframe breve (es. 5min, ultime 4h)
        ohlcv_long:  Candele timeframe lungo (es. 1h, ultimi 3gg)
        short_label: Nome per il timeframe breve (default 'short')
        long_label:  Nome per il timeframe lungo (default 'long')

    Returns:
        dict con:
          - {short_label}: { rsi, ema9, sma20, macd, vwap, atr_pct, price }
          - {long_label}:  { rsi, ema9, sma20, macd, vwap, atr_pct, price }
          - divergence: 'bullish' | 'bearish' | 'neutral'
            (short RSI diverge da long trend = segnale forte)
    """
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
        # Short ipervenduto ma long in uptrend = bullish divergence
        divergence = "bullish"
    elif (short_data.get("rsi", 50) > 65 and
          long_data.get("price", 0) < long_data.get("sma20", 0)):
        # Short ipercomprato ma long in downtrend = bearish divergence
        divergence = "bearish"

    return {
        short_label: short_data,
        long_label: long_data,
        "divergence": divergence,
    }

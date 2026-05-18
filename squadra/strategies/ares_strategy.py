"""
Ares Strategy — Intraday Trend following con SMA crossover + ATR.

Funzione pura: prende OHLCV + parametri, restituisce signal.
Nessuna dipendenza da exchange, DB o stato bot.
"""
from typing import Optional


def _calc_sma(prices: list, period: int) -> Optional[float]:
    """Simple Moving Average."""
    if len(prices) < period:
        return None
    return sum(prices[-period:]) / period


def _calc_atr(ohlcv: list, period: int = 14) -> float:
    """Average True Range."""
    if len(ohlcv) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(ohlcv)):
        high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period if trs else 0.0


def ares_signal(ohlcv: list, fast_period: int = 5, slow_period: int = 20) -> dict:
    """
    Genera segnale trading basato su SMA crossover + ATR.

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]
        fast_period: periodo SMA veloce
        slow_period: periodo SMA lento

    Returns:
        dict con:
          - action: "BUY" | "SELL" | "HOLD"
          - atr: float (ATR value)
          - current_price: float
          - reason: str
    """
    if not ohlcv:
        return {"action": "HOLD", "atr": 0.0, "current_price": 0.0, "reason": "no data"}

    prices = [c[4] for c in ohlcv]  # closing prices
    current_price = prices[-1]
    atr = _calc_atr(ohlcv)

    if len(prices) < slow_period:
        return {"action": "HOLD", "atr": atr, "current_price": current_price,
                "reason": f"building history ({len(prices)}/{slow_period})"}

    fast_sma = _calc_sma(prices, fast_period)
    slow_sma = _calc_sma(prices, slow_period)
    prev_fast = _calc_sma(prices[:-1], fast_period)
    prev_slow = _calc_sma(prices[:-1], slow_period)

    if None in (fast_sma, slow_sma, prev_fast, prev_slow):
        return {"action": "HOLD", "atr": atr, "current_price": current_price,
                "reason": "insufficient data for SMA"}

    # After the None guard, all are float — assert for type checker
    assert fast_sma is not None and slow_sma is not None
    assert prev_fast is not None and prev_slow is not None

    # BUY: crossover rialzista (fast crosses above slow) + prezzo sopra fast
    if prev_fast <= prev_slow and fast_sma > slow_sma and current_price > fast_sma:
        return {"action": "BUY", "atr": atr, "current_price": current_price,
                "reason": f"SMA crossover rialzista (fast={fast_sma:.2f} > slow={slow_sma:.2f})"}

    # SELL: crossover ribassista (fast crosses below slow) + prezzo sotto fast
    if prev_fast >= prev_slow and fast_sma < slow_sma and current_price < fast_sma:
        return {"action": "SELL", "atr": atr, "current_price": current_price,
                "reason": f"SMA crossover ribassista (fast={fast_sma:.2f} < slow={slow_sma:.2f})"}

    return {"action": "HOLD", "atr": atr, "current_price": current_price,
            "reason": f"no crossover (fast={fast_sma:.2f}, slow={slow_sma:.2f})"}

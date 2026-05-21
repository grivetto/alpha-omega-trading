"""
Hermes Strategy — Sentiment analysis via RSI, volume spike, VWAP divergence.

Funzione pura: prende OHLCV + parametri, restituisce signal.
Nessuna dipendenza da exchange, DB o stato bot.
"""
import statistics
from typing import Optional


def _calc_rsi(prices: list, period: int = 14) -> float:
    """Relative Strength Index."""
    if len(prices) < period + 1:
        return 50.0
    gains, losses = [], []
    for i in range(1, len(prices)):
        diff = prices[-i] - prices[-i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = statistics.mean(gains[:period]) if gains else 0
    avg_loss = statistics.mean(losses[:period]) if losses else 0
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _calc_vwap(ohlcv: list) -> Optional[float]:
    """Volume Weighted Average Price."""
    if not ohlcv:
        return None
    tp_vol = sum(((c[1] + c[2] + c[3]) / 3) * c[5] for c in ohlcv)
    vol = sum(c[5] for c in ohlcv)
    return tp_vol / vol if vol > 0 else None


def hermes_signal(ohlcv: list) -> dict:
    """
    Genera segnale basato su sentiment score (-1 bearish, +1 bullish).

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]

    Returns:
        dict con:
          - action: "BUY" | "SELL" | "HOLD"
          - score: float (-1 to +1)
          - rsi: float
          - current_price: float
          - reason: str
    """
    if not ohlcv or len(ohlcv) < 20:
        return {"action": "HOLD", "score": 0.0, "rsi": 50.0,
                "current_price": ohlcv[-1][4] if ohlcv else 0.0,
                "reason": "building history" if ohlcv else "no data"}

    closes = [c[4] for c in ohlcv]
    volumes = [c[5] for c in ohlcv]
    current_price = closes[-1]
    current_volume = volumes[-1]
    avg_volume = statistics.mean(volumes[-20:]) if volumes else 1
    rsi = _calc_rsi(closes)
    vwap = _calc_vwap(ohlcv)

    score = 0.0
    reasons = []

    # Volume spike = sentiment forte (direzione determinata dal prezzo)
    if avg_volume > 0:
        vol_ratio = current_volume / avg_volume
        if vol_ratio > 2.0:
            score += 0.3 if current_price > closes[-5] else -0.3
            reasons.append(f"volume spike {vol_ratio:.1f}x")

    # RSI extremes
    if rsi < 25:
        score += 0.4
        reasons.append(f"RSI ipervenduto ({rsi:.1f})")
    elif rsi > 75:
        score -= 0.4
        reasons.append(f"RSI ipercomprato ({rsi:.1f})")
    elif rsi < 35:
        score += 0.2
        reasons.append(f"RSI basso ({rsi:.1f})")
    elif rsi > 65:
        score -= 0.2
        reasons.append(f"RSI alto ({rsi:.1f})")

    # VWAP position
    if vwap and vwap > 0:
        dist_pct = (current_price - vwap) / vwap * 100
        if dist_pct < -1.5:
            score += 0.2
            reasons.append(f"sotto VWAP ({dist_pct:.1f}%)")
        elif dist_pct > 1.5:
            score -= 0.2
            reasons.append(f"sopra VWAP ({dist_pct:.1f}%)")

    score = max(-1, min(1, score))

    if score >= 0.3:
        action = "BUY"
    elif score <= -0.3:
        action = "SELL"
    else:
        action = "HOLD"

    reason = "; ".join(reasons) if reasons else "no strong signal"
    return {
        "action": action,
        "score": round(score, 3),
        "rsi": round(rsi, 1),
        "current_price": current_price,
        "reason": f"sentiment={score:.2f} ({reason})",
    }

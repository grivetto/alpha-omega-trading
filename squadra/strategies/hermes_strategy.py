"""
Hermes Strategy — Sentiment analysis via RSI, volume spike, VWAP divergence + MACD + multi-timeframe.

v3.1: + multi-timeframe context (MACD, divergence filter, long-trend confirmation)
       Mantiene retrocompatibilità: se ctx non passato, funziona come v3.0.

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


def hermes_signal(ohlcv: list, ctx: Optional[dict] = None) -> dict:
    """
    Genera segnale basato su sentiment score (-1 bearish, +1 bullish).

    Se ctx (da aggregate_timeframes) è fornito, integra:
    - MACD histogram direction (momentum booster)
    - Divergence filter: rifiuta BUY se ctx divergence='bearish'
    - Long-term trend filter: riduce score se long RSI > 65 (ipercomprato lungo)

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]
        ctx: optional dict da aggregate_timeframes() con dati multi-timeframe

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

    # ── Multi-timeframe enhancements (v3.1) ───────────────────────
    if ctx is not None:
        short = ctx.get("short", {})
        long_tf = ctx.get("long", {})

        # MACD momentum boost
        macd = short.get("macd", {})
        if macd:
            macd_hist = macd.get("histogram", 0)
            macd_pct = macd.get("histogram_pct", 0)

            # Strong positive momentum -> boost BUY
            if macd_hist > 0 and macd_pct > 0.01:
                score += 0.15
                reasons.append(f"MACD+ ({macd_pct:.3f}%)")
            # Strong negative momentum -> boost SELL
            elif macd_hist < 0 and macd_pct < -0.01:
                score -= 0.15
                reasons.append(f"MACD- ({macd_pct:.3f}%)")

        # Long-term RSI climate check
        long_rsi = long_tf.get("rsi", 50)
        if long_rsi > 65:
            score -= 0.1  # Long-term ipercomprato = clima bearish
            reasons.append(f"longRSI {long_rsi:.0f}")
        elif long_rsi < 35:
            score += 0.1  # Long-term ipervenduto = clima bullish
            reasons.append(f"longRSI {long_rsi:.0f}")

        # Divergence: veto su BUY se bearish divergence
        divergence = ctx.get("divergence", "neutral")
        if divergence == "bearish":
            score = min(score, -0.1)  # non comprare, forzare HOLD/SELL
            reasons.append("🔴 bearish diverg")
        elif divergence == "bullish":
            score = max(score, 0.1)  # boost minimo, non forzare SELL
            reasons.append("🟢 bullish diverg")

        # ── Social Sentiment (v3.2) ──────────────────────────────
        sent = ctx.get("sentiment", {})
        if sent:
            sent_score = sent.get("score", 0)
            sent_weight = sent.get("weight", 0.15)
            sources = sent.get("sources", [])

            if sent_score != 0:
                # Weighted blend: final_score = tech * (1-w) + sent * w
                # Applichiamo come delta rispetto allo score attuale
                delta = sent_score * sent_weight * 2  # *2 per amplificare l'impatto
                score += delta
                direction = "🟢" if sent_score > 0 else "🔴"
                src_str = ",".join(sources[:2])
                reasons.append(f"{direction}social {sent_score:.2f} [{src_str}]")

    # ── Final action ────────────────────────────────────────────
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

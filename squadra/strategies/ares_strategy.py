"""
Ares Strategy — Intraday Trend following con SMA crossover + ATR + MACD + multi-timeframe.

v3.1: + multi-timeframe context (MACD, long-trend confirmation, divergence filter)
       Mantiene retrocompatibilità: se ctx non passato, funziona come v3.0.

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


def ares_signal(ohlcv: list, fast_period: int = 5, slow_period: int = 20,
                ctx: Optional[dict] = None) -> dict:
    """
    Genera segnale trading basato su SMA crossover + ATR + MACD + trend lungo.

    Se ctx (da aggregate_timeframes) è fornito, integra:
    - MACD confirmation: BUY solo se MACD histogram positivo
    - Long-term trend filter: BUY solo se long-term price > SMA20 (uptrend)
    - Divergence filter: blocca BUY su bearish divergence

    Args:
        ohlcv: list of [timestamp, open, high, low, close, volume]
        fast_period: periodo SMA veloce
        slow_period: periodo SMA lento
        ctx: optional dict da aggregate_timeframes() con dati multi-timeframe

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

    # ── Base signal: SMA crossover ──────────────────────────────
    base_signal = "HOLD"
    base_reason = f"no crossover (fast={fast_sma:.2f}, slow={slow_sma:.2f})"

    if prev_fast <= prev_slow and fast_sma > slow_sma and current_price > fast_sma:
        base_signal = "BUY"
        base_reason = f"SMA crossover rialzista (fast={fast_sma:.2f} > slow={slow_sma:.2f})"
    elif prev_fast >= prev_slow and fast_sma < slow_sma and current_price < fast_sma:
        base_signal = "SELL"
        base_reason = f"SMA crossover ribassista (fast={fast_sma:.2f} < slow={slow_sma:.2f})"

    # NEAR-CROSSOVER (only if no clean crossover)
    elif slow_sma > 0 and abs(fast_sma - slow_sma) / slow_sma < 0.0005:
        if current_price > max(fast_sma, slow_sma):
            base_signal = "BUY"
            base_reason = f"near golden cross (fast={fast_sma:.2f}, slow={slow_sma:.2f})"
        elif current_price < min(fast_sma, slow_sma):
            base_signal = "SELL"
            base_reason = f"near death cross (fast={fast_sma:.2f}, slow={slow_sma:.2f})"

    # ── Multi-timeframe filters (v3.1) ──────────────────────────
    if ctx is not None and base_signal in ("BUY", "SELL"):
        long_tf = ctx.get("long", {})
        short = ctx.get("short", {})
        macd = short.get("macd", {})
        divergence = ctx.get("divergence", "neutral")
        filters_ok = True
        filter_reasons = []

        # 1. MACD confirmation: BUY needs MACD histogram positive
        if macd:
            macd_hist = macd.get("histogram", 0)
            if base_signal == "BUY" and macd_hist < 0:
                filters_ok = False
                filter_reasons.append("MACD negativo")
            elif base_signal == "SELL" and macd_hist > 0:
                filters_ok = False
                filter_reasons.append("MACD positivo")

        # 2. Long-term trend filter: BUY solo se long price > SMA20 (uptrend)
        if base_signal == "BUY":
            long_price = long_tf.get("price", 0)
            long_sma20 = long_tf.get("sma20", 0)
            if long_price > 0 and long_sma20 > 0 and long_price < long_sma20:
                filters_ok = False
                filter_reasons.append(f"long trend down (price {long_price:.1f} < SMA20 {long_sma20:.1f})")

        # 3. Divergence filter: veto su BUY se bearish divergence
        if base_signal == "BUY" and divergence == "bearish":
            filters_ok = False
            filter_reasons.append("🔴 bearish divergence")
        elif base_signal == "SELL" and divergence == "bullish":
            filters_ok = False
            filter_reasons.append("🟢 bullish divergence")

        if not filters_ok:
            return {"action": "HOLD", "atr": atr, "current_price": current_price,
                    "reason": f"filtered: {base_signal} rejected ({' | '.join(filter_reasons)})"}

        # Signal confirmed by multi-timeframe — add MACD detail to reason
        if macd:
            macd_pct = macd.get("histogram_pct", 0)
            base_reason += f" | MACD={'+' if macd.get('histogram', 0) >= 0 else '-'}({macd_pct:.3f}%)"

    return {"action": base_signal, "atr": atr, "current_price": current_price, "reason": base_reason}

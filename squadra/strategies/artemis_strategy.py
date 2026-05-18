"""
Artemis Strategy — BTC Long-Only Trend Follower.

Strategia "set-and-forget" stile Alpha Insider: long BTC quando il trend
è bullish, completamente out quando è bearish.

Funzione pura: prende daily OHLCV + parametri, restituisce signal.
Nessuna dipendenza da exchange, DB o stato bot.

Entry:
  1. Price > SMA200      (BTC sopra la media a lungo termine)
  2. SMA50 > SMA200      (golden cross — trend bullish confermato)

Exit:
  1. Price < SMA200      (BTC sotto la media — bear market)
  (oppure SMA50 < SMA200, death cross)

Timeframe: daily (1d). Trades: 3-5 all'anno in media.
"""
from typing import Optional


def artemis_signal(
    ohlcv: list,
    in_position: bool = False,
    entry_price: float = 0.0,
    fast_period: int = 50,
    slow_period: int = 200,
) -> dict:
    """
    Genera segnale BTC long-only trend following.

    Args:
        ohlcv: Daily OHLCV candles [[timestamp, o, h, l, c, v], ...]
        in_position: True se abbiamo già una posizione aperta
        entry_price: Prezzo di entrata (per calcolo P&L)
        fast_period: Periodo SMA veloce (default 50)
        slow_period: Periodo SMA lenta (default 200)

    Returns:
        dict con:
          - action: "BUY" | "SELL" | "HOLD"
          - current_price: float
          - fast_sma: float (SMA50)
          - slow_sma: float (SMA200)
          - reason: str
          - pnl_pct: float (se in posizione)
    """
    if not ohlcv or len(ohlcv) < slow_period + 1:
        return {
            "action": "HOLD",
            "current_price": 0.0,
            "fast_sma": 0.0,
            "slow_sma": 0.0,
            "reason": f"accumulating data ({len(ohlcv) if ohlcv else 0}/{slow_period + 1})",
            "pnl_pct": 0.0,
        }

    closes = [c[4] for c in ohlcv]
    current_price = closes[-1]
    prev_close = closes[-2] if len(closes) > 1 else current_price

    # SMA calcolate manualmente
    def sma(data: list, period: int) -> float:
        if len(data) < period:
            return 0.0
        return sum(data[-period:]) / period

    fast_sma = sma(closes, fast_period)
    slow_sma = sma(closes, slow_period)

    # P&L se in posizione
    pnl_pct = ((current_price - entry_price) / entry_price * 100) if in_position and entry_price > 0 else 0.0

    # Condizioni di trend
    price_above_slow = current_price > slow_sma
    golden_cross = fast_sma > slow_sma
    death_cross = fast_sma < slow_sma
    price_below_slow = current_price < slow_sma

    # ── EXIT: trend diventato bearish ──
    if in_position:
        if price_below_slow:
            return {
                "action": "SELL",
                "current_price": current_price,
                "fast_sma": round(fast_sma, 2),
                "slow_sma": round(slow_sma, 2),
                "reason": f"price ({current_price:.2f}) < SMA{slow_period} ({slow_sma:.2f}) — bear market exit",
                "pnl_pct": round(pnl_pct, 2),
            }
        if death_cross:
            return {
                "action": "SELL",
                "current_price": current_price,
                "fast_sma": round(fast_sma, 2),
                "slow_sma": round(slow_sma, 2),
                "reason": f"death cross: SMA{fast_period} ({fast_sma:.2f}) < SMA{slow_period} ({slow_sma:.2f})",
                "pnl_pct": round(pnl_pct, 2),
            }

    # ── ENTRY: trend bullish confermato ──
    if not in_position:
        if price_above_slow and golden_cross:
            return {
                "action": "BUY",
                "current_price": current_price,
                "fast_sma": round(fast_sma, 2),
                "slow_sma": round(slow_sma, 2),
                "reason": f"golden cross + price above SMA{slow_period} — bull trend confirmed",
                "pnl_pct": 0.0,
            }

    # ── HOLD: tutto nella norma ──
    status = "IN POSITION" if in_position else "WAITING"
    reason_parts = []
    if not golden_cross and not death_cross:
        reason_parts.append(f"SMA50={fast_sma:.2f} ≈ SMA200={slow_sma:.2f} (flat)")
    elif golden_cross:
        reason_parts.append(f"bullish (SMA50={fast_sma:.2f} > SMA200={slow_sma:.2f})")
    else:
        reason_parts.append(f"bearish (SMA50={fast_sma:.2f} < SMA200={slow_sma:.2f})")
    reason_parts.append(f"price={current_price:.2f}" + (f" > SMA200={slow_sma:.2f}" if price_above_slow else f" < SMA200={slow_sma:.2f}"))
    reason_parts.append(status)

    return {
        "action": "HOLD",
        "current_price": current_price,
        "fast_sma": round(fast_sma, 2),
        "slow_sma": round(slow_sma, 2),
        "reason": " | ".join(reason_parts),
        "pnl_pct": round(pnl_pct, 2),
    }

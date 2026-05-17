"""
Apollo Strategy — Pair Trading via ETH/BTC ratio mean reversion.

Funzione pura: prende OHLCV di due simboli + history del ratio + parametri,
restituisce signal. La storia del ratio e' mantenuta dal bot (state esterno).
Nessuna dipendenza da exchange, DB o stato bot.
"""
import statistics
from typing import Optional


def apollo_signal(
    ohlcv_a: list,
    ohlcv_b: list,
    ratio_history: list,
    z_entry: float = 1.5,
    z_exit: float = 0.3,
) -> dict:
    """
    Genera segnale basato su mean reversion del ratio ETH/BTC.

    Args:
        ohlcv_a: OHLCV per symbol_a (es. ETH/EUR)
        ohlcv_b: OHLCV per symbol_b (es. BTC/EUR)
        ratio_history: lista dei ratio passati (modificata in-place se serve)
        z_entry: Z-score per entrare
        z_exit: Z-score per uscire

    Returns:
        dict con:
          - action: "BUY" | "SELL" | "HOLD" | "EXIT"
          - z_score: float
          - ratio: float
          - current_price_a: float
          - current_price_b: float
          - reason: str
    """
    if not ohlcv_a or not ohlcv_b:
        return {"action": "HOLD", "z_score": 0.0, "ratio": 0.0,
                "current_price_a": 0.0, "current_price_b": 0.0,
                "reason": "no data"}

    closes_a = [c[4] for c in ohlcv_a]
    closes_b = [c[4] for c in ohlcv_b]
    min_len = min(len(closes_a), len(closes_b))
    closes_a, closes_b = closes_a[-min_len:], closes_b[-min_len:]

    current_price_a = closes_a[-1]
    current_price_b = closes_b[-1]

    if current_price_b <= 0:
        return {"action": "HOLD", "z_score": 0.0, "ratio": 0.0,
                "current_price_a": current_price_a, "current_price_b": current_price_b,
                "reason": "invalid price_b"}

    ratio = closes_a[-1] / current_price_b

    if len(ratio_history) < 20:
        updated_history = ratio_history + [ratio]
        return {"action": "HOLD", "z_score": 0.0, "ratio": ratio,
                "current_price_a": current_price_a, "current_price_b": current_price_b,
                "reason": f"building history ({len(ratio_history)}/20)",
                "updated_history": updated_history}

    mean_ratio = statistics.mean(ratio_history)
    std_ratio = statistics.stdev(ratio_history) if len(ratio_history) > 1 else 0.001
    z_score = (ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0

    # Trim history
    updated_history = (ratio_history + [ratio])[-100:]

    # EXIT: ratio reversion o Z-score rientrato
    if abs(z_score) < z_exit:
        return {"action": "EXIT", "z_score": round(z_score, 2), "ratio": round(ratio, 4),
                "current_price_a": current_price_a, "current_price_b": current_price_b,
                "reason": f"ratio reverted (z={z_score:.2f} < {z_exit})",
                "updated_history": updated_history}

    # ENTRY: ratio over-extended
    if z_score > z_entry:
        return {"action": "SELL", "z_score": round(z_score, 2), "ratio": round(ratio, 4),
                "current_price_a": current_price_a, "current_price_b": current_price_b,
                "reason": f"ratio too HIGH (z={z_score:.2f}) -> short ratio, buy {{{{sym_b}}}}",
                "updated_history": updated_history}

    if z_score < -z_entry:
        return {"action": "BUY", "z_score": round(z_score, 2), "ratio": round(ratio, 4),
                "current_price_a": current_price_a, "current_price_b": current_price_b,
                "reason": f"ratio too LOW (z={z_score:.2f}) -> long ratio, buy {{{{sym_a}}}}",
                "updated_history": updated_history}

    return {"action": "HOLD", "z_score": round(z_score, 2), "ratio": round(ratio, 4),
            "current_price_a": current_price_a, "current_price_b": current_price_b,
            "reason": f"z={z_score:.2f} within range",
            "updated_history": updated_history}

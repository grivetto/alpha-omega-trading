#!/usr/bin/env python3
"""Denaro v6 — pure indicator math. No state, no I/O, unit-testable.

All functions operate on raw OHLCV rows as consumed by ccxt:
[timestamp, open, high, low, close, volume] per row.
"""
from __future__ import annotations

from typing import List, Sequence, Tuple

OHLCV = List[List[float]]


def clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x into [lo, hi]."""
    return lo if x < lo else hi if x > hi else x


def true_ranges(closes: Sequence[float], highs: Sequence[float], lows: Sequence[float]) -> List[float]:
    """True Range series (Wilder-style, one value per bar from index 1)."""
    if len(closes) < 2:
        return []
    out: List[float] = []
    prev_close = closes[0]
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - prev_close),
                 abs(lows[i] - prev_close))
        out.append(tr)
        prev_close = closes[i]
    return out


def atr_percent(ohlcv: OHLCV, period: int = 14, default: float = 0.002) -> float:
    """ATR as % of last close. Returns `default` when data is insufficient."""
    if len(ohlcv) < 2:
        return default
    closes = [c[4] for c in ohlcv]
    highs = [c[2] for c in ohlcv]
    lows = [c[3] for c in ohlcv]
    trs = true_ranges(closes, highs, lows)
    if not trs:
        return default
    period = max(1, min(period, len(trs)))
    atr = sum(trs[-period:]) / period
    last = closes[-1]
    return atr / last if last > 0 else default


def momentum_percent(ohlcv: OHLCV, lookback: int = 1) -> float:
    """(close[-1] - close[-1-lookback]) / close[-1-lookback]."""
    if len(ohlcv) < lookback + 1:
        return 0.0
    cur = ohlcv[-1][4]
    prev = ohlcv[-1 - lookback][4]
    return (cur - prev) / prev if prev else 0.0


def volume_ratio(ohlcv: OHLCV, lookback: int = 24) -> float:
    """Last bar volume / average of the previous `lookback` bars."""
    if len(ohlcv) < 2:
        return 1.0
    last_vol = ohlcv[-1][5]
    window = ohlcv[-(lookback + 1):-1]
    if not window:
        return 1.0
    avg = sum(w[5] for w in window) / len(window)
    return last_vol / avg if avg > 0 else 1.0


def volatility_regime(atr_pct: float) -> str:
    if atr_pct < 0.005:
        return "low"
    if atr_pct < 0.015:
        return "normal"
    if atr_pct < 0.03:
        return "high"
    return "extreme"


def volume_regime(ratio: float) -> str:
    if ratio > 3.0:
        return "spike"
    if ratio > 1.5:
        return "high"
    if ratio < 0.3:
        return "low"
    return "normal"


def historical_var(prices: Sequence[float],
                   min_samples: int = 20) -> Tuple[float, float, float]:
    """Historical VaR from sampled price returns.

    Returns (var_95, var_99, cvar_95) as positive loss percentages.
    Falls back to conservative defaults when there is not enough data.
    """
    if len(prices) < min_samples:
        return 0.02, 0.035, 0.03
    step = max(1, len(prices) // 24)
    returns = [(prices[i] - prices[i - step]) / max(1e-10, prices[i - step])
               for i in range(step, len(prices), step)]
    if len(returns) < min_samples:
        return 0.02, 0.035, 0.03
    sorted_ret = sorted(returns)
    n = len(sorted_ret)
    i95 = int(n * 0.05)
    i99 = int(n * 0.01)
    var_95 = abs(sorted_ret[i95]) if sorted_ret[i95] < 0 else 0.02
    var_99 = abs(sorted_ret[i99]) if sorted_ret[i99] < 0 else 0.035
    tail = [r for r in sorted_ret if r <= sorted_ret[i95]]
    cvar_95 = abs(sum(tail) / len(tail)) if tail else 0.03
    return var_95, var_99, cvar_95

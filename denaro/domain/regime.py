#!/usr/bin/env python3
"""Denaro — domain regime filter (puro Python, zero I/O).

Filtro algoritmico di regime macro (requisito 3 ATLAS v6):
- ADX (Wilder, 14) → forza del trend
- ATR% (14) → volatilita' per spread dinamico e trailing TP
- EMA 200 pendenza + prezzo vs EMA 200 → direzione
- RSI (14) → conferma

Classificazione:
- RANGE-BOUND: ADX < adx_range_threshold (default 25) → griglia pura
- TREND:      ADX > adx_trend_threshold (default 30)
    - BEARISH: prezzo < EMA200 (falling knife → blocca i BUY)
    - BULLISH: prezzo > EMA200 (scalper direzionale a favore di trend)

Nota: ADX/ATR richiedono OHLCV reale. Il feeder ZeroMQ (mc2_feeder.py)
distribuisce candle standardizzate; in fallback si usa `from_prices` con
un ADX approssimato (documentato: non e' un sostituto dell'OHLCV reale).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

# soglie di regime (configurabili via RegimeParams)
ADX_RANGE_THRESHOLD = 25.0
ADX_TREND_THRESHOLD = 30.0
ATR_PERIOD = 14
ADX_PERIOD = 14
EMA200_PERIOD = 200
RSI_PERIOD = 14


@dataclass
class RegimeParams:
    adx_range_threshold: float = ADX_RANGE_THRESHOLD
    adx_trend_threshold: float = ADX_TREND_THRESHOLD
    atr_period: int = ATR_PERIOD
    adx_period: int = ADX_PERIOD
    ema200_period: int = EMA200_PERIOD
    rsi_period: int = RSI_PERIOD


@dataclass
class Regime:
    """Stato di regime calcolato per un symbol."""
    name: str                  # range | trend_bull | trend_bear
    adx: float
    atr_pct: float
    ema200: float
    price: float
    rsi: float
    ema200_slope: float        # >0 pendenza positiva
    signal_confidence: float   # 0..1

    @property
    def trending(self) -> bool:
        return self.name in ("trend_bull", "trend_bear")

    @property
    def bullish(self) -> bool:
        return self.name == "trend_bull"

    @property
    def bearish(self) -> bool:
        return self.name == "trend_bear"

    @property
    def range_bound(self) -> bool:
        return self.name == "range"


def _wilder_smooth(values: Sequence[float]) -> float:
    """Media di Wilder (EMA con alpha=1/period) sull'ultimo valore."""
    if not values:
        return 0.0
    return values[-1]


def _ema(values: Sequence[float], period: int) -> float:
    if not values:
        return 0.0
    multiplier = 2 / (period + 1)
    ema = values[0]
    for v in values[1:]:
        ema = (v - ema) * multiplier + ema
    return ema


def _ema_series(values: Sequence[float], period: int) -> List[float]:
    if not values:
        return []
    multiplier = 2 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append((v - out[-1]) * multiplier + out[-1])
    return out


def _rsi(closes: Sequence[float], period: int = 14) -> float:
    if len(closes) < period + 1:
        return 50.0
    gains = [max(closes[i] - closes[i - 1], 0) for i in range(1, len(closes))]
    losses = [max(closes[i - 1] - closes[i], 0) for i in range(1, len(closes))]
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def _true_ranges(highs: Sequence[float], lows: Sequence[float],
                 closes: Sequence[float]) -> List[float]:
    trs = []
    for i in range(1, len(closes)):
        hl = highs[i] - lows[i]
        hc = abs(highs[i] - closes[i - 1])
        lc = abs(lows[i] - closes[i - 1])
        trs.append(max(hl, hc, lc))
    return trs


def _adx(highs: Sequence[float], lows: Sequence[float],
         closes: Sequence[float], period: int = 14) -> float:
    """ADX di Wilder su OHLCV. 0.0 se dati insufficienti."""
    n = len(closes)
    if n < period * 2 + 1:
        return 0.0
    trs = _true_ranges(highs, lows, closes)
    plus_dm: List[float] = []
    minus_dm: List[float] = []
    for i in range(1, n):
        up = highs[i] - highs[i - 1]
        down = lows[i - 1] - lows[i]
        plus_dm.append(up if (up > down and up > 0) else 0.0)
        minus_dm.append(down if (down > up and down > 0) else 0.0)
    # smoothing Wilder (prima media = somma del primo periodo)
    tr14 = sum(trs[:period])
    pd14 = sum(plus_dm[:period])
    md14 = sum(minus_dm[:period])
    dx_values: List[float] = []
    for i in range(period, len(trs)):
        tr14 = tr14 - tr14 / period + trs[i]
        pd14 = pd14 - pd14 / period + plus_dm[i]
        md14 = md14 - md14 / period + minus_dm[i]
        pdi = 100 * pd14 / tr14 if tr14 > 0 else 0.0
        mdi = 100 * md14 / tr14 if tr14 > 0 else 0.0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) > 0 else 0.0
        dx_values.append(dx)
    if not dx_values:
        return 0.0
    # ADX = media di Wilder dei DX
    adx = dx_values[0]
    for dx in dx_values[1:]:
        adx = (adx * (period - 1) + dx) / period
    return adx


def _atr_pct(highs: Sequence[float], lows: Sequence[float],
             closes: Sequence[float], period: int = 14) -> float:
    trs = _true_ranges(highs, lows, closes)
    if len(trs) < period:
        return 0.0
    atr = sum(trs[-period:]) / period
    price = closes[-1]
    return atr / price if price > 0 else 0.0


class RegimeFilter:
    """Calcola il regime da OHLCV (o da prezzi in fallback)."""

    __slots__ = ("params",)

    def __init__(self, params: Optional[RegimeParams] = None) -> None:
        self.params = params or RegimeParams()

    # --- OHLCV reale ----------------------------------------------------------

    def classify(self, ohlcv: Sequence[Sequence[float]]) -> Regime:
        """Classifica il regime da candle [ts, open, high, low, close, volume]."""
        if len(ohlcv) < 30:
            return self._neutral(ohlcv[-1][4] if ohlcv else 0.0)
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        return self._classify_series(highs, lows, closes)

    # --- fallback da prezzi tick ----------------------------------------------

    def from_prices(self, prices: Sequence[float]) -> Regime:
        """Regime approssimato da soli prezzi (senza OHLCV): ADX stimato dalla
        dispersione dei rendimenti, ATR dal range tick. NON sostituisce OHLCV."""
        prices = list(prices)
        if len(prices) < 30:
            return self._neutral(prices[-1] if prices else 0.0)
        closes = prices
        # highs/lows approssimati: range locale di 5 tick attorno a ogni prezzo
        highs = [max(prices[max(0, i - 2):i + 3]) for i in range(len(prices))]
        lows = [min(prices[max(0, i - 2):i + 3]) for i in range(len(prices))]
        return self._classify_series(highs, lows, closes)

    # --- core -----------------------------------------------------------------

    def _classify_series(self, highs: List[float], lows: List[float],
                         closes: List[float]) -> Regime:
        p = self.params
        price = closes[-1]
        adx = _adx(highs, lows, closes, p.adx_period)
        atr_pct = _atr_pct(highs, lows, closes, p.atr_period)
        rsi = _rsi(closes, p.rsi_period)
        ema_series = _ema_series(closes, p.ema200_period)
        ema200 = ema_series[-1] if ema_series else price

        # pendenza EMA200: confronto con EMA200 calcolata N barre fa
        slope = 0.0
        if len(ema_series) > 10 and ema200 > 0:
            prev = ema_series[-11]
            slope = (ema200 - prev) / ema200

        if adx < p.adx_range_threshold:
            name = "range"
            confidence = max(0.0, 1 - adx / p.adx_range_threshold)
        elif price < ema200:
            name = "trend_bear"
            confidence = min(1.0, (adx - p.adx_trend_threshold) / 20 + 0.5)
        else:
            name = "trend_bull"
            confidence = min(1.0, (adx - p.adx_trend_threshold) / 20 + 0.5)

        return Regime(name=name, adx=round(adx, 2), atr_pct=atr_pct,
                      ema200=ema200, price=price, rsi=round(rsi, 1),
                      ema200_slope=slope, signal_confidence=round(confidence, 3))

    def _neutral(self, price: float) -> Regime:
        return Regime(name="range", adx=0.0, atr_pct=0.0, ema200=price,
                      price=price, rsi=50.0, ema200_slope=0.0,
                      signal_confidence=0.0)

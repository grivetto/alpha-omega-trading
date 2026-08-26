"""Test P1 — Hurst exponent: discrimina trend (H alto) da mean-reversion.

NB (onesta): l'R/S analysis sui LIVELLI di prezzo e' un estimatore rumoroso;
l'uso operativo e' RELATIVO (aggiustamento fine dello spread in regime range,
mai gate assoluto). Il test verifica la discriminazione trend vs reversione.
"""
import random

from denaro.domain.regime import RegimeFilter, hurst_exponent


def _trend_series(n=600):
    rng = random.Random(7)
    x = 100.0
    out = []
    for _ in range(n):
        x += 0.05 + rng.gauss(0, 0.1)
        out.append(x)
    return out


def _meanrev_series(n=600):
    rng = random.Random(13)
    x = 100.0
    out = []
    for i in range(n):
        x += (1.0 if (i // 3) % 2 == 0 else -1.0) * 1.0 + rng.gauss(0, 0.2)
        out.append(x)
    return out


def test_hurst_trend_high():
    assert hurst_exponent(_trend_series()) > 0.55


def test_hurst_meanrev_lower_than_trend():
    h_trend = hurst_exponent(_trend_series())
    h_rev = hurst_exponent(_meanrev_series())
    assert h_rev < h_trend  # discrimina: la reversione NON da' H da trend


def test_hurst_short_series_neutral():
    assert hurst_exponent([1.0, 2.0, 3.0]) == 0.5


def test_regime_has_hurst_field():
    r = RegimeFilter().from_prices(_meanrev_series())
    assert 0.0 <= r.hurst <= 1.0

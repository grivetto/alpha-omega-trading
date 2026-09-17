#!/usr/bin/env python3
"""Lo stop iniziale deve esistere dal FILL, non dal tick dopo (round 35).

Il backtest entra con lo stop a entry - stop_atr_mult*ATR (2 ATR) e poi lo alza
col trailing (2.5 ATR). Se al momento del fill il livello registrato fosse 0, il
primo trailing lo ancorerebbe a 2.5 ATR: rischio 25% piu' alto del misurato.
"""
from __future__ import annotations

from denaro.domain.trend import TrendParams, TrendPolicy

GIORNO = 86_400.0
BASE = 1_789_574_400.0


def _candele(n, ultimo_ts, base_h=100.0):
    out = []
    for i in range(n):
        ts = ultimo_ts - GIORNO * (n - 1 - i)
        h = base_h + i
        out.append([ts, h - 5.0, h, h - 6.0, h - 1.0, 1.0])
    return out


def _policy_con_atr():
    pol = TrendPolicy(TrendParams(canale=40, atr_period=14, trend_ema=100,
                                  trail_mult=2.5, stop_atr_mult=2.0))
    pol.precarica_barre(_candele(150, BASE - GIORNO), BASE + 3_600.0)
    assert pol.atr > 0
    return pol


def test_ripristino_con_stop_zero_ancora_allo_stop_iniziale():
    pol = _policy_con_atr()
    assert pol.ripristina_posizione(100.0, 0.0) is True
    atteso = 100.0 - 2.0 * pol.atr
    d = pol.decide(100.0, {}, {}, 1000.0, 1000.0, 1000.0, BASE + 4_000.0)
    assert abs(d.stop_price - pol.round_price(atteso)) < 1e-9, (
        d.stop_price, atteso)
    # NON deve essere il trailing a 2.5 ATR, che sarebbe piu' largo
    assert d.stop_price > 100.0 - 2.5 * pol.atr


def test_ripristino_con_stop_valido_non_lo_peggiora():
    pol = _policy_con_atr()
    stop_persistito = 100.0 - 1.5 * pol.atr      # piu' stretto del trailing
    assert pol.ripristina_posizione(100.0, stop_persistito) is True
    d = pol.decide(100.0, {}, {}, 1000.0, 1000.0, 1000.0, BASE + 4_000.0)
    assert abs(d.stop_price - pol.round_price(stop_persistito)) < 1e-9


def test_ripristino_con_stop_oltre_il_prezzo_lo_riancora():
    """Stop >= entry (dato incoerente) non deve lasciare la posizione scoperta."""
    pol = _policy_con_atr()
    assert pol.ripristina_posizione(100.0, 120.0) is True
    d = pol.decide(100.0, {}, {}, 1000.0, 1000.0, 1000.0, BASE + 4_000.0)
    assert 0 < d.stop_price < 100.0


def test_sell_target_e_lo_stop_iniziale():
    pol = _policy_con_atr()
    assert abs(pol.sell_target(100.0) - pol.round_price(100.0 - 2.0 * pol.atr)) < 1e-9
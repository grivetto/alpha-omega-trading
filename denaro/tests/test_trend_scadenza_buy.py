#!/usr/bin/env python3
"""Un ingresso del trend che non si riempie e' un segnale SCADUTO (round 40).

Al confine il limite e' 0.05% SOPRA il mercato: si riempie in secondi. Se resta
aperto, il prezzo e' scattato oltre il limite: tenerlo blocca ogni ingresso
futuro ("buy gia' in attesa") e puo' riempirsi giorni dopo, a un prezzo che non
e' piu' quello del segnale misurato.
"""
from __future__ import annotations

from denaro.domain.trend import SCADENZA_BUY_S, TrendParams, TrendPolicy

GIORNO = 86_400.0
BASE = 1_789_574_400.0


def _candele(n, ultimo_ts, base_h=100.0):
    out = []
    for i in range(n):
        ts = ultimo_ts - GIORNO * (n - 1 - i)
        h = base_h + i
        out.append([ts, h - 5.0, h, h - 6.0, h - 1.0, 1.0])
    return out


def _policy():
    pol = TrendPolicy(TrendParams(canale=40, atr_period=14, trend_ema=100))
    pol.precarica_barre(_candele(150, BASE - GIORNO), BASE + 3_600.0)
    return pol


def _decide(pol, open_buys, adesso):
    return pol.decide(100.0, open_buys, {}, 1000.0, 1000.0, 1000.0, adesso)


def test_buy_vecchio_viene_cancellato():
    pol = _policy()
    adesso = BASE + 4_000.0
    d = _decide(pol, {"x1": {"amount": 1.0, "price": 100.0,
                            "timestamp": adesso - SCADENZA_BUY_S - 1}}, adesso)
    assert d.to_cancel == ["x1"], d.to_cancel
    assert "scaduto" in d.reason


def test_buy_appena_piazzato_resta():
    pol = _policy()
    adesso = BASE + 4_000.0
    d = _decide(pol, {"x1": {"amount": 1.0, "price": 100.0,
                            "timestamp": adesso - 30.0}}, adesso)
    assert d.to_cancel == []
    assert "attesa" in d.reason


def test_buy_senza_timestamp_non_si_cancella():
    """Dato incompleto: non si cancella (meglio un blocco visibile che un ordine
    buono buttato via)."""
    pol = _policy()
    adesso = BASE + 4_000.0
    d = _decide(pol, {"x1": {"amount": 1.0, "price": 100.0}}, adesso)
    assert d.to_cancel == []


def test_cancellazione_non_tocca_la_posizione():
    """In posizione il ramo del buy aperto non si applica: nessun cancel."""
    pol = _policy()
    adesso = BASE + 4_000.0
    pol.ripristina_posizione(100.0, 96.0)
    d = _decide(pol, {"x1": {"amount": 1.0, "price": 100.0,
                            "timestamp": adesso - SCADENZA_BUY_S - 1}}, adesso)
    assert d.to_cancel == []
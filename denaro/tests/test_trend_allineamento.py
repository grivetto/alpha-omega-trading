#!/usr/bin/env python3
"""Allineamento delle barre live a quelle del backtest (2026-09-17).

Gli exchange non allineano le candele giornaliere a mezzanotte UTC: OKX le
allinea alle 16:00 UTC (mezzanotte UTC+8). Misurato su eea.okx.com il
2026-09-17: ts % 86400 == 57600. Ogni candela dei CSV di ricerca
(backtest_data/dl_*_1D.csv) ha quel confine, quindi le barre che la policy
costruisce dai tick devono chiudersi sullo STESSO confine: altrimenti il live
valuta un canale sfasato di una barra rispetto alla strategia misurata.
"""
from __future__ import annotations

from denaro.domain.trend import TrendParams, TrendPolicy

BASE = 1_789_574_400.0          # 2026-09-16T16:00 UTC: inizio periodo OKX
MEZZANOTTE_UTC = 1_789_603_200.0  # 2026-09-17T00:00 UTC
GIORNO = 86_400.0


def _candele(n, ultimo_ts, base_h=100.0):
    """n candele consecutive che chiudono su ultimo_ts, con high crescenti."""
    out = []
    for i in range(n):
        ts = ultimo_ts - GIORNO * (n - 1 - i)
        h = base_h + i
        out.append([ts, h - 5.0, h, h - 6.0, h - 1.0, 1.0])
    return out


def _policy(canale=40, **kw):
    return TrendPolicy(TrendParams(canale=canale, atr_period=14, trend_ema=100,
                                   **kw))


def test_offset_okx_ricavato_dalle_candele():
    """Le candele OKX arrivano a 16:00 UTC: la policy deve adottare quel confine."""
    pol = _policy()
    n = pol.precarica_barre(_candele(60, BASE - GIORNO), BASE + 3_600.0)
    assert n == 60
    assert pol.params.offset_barre_s == 57_600.0, pol.params.offset_barre_s


def test_barra_dei_tick_si_chiude_alle_16_utc():
    """Il cambio di barra avviene alle 16:00 UTC, non a mezzanotte UTC."""
    pol = _policy()
    pol.precarica_barre(_candele(60, BASE - GIORNO), BASE + 3_600.0)
    assert pol._aggiorna(105.0, BASE + 3_600.0) is False
    assert pol._aggiorna(106.0, BASE + GIORNO - 1.0) is False, (
        "la barra non deve chiudersi prima delle 16:00 UTC")
    assert pol._aggiorna(107.0, BASE + GIORNO) is True
    ultima = list(pol.barre)[-1]
    # la barra appena chiusa e' quella INIZIATA a BASE (16:00 UTC) e finita
    # alle 16:00 UTC del giorno dopo: il suo ts e' l'inizio del periodo
    assert ultima["ts"] == BASE
    # la chiusura della barra e' l'ultimo tick visto PRIMA del confine
    assert ultima["c"] == 106.0


def test_canale_identico_a_quello_del_backtest():
    """Dopo la chiusura della barra il canale e' quello delle candele di ricerca.

    Il canale e' il massimo degli high delle N barre PRIMA dell'ultima chiusa:
    con le candele iniettate (ferme a BASE-GIORNO) piu' la barra dei tick, deve
    valere esattamente il massimo delle ultime 40 candele iniettate.
    """
    pol = _policy()
    candele = _candele(60, BASE - GIORNO)
    pol.precarica_barre(candele, BASE + 3_600.0)
    pol._aggiorna(106.0, BASE + GIORNO - 1.0)
    assert pol._aggiorna(107.0, BASE + GIORNO) is True
    pol._aggiorna_indicatori()
    atteso = max(c[2] for c in candele[-40:])
    assert pol.donchian == atteso, (pol.donchian, atteso)


def test_candele_gia_a_mezzanotte_utc_restano_invariante():
    """Griglia allineata a UTC (o dati storici): nessuno spostamento introdotto."""
    pol = _policy()
    n = pol.precarica_barre(_candele(60, MEZZANOTTE_UTC), MEZZANOTTE_UTC + GIORNO + 60.0)
    assert n == 60
    assert pol.params.offset_barre_s == 0.0
    assert pol._aggiorna(50.0, MEZZANOTTE_UTC + GIORNO + 3_600.0) is False
    assert pol._aggiorna(51.0, MEZZANOTTE_UTC + 2 * GIORNO) is True


def test_offset_esplicito_accettato_dal_costruttore():
    """Il confine si puo' forzare (exchange diversi) e resta nel periodo."""
    p = TrendParams(periodo_barre_s=4 * 3_600.0, offset_barre_s=57_600.0)
    assert p.offset_barre_s == 0.0          # 57600 % 14400
    p2 = TrendParams(offset_barre_s=57_600.0)
    assert p2.offset_barre_s == 57_600.0

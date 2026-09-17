#!/usr/bin/env python3
"""Test del rig di ricerca: le quattro cose che rendono onesta una misura.

Contesto: il laboratorio precedente produceva conclusioni inutilizzabili per
quattro difetti misurati il 2026-09-17 (look-ahead, drawdown sbagliato,
sharpe su equity oraria costante a tratti, walk-forward in fallback
silenzioso). Questi test bloccano il ritorno di ciascuno.
"""
from __future__ import annotations

import math

import pytest

from denaro.research import eval as E


def _barre(valori, inizio_ts=0, passo=3_600_000):
    """Costruisce candele piatte (o= h= l= c= v) da una lista di prezzi."""
    return [{"ts": inizio_ts + i * passo, "o": p, "h": p, "l": p, "c": p, "v": 1000.0}
            for i, p in enumerate(valori)]


# ── 1. look-ahead: nessun round trip nella stessa barra ─────────────────────

def test_nessun_round_trip_nella_stessa_barra():
    """Un buy e il suo sell NON possono chiudersi nella stessa candela.

    Il difetto: si usava il low della barra per riempire il buy e l'high della
    STESSA barra per riempire il sell. Ogni candela con range maggiore di
    buy_distance+profit_target produceva un ciclo completo garantito: bastava
    quello per gonfiare un grid a +400% in due anni.
    """
    base = _barre([100.0] * 25)
    # ultima barra con range enorme: low tocca il buy (99), high supera il sell (99.99)
    base.append({"ts": 25 * 3_600_000, "o": 100.0, "h": 105.0, "l": 95.0,
                 "c": 100.0, "v": 1000.0})
    r = E.backtest_grid(base, {"strategy": "grid", "levels": 1,
                               "buy_distance": 0.01, "profit_target": 0.01,
                               "level_step": 0.005}, capitale=100.0, fee=0.001)
    assert r.trade == 0, (
        "round trip completato nella stessa barra (%d): look-ahead" % r.trade)


def test_il_sell_nasce_dopo_la_barra_del_fill():
    """Se il prezzo resta al target nella barra successiva, il sell si chiude."""
    base = _barre([100.0] * 25)
    base.append({"ts": 25 * 3_600_000, "o": 100.0, "h": 100.0, "l": 95.0,
                 "c": 99.0, "v": 1000.0})          # buy riempito, sell a 99.99 no
    base.append({"ts": 26 * 3_600_000, "o": 99.0, "h": 100.5, "l": 99.0,
                 "c": 100.5, "v": 1000.0})         # ora il sell puo' chiudersi
    r = E.backtest_grid(base, {"strategy": "grid", "levels": 1,
                               "buy_distance": 0.01, "profit_target": 0.01,
                               "level_step": 0.005}, capitale=100.0, fee=0.001)
    assert r.trade == 1, "atteso esattamente 1 round trip, ottenuti %d" % r.trade


# ── 2. drawdown sul picco CORRENTE ──────────────────────────────────────────

def test_max_dd_usa_il_picco_corrente():
    """[100,110,99,105,120] -> dd 10% (da 110 a 99), non 17.5%."""
    r = E.Risultato(nome="t", capitale=100.0)
    r.equity = [100.0, 110.0, 99.0, 105.0, 120.0]
    r.ts = [i * E.GIORNO_MS for i in range(5)]
    assert r.max_dd == pytest.approx(0.10, abs=1e-9)


def test_max_dd_zero_su_equity_crescente():
    r = E.Risultato(nome="t", capitale=100.0)
    r.equity = [100.0, 101.0, 105.0]
    r.ts = [i * E.GIORNO_MS for i in range(3)]
    assert r.max_dd == 0.0


# ── 3. sharpe sui rendimenti GIORNALIERI ────────────────────────────────────

def test_sharpe_e_giornaliero_non_orario():
    """Equity piatta a tratti: il vecchio sharpe orario esplodeva.

    Con equity identica su tutte le ore di un giorno, i rendimenti orari sono
    zeri esatti e mean/std degenera. Quello giornaliero resta finito.
    """
    eq, ts = [], []
    giorni = 40
    for g in range(giorni):
        for ora in range(24):
            eq.append(100.0 + g * 0.5)
            ts.append(g * E.GIORNO_MS + ora * 3_600_000)
    r = E.Risultato(nome="t", capitale=100.0)
    r.equity, r.ts = eq, ts
    assert len(r.rendimenti_giornalieri) == giorni - 1
    assert math.isfinite(r.sharpe)
    # crescita costante dello 0.5% al giorno su base 100 -> sharpe molto alto
    assert r.sharpe > 0


def test_sharpe_negativo_se_il_ritorno_e_negativo():
    r = E.Risultato(nome="t", capitale=100.0)
    r.equity = [100.0 - i * 0.2 for i in range(40)]
    r.ts = [i * E.GIORNO_MS for i in range(40)]
    assert r.ritorno < 0
    assert r.sharpe < 0


# ── 4. walk-forward: niente fallback silenzioso ─────────────────────────────

def test_walk_forward_rifiuta_i_dati_corti():
    """Con dati insufficienti lo DEVE dire, non restituire un backtest singolo.

    Il laboratorio precedente, sotto le 350 barre, tornava un backtest singolo
    senza segnalarlo: tutti i risultati in registry.json erano su ~200 barre
    presentati come walk-forward.
    """
    candele = _barre([100.0] * 100)
    fold, _, motivo = E.walk_forward(candele, "grid",
                                     [{"strategy": "grid", "levels": 2}],
                                     barre_train=1000, barre_test=500)
    assert fold == []
    assert "INSUFFICIENT" in motivo.upper()


def test_walk_forward_produce_fold_e_non_guarda_avanti():
    """Con dati a sufficienza i fold ci sono e i parametri sono congelati."""
    candele = _barre([100.0 + (i % 7) * 0.4 for i in range(3000)])
    griglia = [{"strategy": "grid", "levels": 2, "buy_distance": 0.01,
                "profit_target": 0.01, "level_step": 0.005},
               {"strategy": "grid", "levels": 3, "buy_distance": 0.02,
                "profit_target": 0.02, "level_step": 0.005}]
    fold, _, motivo = E.walk_forward(candele, "grid", griglia,
                                     barre_train=1000, barre_test=500)
    assert len(fold) >= 3, "pochi fold: %d (%s)" % (len(fold), motivo)
    for f in fold:
        assert f.test_da == f.train_a, "il test deve iniziare dove finisce il train"
        assert f.test_a > f.test_da


# ── 5. buy&hold di riferimento ──────────────────────────────────────────────

def test_buy_and_hold():
    c = _barre([100.0, 110.0, 120.0])
    assert E.buy_and_hold(c) == pytest.approx(0.20)
    assert E.buy_and_hold(c, 1) == pytest.approx(120.0 / 110.0 - 1.0)


# ── 6. il gate di robustezza non promuove rumore ────────────────────────────

def test_gate_richiede_fold_e_mediana_positiva():
    v = E.Valutazione(simbolo="X", motore="grid", barre_totali=1000, fold=[],
                      migliore_params={}, motivo="", ritorno_intero=0.5,
                      alpha_intero=0.5, dd_intero=0.1, sharpe_intero=1.0,
                      trade_intero=100, fee_su_lordo=0.0, esposizione=0.0)
    assert v.robusto is False, "senza fold non si promuove nulla"
    # 3 fold tutti positivi ma con pochi trade OOS -> ancora no
    v.fold = [E.Fold(i, 0, 100, 100, 200, 0.01, 0.01, 0.0, 2, 0.0) for i in range(3)]
    assert v.robusto is False, "meno di 30 trade OOS non basta"
    # abbastanza trade e 3/3 fold positivi -> promuovibile
    v.fold = [E.Fold(i, 0, 100, 100, 200, 0.01, 0.02, 0.0, 20, 0.0) for i in range(3)]
    assert v.robusto is True

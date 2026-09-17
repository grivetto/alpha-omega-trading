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

def test_gate_rifiuta_chi_perde_contro_il_buy_and_hold():
    """Fold positivi NON bastano: serve battere il semplice buy-and-hold.

    Caso reale (ETH-EUR 1H, 2026-09-17): 75% di fold positivi, mediana OOS
    +2.02%, ma alpha -2.50% e rendimento sull'intero periodo -13.87%. Il gate
    lo promuoveva: rumore con segno favorevole.
    """
    v = E.Valutazione(simbolo="ETH/EUR", motore="grid", barre_totali=1000,
                      fold=[], migliore_params={}, motivo="", ritorno_intero=-0.14,
                      alpha_intero=-0.14, dd_intero=0.61, sharpe_intero=0.14,
                      trade_intero=85, fee_su_lordo=10.5, esposizione=1.0)
    # 6 fold su 8 positivi, abbondanti trade OOS, ma il buy&hold fa meglio
    v.fold = [E.Fold(i, 0, 100, 100, 200, 0.01, 0.02, 0.0, 25, 0.045)
              for i in range(8)]
    assert v.fold_positivi >= 0.75
    assert v.mediana_oos > 0
    assert v.mediana_alpha < 0, "il buy&hold ha reso piu' della strategia"
    assert v.robusto is False


def test_gate_promuove_solo_con_alpha_positivo():
    v = E.Valutazione(simbolo="X", motore="grid", barre_totali=1000, fold=[],
                      migliore_params={}, motivo="", ritorno_intero=0.2,
                      alpha_intero=0.2, dd_intero=0.1, sharpe_intero=1.0,
                      trade_intero=100, fee_su_lordo=5.0, esposizione=1.0)
    v.fold = [E.Fold(i, 0, 100, 100, 200, 0.01, 0.02, 0.0, 25, 0.005)
              for i in range(8)]
    assert v.mediana_alpha > 0
    assert v.robusto is True

# ── 7. portafoglio: un solo set di parametri per piu' asset ─────────────────

def test_portafoglio_rifiuta_serie_corte():
    """Se un simbolo e' corto, il portafoglio lo deve dire."""
    serie = {"A/EUR": _barre([100.0] * 100),
             "B/EUR": _barre([100.0] * 50)}
    folds, _, motivo = E.walk_forward_portafoglio(serie, "trend",
                                                  [{"strategy": "trend"}],
                                                  barre_train=1000, barre_test=500)
    assert folds == []
    assert "insufficient" in motivo.lower()


def test_portafoglio_produce_fold_allineati():
    """Portafoglio a 3 asset: fold prodotti e test subito dopo il train."""
    serie = {}
    for k, base in (("A/EUR", 100.0), ("B/EUR", 50.0), ("C/EUR", 10.0)):
        # trend rialzista con crolli periodici: cosi' il trailing stop esce e
        # il breakout rientra piu' volte (una serie monotona fa UN solo trade
        # e il portafoglio scarterebbe il parametro per trade < 2).
        prezzi, p = [], base
        for i in range(2400):
            if i % 60 == 59:
                p *= 0.92
            elif i % 60 < 40:
                p *= 1.006
            else:
                p *= 0.998
            prezzi.append(p)
        serie[k] = _barre(prezzi)
    griglia = [{"strategy": "trend", "canale": 20, "atr_period": 14,
                "trail_mult": 3.0, "stop_atr_mult": 2.0, "trend_ema": 0,
                "risk_pct": 0.02, "max_exposure": 1.0}]
    folds, _, motivo = E.walk_forward_portafoglio(serie, "trend", griglia,
                                                  barre_train=800, barre_test=400)
    assert len(folds) >= 3, "pochi fold: %d (%s)" % (len(folds), motivo)
    for f in folds:
        assert f.test_da == f.train_a, "il test deve iniziare dove finisce il train"
        assert f.test_a > f.test_da


def test_metriche_oos_composte():
    """Il composto OOS e' il prodotto dei fold, non la somma."""
    v = E.Valutazione(simbolo="X", motore="trend", barre_totali=1000, fold=[],
                      migliore_params={}, motivo="", ritorno_intero=0.0,
                      alpha_intero=0.0, dd_intero=0.0, sharpe_intero=0.0,
                      trade_intero=0, fee_su_lordo=0.0, esposizione=0.0)
    v.fold = [E.Fold(0, 0, 100, 100, 200, 0.0, 0.10, 0.0, 5, 0.05),
              E.Fold(1, 0, 100, 100, 200, 0.0, 0.10, 0.0, 5, 0.05)]
    assert v.ritorno_oos_composto == pytest.approx(0.21)      # 1.1*1.1-1
    assert v.bh_oos_composto == pytest.approx(0.1025)         # 1.05*1.05-1
    assert v.alpha_oos_composto == pytest.approx(0.21 - 0.1025)
    assert v.peggior_fold == pytest.approx(0.10)

# ── 8. cross-sezionale: la scommessa relativa ───────────────────────────────

def test_xsec_rifiuta_pochi_simboli():
    serie = {"A/EUR": _barre([100.0] * 50), "B/EUR": _barre([100.0] * 50)}
    r = E.backtest_xsec(serie, {"lookback": 10, "k": 1, "rebalance": 5})
    assert r.errore, "con meno di 3 simboli il cross-sezionale non ha senso"


def test_xsec_seleziona_il_migliore():
    """Con un asset che sale e due che scendono, deve scegliere quello che sale."""
    serie = {}
    serie["SU/EUR"] = _barre([100.0 * (1.01 ** i) for i in range(400)])
    serie["GIU1/EUR"] = _barre([100.0 * (0.99 ** i) for i in range(400)])
    serie["GIU2/EUR"] = _barre([100.0 * (0.995 ** i) for i in range(400)])
    r = E.backtest_xsec(serie, {"lookback": 20, "k": 1, "rebalance": 10},
                        capitale=100.0, fee=0.002)
    assert not r.errore
    assert r.ritorno > 0, "doveva seguire l'asset in salita, ritorno %+.2f%%" % (100 * r.ritorno)
    assert r.esposizione_pct > 50.0, "doveva restare investito quasi sempre"


def test_xsec_filtro_di_mercato_manda_a_cash():
    """Con il filtro attivo e un paniere in discesa, l'equity resta piatta."""
    serie = {}
    for k in range(3):
        serie["A%d/EUR" % k] = _barre([100.0 * (0.99 ** i) for i in range(500)])
    senza = E.backtest_xsec(serie, {"lookback": 20, "k": 2, "rebalance": 10},
                            capitale=100.0, fee=0.002)
    con = E.backtest_xsec(serie, {"lookback": 20, "k": 2, "rebalance": 10,
                                  "cash_filter_ma": 100}, capitale=100.0, fee=0.002)
    assert senza.ritorno < 0, "senza filtro un paniere in discesa perde"
    assert con.ritorno > senza.ritorno, "il filtro doveva proteggere il capitale"


def test_xsec_nessuna_selezione_sul_futuro():
    """La classifica a barra i usa solo prezzi fino a i: niente look-ahead.

    Con il primo tratto piatto e poi un crollo solo dell'ultimo asset, la
    strategia non puo' averlo evitato PRIMA che accadesse.
    """
    piatto = _barre([100.0] * 200)
    crollo = _barre([100.0] * 199 + [50.0])
    serie = {"A/EUR": piatto, "B/EUR": piatto, "C/EUR": crollo}
    r = E.backtest_xsec(serie, {"lookback": 20, "k": 1, "rebalance": 10},
                        capitale=100.0, fee=0.0)
    # con fee zero e un solo crollo, il selezionatore non puo' prevederlo:
    # il rendimento non deve essere positivo solo per aver scartato C
    assert r.ritorno <= 0.0, "ha evitato il crollo prima che accadesse: look-ahead"

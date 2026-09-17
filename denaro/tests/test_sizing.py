#!/usr/bin/env python3
"""Regressione: il sizing riserva SEMPRE la fee.

Contesto (2026-09-17): momentum (SOL/EUR) e meanrev (XRP/EUR) hanno
dimensionato l'ordine sull'INTERO saldo; l'exchange ha rifiutato per la fee
(InsufficientFunds). La correzione era rimasta nel working tree, NON
committata, ed e' andata persa a un ripristino del repo. Da qui la regola:
una sola implementazione (denaro.domain.sizing) + questo test.

Questo file verifica l'invariante per TUTTE le strategie: se qualcuno
aggiunge una policy che dimentica la riserva, il test strutturale la becca
prima che arrivi in produzione con denaro vero.
"""
from __future__ import annotations

import pathlib
import re

import pytest

from denaro.domain.policy import Policy
from denaro.domain.sizing import FEE_BUFFER, size_amount

DOMAIN = pathlib.Path(__file__).resolve().parents[1] / "domain"


# --- l'helper -------------------------------------------------------------

def test_la_riserva_e_configurata():
    assert 0.0 < FEE_BUFFER <= 0.05, "riserva fee: piccola ma non nulla"
    assert Policy.FEE_BUFFER == FEE_BUFFER, "Policy deve usare la costante unica"


def test_size_amount_riserva_la_fee():
    # 100 EUR a prezzo 1 -> 99, MAI 100
    assert size_amount(100.0, 1.0, lambda a: a) == pytest.approx(99.0)
    assert size_amount(100.0, 1.0, lambda a: a) < 100.0


@pytest.mark.parametrize("budget,price", [
    (0.0, 1.0), (-5.0, 1.0), (100.0, 0.0), (100.0, -1.0), (100.0, None),
])
def test_size_amount_casi_limite(budget, price):
    assert size_amount(budget, price, lambda a: a) == 0.0


def test_size_amount_clampa_il_buffer():
    ident = lambda a: a
    assert size_amount(100.0, 1.0, ident, 0.25) == pytest.approx(75.0)
    # buffer assurdo: clamp al 50%, l'ordine non si azzera mai del tutto
    assert size_amount(100.0, 1.0, ident, 9.0) == pytest.approx(50.0)
    assert size_amount(100.0, 1.0, ident, -1.0) == pytest.approx(100.0)


# --- guardia strutturale su TUTTO il dominio ------------------------------

def test_nessun_sito_dimensiona_senza_riserva():
    """Una qty = budget/prezzo deve SEMPRE passare da size_amount."""
    budget = r"\b(available|per_level|notional|slice_eur|risk_capital|budget)"
    prezzo = r"(buy_price|price|entry|entry_price|px)\b"
    grezzo = re.compile(budget + r"\s*/\s*" + prezzo)
    colpevoli = []
    for f in sorted(DOMAIN.glob("*.py")):
        for n, riga in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            codice = riga.split("#")[0]
            if '"""' in codice or "def " in codice:
                continue
            if grezzo.search(codice) and "size_amount" not in codice:
                colpevoli.append("%s:%d %s" % (f.name, n, codice.strip()))
    assert not colpevoli, ("sizing senza riserva fee:\n  " + "\n  ".join(colpevoli))


# --- invariante funzionale: ogni policy con denaro vero -------------------

def _serie(da, a, passi):
    return [da + (a - da) * i / (passi - 1) for i in range(passi)]


def _decide(pol, price, saldo=100.0):
    return pol.decide(price=price, open_buys={}, open_sells={}, cash=saldo,
                      capital_config=saldo, free_balance=saldo, now=0.0)


def _controlla_ordini(nome, decisione, saldo=100.0):
    # Il qty viene arrotondato alla precisione dell'exchange: un tick di
    # overshoot e' fisiologico. Il 100% del saldo (il difetto vero) no.
    tetto = saldo * (1.0 - FEE_BUFFER + 1e-6)
    for lvl in decisione.to_place:
        assert lvl.notional <= tetto + 1e-9, (
            "%s: livello da %.4f EUR su %.2f disponibili (riserva fee ignorata)"
            % (nome, lvl.notional, saldo))
    return decisione.to_place


def test_momentum_non_usa_tutto_il_saldo():
    from denaro.domain.momentum import MomentumParams, MomentumPolicy
    p = MomentumPolicy(params=MomentumParams(min_history=5))
    for px in _serie(90.0, 120.0, 40):      # trend rialzista netto
        p.on_price(px)
    d = _decide(p, 121.0)
    ordini = _controlla_ordini("momentum", d)
    assert ordini, "momentum: nessun buy su un trend rialzista netto (%s)" % d.reason


def test_meanrev_non_usa_tutto_il_saldo():
    from denaro.domain.meanrev import MeanReversionParams, MeanReversionPolicy
    p = MeanReversionPolicy(params=MeanReversionParams(min_history=5))
    # discesa DOLCE: RSI va oversold ma il prezzo resta entro
    # max_dev_from_mean (5%), altrimenti la policy -- correttamente -- salta
    for px in _serie(100.0, 97.0, 30):
        p.on_price(px)
    d = _decide(p, 97.0)
    ordini = _controlla_ordini("meanrev", d)
    assert ordini, "meanrev: nessun buy su discesa netta (%s)" % d.reason


def test_adaptive_non_usa_tutto_il_saldo():
    from denaro.domain.adaptive import AdaptiveEngine, AdaptiveParams
    p = AdaptiveEngine(params=AdaptiveParams())
    for px in _serie(100.0, 100.9, 30):
        p.on_price(px)
    d = _decide(p, 101.0)
    _controlla_ordini("adaptive", d)
    assert d.to_place, "adaptive: nessun livello (%s)" % d.reason


def test_grid_non_usa_tutto_il_saldo():
    from denaro.domain.grid import GridParams, GridPolicy
    p = GridPolicy(GridParams(levels=3, buy_distance=0.01))
    d = _decide(p, 100.0)
    ordini = _controlla_ordini("grid", d)
    assert len(ordini) == 3, "grid: attesi 3 livelli, ottenuti %d" % len(ordini)


def test_mincapture_non_usa_tutto_il_saldo():
    from denaro.domain.mincapture_grid import MinCaptureConfig, MinCaptureGridPolicy
    p = MinCaptureGridPolicy(MinCaptureConfig(symbol="SOL/EUR", capital_eur=100.0, levels=4))
    for px in _serie(100.0, 100.0, 6):
        p.on_price(px)
    d = _decide(p, 100.0)
    _controlla_ordini("mincapture", d)

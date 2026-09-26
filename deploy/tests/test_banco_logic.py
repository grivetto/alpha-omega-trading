#!/usr/bin/env python3
"""Logica pura del banco a secco (deploy/banco/money_banco_secco.py).

Sono i casi che il progetto precedente ha sbagliato davvero: lo step_size con
`int(step)` -> 0, l'equity che ignora gli asset, la guardia che salta in
silenzio. Qui la logica e' provata senza rete e senza chiavi.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _modulo():
    spec = importlib.util.spec_from_file_location(
        "money_banco_secco", ROOT / "deploy" / "banco" / "money_banco_secco.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


@pytest.fixture()
def m():
    return _modulo()


def test_arrotonda_a_step_floor_e_non_int(m):
    """Il bug ccxt 4.x: int(0.001) == 0 -> qty sempre zero."""
    assert m.decimali_di_step(0.001) == 3
    assert m.arrotonda_a_step(1.23456, 0.001) == 1.234
    assert m.arrotonda_a_step(0.00007758, 0.00001) == 0.00007
    assert m.arrotonda_a_step(7.9, 1) == 7.0
    assert m.arrotonda_a_step(1.23456, 0.001) != 0.0, "int(step) darebbe 0"


def test_quantita_da_nozionale_caso_reale(m):
    """6.50075 EUR a 83784.2 EUR/BTC, step 1e-5: il caso vero del collaudo."""
    q = m.quantita_da_nozionale(6.50075, 83784.2, 0.00001)
    assert q == 0.00007
    assert m.quantita_da_nozionale(6.5, 0.0, 0.001) == 0.0
    assert m.quantita_da_nozionale(0.5, 80000.0, 0.00001) == 0.0, \
        "sotto lo step il capitale non fa un ordine: meglio zero che fantasia"


def test_guardia_pass_e_non_finanziato_con_i_tre_numeri(m):
    assert m.guardia_capitale(26.0030, 26.0030)["esito"] == "PASS"
    g = m.guardia_capitale(20.5, 26.0030)
    assert g["esito"] == "NON_FINANZIATO"
    assert "20.5000" in g["messaggio"]
    assert "26.0030" in g["messaggio"]
    assert "5.5030" in g["messaggio"]


def test_equity_include_gli_asset_e_non_arrotonda_a_zero(m):
    eq, det = m.calcola_equity({"EUR": 6.0, "SOL": 0.1},
                               lambda c: 200.0 if c == "SOL" else None)
    assert abs(eq - 26.0) < 1e-9, "6 EUR + 20 EUR di SOL = 26 EUR di equity"
    assert det["SOL"]["valore_eur"] == 20.0
    eq2, det2 = m.calcola_equity({"FOO": 1.0}, lambda c: None)
    assert eq2 == 0.0
    assert det2["FOO"]["prezzo_eur"] is None
    assert det2["FOO"]["nota"], "asset senza prezzo: nota esplicita, mai zero silenzioso"


def test_saldi_nonzero_usa_total(m):
    """`total` (free+used): i fondi impegnati in ordini aperti contano."""
    bilancio = {"info": {}, "timestamp": 1, "datetime": "x",
                "free": {"EUR": 5.0}, "used": {}, "total": {"EUR": 6.0},
                "EUR": {"free": 5.0, "used": 1.0, "total": 6.0},
                "BTC": {"free": 0.0, "used": 0.0, "total": 0.0}}
    assert m.saldi_nonzero(bilancio) == {"EUR": 6.0}


def test_ordine_dry_run_etichettato(m):
    o = m.costruisci_ordine("BTC/EUR", 0.00007, 83784.2, capitale=26.003,
                            frazione=0.25, pedaggio_pct=0.550,
                            tariffa_nome="okx_eea_spot")
    assert o["etichetta"] == "DRY-RUN, NON INVIATO"
    assert o["side"] == "buy"
    assert o["type"] == "market"
    assert o["nozionale_teorico_eur"] == 6.5008


def test_metrica_risponde_alle_domande_della_spec(m):
    """§6: dal solo log — girato? quanto valeva? guardia? ordine? pedaggio? quadra?"""
    riga = m.formatta_metrica(
        esito="PASS", equity_eur=26.003, equity_trading=0.0, equity_funding=26.003,
        capitale_dichiarato=26.003, nozionale_eur=6.5008, quantita=0.00007,
        symbol="BTC/EUR", pedaggio_pct=0.550, tariffa_nome="okx_eea_spot",
        chiave_perm="read_only", chiave_solo_lettura="si", ordini_aperti=0,
        riconciliazione_quadra="si", timestamp="2026-09-26T00:00:00Z")
    assert riga.startswith("METRICA ")
    for campo in ("banco_esito=PASS", "equity_trading_eur=0.0000",
                  "equity_funding_eur=26.0030", "capitale_dichiarato=26.0030",
                  "nozionale_eur=6.5008", "pedaggio_assunto_pct=0.550",
                  "tariffa=okx_eea_spot", "riconciliazione_quadra=si",
                  "chiave_solo_lettura=si", "timestamp=2026-09-26T00:00:00Z"):
        assert campo in riga, f"campo mancante nella metrica: {campo}"


def test_self_test_interno_del_modulo(m, capsys):
    assert m._self_test() == 0
    assert "SELF-TEST OK" in capsys.readouterr().out

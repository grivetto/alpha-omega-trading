"""Test deterministici per ``carry/carry_fase2.py`` (pianificatore carry F2).

REQ: REQ-20261002-234000-F2CARRY — spec ``docs/63_carry_fase2_impl_2026-10-03.md``.

Tutti gli attesi sono calcolati a mano (nessuna libreria di trading, nessuna
rete). Lo stile di caricamento del modulo segue ``tools/tests/test_fleet_integrity.py``:
il file viene caricato per percorso dal root del repo, senza dipendere da
``PYTHONPATH`` o da un ``__init__.py`` nella cartella ``carry/``.

Esecuzione::

    python -m pytest tools/tests/test_carry_fase2.py -q
"""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _carica_modulo():
    spec = importlib.util.spec_from_file_location("carry_fase2", ROOT / "carry" / "carry_fase2.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # serve a dataclasses (annotazioni differite)
    spec.loader.exec_module(mod)
    return mod


cf = _carica_modulo()


# --------------------------------------------------------------------------- #
# helper
# --------------------------------------------------------------------------- #
def _spec(base: str, ct_val: float, min_ct: float, spot_min: float):
    """Spec della tabella docs/20: ct_step = min_ct, spot_step = spot_min."""
    return cf.InstrumentSpec(
        base=base,
        ct_val=ct_val,
        min_ct=min_ct,
        ct_step=min_ct,
        spot_min=spot_min,
        spot_step=spot_min,
    )


def _spec_sintetica(base: str):
    """Spec neutra 1:1 per i test di capitale (ct_val=1, passo 1, spot .01)."""
    return cf.InstrumentSpec(base=base, ct_val=1.0, min_ct=1.0, ct_step=1.0, spot_min=0.01, spot_step=0.01)


def _stato(base: str, spot_qty: float, contratti: float, ct_val: float = 10.0):
    return cf.StatoCoppia(base=base, spot_qty=spot_qty, contratti=contratti, ct_val=ct_val)


# --------------------------------------------------------------------------- #
# 1. arrotondamenti per tipo (tabella docs/20, attesi a mano)
# --------------------------------------------------------------------------- #
def test_doge_11_contratti_110_doge():
    # DOGE ct_val=10, min 1, spot_min 10.
    # target 11,00 / (10 * 0,095) = 11,578... -> floor 11 ct -> spot 11*10 = 110.
    plan = cf.pianifica_coppia(_spec("DOGE", 10.0, 1.0, 10.0), 11.00, 0.095, 0.095)
    assert plan.operabile is True
    assert plan.contratti == 11.0
    assert plan.spot_qty == 110.0
    assert plan.delta_residuo == 0.0
    assert plan.nozionale_stimato == pytest.approx(10.45)
    assert plan.costo_spot == pytest.approx(10.45)
    assert plan.margine_stimato == pytest.approx(10.45)


def test_ada_floor_su_target_maggiore():
    # ADA ct_val=10, min 1, prezzo 0,20 -> valore contratto 2,00.
    # target 22,50 -> 11,25 ct -> floor 11 ct -> spot 110; costo 110*0,2 = 22,00.
    plan = cf.pianifica_coppia(_spec("ADA", 10.0, 1.0, 10.0), 22.50, 0.20, 0.20)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (11.0, 110.0, 0.0)
    assert plan.nozionale_stimato == pytest.approx(22.00)
    assert plan.costo_spot == pytest.approx(22.00)


def test_dot_quantizzazione_intera():
    # DOT ct_val=1, min 1, prezzo 1,0: 11,9 ct -> floor 11 ct -> spot 11.
    plan = cf.pianifica_coppia(_spec("DOT", 1.0, 1.0, 1.0), 11.9, 1.0, 1.0)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (11.0, 11.0, 0.0)
    assert plan.costo_spot == pytest.approx(11.0)


def test_link_step_spot_fine():
    # LINK ct_val=1, min 1, spot_step 0,1: 11,55 -> 11 ct -> 11,0 spot.
    plan = cf.pianifica_coppia(_spec("LINK", 1.0, 1.0, 0.1), 11.55, 1.0, 1.0)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (11.0, 11.0, 0.0)


def test_xrp_quantizzazione_intera():
    # XRP ct_val=1, min 1: 12,7 -> 12 ct -> 12 spot.
    plan = cf.pianifica_coppia(_spec("XRP", 1.0, 1.0, 1.0), 12.7, 1.0, 1.0)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (12.0, 12.0, 0.0)


def test_avax_contratti_frazionari():
    # AVAX ct_val=10, min 0,1, ct_step 0,1, prezzo 20:
    # 100 / (10*20) = 0,5 ct -> 0,5 ct -> spot 0,5*10 = 5,0.
    plan = cf.pianifica_coppia(_spec("AVAX", 10.0, 0.1, 0.1), 100.0, 20.0, 20.0)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (0.5, 5.0, 0.0)
    assert plan.margine_stimato == pytest.approx(100.0)


def test_ltc_contratti_frazionari_e_step_spot():
    # LTC ct_val=0,1, min 1, prezzo 90 -> valore contratto 9,00.
    # 100 / 9 = 11,111... -> floor 11 ct -> spot 11*0,1 = 1,1 (step 0,01) -> 1,1.
    plan = cf.pianifica_coppia(_spec("LTC", 0.1, 1.0, 0.01), 100.0, 90.0, 90.0)
    assert (plan.contratti, plan.spot_qty, plan.delta_residuo) == (11.0, 1.1, 0.0)
    assert plan.nozionale_stimato == pytest.approx(99.0)
    assert plan.costo_spot == pytest.approx(99.0)


def test_floor_contratti_mai_sopra_nozionale():
    # 10,999 contratti teorici -> floor 10 (il piano non supera il target).
    plan = cf.pianifica_coppia(_spec("X", 1.0, 1.0, 0.01), 10.999, 1.0, 1.0)
    assert plan.contratti == 10.0
    assert plan.nozionale_stimato == pytest.approx(10.0)
    assert plan.nozionale_stimato <= 10.999


def test_spot_arrotondato_per_eccesso_delta_non_negativo():
    # ct_val 1,05 (non multiplo di spot_step 0,1): 3,5/1,05 -> 3 ct;
    # spot_raw 3,15 -> ceil 0,1 = 3,20 -> delta 0,05 >= 0.
    plan = cf.pianifica_coppia(_spec("X", 1.05, 1.0, 0.1), 3.5, 1.0, 1.0)
    assert plan.contratti == 3.0
    assert plan.spot_qty == pytest.approx(3.2)
    assert plan.delta_residuo == pytest.approx(0.05)
    assert plan.delta_residuo >= 0.0


# --------------------------------------------------------------------------- #
# 2. rifiuti (sizing / budget / input) — mai clampati
# --------------------------------------------------------------------------- #
def test_sotto_minimo_strumento_rifiutata():
    # DOT min 1 ct, prezzo 1000, target 1 -> 0,001 ct -> floor 0 < 1.
    plan = cf.pianifica_coppia(_spec("DOT", 1.0, 1.0, 1.0), 1.0, 1000.0, 1000.0)
    assert plan.operabile is False
    assert "sotto minimo strumento" in plan.motivo
    assert (plan.contratti, plan.spot_qty) == (0.0, 0.0)
    assert (plan.costo_spot, plan.margine_stimato, plan.delta_residuo) == (0.0, 0.0, 0.0)


def test_delta_oltre_tolleranza_rifiutata():
    # spot_step 10 molto piu' grosso di ct_val 1 -> delta 10 > 1 ct: rifiuto.
    spec = cf.InstrumentSpec(base="X", ct_val=1.0, min_ct=1.0, ct_step=1.0, spot_min=10.0, spot_step=10.0)
    plan = cf.pianifica_coppia(spec, 11.0, 1.0, 1.0)
    assert plan.operabile is False
    assert "delta oltre tolleranza" in plan.motivo


def test_costo_oltre_budget_rifiutata_senza_clamp():
    # DOGE: commit atteso 10,45 + 10,45 = 20,90.
    spec = _spec("DOGE", 10.0, 1.0, 10.0)
    ko = cf.pianifica_coppia(spec, 11.00, 0.095, 0.095, capitale_disponibile=20.0)
    assert ko.operabile is False
    assert "costo oltre capitale" in ko.motivo
    assert ko.contratti == 0.0  # nessun taglio del nozionale per rientrare
    ok = cf.pianifica_coppia(spec, 11.00, 0.095, 0.095, capitale_disponibile=20.90)
    assert ok.operabile is True
    assert ok.contratti == 11.0


def test_step_contratti_violato():
    with pytest.raises(ValueError, match="ct_step violato"):
        cf.InstrumentSpec(base="X", ct_val=1.0, min_ct=2.0, ct_step=3.0, spot_min=1.0, spot_step=1.0)


def test_step_spot_violato():
    with pytest.raises(ValueError, match="spot_step violato"):
        cf.InstrumentSpec(base="X", ct_val=1.0, min_ct=1.0, ct_step=1.0, spot_min=0.3, spot_step=0.2)


@pytest.mark.parametrize("prezzo", [-1.0, 0.0, float("nan"), float("inf")])
def test_prezzo_non_valido_valueerror(prezzo):
    with pytest.raises(ValueError):
        cf.pianifica_coppia(_spec("DOGE", 10.0, 1.0, 10.0), 11.0, prezzo, 0.095)
    with pytest.raises(ValueError):
        cf.pianifica_coppia(_spec("DOGE", 10.0, 1.0, 10.0), 11.0, 0.095, prezzo)


@pytest.mark.parametrize("target", [-5.0, 0.0, float("nan")])
def test_target_non_valido_valueerror(target):
    with pytest.raises(ValueError):
        cf.pianifica_coppia(_spec("DOGE", 10.0, 1.0, 10.0), target, 0.095, 0.095)


def test_quantita_negative_valueerror():
    with pytest.raises(ValueError):
        cf.calcola_delta(-1.0, 11.0, 10.0)
    with pytest.raises(ValueError):
        cf.calcola_delta(110.0, -11.0, 10.0)
    with pytest.raises(ValueError):
        cf.StatoCoppia(base="DOGE", spot_qty=-1.0, contratti=1.0, ct_val=10.0)


def test_capitale_nullo_valueerror():
    specs = tuple(_spec_sintetica(b) for b in ("A", "B"))
    prezzi = {"A": (1.0, 1.0), "B": (1.0, 1.0)}
    with pytest.raises(ValueError, match="capitale_commit"):
        cf.pianifica_portafoglio(specs, 0.0, 100.0, prezzi)
    with pytest.raises(ValueError, match="capitale_commit"):
        cf.pianifica_portafoglio(specs, -100.0, 100.0, prezzi)


def test_prezzo_mancante_valueerror():
    specs = tuple(_spec_sintetica(b) for b in ("A", "B"))
    with pytest.raises(ValueError, match="manca il prezzo"):
        cf.pianifica_portafoglio(specs, 1000.0, 100.0, {"A": (1.0, 1.0)})


def test_spec_non_valida_valueerror():
    with pytest.raises(ValueError):
        cf.pianifica_coppia("non-una-spec", 100.0, 1.0, 1.0)


# --------------------------------------------------------------------------- #
# 3. delta e tolleranza
# --------------------------------------------------------------------------- #
def test_calcola_delta_esatto_zero():
    assert cf.calcola_delta(110.0, 11.0, 10.0) == 0.0
    assert cf.calcola_delta(0.0, 0.0, 10.0) == 0.0


@pytest.mark.parametrize(
    "delta,atteso",
    [
        (0.0, True),
        (10.0, True),  # bordo tolleranza (1 ct = 10 unita' base)
        (-10.0, True),  # bordo negativo
        (10.0001, False),
        (-10.0001, False),
    ],
)
def test_entro_tolleranza_bordo(delta, atteso):
    assert cf.entro_tolleranza(delta, 10.0, 1.0) is atteso


def test_entro_tolleranza_input_non_validi():
    with pytest.raises(ValueError):
        cf.entro_tolleranza(1.0, 0.0, 1.0)
    with pytest.raises(ValueError):
        cf.entro_tolleranza(1.0, 10.0, 0.0)


# --------------------------------------------------------------------------- #
# 4. riconciliazione
# --------------------------------------------------------------------------- #
def test_riconcilia_tutto_ok():
    atteso = _stato("DOGE", 110.0, 11.0)
    diffs = cf.riconcilia(atteso, _stato("DOGE", 110.0, 11.0))
    assert [d.campo for d in diffs] == ["spot", "contratti"]
    assert all(d.ok for d in diffs)
    assert all(d.delta == 0.0 for d in diffs)
    assert cf.verdetto_riconciliazione(diffs) == "ok"


def test_riconcilia_una_differenza():
    atteso = _stato("DOGE", 110.0, 11.0)
    diffs = cf.riconcilia(atteso, _stato("DOGE", 110.0, 9.0))
    spot, perp = diffs
    assert spot.ok is True and spot.delta == 0.0
    assert perp.ok is False and perp.delta == -2.0  # -2 ct > tolleranza 1 ct
    assert cf.verdetto_riconciliazione(diffs) == "ko"


def test_riconcilia_fill_parziale():
    atteso = _stato("DOGE", 110.0, 11.0)
    diffs = cf.riconcilia(atteso, _stato("DOGE", 55.0, 5.0))
    assert [d.delta for d in diffs] == [-55.0, -6.0]
    assert all(d.ok is False for d in diffs)
    assert cf.verdetto_riconciliazione(diffs) == "ko"


def test_riconcilia_al_bordo_tolleranza():
    # spot -10 (= 1 ct) e perp -1 ct: entrambi al bordo -> ok.
    diffs = cf.riconcilia(_stato("DOGE", 110.0, 11.0), _stato("DOGE", 100.0, 10.0))
    assert [d.delta for d in diffs] == [-10.0, -1.0]
    assert all(d.ok for d in diffs)
    assert cf.verdetto_riconciliazione(diffs) == "ok"


def test_riconcilia_base_diversa_valueerror():
    with pytest.raises(ValueError, match="base diversa"):
        cf.riconcilia(_stato("DOGE", 110.0, 11.0), _stato("ADA", 110.0, 11.0))


# --------------------------------------------------------------------------- #
# 5. portafoglio multi-coppia
# --------------------------------------------------------------------------- #
def _portafoglio_4():
    ordinate = tuple(_spec_sintetica(b) for b in ("DOT", "DOGE", "ADA", "LINK"))
    prezzi = {b: (1.0, 1.0) for b in ("DOT", "DOGE", "ADA", "LINK")}
    return ordinate, prezzi


def test_portafoglio_850_tutte_le_coppie():
    ordinate, prezzi = _portafoglio_4()
    pf = cf.pianifica_portafoglio(ordinate, 850.0, 100.0, prezzi)
    # 4 coppie * (100 spot + 100 margine) = 800 <= 850.
    assert [p.base for p in pf.piani] == ["DOT", "DOGE", "ADA", "LINK"]
    assert pf.scartate == ()
    assert pf.commit_totale == pytest.approx(800.0)
    assert pf.note == ()


def test_portafoglio_500_due_coppie_e_scartate():
    ordinate, prezzi = _portafoglio_4()
    pf = cf.pianifica_portafoglio(ordinate, 500.0, 100.0, prezzi)
    # 2 coppie * 200 = 400; la terza (200) non entra -> stop, 2 scartate.
    assert [p.base for p in pf.piani] == ["DOT", "DOGE"]
    assert [b for b, _ in pf.scartate] == ["ADA", "LINK"]
    assert "capitale insufficiente" in pf.scartate[0][1]
    assert "fermata in sequenza" in pf.scartate[1][1]
    assert pf.commit_totale == pytest.approx(400.0)
    assert any("stop in sequenza" in n for n in pf.note)


def test_portafoglio_target_scalare_o_mappa_equivalenti():
    ordinate, prezzi = _portafoglio_4()
    scalare = cf.pianifica_portafoglio(ordinate, 850.0, 100.0, prezzi)
    mappa = cf.pianifica_portafoglio(ordinate, 850.0, {b: 100.0 for b in ("DOT", "DOGE", "ADA", "LINK")}, prezzi)
    assert scalare == mappa


def test_portafoglio_target_mancante_valueerror():
    ordinate, prezzi = _portafoglio_4()
    with pytest.raises(ValueError, match="manca il target"):
        cf.pianifica_portafoglio(ordinate, 850.0, {"DOT": 100.0}, prezzi)


def test_portafoglio_prezzi_in_formato_mappa():
    ordinate, _ = _portafoglio_4()
    prezzi = {b: {"spot": 1.0, "perp": 1.0} for b in ("DOT", "DOGE", "ADA", "LINK")}
    pf = cf.pianifica_portafoglio(ordinate, 850.0, 100.0, prezzi)
    assert len(pf.piani) == 4


# --------------------------------------------------------------------------- #
# 6. chiusura
# --------------------------------------------------------------------------- #
def test_chiusura_completa_perp_prima_poi_spot():
    azioni = cf.pianifica_chiusura(_stato("DOGE", 110.0, 11.0))
    assert [(a.mercato, a.lato, a.quantita, a.reduce_only) for a in azioni] == [
        ("perp", "buy", 11.0, True),
        ("spot", "sell", 110.0, False),
    ]


def test_chiusura_stato_chiuso_piano_vuoto():
    assert cf.pianifica_chiusura(_stato("DOGE", 0.0, 0.0)) == []


def test_chiusura_spot_senza_perp_solo_sell():
    azioni = cf.pianifica_chiusura(_stato("DOGE", 50.0, 0.0))
    assert [(a.mercato, a.lato, a.quantita) for a in azioni] == [("spot", "sell", 50.0)]


def test_chiusura_perp_senza_spot_solo_reduce():
    azioni = cf.pianifica_chiusura(_stato("DOGE", 0.0, 7.0))
    assert [(a.mercato, a.lato, a.quantita, a.reduce_only) for a in azioni] == [("perp", "buy", 7.0, True)]


def test_chiusura_multipla_ordine_per_coppia():
    stati = [_stato("DOGE", 110.0, 11.0), _stato("ADA", 110.0, 11.0)]
    azioni = cf.pianifica_chiusura(stati)
    assert [(a.base, a.mercato) for a in azioni] == [
        ("DOGE", "perp"),
        ("DOGE", "spot"),
        ("ADA", "perp"),
        ("ADA", "spot"),
    ]


# --------------------------------------------------------------------------- #
# 7. riepilogo
# --------------------------------------------------------------------------- #
def test_riepilogo_portafoglio_totali():
    ordinate, prezzi = _portafoglio_4()
    pf = cf.pianifica_portafoglio(ordinate, 850.0, 100.0, prezzi)
    r = cf.riepilogo(pf)
    assert r["n_coppie"] == 4
    assert r["n_scartate"] == 0
    assert r["spot_totale"] == pytest.approx(400.0)
    assert r["margine_totale"] == pytest.approx(400.0)
    assert r["nozionale_totale"] == pytest.approx(400.0)
    assert r["delta_totale"] == pytest.approx(0.0)
    assert r["commit_totale"] == pytest.approx(800.0)


def test_riepilogo_da_stato():
    stato = cf.StatoCoppia(
        base="DOGE",
        spot_qty=110.0,
        contratti=11.0,
        ct_val=10.0,
        prezzo_spot=0.095,
        prezzo_perp=0.095,
    )
    r = cf.riepilogo(stato)
    assert r["n_coppie"] == 1
    assert r["spot_totale"] == pytest.approx(10.45)
    assert r["margine_totale"] == pytest.approx(10.45)
    assert r["nozionale_totale"] == pytest.approx(10.45)
    assert r["delta_totale"] == pytest.approx(0.0)


def test_riepilogo_tipo_non_valido_valueerror():
    with pytest.raises(ValueError, match="riepilogo"):
        cf.riepilogo(42)


# --------------------------------------------------------------------------- #
# 8. determinismo, proprieta' e purezza
# --------------------------------------------------------------------------- #
def test_determinismo_due_run_identici():
    ordinate, prezzi = _portafoglio_4()
    run1 = cf.pianifica_portafoglio(ordinate, 500.0, 100.0, prezzi)
    run2 = cf.pianifica_portafoglio(ordinate, 500.0, 100.0, prezzi)
    assert run1 == run2
    assert cf.riepilogo(run1) == cf.riepilogo(run2)


def test_griglia_mai_output_negativi_o_non_finiti():
    specs = [
        _spec("DOGE", 10.0, 1.0, 10.0),
        _spec("AVAX", 10.0, 0.1, 0.1),
        _spec("LTC", 0.1, 1.0, 0.01),
        _spec("DOT", 1.0, 1.0, 1.0),
    ]
    for spec in specs:
        for target in (0.5, 1.0, 7.3, 11.9, 50.0, 123.4):
            for prezzo in (0.01, 0.1, 1.0, 3.3, 90.0):
                plan = cf.pianifica_coppia(spec, target, prezzo, prezzo)
                for campo in (
                    "contratti",
                    "spot_qty",
                    "nozionale_stimato",
                    "costo_spot",
                    "margine_stimato",
                    "delta_residuo",
                ):
                    valore = getattr(plan, campo)
                    assert math.isfinite(valore)
                    assert valore >= 0.0


def test_dataclass_frozen():
    plan = cf.pianifica_coppia(_spec("DOGE", 10.0, 1.0, 10.0), 11.00, 0.095, 0.095)
    with pytest.raises(dataclasses.FrozenInstanceError):
        plan.contratti = 999.0  # type: ignore[misc]


def test_modulo_puro_solo_stdlib_senza_rete():
    """Il sorgente importa solo stdlib consentita e non apre I/O/processi."""
    sorgente = (ROOT / "carry" / "carry_fase2.py").read_text(encoding="utf-8")
    albero = ast.parse(sorgente)
    consentiti = {"__future__", "collections", "math", "numbers", "dataclasses"}
    vietati = {"ccxt", "requests", "socket", "urllib", "http", "ssl", "subprocess", "asyncio"}
    importati = set()
    chiamate = set()
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.Import):
            importati.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module:
            importati.add(nodo.module.split(".")[0])
        elif isinstance(nodo, ast.Call) and isinstance(nodo.func, ast.Name):
            chiamate.add(nodo.func.id)
    assert not (importati & vietati), f"import vietati: {importati & vietati}"
    assert importati <= consentiti, f"import non previsti: {importati - consentiti}"
    assert not (chiamate & {"open", "eval", "exec", "compile"}), "I/O o eval nel modulo"

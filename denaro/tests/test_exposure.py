#!/usr/bin/env python3
"""Cap di esposizione di conto (docs/55, Q6).

Il difetto che questi test fissano: il cap del motore e' **per bot**, e con piu'
bot sullo stesso conto nessuno vede la somma. Questi test non descrivono un
difetto da correggere (a differenza di `test_rischi_capitale.py`): verificano che
il guardrail nuovo faccia esattamente cio' che dichiara.

La seconda parte copre il CABLAGGIO (difetto B): il registro era pronto
(`domain/exposure.py`) e `BotTask.exposure` era gia' previsto, ma NESSUNO lo
costruiva — il cap esisteva solo nei test. Qui si verifica che il nodo lo
inietti davvero, che il tick rifiuti il piazzamento oltre il cap e che
`commit`/`release` seguano fill e chiusura.

Niente `tempfile`: la sandbox scrive solo dentro il repo, quindi i file del nodo
finiscono sotto `.pytmp/pt-cap/`.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from denaro.application.config import NodeConfig
from denaro.application.orchestrator import BotConfig, BotTask
from denaro.denaro_node import NodeApp
from denaro.domain.exposure import AccountExposure
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.market_data import MarketDataHub
from denaro.tests.test_rischi_capitale import FakeExchange


def test_senza_cap_tutto_e_ammesso():
    """`cap <= 0` = nessun cap: il comportamento storico resta invariato."""
    e = AccountExposure(0.0)
    assert e.capped is False
    assert e.can_open("a", 999_999.0) is True
    assert e.headroom() == float("inf")


def test_il_bot_successivo_non_apre_oltre_il_cap():
    """E' la voce Q6: il cap e' sul TOTALE, non sul singolo bot."""
    e = AccountExposure(100.0)
    assert e.can_open("a", 60.0) is True
    e.commit("a", 60.0)
    # 60 + 60 = 120 > 100 -> il secondo bot non apre
    assert e.can_open("b", 60.0) is False
    # ma 40 sta dentro
    assert e.can_open("b", 40.0) is True
    e.commit("b", 40.0)
    assert e.total() == 100.0
    assert e.headroom() == 0.0
    # e il terzo, con il conto pieno, non apre nulla
    assert e.can_open("c", 0.01) is False


def test_pari_al_cap_e_ammesso():
    """Il confine: il cap e' un tetto, non un limite stretto."""
    e = AccountExposure(50.0)
    assert e.can_open("a", 50.0) is True


def test_lo_stesso_bot_sostituisce_il_suo_impegno_non_lo_somma():
    """Un bot che riapre sta dimensionando, non raddoppiando."""
    e = AccountExposure(100.0)
    e.commit("a", 80.0)
    assert e.can_open("a", 80.0) is True, (
        "un bot non deve bloccare se stesso per il proprio impegno precedente")
    assert e.total() == 80.0, "commit deve sostituire, non sommare"


def test_il_rilascio_liberaL_headroom_ed_e_idempotente():
    e = AccountExposure(100.0)
    e.commit("a", 70.0)
    e.commit("b", 30.0)
    assert e.can_open("c", 1.0) is False
    e.release("a")
    assert e.total() == 30.0
    assert e.can_open("c", 70.0) is True
    e.release("a")            # gia' rilasciato: non e' un errore
    e.release("mai-visto")    # mai registrato: non e' un errore
    assert e.total() == 30.0


def test_un_impegno_non_positivo_non_blocca_e_non_sporca():
    """Un notional 0 (nessun ordine da piazzare) non deve consumare cap."""
    e = AccountExposure(10.0)
    assert e.can_open("a", 0.0) is True
    e.commit("a", -5.0)
    assert e.total() == 0.0, "un impegno negativo e' un errore: si azzera"


def test_snapshot_e_serializzabile_per_health():
    import json
    e = AccountExposure(100.0)
    e.commit("bot-1", 42.5)
    s = e.snapshot()
    json.dumps(s)                      # non solleva: e' JSON-safe
    assert s["cap_notional"] == 100.0
    assert s["impegnato_totale"] == 42.5
    assert s["headroom"] == 57.5
    assert s["bot"] == {"bot-1": 42.5}


def test_senza_cap_lo_snapshot_non_inventa_un_headroom():
    e = AccountExposure(0.0)
    s = e.snapshot()
    assert s["headroom"] is None, (
        "senza cap non esiste un 'quanto resta': pubblicare un numero lo "
        "farebbe leggere come un limite reale")


# --- 2. il cablaggio nel nodo (difetto B) ------------------------------------
#
# Il difetto: `BotTask.exposure` esisteva ed era iniettabile, ma
# `denaro_node.py` non lo costruiva mai. Con il cap a 0 il comportamento resta
# quello storico (nessun registro); con il cap dichiarato, tutti i bot dello
# stesso conto condividono UN registro e vedono la somma.

# I file del nodo finiscono in una cartella NOSTRA sotto `.pytmp`, non dentro
# `--basetemp`: quella la possiede pytest (la ricrea a ogni sessione, con ACL
# proprietarie) e i file scritti li' dentro diventano inaccessibili quando la
# suite gira intera.
_ROOT = Path(__file__).resolve().parents[2]
_TMP = _ROOT / ".pytmp" / "dsh_esposizione"
PREZZI = {"ADA/EUR": 1.0, "SOL/EUR": 100.0, "XRP/EUR": 0.5}


class _RestFinto:
    """Client REST pubblico finto: al hub serve solo un `fetch_ticker`."""

    def fetch_ticker(self, symbol):
        return {"last": PREZZI[symbol]}


def _config_nodo(bots: list, cap_nodo: float = 0.0) -> dict:
    """Config del nodo PASSATA dallo schema Pydantic (non un dict a mano).

    E' il punto del test: `NodeConfig` scarta in silenzio le chiavi non
    dichiarate (bug F1). Se `exposure_cap_notional` non fosse nello schema, il
    cap sparirebbe qui e nessuno se ne accorgerebbe fino al conto reale.
    """
    raw = {
        "data_dir": str(_TMP),
        "overrides_file": str(_TMP / "nessun_override.json"),
        "bots": bots,
    }
    if cap_nodo:
        raw["exposure_cap_notional"] = cap_nodo
    return NodeConfig(**raw).to_dict()


def _nodo(bots: list, cap_nodo: float = 0.0) -> NodeApp:
    _TMP.mkdir(parents=True, exist_ok=True)
    hub = MarketDataHub(ex_rest=_RestFinto(), ex_pro=None, ws_enabled=False)
    return NodeApp(_config_nodo(bots, cap_nodo), hub=hub)


def _bot_cfg(symbol: str, prefix: str = "") -> dict:
    cfg = {"symbol": symbol, "mode": "paper", "capital": 100.0, "levels": 3,
           "tick_interval": 30}
    if prefix:
        cfg["env_prefix"] = prefix
    return cfg


def test_senza_cap_il_nodo_non_inietta_nulla():
    """Cap assente = nessun registro = comportamento storico invariato."""
    app = _nodo([_bot_cfg("ADA/EUR"), _bot_cfg("SOL/EUR")])
    bot = app.orchestrator.bots["paper:-:ADA/EUR"]
    assert bot.exposure is None, (
        "senza `exposure_cap_notional` il bot ha un registro: il cap verrebbe "
        "applicato a una flotta che non l'ha chiesto")


def test_il_nodo_condivide_un_registro_per_conto():
    """Bot dello stesso conto → STESSO registro (altrimenti nessuna somma)."""
    app = _nodo([_bot_cfg("ADA/EUR"), _bot_cfg("SOL/EUR")], cap_nodo=120.0)
    ada = app.orchestrator.bots["paper:-:ADA/EUR"]
    sol = app.orchestrator.bots["paper:-:SOL/EUR"]

    assert ada.exposure is not None and sol.exposure is not None
    assert ada.exposure is sol.exposure, (
        "due bot dello stesso conto hanno registri DIVERSI: la somma degli "
        "impegni — cioe' il cap — non esiste")
    assert ada.exposure.cap == pytest.approx(120.0)

    # il conto e' la somma: l'impegno di uno si vede dall'altro
    ada.exposure.commit("paper:-:ADA/EUR", 100.0)
    assert sol.exposure.can_open("paper:-:SOL/EUR", 100.0) is False
    assert sol.exposure.headroom() == pytest.approx(20.0)


def test_conti_diversi_restano_separati():
    """Prefisso env diverso = sub-account diverso: registri distinti."""
    app = _nodo([_bot_cfg("ADA/EUR"), _bot_cfg("XRP/EUR", prefix="ALT_")],
                cap_nodo=120.0)
    ada = app.orchestrator.bots["paper:-:ADA/EUR"]
    xrp = app.orchestrator.bots["paper:ALT_:XRP/EUR"]

    assert ada.exposure is not xrp.exposure, (
        "due sub-account diversi condividono il registro: un conto esaurirebbe "
        "il cap dell'altro")
    assert xrp.exposure.cap == pytest.approx(120.0), (
        "il cap di nodo deve valere anche per gli altri conti del nodo")


def test_un_cap_di_bot_piu_basso_vince_e_lo_dice():
    """Fra dichiarazioni in conflitto sullo stesso conto si sceglie il prudente."""
    bot_a = _bot_cfg("ADA/EUR")
    bot_a["exposure_cap_notional"] = 50.0
    bot_b = _bot_cfg("SOL/EUR")
    bot_b["exposure_cap_notional"] = 90.0
    app = _nodo([bot_a, bot_b], cap_nodo=120.0)
    reg = app.orchestrator.bots["paper:-:ADA/EUR"].exposure
    assert reg is app.orchestrator.bots["paper:-:SOL/EUR"].exposure
    assert reg.cap == pytest.approx(50.0), (
        "il cap piu' PERMISSIVO ha vinto: sarebbe un modo silenzioso di alzare "
        "il rischio di conto")


# --- 3. il tick usa il cap ---------------------------------------------------

class _JournalFinto:
    """Journal in memoria: nessun file, nessun fsync."""

    def __init__(self) -> None:
        self.righe: list = []

    def append(self, record: dict) -> None:
        self.righe.append(record)

    def eventi(self, nome: str) -> list:
        return [r for r in self.righe if r.get("event") == nome]


class _PolicyTrendLike(GridPolicy):
    """GridPolicy sul ramo a STOP MONITORATO: e' il ramo che, al fill, registra
    la posizione in `state.posizione_aperta`."""
    STOP_MONITORATO = True


def _bot(ex, capital: float = 30.0,
         bot_key: str = "paper:-:ADA/EUR", trend: bool = False) -> BotTask:
    """BotTask senza path di stato: nessuna I/O su disco."""
    cfg = BotConfig(symbol="ADA/EUR", capital=capital, levels=1, fee=0.0,
                    buy_distance=0.01, profit_target=0.015, bot_key=bot_key)
    policy = (_PolicyTrendLike(GridParams(levels=1)) if trend
              else GridPolicy(GridParams(levels=1)))
    return BotTask(cfg, ex, policy, RiskManager())


def test_il_tick_rifiuta_il_piazzamento_oltre_il_cap():
    """Il caso Q6: il conto e' pieno, il bot NON apre e lo dice in chiaro."""
    ex = FakeExchange(price=100.0, free_quote=30.0)
    bot = _bot(ex)
    bot.journal = _JournalFinto()
    reg = AccountExposure(5.0)          # il bot vorrebbe impegnare ~30
    bot.exposure = reg

    asyncio.run(bot.tick())

    assert ex.placed == [], (
        f"il bot ha piazzato {len(ex.placed)} ordini con un cap di 5 nozionale: "
        "il tetto di conto non e' stato applicato")
    assert "cap di esposizione di conto" in bot._last_error
    assert "headroom esaurito" in bot._last_error, (
        f"il motivo del rifiuto non e' leggibile in health: {bot._last_error!r}")
    eventi = bot.journal.eventi("exposure_cap_blocked")
    assert len(eventi) == 1, (
        f"nessun evento di journal dedicato al blocco (trovati {len(eventi)})")
    assert eventi[0]["cap"] == pytest.approx(5.0)
    assert eventi[0]["richiesto"] > 0


def test_sotto_il_cap_il_bot_piazza_e_impegna_il_nozionale_vero():
    """Il nozionale e' size x prezzo, non il capitale configurato."""
    ex = FakeExchange(price=100.0, free_quote=30.0)
    bot = _bot(ex)
    bot.exposure = AccountExposure(1000.0)

    asyncio.run(bot.tick())

    assert ex.placed, "controllo fallito: con cap ampio il bot non ha piazzato"
    atteso = sum(o["amount"] * o["price"] for o in ex.placed)
    assert bot.exposure.impegnato("paper:-:ADA/EUR") == pytest.approx(atteso), (
        "l'impegno registrato non corrisponde agli ordini piazzati: il cap "
        "misurerebbe qualcosa che non e' l'esposizione")


def test_commit_segue_il_fill_e_release_segue_la_chiusura():
    """Sul fill si impegna la posizione; da flat si rilascia l'impegno."""
    ex = FakeExchange(price=100.0, free_quote=30.0)
    ex.fetch_open_orders = lambda symbol: []      # l'ordine non e' piu' aperto
    ex.fetch_order = lambda oid, symbol: {
        "id": oid, "status": "closed", "amount": 0.1, "filled": 0.1,
        "price": 99.0}
    bot = _bot(ex, trend=True)
    reg = AccountExposure(1000.0)
    bot.exposure = reg
    # nessun nuovo ordine in questo tick: si misura SOLO il fill
    bot.trading_paused = True
    bot.state.open_buys["o1"] = {"amount": 0.1, "price": 99.0,
                                 "timestamp": 0.0, "level": 0}

    asyncio.run(bot.tick())

    pos = bot.state.posizione_aperta
    assert pos is not None, "controllo fallito: il fill non ha registrato posizione"
    assert reg.impegnato("paper:-:ADA/EUR") == pytest.approx(
        pos["amount"] * 100.0), (
        "dopo il fill il registro non riporta la posizione: il cap non vede "
        "l'esposizione vera")

    # ...la posizione si chiude: il bot e' FLAT (nessuna posizione, nessun ordine)
    bot.state.posizione_aperta = None
    bot.state.open_buys.clear()
    bot.state.open_sells.clear()
    asyncio.run(bot.tick())

    assert reg.impegnato("paper:-:ADA/EUR") == 0.0, (
        "un bot flat non ha rilasciato il suo impegno: il cap del conto "
        "resterebbe esaurito per sempre")
    assert reg.can_open("paper:-:ALTRO/EUR", 900.0) is True

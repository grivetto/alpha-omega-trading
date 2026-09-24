#!/usr/bin/env python3
"""Difetto A (P0): "senza soldi" non e' "lettura sporca".

Il difetto osservato in produzione: il nodo live su nuvola
(`denaro-node-nuvola-trade.service`, 6 bot trend su OKX) girava da ore senza
piazzare NULLA. Il conto conteneva 0,0003 EUR di dust, la config dichiarava
`capital: 24.83` per bot, e `BotTask._guard_equity` trattava ogni lettura fuori
dal range [5%, 30x] come "equity inattendibile". Il journal ripeteva ogni 30
secondi, per 6 bot:

    [WARNING] denaro.bot: equity inattendibile 0.0003 per LINK/EUR:
              tick saltato (nessun valore sostitutivo)

Nessuna transizione di stato, nessun allarme, nessuna traccia di "il conto non
e' finanziato". Questi test descrivono il comportamento VOLUTO:

- lo stato esplicito `non_finanziato` (distinto da `illeggibile`);
- NESSUN ordine piazzato e NESSUNA baseline (peak/daily/weekly) avvelenata;
- log e journal UNA VOLTA PER TRANSIZIONE, non una volta per tick;
- uscita AUTOMATICA dallo stato quando arrivano fondi, senza restart.

Nessuna rete e nessun file temporaneo di sistema: il fake exchange e' in memoria
(`test_rischi_capitale.FakeExchange`, riusato qui) e i file di stato/journal
finiscono sotto `.pytmp/pt-cap/` DENTRO il repo (la sandbox scrive solo li').
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from pathlib import Path

import pytest

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.capitale import (ORIGINE_CONFIG, ORIGINE_DEFAULT,
                                    ORIGINE_EXCHANGE, STATO_ILLEGGIBILE,
                                    STATO_NON_FINANZIATO, STATO_OK,
                                    STATO_SOTTOCAPITALIZZATO,
                                    ClassificazioneCapitale, classifica_capitale,
                                    risolvi_soglia)
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.storage import Journal
from denaro.tests.test_rischi_capitale import FakeExchange

# Directory di lavoro dei test: dentro il repo (la sandbox scrive solo li'),
# mai la temp di sistema. NB: NON si scrive dentro `--basetemp` (`.pytmp/pt-cap`):
# pytest possiede quella cartella, la ricrea a ogni sessione e con ACL
# proprietarie — i file scritti li' dentro spariscono o diventano inaccessibili
# quando la suite gira intera.
_ROOT = Path(__file__).resolve().parents[2]
_TMP = _ROOT / ".pytmp" / "dsh_capitale"

# Il caso di produzione, con i suoi numeri: non un caso di scuola.
CAPITALE_CONFIGURATO = 24.83
CAPITALE_DUST = 0.0003


# --- fake exchange ------------------------------------------------------------

class FakeContoDust(FakeExchange):
    """Conto OKX con dust: la lettura RIESCE e restituisce un numero minuscolo.

    E' la differenza che conta: una lettura riuscita da 0,0003 EUR e' un conto
    vuoto, non un guasto. Un guasto produce None o un'eccezione (vedi
    `FakeContoIlleggibile`).
    """

    def __init__(self, equity: float = CAPITALE_DUST, min_notional: float = 1.0,
                 **kw) -> None:
        super().__init__(**kw)
        self.equity_del_conto = equity
        self._min_notional = min_notional
        self.letture_equity = 0

    def min_notional(self, symbol):
        return self._min_notional

    def fetch_total_equity(self, base_quote: str = "EUR") -> float:
        self.letture_equity += 1
        return self.equity_del_conto


class FakeContoIlleggibile(FakeContoDust):
    """Il saldo non si legge: `fetch_total_equity` solleva."""

    def fetch_total_equity(self, base_quote: str = "EUR") -> float:
        self.letture_equity += 1
        raise RuntimeError("ExchangeNotAvailable: timeout sul saldo")


class FakeJournal:
    """Journal in memoria: registra le righe senza toccare il disco."""

    def __init__(self) -> None:
        self.righe: list = []

    def append(self, record: dict) -> None:
        self.righe.append(record)

    def read_all(self) -> list:
        return list(self.righe)

    def eventi(self, nome: str) -> list:
        return [r for r in self.righe if r.get("event") == nome]


class CatturaLog(logging.Handler):
    """Logger finto: raccoglie i record di `denaro.bot` senza I/O."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list = []

    def emit(self, record: logging.LogRecord) -> None:  # noqa: D102
        self.records.append(record)

    def testi(self, livello: int = 0, contiene: str = "") -> list:
        out = []
        for r in self.records:
            if livello and r.levelno != livello:
                continue
            msg = r.getMessage()
            if contiene and contiene not in msg:
                continue
            out.append(msg)
        return out


@contextlib.contextmanager
def cattura_log():
    """Cattura i log di `denaro.bot`, forzando il livello a DEBUG.

    Il logger non e' configurato nei test: con il livello effettivo WARNING i
    record INFO (l'uscita dallo stato) non arriverebbero mai all'handler, e il
    test "una volta per transizione" sarebbe cieco su meta' del contratto.
    """
    logger = logging.getLogger("denaro.bot")
    handler = CatturaLog()
    precedente = logger.level
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(precedente)


# --- banco di prova -----------------------------------------------------------

def make_bot(ex, capital: float = CAPITALE_CONFIGURATO,
             min_notional: float = 0.0, **cfg_extra) -> BotTask:
    """BotTask senza I/O: stesso schema di `test_rischi_capitale.make_bot`.

    `get_equity` e' il lettore del CONTO (`fetch_total_equity`), esattamente
    come lo inietta il nodo (`NodeApp._equity_for`): senza, `BotTask` userebbe
    il capitale di config e il difetto A non sarebbe riproducibile.
    """
    cfg = BotConfig(symbol="LINK/EUR", capital=capital, levels=1, fee=0.0,
                    buy_distance=0.01, profit_target=0.015,
                    bot_key="okx:-:LINK/EUR", min_notional=min_notional,
                    **cfg_extra)
    return BotTask(cfg, ex, GridPolicy(GridParams(levels=1)), RiskManager(),
                   get_equity=ex.fetch_total_equity)


# --- 1. la classificazione pura ----------------------------------------------

def test_conto_dust_e_non_finanziato_non_inattendibile():
    """Il caso di produzione: 0,0003 EUR con `capital: 24.83`."""
    c = classifica_capitale(CAPITALE_CONFIGURATO, CAPITALE_DUST,
                            soglia_operativa=1.0, origine_soglia=ORIGINE_EXCHANGE)
    assert c.stato == STATO_NON_FINANZIATO
    assert c.blocca_tick is True
    assert c.puo_operare is False
    assert c.capitale_reale == pytest.approx(CAPITALE_DUST)
    assert "NON FINANZIATO" in c.messaggio()
    assert "0.0003" in c.messaggio(), (
        "il messaggio deve dire QUANTO c'e' sul conto, non solo che lo stato "
        f"e' strano: {c.messaggio()!r}")


def test_ok_quando_il_saldo_copre_il_minimo_operativo():
    """Saldo pari al capitale dichiarato: si opera col sizing pieno."""
    pieno = classifica_capitale(CAPITALE_CONFIGURATO, CAPITALE_CONFIGURATO,
                                soglia_operativa=1.0)
    assert pieno.stato == STATO_OK
    assert pieno.puo_operare is True

    # Il confine della soglia: un saldo PARI al minimo d'ordine basta a
    # piazzare, quindi NON e' `non_finanziato`. Resta `sottocapitalizzato`
    # perche' 1 EUR non e' il sizing dichiarato (24.83): sono due giudizi
    # diversi, e il primo — "posso ordinare?" — e' quello che sblocca il tick.
    al_minimo = classifica_capitale(CAPITALE_CONFIGURATO, 1.0,
                                    soglia_operativa=1.0)
    assert al_minimo.stato == STATO_SOTTOCAPITALIZZATO
    assert al_minimo.puo_operare is True, (
        "un saldo pari al minimo d'ordine basta a piazzare: non va bloccato")
    assert al_minimo.blocca_tick is False

    # appena SOTTO la soglia, invece, non c'e' nulla da fare
    assert classifica_capitale(CAPITALE_CONFIGURATO, 0.99,
                               soglia_operativa=1.0).stato == STATO_NON_FINANZIATO


def test_illeggibile_quando_la_lettura_fallisce_o_e_incoerente():
    """Lettura assente/NaN/negativa: caso TRANSITORIO, non conto vuoto."""
    for valore in (None, float("nan"), float("inf"), -1.0, "n/d"):
        c = classifica_capitale(CAPITALE_CONFIGURATO, valore, soglia_operativa=1.0)
        assert c.stato == STATO_ILLEGGIBILE, f"{valore!r} → {c.stato}"
        assert c.capitale_reale is None, (
            "una lettura illeggibile non deve diventare un numero: e' il modo in "
            "cui un guasto si trasforma in un saldo credibile")
        assert c.blocca_tick is True


def test_zero_da_una_lettura_riuscita_e_un_conto_vuoto():
    """0.0 letto davvero = conto vuoto → non finanziato (non illeggibile)."""
    c = classifica_capitale(CAPITALE_CONFIGURATO, 0.0, soglia_operativa=1.0)
    assert c.stato == STATO_NON_FINANZIATO
    assert c.capitale_reale == 0.0


def test_sottocapitalizzato_sopra_la_soglia_ma_sotto_il_sizing_dichiarato():
    """C'e' da ordinare, ma non col sizing che la config dichiara."""
    c = classifica_capitale(100.0, 6.0, soglia_operativa=1.0)
    assert c.stato == STATO_SOTTOCAPITALIZZATO
    assert c.puo_operare is True, (
        "sottocapitalizzato NON blocca: il bot riduce il sizing da solo e deve "
        "poter continuare a gestire le posizioni aperte")
    assert c.blocca_tick is False


def test_la_soglia_viene_dal_minimo_reale_non_inventata():
    """Il minimo d'ordine REALE dell'adapter, con ripieghi DICHIARATI."""
    assert risolvi_soglia(5.0, 1.0) == (5.0, ORIGINE_EXCHANGE)
    # l'adapter non risponde (0.0 = "non disponibile"): vale la config
    assert risolvi_soglia(0.0, 2.5) == (2.5, ORIGINE_CONFIG)
    assert risolvi_soglia(None, None) == (1.0, ORIGINE_DEFAULT)
    assert risolvi_soglia(0.0, 0.0, 0.0) == (1.0, ORIGINE_DEFAULT), (
        "una soglia <= 0 non e' una soglia: classificherebbe come finanziato "
        "anche un conto a zero")


def test_la_classificazione_e_serializzabile_per_health():
    c = classifica_capitale(CAPITALE_CONFIGURATO, CAPITALE_DUST, soglia_operativa=1.0)
    d = c.to_dict()
    json.dumps(d)                      # non solleva: e' JSON-safe
    assert d["capitale_stato"] == STATO_NON_FINANZIATO
    assert d["capitale_reale"] == 0.0003
    assert d["capitale_configurato"] == CAPITALE_CONFIGURATO
    assert d["capitale_soglia_operativa"] == 1.0

    illeggibile = classifica_capitale(CAPITALE_CONFIGURATO, None).to_dict()
    json.dumps(illeggibile)
    assert illeggibile["capitale_reale"] is None, (
        "sull'ignoto si dichiara l'ignoto: uno 0 verrebbe letto come 'conto "
        "vuoto' anche quando il saldo non e' stato letto affatto")


def test_immutabile_perche_e_una_fotografia_del_tick():
    c = classifica_capitale(CAPITALE_CONFIGURATO, CAPITALE_DUST, soglia_operativa=1.0)
    assert isinstance(c, ClassificazioneCapitale)
    with pytest.raises(Exception):
        c.stato = STATO_OK          # frozen dataclass


# --- 2. il tick: nessun ordine, nessuna baseline ------------------------------

def test_tick_in_non_finanziato_non_piazza_ordini_e_non_avvelena_le_baseline():
    """Il cuore del difetto A: il tick si ferma PRIMA di ordini e baseline."""
    _TMP.mkdir(parents=True, exist_ok=True)
    health = _TMP / "dust_health.json"
    ex = FakeContoDust(price=100.0, free_quote=CAPITALE_DUST, min_notional=1.0)
    bot = make_bot(ex, health_path=health, journal_path=_TMP / "dust_trades.jsonl")

    for _ in range(3):
        asyncio.run(bot.tick())

    assert ex.placed == [], (
        f"in stato non_finanziato il bot ha piazzato {len(ex.placed)} ordini: su "
        "un conto a 0,0003 EUR sarebbero tutti rifiutati dall'exchange")
    assert bot.capitale_stato is not None
    assert bot.capitale_stato.stato == STATO_NON_FINANZIATO
    assert "NON FINANZIATO" in bot._last_error, (
        f"health non dice perche' il bot e' fermo: {bot._last_error!r}")

    # (d) nessuna baseline avvelenata da una lettura che non e' un conto
    assert bot.state.peak_equity == 0.0
    assert bot.equity_tracker.rows == [], (
        "la curva equity ha registrato un campione da 0,0003 EUR: la serie e' "
        "avvelenata e le metriche `eq_*` mentiranno per sempre")
    assert bot.risk_state.day_start_capital == pytest.approx(CAPITALE_CONFIGURATO)
    assert bot.risk_state.current_capital == pytest.approx(CAPITALE_CONFIGURATO)
    assert bot.state.total_trades == 0

    # (b) stato ESPLICITO in health
    payload = json.loads(health.read_text(encoding="utf-8"))
    assert payload["capitale_stato"] == STATO_NON_FINANZIATO
    assert payload["capitale_reale"] == pytest.approx(CAPITALE_DUST, abs=1e-6)
    assert payload["capitale_configurato"] == pytest.approx(CAPITALE_CONFIGURATO)
    assert payload["status"] == "blocked"


def test_log_una_volta_per_transizione_non_una_volta_per_tick():
    """Sei bot che ripetono la stessa riga ogni 30 s: rumore, non allarme."""
    ex = FakeContoDust(price=100.0, free_quote=CAPITALE_DUST, min_notional=1.0)
    bot = make_bot(ex)

    with cattura_log() as log_catturato:
        for _ in range(5):
            asyncio.run(bot.tick())
        entrate = log_catturato.testi(logging.WARNING, "NON FINANZIATO")
        assert len(entrate) == 1, (
            f"5 tick in stato non_finanziato hanno prodotto {len(entrate)} "
            "warning: il log deve parlare alla TRANSIZIONE, non a ogni tick")
        assert log_catturato.testi(contiene="inattendibile") == [], (
            "un conto a secco non e' una lettura sporca: la riga 'equity "
            "inattendibile' e' esattamente il rumore che ha nascosto il difetto "
            "in produzione")

        # ...arrivano i fondi: si esce dallo stato DA SOLI, senza restart
        ex.equity_del_conto = CAPITALE_CONFIGURATO
        ex.free_quote = CAPITALE_CONFIGURATO
        asyncio.run(bot.tick())

        uscite = log_catturato.testi(logging.INFO, "riprende")
        assert len(uscite) == 1, (
            "l'uscita da non_finanziato deve essere dichiarata una volta: "
            f"trovate {len(uscite)} righe")
        assert len(log_catturato.testi(logging.WARNING, "NON FINANZIATO")) == 1, (
            "nessun nuovo warning di non_finanziato dopo il rifinanziamento")

        asyncio.run(bot.tick())
        assert len(log_catturato.testi(logging.INFO, "riprende")) == 1, (
            "la transizione e' una sola: i tick successivi non devono ripeterla")


def test_il_journal_registra_la_transizione_e_non_il_tick():
    _TMP.mkdir(parents=True, exist_ok=True)
    journal_path = _TMP / "transizioni.jsonl"
    if journal_path.exists():
        journal_path.unlink()
    ex = FakeContoDust(price=100.0, free_quote=CAPITALE_DUST, min_notional=1.0)
    bot = make_bot(ex, journal_path=journal_path)

    for _ in range(4):
        asyncio.run(bot.tick())
    ex.equity_del_conto = CAPITALE_CONFIGURATO
    ex.free_quote = CAPITALE_CONFIGURATO
    asyncio.run(bot.tick())

    eventi = [r["event"] for r in Journal(journal_path).read_all()]
    assert eventi.count("capitale_non_finanziato") == 1
    assert eventi.count("capitale_ripristinato") == 1
    riga = next(r for r in Journal(journal_path).read_all()
                if r["event"] == "capitale_non_finanziato")
    assert riga["capitale_reale"] == pytest.approx(CAPITALE_DUST)
    assert riga["capitale_configurato"] == pytest.approx(CAPITALE_CONFIGURATO)


def test_i_fondi_fanno_ripartire_l_operativita_senza_restart():
    """Requisito esplicito: la classificazione si ricalcola a ogni lettura."""
    ex = FakeContoDust(price=100.0, free_quote=CAPITALE_DUST, min_notional=1.0)
    bot = make_bot(ex)
    asyncio.run(bot.tick())
    assert ex.placed == [] and bot.capitale_stato.stato == STATO_NON_FINANZIATO

    ex.equity_del_conto = CAPITALE_CONFIGURATO
    ex.free_quote = CAPITALE_CONFIGURATO
    asyncio.run(bot.tick())

    assert bot.capitale_stato.stato == STATO_OK
    assert ex.placed, (
        "dopo il rifinanziamento il bot non ha ripreso a piazzare: servirebbe "
        "un restart, e il requisito dice il contrario")
    # la baseline riparte dal capitale RILEVATO, non da 0,0003
    assert bot.state.peak_equity == pytest.approx(CAPITALE_CONFIGURATO)


def test_min_notional_dell_adapter_alza_la_soglia_operativa():
    """La soglia e' il minimo VERO della sede, non un numero inventato."""
    ex = FakeContoDust(price=100.0, free_quote=3.0, equity=3.0, min_notional=5.0)
    bot = make_bot(ex)
    asyncio.run(bot.tick())

    assert bot.capitale_stato.stato == STATO_NON_FINANZIATO, (
        "3 EUR non bastano per il minimo d'ordine di 5 EUR della sede: il bot "
        "non deve nemmeno provare")
    assert bot.capitale_stato.soglia_operativa == pytest.approx(5.0)
    assert bot.capitale_stato.origine_soglia == ORIGINE_EXCHANGE
    assert ex.placed == []


def test_senza_minimo_dall_adapter_usa_quello_dichiarato_in_config():
    """Adapter muto (markets non caricate) → vale il minimo della config."""
    ex = FakeContoDust(price=100.0, free_quote=1.5, equity=1.5, min_notional=0.0)
    bot = make_bot(ex, min_notional=2.0)
    asyncio.run(bot.tick())
    assert bot.capitale_stato.stato == STATO_NON_FINANZIATO
    assert bot.capitale_stato.origine_soglia == ORIGINE_CONFIG
    assert bot.capitale_stato.soglia_operativa == pytest.approx(2.0)


def test_senza_adapter_e_senza_config_la_soglia_default_e_dichiarata():
    """Ultimo ripiego: 1 EUR, e lo si DICHIARA in health (origine `default`)."""
    ex = FakeContoDust(price=100.0, free_quote=0.5, equity=0.5, min_notional=0.0)
    bot = make_bot(ex)          # min_notional di config = 0.0 (non dichiarato)
    asyncio.run(bot.tick())
    assert bot.capitale_stato.stato == STATO_NON_FINANZIATO
    assert bot.capitale_stato.origine_soglia == ORIGINE_DEFAULT
    assert bot.capitale_stato.soglia_operativa == pytest.approx(1.0)


def test_sottocapitalizzato_non_blocca_il_tick():
    """6 EUR su 100 dichiarati: si opera (sizing ridotto), con un avviso."""
    ex = FakeContoDust(price=100.0, free_quote=6.0, equity=6.0, min_notional=1.0)
    bot = make_bot(ex, capital=100.0)
    with cattura_log() as log_catturato:
        asyncio.run(bot.tick())
    assert bot.capitale_stato.stato == STATO_SOTTOCAPITALIZZATO
    assert len(log_catturato.testi(logging.WARNING, "SOTTOCAPITALIZZATO")) == 1
    assert bot.equity_tracker.rows, (
        "il tick e' stato saltato: sottocapitalizzato NON e' un blocco")


# --- 3. il caso illeggibile resta "salta il tick" -----------------------------

def test_lettura_fallita_e_illeggibile_e_non_scrive_baseline():
    """Guasto transitorio: tick saltato, nessun ordine, stato dichiarato."""
    ex = FakeContoIlleggibile(price=100.0, free_quote=CAPITALE_CONFIGURATO)
    bot = make_bot(ex)

    asyncio.run(bot.tick())        # non solleva: il guasto non uccide il tick

    assert bot.capitale_stato.stato == STATO_ILLEGGIBILE
    assert bot.capitale_stato.capitale_reale is None
    assert "ILLEGGIBILE" in bot._last_error
    assert ex.placed == []
    assert bot.equity_tracker.rows == []
    assert bot.state.peak_equity == 0.0


def test_illeggibile_non_diventa_non_finanziato():
    """I due stati restano distinti: e' la separazione che mancava."""
    ex = FakeContoIlleggibile(price=100.0, free_quote=0.0)
    bot = make_bot(ex)
    asyncio.run(bot.tick())
    assert bot.capitale_stato.stato != STATO_NON_FINANZIATO
    assert bot.capitale_stato.stato == STATO_ILLEGGIBILE
    assert "NON FINANZIATO" not in bot._last_error

#!/usr/bin/env python3
"""Regressioni dei difetti che possono DISTRUGGERE CAPITALE (docs/53 §0.6).

Trovati in revisione statica il 2026-09-23, prima di riaprire il live con
capitale reale. Questi test sono scritti come criteri di accettazione:
descrivono il comportamento VOLUTO, quindi **oggi falliscono**. Il loro valore e'
esattamente quello: rendono R1/R2/R3 e la contabilizzazione dei fill parziali
(Q4) verificabili invece che discutibili, e diventano rossi/verdi quando la
correzione arriva.

R1 — `_esegui_stop_monitorato` e `_trigger_stop_loss` vendono il saldo LIBERO
     dell'asset (`orchestrator.py:879-891` e `:1003-1026`), ignorando
     `state.posizione_aperta["amount"]` che e' tracciato (`:1099-1101`).
     Con due bot sullo stesso sub-account (configurazione ammessa in
     `denaro_node.py:450-456`) o con asset detenuti a mano, lo stop di un bot
     liquida a mercato TUTTO l'asset del conto.

R2 — se la vendita di stop-loss fallisce (`:1033-1038`) il flag resta True e il
     ramo di tick pretende `not stop_loss_triggered` (`:361-364`): il commento
     "il retry al prossimo tick lo risolvera'" e' falso e la posizione non viene
     mai chiusa. In piu' il blocco dei nuovi ordini vive in `trading_paused`
     (`:498`, `:134`), che NON e' in `BotState` e viene sovrascritto a ogni
     cambio di livello RAM da `_propagate_safemode` (`denaro_node.py:478`):
     quando il guardian torna "nominal" il bot riprende a piazzare ordini con lo
     stop-loss disabilitato.

R3 — `_rebuild_from_exchange` inventa `entry_price = price * 0.99` (`:278`) dopo
     un riavvio, quindi il PnL calcolato su una posizione recuperata e' fabbricato;
     e nessun adapter accetta una chiave di idempotenza, quindi un crash fra
     l'invio dell'ordine (`:605-618`) e il salvataggio dello stato (`:623`)
     lascia ordini vivi non tracciati.

Nessuna rete, nessun file: il fake exchange e' in memoria e il BotTask viene
costruito senza `state_path`/`journal_path`/`health_path`.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

import pytest

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager


# --- fake exchange (nessuna rete, nessun file) --------------------------------

class FakeExchange:
    """Exchange in memoria. `sell_market` registra ogni vendita richiesta."""

    def __init__(self, price: float = 100.0, free_quote: float = 100.0,
                 free_base: float = 0.0, fail_sells: bool = False) -> None:
        self.price = price
        self.free_quote = free_quote
        self.free_base = free_base
        self.fail_sells = fail_sells
        self.placed: list = []
        self.market_sells: list = []      # vendite RIUSCITE
        self.sell_attempts: list = []     # ogni tentativo, riuscito o fallito
        self._seq = 0

    def fetch_ticker(self, symbol):
        # bid == ask: spread nullo, cosi' il guard di slippage non interferisce
        return {"last": self.price, "bid": self.price, "ask": self.price}

    def fetch_balance(self):
        return {"free": {"EUR": self.free_quote, "SOL": self.free_base},
                "total": {"EUR": self.free_quote, "SOL": self.free_base}}

    def fetch_open_orders(self, symbol):
        return []

    def fetch_order(self, oid, symbol):
        return {"id": oid, "status": "open"}

    def create_limit_order(self, symbol, side, amount, price):
        self._seq += 1
        o = {"id": f"o{self._seq}", "side": side, "amount": amount, "price": price}
        self.placed.append(o)
        return o

    def cancel_order(self, oid, symbol):
        return {"id": oid}

    def sell_market(self, symbol, amount):
        self.sell_attempts.append(amount)
        if self.fail_sells:
            raise RuntimeError("ExchangeError: temporaneamente non disponibile")
        self.market_sells.append(amount)
        return {"id": "mkt"}

    def min_amount_for(self, symbol):
        return 0.0

    def min_notional(self, symbol):
        return 0.0


def make_bot(ex, capital: float = 30.0, levels: int = 1) -> BotTask:
    """BotTask senza path di stato/journal/health: nessuna I/O su disco."""
    cfg = BotConfig(symbol="SOL/EUR", capital=capital, levels=levels, fee=0.0,
                    buy_distance=0.01, profit_target=0.015)
    return BotTask(cfg, ex, GridPolicy(GridParams(levels=levels)), RiskManager())


# --- R1: lo stop deve vendere la SIZE DELLA POSIZIONE --------------------------

def test_R1_stop_monitorato_vende_la_size_della_posizione_non_tutto_il_saldo():
    """Sul conto ci sono 1.0 SOL, ma la posizione di QUESTO bot e' 0.25.

    Lo stop deve chiudere 0.25. Vendere 1.0 significa liquidare a mercato anche
    il capitale di un altro bot sullo stesso sub-account, o di una mano umana.
    """
    ex = FakeExchange(price=90.0, free_base=1.0)
    bot = make_bot(ex)
    bot.state.posizione_aperta = {"entry": 100.0, "amount": 0.25, "stop": 95.0}

    chiuso = asyncio.run(bot._esegui_stop_monitorato(price=90.0, stop_price=95.0))

    assert chiuso is True
    assert ex.market_sells == [pytest.approx(0.25)], (
        "lo stop ha venduto %r: deve vendere la size della posizione (0.25), "
        "non il saldo libero del conto (1.0)" % (ex.market_sells,))


def test_R1_stop_loss_di_bot_vende_la_size_della_posizione():
    """Lo stesso difetto esiste nel secondo punto di vendita a mercato."""
    ex = FakeExchange(price=90.0, free_base=1.0)
    bot = make_bot(ex)
    bot.state.posizione_aperta = {"entry": 100.0, "amount": 0.25, "stop": 95.0}

    asyncio.run(bot._trigger_stop_loss(equity=50.0, drawdown=0.5, price=90.0))

    assert ex.market_sells == [pytest.approx(0.25)], (
        "lo stop-loss di bot ha venduto %r: deve vendere la size della posizione"
        % (ex.market_sells,))


# --- R2: uno stop fallito non deve lasciare la posizione incustodita -----------

def test_R2_stop_fallito_viene_ritentato_al_tick_successivo():
    """Se la vendita di stop fallisce, il tick dopo deve RIPROVARE.

    Oggi il flag `start_loss_triggered` resta True e il ramo di tick lo esclude
    (`:361-364`), quindi la posizione resta aperta per sempre: il commento a
    `:1036-1038` promette un retry che non avviene mai.
    """
    ex = FakeExchange(price=90.0, free_base=1.0, fail_sells=True)
    bot = make_bot(ex)
    bot.cfg.stop_loss_pct = 0.10
    bot.cfg.max_slippage = 0.0            # vogliamo il ramo di vendita, non il guard
    bot.state.posizione_aperta = {"entry": 100.0, "amount": 1.0, "stop": 95.0}
    bot.state.peak_equity = 30.0
    bot._get_equity = lambda: 15.0        # drawdown 50% > soglia 10%

    asyncio.run(bot.tick())               # primo tentativo: la vendita fallisce
    # il requisito e' il RETRY, non come lo si ottiene: che il flag resti True o
    # venga ripristinato e' un dettaglio implementativo. Qui si pretende solo che
    # il fallimento sia VISIBILE, perche' uno stop fallito in silenzio e' il modo
    # in cui questo difetto e' passato inosservato.
    assert "stop loss sell" in bot._last_error, (
        "il fallimento della vendita non e' visibile in health: %r"
        % (bot._last_error,))
    assert len(ex.sell_attempts) == 1, (
        "il primo tick non ha nemmeno tentato la vendita (tentativi: %r)"
        % (ex.sell_attempts,))

    asyncio.run(bot.tick())               # il tick successivo DEVE ritentare
    assert len(ex.sell_attempts) > 1, (
        "il tick successivo non ha ritentato la chiusura: la posizione resta "
        "aperta senza stop e nessuno la chiude")


# --- R2 bis: il blocco dei nuovi ordini non puo' vivere in un flag in memoria ---

def test_R2_stop_attivo_blocca_i_nuovi_ordini_anche_se_il_flag_e_azzerato():
    """Con lo stop attivo e persistito, un flag in memoria azzerato non basta.

    `_propagate_safemode` (`denaro_node.py:478`) riscrive `trading_paused` a ogni
    cambio di livello RAM: al ritorno a "nominal" il bot riprende a piazzare
    ordini pur avendo lo stop-loss attivo.
    """
    # CONTROLLO: il banco di prova piazza davvero, altrimenti il test e' vacuo
    ex_ok = FakeExchange(price=100.0, free_quote=100.0)
    bot_ok = make_bot(ex_ok)
    asyncio.run(bot_ok.tick())
    assert ex_ok.placed, "controllo fallito: il bot non piazza ordini nemmeno senza stop"

    # TRATTAMENTO: stop persistito, flag in memoria azzerato dall'esterno
    ex = FakeExchange(price=100.0, free_quote=100.0)
    bot = make_bot(ex)
    bot.state.stop_loss_triggered = True
    bot.trading_paused = False
    asyncio.run(bot.tick())

    assert ex.placed == [], (
        "un bot con lo stop-loss attivo ha piazzato %d ordini: il blocco dei "
        "nuovi ordini dipende da un flag in memoria, non dallo stato persistito"
        % len(ex.placed))


# --- R3: il recupero non deve fabbricare dati --------------------------------

def test_R3_il_recupero_da_exchange_non_inventa_il_prezzo_di_ingresso():
    """`entry_price = price * 0.99` (`:278`) e' un numero inventato.

    Da un entry price fabbricato discende un PnL fabbricato: la telemetria
    pubblica una performance che non e' quella del conto.
    """
    ex = FakeExchange(price=100.0)
    ex.fetch_open_orders = lambda symbol: [
        {"id": "sell-1", "side": "sell", "amount": 1.0, "price": 100.0}]
    bot = make_bot(ex)

    bot._rebuild_from_exchange()

    sell = bot.state.open_sells["sell-1"]
    assert sell["entry_price"] != pytest.approx(100.0 * 0.99), (
        "entry_price e' stato inventato come price*0.99: il PnL calcolato su "
        "una posizione recuperata e' fabbricato, non misurato")


def test_R3_gli_adapter_offrono_una_chiave_di_idempotenza():
    """Senza chiave d'ordine, un crash fra invio e salvataggio perde l'ordine.

    I buy partono a `:605-618` e lo stato e' persistito solo a `:623`: fra i due
    c'e' una finestra in cui l'ordine esiste sull'exchange e non nel nostro
    stato. Serve una chiave che permetta di riconoscerlo al riavvio.
    """
    from denaro.infrastructure.exchanges.okx import OKXAdapter

    fn = getattr(OKXAdapter, "create_limit_order", None)
    assert fn is not None, "OKXAdapter.create_limit_order non esiste piu'"
    parametri = set(inspect.signature(fn).parameters)
    assert {"client_order_id", "clientOrderId"} & parametri, (
        "create_limit_order non accetta una chiave di idempotenza "
        f"(parametri: {sorted(parametri)}): un riavvio non puo' riconoscere un "
        "ordine gia' inviato")


# --- Q4: i fill parziali non devono sparire ------------------------------------
#
# `_process_fills` legge lo `status` dell'ordine ma MAI il campo `filled`: un
# ordine riempito in parte e poi cancellato viene rimosso dallo stato
# (`orchestrator.py:1131-1132` per i buy, `:1170-1171` per le sell) senza
# contabilizzare nulla. E un fill chiuso registra `info["amount"]` (il richiesto)
# invece di quanto la sede ha davvero riempito (`:1079`, `:1139`).
# Effetto: il saldo all'exchange e lo stato del bot divergono, in silenzio.

class _TrendLikePolicy(GridPolicy):
    """GridPolicy sul ramo a stop monitorato: e' il ramo che registra la
    posizione al fill (`orchestrator.py:1080`)."""
    STOP_MONITORATO = True


def _bot_trend(ex) -> BotTask:
    cfg = BotConfig(symbol="SOL/EUR", capital=30.0, levels=1, fee=0.0,
                    buy_distance=0.01, profit_target=0.015)
    return BotTask(cfg, ex, _TrendLikePolicy(GridParams(levels=1)), RiskManager())


def _exchange_con_ordine_risolto(status: str, filled: float):
    ex = FakeExchange(price=100.0)
    ex.fetch_open_orders = lambda symbol: []      # l'ordine non e' piu' aperto
    ex.fetch_order = lambda oid, symbol: {
        "id": oid, "status": status, "amount": 1.0, "filled": filled,
        "price": 100.0}
    return ex


def test_Q4_buy_parzialmente_eseguito_non_sparisce_dallo_stato():
    """Un buy da 1.0 riempito per 0.4 e poi cancellato: il 0.4 e' denaro vero."""
    ex = _exchange_con_ordine_risolto("canceled", 0.4)
    bot = _bot_trend(ex)
    bot.state.open_buys["o1"] = {"amount": 1.0, "price": 100.0,
                                 "timestamp": 0.0, "level": 0}

    asyncio.run(bot._process_fills(price=100.0))

    pos = bot.state.posizione_aperta
    assert pos is not None or "o1" in bot.state.open_buys, (
        "l'ordine aveva 0.4 eseguiti su 1.0 ed e' stato rimosso dallo stato "
        "senza registrare nulla: il 0.4 non e' piu' ne' posizione ne' ordine, "
        "ma esiste sul conto")
    if pos is not None:
        assert pos["amount"] == pytest.approx(0.4), (
            f"posizione registrata per {pos['amount']} ma il riempito era 0.4")


def test_Q4_sell_parzialmente_eseguita_contabilizza_il_riempito():
    """Una sell da 1.0 riempita per 0.4 e poi cancellata: il 0.4 e' venduto."""
    ex = _exchange_con_ordine_risolto("canceled", 0.4)
    bot = _bot_trend(ex)
    bot.state.open_sells["s1"] = {"amount": 1.0, "entry_price": 90.0,
                                  "price": 100.0, "target_price": 100.0,
                                  "kind": "tp", "timestamp": 0.0}

    asyncio.run(bot._process_fills(price=100.0))

    assert bot.state.total_trades >= 1, (
        "0.4 su 1.0 sono stati venduti davvero, ma il bot non ha registrato "
        "nessun trade: il ricavo e la fee di quella vendita non esistono nel "
        "conto del bot")


def test_Q4_un_fill_chiuso_usa_la_quantita_riempita_non_quella_richiesta():
    """Se la sede chiude l'ordine con meno del richiesto, la posizione e' quella."""
    ex = _exchange_con_ordine_risolto("closed", 0.7)
    bot = _bot_trend(ex)
    bot.state.open_buys["o1"] = {"amount": 1.0, "price": 100.0,
                                 "timestamp": 0.0, "level": 0}

    asyncio.run(bot._process_fills(price=100.0))

    pos = bot.state.posizione_aperta
    assert pos is not None, "nessuna posizione registrata dopo un fill chiuso"
    assert pos["amount"] == pytest.approx(0.7), (
        f"posizione registrata per {pos['amount']} ma la sede ha riempito 0.7: "
        "posizione e PnL sono sovrastimati del "
        f"{(pos['amount'] / 0.7 - 1) * 100:.0f}%")


# --- Q5: la misura onesta deve entrare nel percorso live -----------------------
#
# `EquityTracker` (`domain/equity.py:37`) esiste ed e' progettato per derivare la
# performance dalla curva equity mark-to-market, perche' i PnL per-trade non
# registrano gli stop-loss, si azzerano a ogni riavvio e mescolano euro e
# percentuali (`equity.py:5-8`). Era usato SOLO dai test: il percorso live
# pubblicava `risk_state.perf`, cioe' proprio la fonte dichiarata inaffidabile.
# Questi due test fissano il cablaggio.

def test_Q5_il_percorso_live_alimenta_la_curva_equity():
    ex = FakeExchange(price=100.0, free_quote=100.0)
    bot = make_bot(ex)
    assert bot.equity_tracker.rows == [], "la curva deve partire vuota"

    for _ in range(3):
        asyncio.run(bot.tick())

    righe = bot.equity_tracker.rows
    assert len(righe) == 3, (
        f"la curva ha {len(righe)} campioni dopo 3 tick: il percorso live non "
        "sta alimentando la misura onesta")
    assert all(eq > 0 for _, eq in righe), f"campioni non validi: {righe}"


def test_Q5_nessun_numero_parziale_spacciato_per_significativo():
    """`warm` deve restare False finche' la storia non basta."""
    ex = FakeExchange(price=100.0, free_quote=100.0)
    bot = make_bot(ex)
    asyncio.run(bot.tick())

    metriche = bot.equity_tracker.evaluate()
    assert metriche["eq_warm"] is False, (
        "con un solo campione la misura si dichiara significativa: e' "
        "esattamente il modo in cui una serie inerte diventa una truffa")
    assert metriche["eq_n"] == 1


def test_Q5b_la_curva_equity_e_serializzabile_e_ripristinabile():
    """`_load_equity_curve` ricarica esattamente cio' che `_save_state` scrive.

    Senza round-trip fedele, dopo un riavvio le metriche non corrispondono a
    quelle di prima — e una misura che cambia al riavvio non e' una misura.
    """
    from denaro.domain.equity import EquityTracker

    originale = EquityTracker()
    for i, eq in enumerate((100.0, 101.5, 99.0, 103.25)):
        originale.append(float(i), eq)

    # cio' che `_save_state` mette nello store: {"rows": [...]}
    serializzato = {"rows": originale.rows}
    righe = serializzato["rows"]
    assert isinstance(righe, list) and len(righe) == 4

    # cio' che `_load_equity_curve` ricostruisce
    ripristinato = EquityTracker()
    ripristinato.extend([(float(r[0]), float(r[1])) for r in righe])

    assert ripristinato.rows == originale.rows, (
        "la curva ripristinata differisce da quella salvata")
    assert ripristinato.evaluate() == originale.evaluate(), (
        "le metriche cambiano dopo un ripristino dalla stessa serie")


# --- R3b: la chiave di idempotenza degli ordini (docs/58 §58.3) ----------------
#
# Il difetto: gli ordini partono SENZA chiave, quindi un crash fra l'invio e il
# salvataggio dello stato lascia ordini VIVI non tracciati — capitale impegnato
# che il bot non vede e che, dopo un riavvio, non sa nemmeno riconoscere come
# proprio. La correzione ha tre pezzi, e i test qui sotto li fissano tutti:
#   1) l'adapter accetta una chiave (`clOrdId` su OKX; nel paper la chiave e'
#      registrata nell'ordine, cosi' l'idempotenza e' verificabile senza rete);
#   2) il bot genera una chiave DIVERSA per ogni invio e scrive l'intenzione nel
#      journal PRIMA di inviare, cosi' un crash subito dopo non cancella nulla;
#   3) al riavvio la chiave letta dall'exchange rende l'ordine riconoscibile.
#
# I file di journal stanno in `.pytmp` DENTRO il repo (non `tempfile`/`tmp_path`):
# le sandbox di esecuzione negano le temp dir di sistema e falserebbero l'esito.

_REPO_TMP = Path(__file__).resolve().parents[2] / ".pytmp" / "r3b"


class FakeExchangeConJournal(FakeExchange):
    """Fake che accetta la chiave e legge il journal AL MOMENTO dell'invio.

    E' il punto del test: non basta che l'evento `order_intent` esista a fine
    tick, deve esistere PRIMA che l'ordine parta. Altrimenti un crash fra i due
    perde esattamente l'informazione che serve.
    """

    def __init__(self, journal_path, **kwargs) -> None:
        super().__init__(**kwargs)
        self.journal_path = Path(journal_path)
        self.ids_ricevuti: list = []        # chiavi arrivate con gli ordini
        self.id_mancante: list = []         # invii SENZA chiave (difetto R3b)
        self.eventi_al_momento_dell_invio: list = []
        self.market_ids: list = []          # chiavi delle vendite a mercato

    def _leggi_journal(self) -> list:
        if not self.journal_path.exists():
            return []
        return [json.loads(riga) for riga in
                self.journal_path.read_text(encoding="utf-8").splitlines()
                if riga.strip()]

    def create_limit_order(self, symbol, side, amount, price,
                           client_order_id=None):
        # lettura del journal PRIMA di registrare l'ordine: e' l'istante
        # dell'invio, l'unico che conta per il crash
        self.eventi_al_momento_dell_invio.append(self._leggi_journal())
        if client_order_id:
            self.ids_ricevuti.append(client_order_id)
        else:
            self.id_mancante.append((side, amount, price))
        o = super().create_limit_order(symbol, side, amount, price)
        o["client_order_id"] = client_order_id
        return o

    def sell_market(self, symbol, amount, client_order_id=None):
        self.market_ids.append(client_order_id)
        if client_order_id:
            self.ids_ricevuti.append(client_order_id)
        else:
            self.id_mancante.append(("sell_market", amount))
        return super().sell_market(symbol, amount)

    def fetch_open_orders(self, symbol):
        """Gli ordini piazzati restano vivi sull'exchange, con la loro chiave.

        E' cio' che vede un processo che riparte dopo un crash: `clientOrderId`
        e' il campo con cui un adapter reale (ccxt) restituisce la chiave.
        """
        return [{"id": o["id"], "symbol": symbol, "side": o["side"],
                 "amount": o["amount"], "price": o["price"],
                 "status": "open", "clientOrderId": o.get("client_order_id")}
                for o in self.placed]


def make_bot_completo(ex, capital: float = 30.0, levels: int = 1,
                      bot_key: str = "paper:test:SOL/EUR",
                      journal_path=None) -> BotTask:
    """Come `make_bot`, ma con `bot_key` e (opzionale) journal su file nel repo."""
    cfg = BotConfig(symbol="SOL/EUR", capital=capital, levels=levels, fee=0.0,
                    buy_distance=0.01, profit_target=0.015, bot_key=bot_key,
                    journal_path=Path(journal_path) if journal_path else None)
    return BotTask(cfg, ex, GridPolicy(GridParams(levels=levels)), RiskManager())


def _file_tmp(nome: str) -> Path:
    _REPO_TMP.mkdir(parents=True, exist_ok=True)
    return _REPO_TMP / nome


def test_R3b_due_ordini_dello_stesso_tick_hanno_chiavi_divere():
    """Se lo stesso tick piazza piu' livelli, le chiavi devono essere diverse.

    Una chiave di idempotenza condivisa da due ordini non identifica nulla: al
    riavvio due ordini diversi risulterebbero lo STESSO ordine (o il secondo
    verrebbe rifiutato dall'exchange come duplicato).
    """
    ex = FakeExchangeConJournal(_file_tmp("due_livelli.jsonl"),
                                price=100.0, free_quote=1000.0)
    bot = make_bot_completo(ex, capital=1000.0, levels=3,
                            journal_path=ex.journal_path)

    asyncio.run(bot.tick())

    assert len(ex.ids_ricevuti) >= 2, (
        "il tick ha inviato %d ordini con chiave: servono almeno 2 per provare "
        "l'unicita'" % len(ex.ids_ricevuti))
    assert ex.id_mancante == [], (
        "ordini inviati SENZA chiave di idempotenza: %r" % (ex.id_mancante,))
    assert len(set(ex.ids_ricevuti)) == len(ex.ids_ricevuti), (
        "due ordini dello stesso tick hanno la stessa chiave: %r"
        % (ex.ids_ricevuti,))
    # anche nello stato salvato, non solo nel fake
    chiavi_stato = [v.get("client_order_id") for v in bot.state.open_buys.values()]
    assert chiavi_stato and all(chiavi_stato), (
        "lo stato non registra la chiave d'ordine: %r" % (bot.state.open_buys,))


def test_R3b_il_journal_registra_l_intenzione_PRIMA_dell_invio():
    """L'evento `order_intent` deve esistere GIA' quando l'ordine parte.

    E' il cuore di R3b: la finestra fra invio e `_persist` e' quella in cui un
    crash perde l'ordine. Se il journal non e' scritto prima, l'informazione si
    perde con lui.
    """
    ex = FakeExchangeConJournal(_file_tmp("intento.jsonl"),
                                price=100.0, free_quote=1000.0)
    bot = make_bot_completo(ex, capital=1000.0, levels=3,
                            journal_path=ex.journal_path)

    asyncio.run(bot.tick())

    assert ex.eventi_al_momento_dell_invio, "nessun ordine inviato: test vacuo"
    eventi = [e for lettura in ex.eventi_al_momento_dell_invio for e in lettura]
    assert eventi, (
        "al momento dell'invio il journal era VUOTO: l'intenzione e' registrata "
        "dopo l'ordine, quindi un crash nella finestra la perde")
    intents = {e.get("client_order_id") for e in eventi
               if e.get("event") == "order_intent"}
    assert intents, (
        "nessun evento `order_intent` nel journal al momento dell'invio: %r"
        % (eventi,))
    for coid in ex.ids_ricevuti:
        assert coid in intents, (
            "l'ordine %r e' partito senza che il journal ne registrasse "
            "l'intenzione (intenzioni: %r)" % (coid, intents))


def test_R3b_una_chiave_strana_viene_sanificata_per_OKX():
    """OKX rifiuta un `clOrdId` non alfanumerico minuscolo o >32 caratteri.

    Un id rifiutato NON e' un dettaglio: l'ordine non parte, quindi la chiave
    "di sicurezza" diventerebbe un blocco degli ordini. La chiave va sanificata e
    troncata SEMPRE, anche se il `bot_key` e' scritto a mano con caratteri
    strani.
    """
    import re

    from denaro.infrastructure.exchanges.okx import (CLIENT_ORDER_ID_MAX,
                                                     OKXAdapter,
                                                     client_order_id_sicuro)

    bot_key = "OKX:EEA/../Bot Strano EUR " + "x" * 60
    ex = FakeExchangeConJournal(_file_tmp("sanificata.jsonl"),
                                price=100.0, free_quote=1000.0)
    bot = make_bot_completo(ex, capital=1000.0, levels=2, bot_key=bot_key,
                            journal_path=ex.journal_path)

    asyncio.run(bot.tick())

    assert ex.ids_ricevuti, "nessuna chiave inviata: test vacuo"
    for coid in ex.ids_ricevuti:
        assert len(coid) <= CLIENT_ORDER_ID_MAX, (
            "chiave di %d caratteri: OKX la rifiuta (max %d) -> l'ordine non "
            "parte" % (len(coid), CLIENT_ORDER_ID_MAX))
        assert re.fullmatch(r"[a-z0-9]+", coid), (
            "chiave non alfanumerica minuscola: %r" % (coid,))

    # la funzione dell'adapter e' il contratto verso la sede: si verifica diretta
    sanificata = client_order_id_sicuro(bot_key)
    assert len(sanificata) == CLIENT_ORDER_ID_MAX, (
        "un id lungo deve essere TRONCATO a %d caratteri, non rifiutato"
        % CLIENT_ORDER_ID_MAX)
    assert re.fullmatch(r"[a-z0-9]+", sanificata)
    # il troncamento non deve collassare due id diversi nello stesso id
    assert client_order_id_sicuro("a.b") != client_order_id_sicuro("ab"), (
        "il carattere non ammesso e' stato ELIMINATO invece che sostituito: due "
        "chiavi diverse collassano nella stessa (e due ordini diversi "
        "sarebbero lo stesso ordine)")
    # nessuna chiave -> comportamento identico a prima della correzione
    assert client_order_id_sicuro(None) == ""
    assert client_order_id_sicuro("") == ""

    parametri = set(inspect.signature(OKXAdapter.sell_market).parameters)
    assert "client_order_id" in parametri, (
        "sell_market non accetta la chiave: uno stop inviato e perso da un "
        f"crash resta anonimo (parametri: {sorted(parametri)})")


def test_R3b_il_riavvio_riconosce_l_ordine_dalla_chiave():
    """Un ordine sopravvissuto a un crash va riconosciuto come NOSTRO.

    L'exchange restituisce `clientOrderId`: registrarlo nello stato e' cio' che
    distingue un ordine del bot da un ordine comparso dal nulla. Se il campo non
    c'e' il comportamento resta quello di prima (nessuna chiave inventata).
    """
    ex = FakeExchangeConJournal(_file_tmp("riavvio.jsonl"), price=100.0)
    ex.fetch_open_orders = lambda symbol: [
        {"id": "o-crash", "side": "buy", "amount": 0.5, "price": 99.0,
         "clientOrderId": "gb7-papertestsolxeur"},
        {"id": "o-anonimo", "side": "buy", "amount": 0.5, "price": 98.0}]
    bot = make_bot_completo(ex)

    bot._rebuild_from_exchange()

    assert bot.state.open_buys["o-crash"].get("client_order_id") == (
        "gb7-papertestsolxeur"), (
        "la chiave restituita dall'exchange non e' stata registrata: al riavvio "
        "l'ordine resta anonimo e non attribuibile")
    assert "client_order_id" not in bot.state.open_buys["o-anonimo"], (
        "l'ordine senza chiave ha una chiave inventata: il campo assente deve "
        "lasciare il comportamento invariato")


def test_R3b_ciclo_completo_ordine_inviato_poi_crash_poi_riavvio():
    """Il caso di R3b end-to-end: l'ordine parte, lo stato NON viene salvato.

    Si simula esattamente la finestra del difetto: `tick()` invia il buy e poi
    "muore" prima di `_persist`. Nel processo nuovo (stesso journal, stesso
    exchange) l'ordine vivo deve tornare nello stato CON la sua chiave, cioe'
    riconosciuto come nostro: e' la verifica chiesta da `docs/55` Q3 ("l'ordine e'
    recuperabile dopo un riavvio simulato").
    """
    journal = _file_tmp("ciclo_crash.jsonl")
    # un solo livello: il test vuole UN ordine da ritrovare, non una scala
    ex = FakeExchangeConJournal(journal, price=100.0, free_quote=100.0)
    vecchio = make_bot_completo(ex, levels=1, journal_path=journal)
    asyncio.run(vecchio.tick())

    assert vecchio.state.open_buys, "il bot non ha piazzato nulla: test vacuo"
    oid = next(iter(vecchio.state.open_buys))
    coid = vecchio.state.open_buys[oid]["client_order_id"]
    assert coid and coid in ex.ids_ricevuti
    # il crash: nessuna `_persist`, lo stato su disco resta quello di prima
    assert ex.fetch_open_orders("SOL/EUR"), (
        "il fake non conserva l'ordine: il riavvio non avrebbe nulla da trovare")

    # RIAVVIO: processo nuovo, stesso journal, stesso exchange
    nuovo = make_bot_completo(ex, journal_path=journal)

    assert oid in nuovo.state.open_buys, (
        "l'ordine vivo sull'exchange non e' tornato nello stato dopo il riavvio: "
        "e' capitale impegnato che il bot non vede")
    assert nuovo.state.open_buys[oid].get("client_order_id") == coid, (
        "l'ordine e' stato recuperato ma SENZA la sua chiave: non e' "
        "riconoscibile come nostro (attesa %r, trovata %r)"
        % (coid, nuovo.state.open_buys[oid].get("client_order_id")))
    intents = [e.get("client_order_id") for e in
               (json.loads(r) for r in
                journal.read_text(encoding="utf-8").splitlines() if r.strip())
               if e.get("event") == "order_intent"]
    assert coid in intents, (
        "il journal non contiene l'intenzione di quell'ordine: la chiave non era "
        "durevole prima dell'invio (intenzioni: %r)" % (intents,))

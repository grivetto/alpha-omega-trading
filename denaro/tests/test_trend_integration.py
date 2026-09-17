#!/usr/bin/env python3
"""Collaudo end-to-end della TrendPolicy con l'orchestratore vero.

Perche' esiste: i test unitari verificano la LOGICA della policy (barre, ATR,
segnale, trailing) e l'equivalenza col backtest sul segnale. Ma il percorso
completo — decide -> piazzamento -> fill -> sell_target -> trailing -> uscita —
non era mai girato con l'orchestratore. Un difetto di integrazione si
manifesterebbe solo al PRIMO segnale live, cioe' tra giorni o settimane, con
denaro vero.

Qui si simula l'intero ciclo con FakeExchange e un orologio controllato.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.risk import RiskManager
from denaro.domain.trend import TrendParams, TrendPolicy

GIORNO = 86_400.0


class Orologio:
    """Orologio controllabile: il trend decide solo al cambio di giornata."""

    def __init__(self, t: float) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


class FakeExchange:
    """Exchange in-memory minimale (stessa semantica di FakeExchange dei test
    dell'orchestrator: i fill avvengono solo su market_trade)."""

    def __init__(self, price: float, free_quote: float = 100.0) -> None:
        self.price = price
        self.free = free_quote
        self.asset = 0.0
        self.quote = "EUR"
        self.base = "SOL"
        self.orders = {}
        self._next = 1

    def create_limit_order(self, symbol, side, amount, price):
        oid = "o%d" % self._next
        self._next += 1
        o = {"id": oid, "symbol": symbol, "side": side, "amount": float(amount),
             "price": float(price), "status": "open"}
        self.orders[oid] = o
        return o

    def cancel_order(self, oid, symbol):
        if oid in self.orders:
            self.orders[oid]["status"] = "canceled"
        return {"id": oid, "status": "canceled"}

    def fetch_order(self, oid, symbol):
        return self.orders.get(oid, {"status": "closed", "filled": 0})

    def fetch_open_orders(self, symbol):
        return [o for o in self.orders.values() if o["status"] == "open"]

    def fetch_balance(self):
        return {"free": {self.quote: self.free, self.base: self.asset},
                "total": {self.quote: self.free + self.asset * self.price,
                          self.base: self.asset}}

    def fetch_ticker(self, symbol):
        return {"last": self.price}

    def sell_market(self, symbol, amount):
        amount = float(amount)
        if amount <= 0:
            return {"id": "", "status": "rejected"}
        self.free += amount * self.price
        self.asset -= amount
        return {"id": "stop-market", "status": "closed"}

    def market_trade(self, price):
        self.price = price
        for o in list(self.orders.values()):
            if o["status"] != "open":
                continue
            if o["side"] == "buy" and price <= o["price"]:
                o["status"] = "filled"
                self.free -= o["amount"] * o["price"]
                self.asset += o["amount"]
            elif o["side"] == "sell" and price >= o["price"]:
                o["status"] = "filled"
                self.free += o["amount"] * o["price"]
                self.asset -= o["amount"]


def _barre_piatte(n, prezzo=100.0, ultimo=None):
    """n barre giornaliere; l'ultima puo' avere una chiusura diversa."""
    righe = []
    for i in range(n):
        p = prezzo if (ultimo is None or i < n - 1) else ultimo
        righe.append([(i + 1) * GIORNO, p, p * 1.01, p * 0.99, p, 1000.0])
    return righe


class TestTrendIntegrazione(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _bot(self, orol, pol, ex):
        cfg = BotConfig(
            symbol="SOL/EUR", capital=100.0, fee=0.002,
            state_path=Path(self.dir) / "state.json",
            journal_path=Path(self.dir) / "trades.jsonl",
            health_path=Path(self.dir) / "health.json",
        )
        return BotTask(cfg, ex, pol, RiskManager(daily_loss_limit=0.05,
                                                max_drawdown_limit=0.20),
                       now=orol)

    def _policy(self):
        return TrendPolicy(TrendParams(canale=5, atr_period=3, trail_mult=3.0,
                                       stop_atr_mult=2.0, trend_ema=0,
                                       risk_pct=0.02, entry_slip=0.0005))

    def test_ciclo_completo_breakout_trailing_uscita(self):
        orol = Orologio(GIORNO * 10)
        pol = self._policy()
        # storico precaricato: 10 giornate piatte attorno a 100
        pol.precarica_barre(_barre_piatte(10))
        ex = FakeExchange(price=100.0, free_quote=100.0)
        bot = self._bot(orol, pol, ex)

        async def scenario():
            # --- giorno 10: due tick, l'ultimo con chiusura alta (il breakout) ---
            await bot.tick()
            ex.price = 130.0
            await bot.tick()
            assert not bot.state.open_buys, "non deve comprare prima della chiusura"

            # --- giorno 11: il cambio di giornata chiude la barra e rivela il breakout ---
            orol.t = GIORNO * 11
            ex.price = 130.0
            await bot.tick()
            assert bot.state.open_buys, "breakout: doveva piazzare un buy"
            oid, info = next(iter(bot.state.open_buys.items()))
            notional = info["price"] * info["amount"]
            assert 0 < notional <= 100.0, "notional fuori scala: %s" % notional
            assert info["price"] > 130.0, "l'ingresso e' un limite sopra il mercato"

            # --- fill del buy: con lo stop monitorato NON si piazza alcuna
            #     vendita a riposo ---
            ex.market_trade(130.0)
            await bot.tick()
            assert not bot.state.open_buys, "il buy doveva risultare riempito"
            # DIFETTO del 2026-09-17: qui si piazzava un LIMITE di vendita a
            # entry - 2*ATR, cioe' SOTTO il mercato, che si sarebbe riempito
            # subito al miglior bid. La protezione si pubblica come livello.
            assert not bot.state.open_sells, (
                "nessuna vendita a riposo: la protezione e' lo stop monitorato "
                "(trovate %s)" % (bot.state.open_sells,))
            pos = bot.state.posizione_aperta
            assert pos, "la posizione doveva essere registrata nello stato"
            assert abs(pos["entry"] - info["price"]) < 1e-9
            stop0 = pol.stop
            atteso = info["price"] - 2.0 * pol.atr
            assert abs(stop0 - atteso) < 1.0, (
                "stop iniziale %s, atteso %s (entry - 2*ATR)" % (stop0, atteso))
            # nessun ordine di vendita puo' riposare SOTTO il mercato: si
            # riempirebbe all'istante (era il difetto)
            for o in ex.orders.values():
                if o["side"] == "sell" and o["status"] == "open":
                    assert o["price"] >= ex.price, (
                        "vendita limite sotto il mercato: %s" % (o["price"],))

            # --- il prezzo sale: il trailing deve alzare lo stop ---
            orol.t = GIORNO * 11 + 3600
            ex.price = 150.0
            await bot.tick()
            assert not bot.state.open_sells, "lo stop non e' un ordine a riposo"
            stop1 = pol.stop
            assert stop1 > stop0, (
                "il trailing doveva salire: %s -> %s" % (stop0, stop1))

            # --- il prezzo attraversa lo stop: si esce A MERCATO ---
            ex.price = stop1
            await bot.tick()
            assert bot.state.posizione_aperta is None, (
                "la posizione doveva chiudersi: %s" % (bot.state.posizione_aperta,))
            assert ex.asset < 1e-9, "posizione non chiusa: %s" % ex.asset
            assert not bot.state.open_sells
            assert pol.in_posizione is False, "la policy doveva tornare flat"

        asyncio.run(scenario())

    def test_lo_stop_non_vende_al_momento_del_piazzamento(self):
        """Regressione del difetto del 2026-09-17.

        Lo stop iniziale e' entry - 2*ATR, cioe' SOTTO il mercato. Un ordine
        LIMITE di vendita a quel prezzo si riempie immediatamente al miglior
        bid: il bot avrebbe comprato e rivenduto nello stesso istante,
        perdendo spread + 2 fee a ogni ciclo. La protezione non esisteva.

        Qui si verifica che dopo il fill NON resti alcuna vendita a riposo e
        che la posizione sopravviva a un mercato FERMO al prezzo d'ingresso.
        """
        orol = Orologio(GIORNO * 10)
        pol = self._policy()
        pol.precarica_barre(_barre_piatte(10))
        ex = FakeExchange(price=100.0, free_quote=100.0)
        bot = self._bot(orol, pol, ex)

        async def scenario():
            await bot.tick()
            # giorno 10: la chiusura sale a 130 (e' il breakout, ma la barra
            # non e' ancora chiusa)
            ex.price = 130.0
            await bot.tick()
            assert not bot.state.open_buys, "non compra a barra aperta"
            # giorno 11: il cambio di giornata chiude la barra e rivela il
            # breakout
            orol.t = GIORNO * 11
            await bot.tick()
            assert bot.state.open_buys, "breakout: doveva piazzare un buy"
            ex.market_trade(130.0)
            await bot.tick()
            assert bot.state.posizione_aperta, "posizione non registrata"
            vendite = [o for o in ex.orders.values()
                       if o["side"] == "sell" and o["status"] == "open"]
            assert vendite == [], (
                "il bot ha lasciato una vendita a riposo: %s" % (vendite,))
            # mercato fermo al prezzo d'ingresso: non deve succedere NULLA
            asset_prima = ex.asset
            await bot.tick()
            assert bot.state.posizione_aperta is not None, (
                "la posizione si e' chiusa da sola: e' il difetto")
            assert abs(ex.asset - asset_prima) < 1e-12, (
                "l'asset e' cambiato senza un vero stop: %s -> %s"
                % (asset_prima, ex.asset))
            assert bot.state.open_sells == {}

        asyncio.run(scenario())

    def test_adozione_di_posizione_non_tracciata(self):
        """Restart con asset in mano e stato assente: la posizione si adotta.

        Senza adozione il bot resterebbe FLAT avendo l'asset, cioe' con una
        posizione scoperta e senza alcuno stop.
        """
        orol = Orologio(GIORNO * 10)
        pol = self._policy()
        pol.precarica_barre(_barre_piatte(10))
        pol.atr = 2.0
        ex = FakeExchange(price=100.0, free_quote=0.0)
        ex.asset = 1.0            # posizione rimasta da prima del riavvio
        bot = self._bot(orol, pol, ex)

        async def scenario():
            await bot.tick()
            assert pol.in_posizione is True, (
                "la posizione doveva essere adottata (reason=%s)"
                % getattr(pol, "_ultima_reason", ""))
            assert pol.stop == 96.0, "stop adottato: %s" % pol.stop

        asyncio.run(scenario())

    def test_non_compra_senza_breakout(self):
        """Serie piatta: nessun ordine, nessun errore."""
        orol = Orologio(GIORNO * 10)
        pol = self._policy()
        pol.precarica_barre(_barre_piatte(10))
        ex = FakeExchange(price=100.0, free_quote=100.0)
        bot = self._bot(orol, pol, ex)

        async def scenario():
            for giorno in range(10, 14):
                orol.t = GIORNO * giorno
                ex.price = 100.0 + (giorno % 2) * 0.5
                await bot.tick()
            assert not bot.state.open_buys, "serie piatta: nessun buy"
            assert not bot.state.open_sells

        asyncio.run(scenario())

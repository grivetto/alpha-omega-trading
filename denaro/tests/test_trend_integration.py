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

            # --- fill del buy ---
            ex.market_trade(130.0)
            await bot.tick()
            assert not bot.state.open_buys, "il buy doveva risultare riempito"
            assert bot.state.open_sells, "dopo il fill serve la protezione iniziale"
            soid, sinfo = next(iter(bot.state.open_sells.items()))
            stop0 = sinfo.get("target_price") or sinfo["price"]
            atteso = info["price"] - 2.0 * pol.atr
            assert abs(stop0 - atteso) < 1.0, (
                "stop iniziale %s, atteso %s (entry - 2*ATR)" % (stop0, atteso))

            # --- il prezzo sale: il trailing deve alzare lo stop ---
            orol.t = GIORNO * 11 + 3600
            ex.price = 150.0
            await bot.tick()
            aperti = bot.state.open_sells
            assert aperti, "lo stop non deve sparire"
            soid2, sinfo2 = next(iter(aperti.items()))
            stop1 = sinfo2.get("target_price") or sinfo2["price"]
            assert stop1 > stop0, (
                "il trailing doveva salire: %s -> %s" % (stop0, stop1))

            # --- il prezzo torna allo stop: si esce ---
            ex.market_trade(stop1)
            await bot.tick()
            assert not bot.state.open_sells, "allo stop si doveva uscire"
            assert ex.asset < 1e-9, "posizione non chiusa: %s" % ex.asset

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

#!/usr/bin/env python3
"""Test dell'orchestrator: ciclo completo grid con FakeExchange.

Copre il fix C7 end-to-end: mai piu' di `levels` buy aperti, re-grid
idempotente, fill → sell, PnL journalizzato, CB azionato, ripristino.
"""
import asyncio
import tempfile
import unittest
from pathlib import Path

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.infrastructure.storage import Journal


class FakeExchange:
    """Exchange in-memory con simulazione di mercato deterministico."""

    def __init__(self, price: float, free_quote: float = 30.0, quote: str = "EUR"):
        self.price = price
        self.free = free_quote
        self.asset = 0.0
        self.quote = quote
        self.orders = {}
        self._next = 1

    def create_limit_order(self, symbol, side, amount, price):
        oid = f"o{self._next}"
        self._next += 1
        order = {"id": oid, "symbol": symbol, "side": side,
                 "amount": amount, "price": price, "status": "open"}
        self.orders[oid] = order
        return order

    def cancel_order(self, oid, symbol):
        if oid in self.orders:
            self.orders[oid]["status"] = "canceled"

    def fetch_order(self, oid, symbol):
        return self.orders.get(oid, {"status": "closed", "filled": 0})

    def fetch_open_orders(self, symbol):
        return [o for o in self.orders.values() if o["status"] == "open"]

    def fetch_balance(self):
        total = self.free + self.asset * self.price
        return {"free": {self.quote: self.free}, "total": {self.quote: total}}

    def fetch_ticker(self, symbol):
        return {"last": self.price}

    def market_trade(self, price):
        """Muove il mercato e riempie gli ordini incrociati."""
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


def make_bot(exchange, tmpdir, capital=30.0, levels=3, now=None) -> BotTask:
    cfg = BotConfig(
        symbol="SOL/EUR", capital=capital, levels=levels,
        buy_distance=0.01, profit_target=0.02,
        state_path=Path(tmpdir) / "state.json",
        journal_path=Path(tmpdir) / "trades.jsonl",
        health_path=Path(tmpdir) / "health.json",
    )
    policy = GridPolicy(GridParams(levels=levels, buy_distance=0.01,
                                   profit_target=0.02, level_step=0.005,
                                   retarget_factor=1.5))
    risk = RiskManager(daily_loss_limit=0.05, max_drawdown_limit=0.15)
    return BotTask(cfg, exchange, policy, risk, now=now)


class TestBotTask(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    async def test_bootstrap_piazza_3_buy(self):
        ex = FakeExchange(price=100.0)
        bot = make_bot(ex, self.dir)
        await bot.tick()
        self.assertEqual(len(bot.state.open_buys), 3)
        # notional per livello = 10 (30/3)
        for info in bot.state.open_buys.values():
            self.assertAlmostEqual(info["price"] * info["amount"], 10.0, places=3)
        # health scritta
        health = (Path(self.dir) / "health.json").read_text()
        self.assertIn('"status": "running"', health)

    async def test_fill_crea_sell_al_tp(self):
        ex = FakeExchange(price=100.0)
        bot = make_bot(ex, self.dir)
        await bot.tick()
        # il mercato scende sotto il primo livello (~99.0)
        ex.market_trade(98.8)
        await bot.tick()
        sells = bot.state.open_sells
        self.assertEqual(len(sells), 1)
        sell = next(iter(sells.values()))
        # target = entry × 1.02
        self.assertAlmostEqual(sell["target_price"], 99.0 * 1.02, places=3)
        # il buy riempito esce dagli open
        self.assertEqual(len(bot.state.open_buys), 2)

    async def test_sell_filled_journalizza_pnl(self):
        ex = FakeExchange(price=100.0)
        bot = make_bot(ex, self.dir)
        await bot.tick()
        ex.market_trade(98.8)   # riempie il buy a 99.0
        await bot.tick()        # piazza il sell a 100.98
        ex.market_trade(101.5)  # riempie il sell
        await bot.tick()
        self.assertEqual(bot.state.total_trades, 1)
        self.assertGreater(bot.state.total_pnl, 0.0)
        # journal con sell_filled
        records = Journal(Path(self.dir) / "trades.jsonl").read_all()
        events = [r["event"] for r in records]
        self.assertIn("sell_filled", events)

    async def test_re_grid_idempotente_mai_sopra_levels(self):
        ex = FakeExchange(price=100.0)
        bot = make_bot(ex, self.dir)
        await bot.tick()
        # riempie 2 buy → dopo il tick restano 1 buy + 2 nuovi → mai > 3
        ex.market_trade(98.3)   # riempie 99.0 e 98.5
        await bot.tick()
        self.assertLessEqual(len(bot.state.open_buys), 3)
        self.assertEqual(len(bot.state.open_buys) + len(bot.state.open_sells), 3)
        # il mercato risale: nessun doppione piazzato
        ex.market_trade(100.0)
        await bot.tick()
        self.assertLessEqual(len(bot.state.open_buys), 3)

    async def test_cb_apre_e_blocca_nuovi_ordini(self):
        ex = FakeExchange(price=100.0, free_quote=30.0)
        equity = {"v": 100.0}
        bot = make_bot(ex, self.dir, now=lambda: 1_000_000.0)
        bot._get_equity = lambda: equity["v"]
        await bot.tick()
        self.assertEqual(len(bot.state.open_buys), 3)
        # crollo equity > max_drawdown (15%)
        equity["v"] = 80.0
        await bot.tick()
        health = (Path(self.dir) / "health.json").read_text()
        self.assertIn('"status": "blocked"', health)
        self.assertIn("CB OPEN", bot._last_error)
        # nessun nuovo ordine con CB open
        buys_before = len(bot.state.open_buys)
        await bot.tick()
        self.assertLessEqual(len(bot.state.open_buys), buys_before)

    async def test_ripristino_da_journal_e_exchange(self):
        ex = FakeExchange(price=100.0)
        bot = make_bot(ex, self.dir)
        await bot.tick()
        ex.market_trade(98.8)
        await bot.tick()        # buy riempito → sell piazzato
        ex.market_trade(101.5)
        await bot.tick()        # sell riempito → pnl journalizzato
        self.assertEqual(bot.state.total_trades, 1)

        # nuovo processo (stesso stato/journal/exchange): PnL ricostruito dal journal
        bot2 = make_bot(ex, self.dir)
        self.assertEqual(bot2.state.total_pnl, bot.state.total_pnl)
        self.assertEqual(bot2.state.total_trades, 1)
        # ordini aperti ricostruiti dall'exchange
        self.assertEqual(len(bot2.state.open_buys),
                         len([o for o in ex.orders.values() if o["status"] == "open"
                              and o["side"] == "buy"]))


if __name__ == "__main__":
    unittest.main()

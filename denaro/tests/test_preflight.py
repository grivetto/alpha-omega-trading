#!/usr/bin/env python3
"""Test TODO punto 1: equity dinamica + NOTIONAL pre-flight."""
import unittest
from unittest.mock import patch

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager


class FakeLiveExchange:
    """Exchange con capitale bloccato in buy limit (simula OKX/Kraken)."""

    def __init__(self, free=100.0, locked=40.0, min_not=5.0):
        self._free = free
        self._locked = locked
        self._min_not = min_not
        self.created = []

    def fetch_balance(self):
        return {"free": {"EUR": self._free}, "total": {"EUR": self._free}}

    def fetch_ticker(self, symbol):
        return {"last": 1.0}

    def available_trading_capital(self, quote="EUR"):
        return self._free + self._locked

    def min_notional(self, symbol):
        return self._min_not

    def create_limit_order(self, symbol, side, amount, price):
        self.created.append((side, amount, price))
        return {"id": f"o{len(self.created)}", "status": "open"}

    def cancel_order(self, oid, symbol):
        return {"id": oid, "status": "canceled"}

    def fetch_order(self, oid, symbol):
        return {"status": "open"}

    def fetch_open_orders(self, symbol):
        return []


class TestDynamicEquity(unittest.TestCase):
    def test_available_capital_free_plus_locked(self):
        ex = FakeLiveExchange(free=100.0, locked=40.0)
        self.assertEqual(ex.available_trading_capital("EUR"), 140.0)
        self.assertEqual(ex.available_trading_capital(), 140.0)

    def test_paper_available_e_cash(self):
        from denaro.infrastructure.exchanges.paper import PaperExchange
        ex = PaperExchange("ADA/EUR", capital=300.0)
        self.assertEqual(ex.available_trading_capital(), 300.0)
        self.assertEqual(ex.min_notional("ADA/EUR"), 0.0)


class TestNotionalPreFlight(unittest.IsolatedAsyncioTestCase):
    def _bot(self, ex, capital=30.0):
        cfg = BotConfig(symbol="ADA/EUR", capital=capital, levels=3,
                        buy_distance=0.01, profit_target=0.02)
        policy = GridPolicy(GridParams(levels=3, buy_distance=0.01,
                                       profit_target=0.02))
        risk = RiskManager()
        return BotTask(cfg, ex, policy, risk,
                       price_source=lambda: 1.0)

    async def test_blocco_se_min_notional_supera_capitale(self):
        """min_notional 15 > capitale disponibile 10 → blocco totale."""
        ex = FakeLiveExchange(free=10.0, locked=0.0, min_not=15.0)
        bot = self._bot(ex, capital=30.0)
        await bot.tick()
        self.assertEqual(ex.created, [])
        self.assertIn("PRE-FLIGHT BLOCK", bot._last_error)

    async def test_skip_se_nessun_livello_raggiunge_il_minimo(self):
        # min_notional 10.5: nessun livello (notional ~10) lo raggiunge
        ex = FakeLiveExchange(free=30.0, locked=0.0, min_not=10.5)
        bot = self._bot(ex, capital=30.0)
        await bot.tick()
        self.assertEqual(ex.created, [])
        # non e' un blocco per capitale (available 30 >= 10.5) ma per size
        self.assertNotIn("PRE-FLIGHT BLOCK", bot._last_error)

    async def test_nessun_blocco_con_capitale_sufficiente(self):
        ex = FakeLiveExchange(free=30.0, locked=0.0, min_not=5.0)
        bot = self._bot(ex, capital=30.0)
        await bot.tick()
        self.assertEqual(len(ex.created), 3)


if __name__ == "__main__":
    unittest.main()

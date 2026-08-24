#!/usr/bin/env python3
"""Test SafeModeGuardian (3 livelli) + SqliteStateStore (WAL)."""
import asyncio
import tempfile
import unittest
from pathlib import Path

from denaro.application.safemode import SafeModeGuardian
from denaro.infrastructure.sqlite_store import SqliteStateStore


class FakeRam:
    def __init__(self, value=50.0):
        self.value = value

    def __call__(self):
        return self.value


class TestSafeModeGuardian(unittest.TestCase):
    def test_livelli(self):
        ram = FakeRam()
        g = SafeModeGuardian(ram_provider=ram)
        self.assertEqual(g.check(50.0), "nominal")
        self.assertEqual(g.check(72.0), "caution")
        self.assertEqual(g.check(88.0), "safe")
        self.assertEqual(g.check(96.0), "emergency")

    def test_flag_per_livello(self):
        g = SafeModeGuardian(ram_provider=FakeRam())
        g.apply_level("caution")
        self.assertFalse(g.trading_paused)
        self.assertTrue(g.noncritical_throttled)
        g.apply_level("safe")
        self.assertTrue(g.trading_paused)
        self.assertTrue(g.noncritical_throttled)
        g.apply_level("emergency")
        self.assertTrue(g.trading_paused)
        g.apply_level("nominal")
        self.assertFalse(g.trading_paused)
        self.assertFalse(g.noncritical_throttled)

    def test_check_usa_il_provider(self):
        ram = FakeRam(88.0)
        g = SafeModeGuardian(ram_provider=ram)
        self.assertEqual(g.check(), "safe")


class TestSafeModeLoop(unittest.IsolatedAsyncioTestCase):
    async def test_emergency_callback_una_volta(self):
        ram = FakeRam(96.0)
        g = SafeModeGuardian(ram_provider=ram, interval_s=1.0)
        emergencies = []

        async def on_emergency():
            emergencies.append(1)

        g._task = asyncio.create_task(g.run(on_emergency=on_emergency))
        await asyncio.sleep(2.5)
        await g.stop()
        # la callback EMERGENCY scatta una sola volta (flag _emergency_handled)
        self.assertEqual(len(emergencies), 1)

    async def test_propagazione_flag_ai_bot(self):
        # NB: interval_s ha un minimo di 1.0 (design: monitoraggio RAM non aggressivo)
        ram = FakeRam(50.0)
        g = SafeModeGuardian(ram_provider=ram, interval_s=1.0)
        propagated = []

        async def on_change():
            propagated.append(g.trading_paused)

        g._task = asyncio.create_task(g.run(on_change=on_change))
        await asyncio.sleep(1.2)     # nominal (nessun cambio)
        ram.value = 88.0             # -> safe: trading_paused True
        await asyncio.sleep(1.2)
        ram.value = 50.0             # -> nominal: trading_paused False
        await asyncio.sleep(1.2)
        await g.stop()
        self.assertIn(True, propagated)
        self.assertIn(False, propagated)


class TestSqliteStateStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "state.sqlite"

    def tearDown(self):
        self._tmp.cleanup()

    def test_save_load(self):
        s = SqliteStateStore(self.path)
        s.save("ADA/EUR", {"pnl": 1.5, "trades": 3})
        self.assertEqual(s.load("ADA/EUR"), {"pnl": 1.5, "trades": 3})
        s.close()

    def test_wal_mode_attivo(self):
        s = SqliteStateStore(self.path)
        self.assertEqual(s.journal_mode().lower(), "wal")
        s.close()

    def test_load_mancante_ritorna_none(self):
        s = SqliteStateStore(self.path)
        self.assertIsNone(s.load("nope"))
        s.close()

    def test_overwrite(self):
        s = SqliteStateStore(self.path)
        s.save("k", {"v": 1})
        s.save("k", {"v": 2})
        self.assertEqual(s.load("k"), {"v": 2})
        s.close()

    def test_keys(self):
        s = SqliteStateStore(self.path)
        s.save("a", 1)
        s.save("b", 2)
        self.assertEqual(sorted(s.keys()), ["a", "b"])
        s.close()


class TestBotSafemodePause(unittest.IsolatedAsyncioTestCase):
    async def test_trading_paused_blocca_nuovi_ordini(self):
        from denaro.application.orchestrator import BotConfig, BotTask
        from denaro.domain.grid import GridParams, GridPolicy
        from denaro.domain.risk import RiskManager
        from denaro.infrastructure.exchanges.paper import PaperExchange

        ex = PaperExchange("ADA/EUR", capital=300.0)
        ex.update_price(1.0)
        cfg = BotConfig(symbol="ADA/EUR", capital=300.0, levels=3,
                        buy_distance=0.01, profit_target=0.02)
        bot = BotTask(cfg, ex, GridPolicy(GridParams(levels=3, buy_distance=0.01,
                                                     profit_target=0.02)),
                      RiskManager(), price_source=lambda: 1.0)
        await bot.tick()
        self.assertEqual(len(bot.state.open_buys), 3)

        bot.trading_paused = True
        await bot.tick()
        # nessun NUOVO ordine (ma lo stato resta)
        self.assertLessEqual(len(bot.state.open_buys), 3)
        self.assertEqual(len(bot.state.open_buys), 3)  # invariato

        bot.trading_paused = False
        await bot.tick()
        self.assertLessEqual(len(bot.state.open_buys), 3)


if __name__ == "__main__":
    unittest.main()

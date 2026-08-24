#!/usr/bin/env python3
"""Test del Node (M6): paper bots su 1 processo asyncio + parita' engine_paper."""
import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from denaro.denaro_node import NodeApp
from denaro.domain.grid import GridParams, GridPolicy
from denaro.infrastructure.market_data import MarketDataHub


class FakeRest:
    def __init__(self, prices):
        self.prices = prices

    def fetch_ticker(self, symbol):
        return {"last": self.prices[symbol]}


def make_config(data_dir: str, bots=None) -> dict:
    return {
        "data_dir": data_dir,
        "supervisor": {"ram_critical_pct": 0.85, "ram_throttle_pct": 0.70,
                       "cpu_critical_pct": 0.90},
        "bots": bots or [
            {"symbol": "ADA/EUR", "mode": "paper", "capital": 300, "levels": 3,
             "buy_distance": 0.015, "profit_target": 0.02, "tick_interval": 30},
            {"symbol": "SOL/EUR", "mode": "paper", "capital": 100, "levels": 3,
             "buy_distance": 0.01, "profit_target": 0.015, "tick_interval": 30},
            {"symbol": "XRP/EUR", "mode": "paper", "capital": 100, "levels": 3,
             "buy_distance": 0.01, "profit_target": 0.015, "tick_interval": 30},
        ],
    }


async def push_price(hub: MarketDataHub, symbol: str, price: float) -> None:
    """Inietta un prezzo nel hub: aggiorna cache e alimenta i paper exchange."""
    await hub._broadcast(symbol, price)


class TestNodeApp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def _app(self, bots=None) -> NodeApp:
        rest = FakeRest({"ADA/EUR": 1.0, "SOL/EUR": 100.0, "XRP/EUR": 0.5})
        hub = MarketDataHub(ex_rest=rest, ex_pro=None, ws_enabled=False)
        config = make_config(self.dir, bots)
        return NodeApp(config, hub=hub)

    async def test_avvio_3_bot_paper_e_griglia(self):
        app = self._app()
        await app.hub.start()
        for symbol in ("ADA/EUR", "SOL/EUR", "XRP/EUR"):
            bot = app.orchestrator.bots[symbol]
            await push_price(app.hub, symbol, {"ADA/EUR": 1.0,
                                               "SOL/EUR": 100.0,
                                               "XRP/EUR": 0.5}[symbol])
            await bot.tick()
            self.assertEqual(len(bot.state.open_buys), 3, symbol)
            # health file scritto
            health = Path(self.dir) / f"{symbol.replace('/', '_')}_health.json"
            self.assertTrue(health.exists())
        await app.hub.stop()

    async def test_parita_engine_paper_un_ciclo(self):
        """Parita' con la semantica del motore paper v1 su un ciclo completo:
        prezzo 1.00 → griglia → drop 0.97 (fill) → rise 1.01 (sell).
        Il riferimento e' calcolato con le stesse funzioni di dominio."""
        app = self._app(bots=[{"symbol": "ADA/EUR", "mode": "paper", "capital": 300,
                               "levels": 3, "buy_distance": 0.015,
                               "profit_target": 0.02, "tick_interval": 30}])
        await app.hub.start()
        bot = app.orchestrator.bots["ADA/EUR"]

        # riferimento (dominio puro): plan_grid + sell_target + fee paper
        pol = GridPolicy(GridParams(levels=3, buy_distance=0.015,
                                    profit_target=0.02, level_step=0.005))
        plan = pol.plan_grid(price=1.0, capital=300.0)
        ref_pnl = 0.0
        for level in plan:
            sell = pol.sell_target(level.buy_price)
            cost = level.amount * level.buy_price * 1.001
            proceeds = level.amount * sell * 0.999
            ref_pnl += proceeds - cost

        # ciclo reale sul Node
        await push_price(app.hub, "ADA/EUR", 1.0)
        await bot.tick()
        self.assertEqual(len(bot.state.open_buys), 3)
        await push_price(app.hub, "ADA/EUR", 0.97)   # fill tutti i buy
        await bot.tick()                              # piazza i sell
        self.assertEqual(len(bot.state.open_sells), 3)
        await push_price(app.hub, "ADA/EUR", 1.01)   # fill tutti i sell
        await bot.tick()                              # registra PnL
        self.assertEqual(bot.state.total_trades, 3)
        self.assertAlmostEqual(bot.state.total_pnl, ref_pnl, delta=abs(ref_pnl) * 0.05 + 1e-6)

        # equity finale ≈ capitale + PnL (asset azzerati)
        ex = app.orchestrator.bots["ADA/EUR"].ex
        self.assertAlmostEqual(ex.equity(), 300.0 + bot.state.total_pnl, delta=1e-3)
        await app.hub.stop()

    async def test_drop_poi_recupero_senza_sovraesposizione(self):
        app = self._app()
        await app.hub.start()
        bot = app.orchestrator.bots["SOL/EUR"]
        await push_price(app.hub, "SOL/EUR", 100.0)
        await bot.tick()
        # drop sotto tutti i livelli → 3 fill → 3 sell
        await push_price(app.hub, "SOL/EUR", 97.0)
        await bot.tick()
        self.assertLessEqual(len(bot.state.open_buys), 3)
        self.assertEqual(len(bot.state.open_sells), 3)
        # recovery: il mercato risale sopra i target → sell riempiti
        await push_price(app.hub, "SOL/EUR", 102.0)
        await bot.tick()
        self.assertEqual(bot.state.total_trades, 3)
        self.assertGreater(bot.state.total_pnl, 0.0)
        # nessuna sovraesposizione residua
        self.assertLessEqual(len(bot.state.open_buys), 3)
        await app.hub.stop()

    async def test_stop_graceful(self):
        app = self._app()
        await app.hub.start()
        await app.orchestrator.start_all()
        self.assertEqual(len(app.orchestrator.bots), 3)
        await app.orchestrator.stop_all()
        await app.hub.stop()
        # nessun task residuo
        self.assertTrue(all(b._task is None or b._task.done()
                            for b in app.orchestrator.bots.values()))


class TestLiveConfig(unittest.TestCase):
    """Path live M7: struttura config + guardie sulle chiavi (mai hardcoded)."""

    def setUp(self):
        root = Path(__file__).resolve().parent.parent.parent
        self.live_cfg = root / "config" / "node.yaml"

    def test_config_live_struttura(self):
        """Config unificata: paper attivi + live OKX/Kraken ATTIVI (cutover),
        ex-ATLAS disabilitato (attivazione dopo verifica)."""
        from denaro.application.config import load_node_config
        cfg = load_node_config(self.live_cfg)
        self.assertTrue(cfg.hub.ws_enabled)
        modes = {(b.symbol, b.mode) for b in cfg.bots}
        self.assertIn(("ADA/EUR", "paper"), modes)
        self.assertIn(("ADA/EUR", "okx"), modes)
        self.assertIn(("SOL/EUR", "kraken"), modes)
        # i bot live Denaro sono attivi; l'ex-ATLAS resta disabilitato
        live = [b for b in cfg.bots if b.mode != "paper"]
        denaro_live = [b for b in live if b.env_prefix != "ATLAS_"]
        atlas = [b for b in live if b.env_prefix == "ATLAS_"]
        self.assertTrue(all(b.enabled for b in denaro_live))
        self.assertTrue(all(b.enabled is False for b in atlas))
        # health_path verso i path v3.3 (dashboard/Zabbix invariati)
        ada = next(b for b in live if b.symbol == "ADA/EUR" and b.mode == "okx")
        self.assertTrue(ada.health_path.endswith("health/ada.json"))
        # nessuna chiave nel config versionato
        raw = self.live_cfg.read_text(encoding="utf-8")
        self.assertNotIn("api_key", raw)
        self.assertNotIn("secret", raw)
        self.assertNotIn("passphrase", raw)

    def test_build_exchange_chiavi_mancanti(self):
        """Senza env, mode okx/kraken devono fallire con ValueError."""
        from denaro.denaro_node import build_exchange
        with self.assertRaises(ValueError):
            build_exchange({"mode": "okx", "symbol": "ADA/EUR"}, Path("."))
        with self.assertRaises(ValueError):
            build_exchange({"mode": "kraken", "symbol": "SOL/EUR"}, Path("."))

    def test_build_exchange_paper(self):
        from denaro.denaro_node import build_exchange
        ex = build_exchange({"mode": "paper", "symbol": "ADA/EUR",
                             "capital": 300.0}, Path("."))
        self.assertEqual(ex.cash, 300.0)

    def test_build_exchange_modo_sconosciuto(self):
        from denaro.denaro_node import build_exchange
        with self.assertRaises(ValueError):
            build_exchange({"mode": "bybit", "symbol": "X/EUR"}, Path("."))


if __name__ == "__main__":
    unittest.main()

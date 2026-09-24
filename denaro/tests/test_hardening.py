#!/usr/bin/env python3
"""Regressioni di hardening (audit 2026-09).

Ogni test blocca UN difetto riprodotto sull'architettura precedente:

1. la scala di vendita bilaterale si duplicava a ogni tick (2,4,6,8... ordini
   su mercato fermo) → asset bloccato e tempo di tick crescente;
2. lo stato di rischio (peak / baseline daily-weekly / CB / storico trade)
   era ricostruito da zero a ogni restart → il circuit breaker si azzerava;
3. 'KrakenPermanentError' non era importato → 'NameError' sul ramo di cancel;
4. 'Policy.on_fill' non veniva mai invocato → l'inventario delle policy
   stateful (VAGR/IRMR/MinCapture) restava a zero per sempre;
5. '_guard_equity' faceva I/O sincrono sul thread dell'event loop;
6. il ResourceSupervisor non rallentava mai i tick (metriche sempre a zero e
   'adjusted_interval' mai chiamato);
7. la valuta di quotazione era hardcoded "EUR" nella lettura del balance.
"""
import asyncio
import inspect
import json
import tempfile
import time
import unittest
from pathlib import Path

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.application.supervisor import NodeMetrics, ResourceSupervisor
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager
from denaro.domain.types import CBState, CoreState
from denaro.infrastructure.exchanges.errors import PermanentExchangeError
from denaro.infrastructure.storage import AtomicFile, Journal
from denaro.tests.test_orchestrator import FakeExchange


def _cfg(tmp: Path, **kw) -> BotConfig:
    base = dict(symbol="SOL/EUR", capital=30.0, levels=3,
                buy_distance=0.01, profit_target=0.02,
                state_path=tmp / "state.json",
                risk_state_path=tmp / "risk.json",
                journal_path=tmp / "trades.jsonl",
                health_path=tmp / "health.json")
    base.update(kw)
    return BotConfig(**base)


def _grid(levels=3, **kw) -> GridPolicy:
    params = dict(levels=levels, buy_distance=0.01, profit_target=0.02,
                  level_step=0.005, retarget_factor=1.5)
    params.update(kw)
    return GridPolicy(GridParams(**params))


class _Base(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def make(self, ex, policy=None, now=None, **kw) -> BotTask:
        return BotTask(_cfg(self.dir, **kw), ex,
                       policy or _grid(kw.get("levels", 3)),
                       RiskManager(daily_loss_limit=0.05,
                                   max_drawdown_limit=0.30),
                       now=now or (lambda: 1_000_000.0))


# --- 1. scala di vendita idempotente -----------------------------------------

class TestLadderIdempotence(_Base):
    async def test_open_sells_do_not_grow_on_a_flat_market(self):
        """Su mercato fermo la scala resta a 'sell_levels', non cresce."""
        ex = FakeExchange(price=100.0, free_quote=30.0)
        ex.asset = 0.6
        bot = self.make(ex, _grid(sell_levels=2, sell_distance=0.02,
                                  sell_step=0.01))
        counts = []
        for _ in range(8):
            await bot.tick()
            counts.append(len(bot.state.open_sells))
        # prima del fix era [2, 4, 6, 8, 10, 12, 14, 16]
        self.assertEqual(counts, [2] * 8, f"scala duplicata: {counts}")

    async def test_ladder_survives_a_market_move_without_duplicating(self):
        """Anche se il mercato si muove (i prezzi non combaciano piu'), il
        budget per livello impedisce di superare 'sell_levels'."""
        ex = FakeExchange(price=100.0, free_quote=30.0)
        ex.asset = 0.6
        bot = self.make(ex, _grid(sell_levels=3, sell_distance=0.02,
                                  sell_step=0.01))
        for price in (100.0, 100.4, 100.9, 101.3, 100.7):
            ex.market_trade(price)
            await bot.tick()
            self.assertLessEqual(
                len(bot.state.open_sells), 3,
                f"scala oltre il budget a {price}: {len(bot.state.open_sells)}")

    async def test_ladder_not_duplicated_after_restart(self):
        """Gli ordini ricaricati dall'exchange non hanno 'kind': la scala non
        deve raddoppiare al primo tick dopo un riavvio."""
        ex = FakeExchange(price=100.0, free_quote=30.0)
        ex.asset = 0.6
        policy = lambda: _grid(sell_levels=2, sell_distance=0.02, sell_step=0.01)
        bot = self.make(ex, policy())
        await bot.tick()
        before = len(bot.state.open_sells)
        self.assertEqual(before, 2)

        restarted = self.make(ex, policy())          # nuovo processo
        self.assertEqual(len(restarted.state.open_sells), 2)  # da exchange
        for _ in range(4):
            await restarted.tick()
        self.assertLessEqual(len(restarted.state.open_sells), 2,
                             "la scala e' stata duplicata dopo il restart")


# --- 2. persistenza dello stato di rischio ------------------------------------

class TestRiskStatePersistence(_Base):
    async def test_peak_daily_weekly_and_cb_survive_a_restart(self):
        ex = FakeExchange(price=100.0)
        bot = self.make(ex)
        bot.risk_state.trade_results.extend([1.0, -0.5, 2.0, 1.5, -0.2, 3.0])
        for _ in range(6):
            bot.risk_state.perf.update(0.01)
        bot.risk_state.perf.consecutive_losses = 3
        bot.risk_state.peak_capital = 44.0
        bot.risk_state.day_start_capital = 41.0
        bot.risk_state.week_start_capital = 39.0
        bot.risk_state.cb.state = CBState.HALF_OPEN
        bot.risk_state.cb.reason = "consecutive_losses_3"
        bot._save_state()

        again = self.make(ex)
        self.assertAlmostEqual(again.risk_state.peak_capital, 44.0)
        self.assertAlmostEqual(again.risk_state.day_start_capital, 41.0)
        self.assertAlmostEqual(again.risk_state.week_start_capital, 39.0)
        self.assertEqual(len(again.risk_state.trade_results), 6)
        self.assertEqual(again.risk_state.perf.consecutive_losses, 3)
        self.assertIs(again.risk_state.cb.state, CBState.HALF_OPEN)
        self.assertEqual(again.risk_state.cb.reason, "consecutive_losses_3")

    async def test_baseline_not_poisoned_by_dataclass_defaults(self):
        """Con un file di rischio assente, la baseline DEVE essere il capitale
        del bot (30.0), non il default 100.0 di CoreState."""
        ex = FakeExchange(price=100.0)
        bot = self.make(ex)
        self.assertAlmostEqual(bot.risk_state.week_start_capital, 30.0)
        self.assertAlmostEqual(bot.risk_state.day_start_capital, 30.0)

    async def test_corrupt_cb_state_fails_safe_open(self):
        """Uno stato CB illeggibile non deve DISARMARE il breaker."""
        AtomicFile(self.dir / "risk.json").write_json({"cb": {"state": "BOGUS"}})
        bot = self.make(FakeExchange(price=100.0))
        self.assertIs(bot.risk_state.cb.state, CBState.OPEN)

    async def test_corrupt_risk_file_does_not_crash_bot_construction(self):
        (self.dir / "risk.json").write_text("{not json at all", encoding="utf-8")
        bot = self.make(FakeExchange(price=100.0))
        self.assertAlmostEqual(bot.risk_state.peak_capital, 30.0)

    def test_core_state_codec_round_trip_is_bounded(self):
        s = CoreState(initial_capital=12.0, current_capital=12.0,
                      peak_capital=12.0, day_start_capital=12.0,
                      week_start_capital=12.0)
        s.trade_results.extend([0.1] * 900)
        data = s.to_dict()
        json.dumps(data)  # deve essere JSON-serializzabile
        self.assertEqual(len(data["trade_results"]), 500)  # bound di memoria


# --- 3. errori permanenti sul cancel ------------------------------------------

class _PermanentCancelExchange(FakeExchange):
    def cancel_order(self, oid, symbol):
        raise PermanentExchangeError("EOrder:Unknown order")


class TestPermanentCancelError(_Base):
    async def test_tick_survives_a_permanent_cancel_error(self):
        """Prima: 'KrakenPermanentError' non importato → NameError nel tick."""
        ex = _PermanentCancelExchange(price=100.0, free_quote=30.0)
        bot = self.make(ex)
        await bot.tick()
        self.assertEqual(len(bot.state.open_buys), 3)

        ex.market_trade(103.0)      # i buy a 99/98.5/98 diventano stantii
        await bot.tick()            # non deve sollevare (prima: NameError)
        # gli ordini "permanenti" sono stati rimossi dallo STATO del bot: non
        # restano appesi a bloccare l'invariante di griglia.
        self.assertLessEqual(len(bot.state.open_buys), 3)
        self.assertNotIn("o1", bot.state.open_buys)
        self.assertNotIn("o2", bot.state.open_buys)
        self.assertNotIn("o3", bot.state.open_buys)

    async def test_okx_and_kraken_errors_share_the_common_base(self):
        from denaro.infrastructure.exchanges.kraken import KrakenPermanentError
        from denaro.infrastructure.exchanges.okx import OKXPermanentError
        for cls in (KrakenPermanentError, OKXPermanentError):
            self.assertTrue(issubclass(cls, PermanentExchangeError))


# --- 4. on_fill verso la policy ------------------------------------------------

class _SpyPolicy(GridPolicy):
    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fills = []

    def on_fill(self, order_id, side, price, size):
        self.fills.append((order_id, side, price, size))


class TestPolicyFillNotification(_Base):
    async def test_buy_fill_is_notified_to_the_policy(self):
        ex = FakeExchange(price=100.0)
        spy = _SpyPolicy(GridParams(levels=3, buy_distance=0.01,
                                    profit_target=0.02, level_step=0.005))
        bot = self.make(ex, spy)
        await bot.tick()
        self.assertEqual(spy.fills, [])
        ex.market_trade(98.8)       # riempie il buy a ~99
        await bot.tick()
        self.assertEqual(len(spy.fills), 1)
        oid, side, price, size = spy.fills[0]
        self.assertEqual(side, "buy")
        self.assertGreater(size, 0)
        self.assertGreater(price, 0)

    async def test_sell_fill_is_notified_to_the_policy(self):
        ex = FakeExchange(price=100.0)
        spy = _SpyPolicy(GridParams(levels=3, buy_distance=0.01,
                                    profit_target=0.02, level_step=0.005))
        bot = self.make(ex, spy)
        await bot.tick()
        ex.market_trade(98.8)
        await bot.tick()
        ex.market_trade(101.5)      # riempie il TP sell
        await bot.tick()
        self.assertEqual([s for _, s, _, _ in spy.fills], ["buy", "sell"])

    async def test_alternative_policy_signatures_are_tolerated(self):
        """AdaptiveVolGrid usa 'on_fill(side, price, qty, fee, ts)': il
        dispatcher deve adattarsi senza sollevare."""
        inner = GridPolicy(GridParams(levels=3, buy_distance=0.01,
                                      profit_target=0.02, level_step=0.005))

        class _Alt:
            """Policy con la firma "nuova" di AdaptiveVolGrid."""

            def __init__(self):
                self.calls = []

            def sell_target(self, e):
                return inner.sell_target(e)

            def decide(self, *a, **k):
                return inner.decide(*a, **k)

            def on_fill(self, side, price, qty, fee, ts):
                self.calls.append((side, price, qty))

        ex = FakeExchange(price=100.0)
        alt = _Alt()
        bot = self.make(ex, alt)
        await bot.tick()                       # piazza i buy
        ex.market_trade(98.8)
        await bot.tick()
        self.assertEqual([c[0] for c in alt.calls], ["buy"])

    async def test_a_raising_policy_on_fill_does_not_break_the_tick(self):
        class _Bad(_SpyPolicy):
            def on_fill(self, *a, **k):
                raise RuntimeError("policy rotta")

        ex = FakeExchange(price=100.0)
        bot = self.make(ex, _Bad(GridParams(levels=3, buy_distance=0.01,
                                            profit_target=0.02,
                                            level_step=0.005)))
        await bot.tick()
        ex.market_trade(98.8)
        await bot.tick()            # non deve sollevare
        self.assertEqual(bot.state.total_trades, 0)


# --- 5. l'I/O non blocca l'event loop ------------------------------------------

class _SlowBalanceExchange(FakeExchange):
    def __init__(self, *a, delay=0.25, **kw):
        super().__init__(*a, **kw)
        self.delay = delay
        self.balance_calls = 0

    def fetch_balance(self):
        self.balance_calls += 1
        time.sleep(self.delay)
        return super().fetch_balance()


class TestEventLoopIsNotBlocked(_Base):
    async def test_guard_equity_is_a_coroutine(self):
        self.assertTrue(inspect.iscoroutinefunction(BotTask._guard_equity))

    async def test_slow_balance_fetch_does_not_freeze_other_tasks(self):
        """La guardia equity deve fare I/O in 'to_thread': mentre attende, gli
        altri task del nodo devono continuare a girare."""
        ex = _SlowBalanceExchange(price=100.0, delay=0.30)
        bot = self.make(ex)
        # Lettura SPORCA per eccesso (capitale 30 → 5000 e' oltre 30x): e' il
        # caso che entra nel ramo lento di `_guard_equity`, quello che chiama
        # `fetch_balance` (qui rallentato di proposito). NB: non si usa piu' 0.0
        # — dal difetto A (2026-09-25) uno zero LETTO e' un conto vuoto, cioe'
        # lo stato `non_finanziato`, che salta il tick PRIMA di qualunque I/O:
        # il test non misurerebbe piu' nulla (visto: il tick diventava istantaneo
        # e l'heartbeat avanzava di 2 soli passi).
        bot._get_equity = lambda: 5000.0   # fuori range → entra nel ramo lento

        ticks = {"n": 0}
        stop = asyncio.Event()

        async def heartbeat():
            while not stop.is_set():
                ticks["n"] += 1
                await asyncio.sleep(0.01)

        hb = asyncio.create_task(heartbeat())
        await bot.tick()
        stop.set()
        await hb
        # con I/O sincrono sul loop il heartbeat NON potrebbe avanzare
        self.assertGreater(ticks["n"], 5,
                           f"event loop bloccato (heartbeat={ticks['n']})")


# --- 6. throttling del supervisore --------------------------------------------

class TestSupervisorThrottling(_Base):
    async def test_tick_interval_scales_under_ram_pressure(self):
        ex = FakeExchange(price=100.0)
        bot = self.make(ex, tick_interval=30.0)
        self.assertAlmostEqual(bot._tick_interval(), 30.0)
        bot._supervisor = ResourceSupervisor(
            get_metrics=lambda: NodeMetrics(rss_mb=900.0, ram_total_mb=1000.0))
        self.assertGreater(bot._tick_interval(), 30.0)

    async def test_default_metrics_read_real_ram(self):
        st = ResourceSupervisor().check()
        self.assertIn(st.level, ("nominal", "throttled", "critical"))

    async def test_orchestrator_injects_the_supervisor_into_bots(self):
        from denaro.application.orchestrator import TradeOrchestrator
        sup = ResourceSupervisor()
        orch = TradeOrchestrator(supervisor=sup)
        bot = self.make(FakeExchange(price=100.0))
        orch.add_bot(bot)
        await orch.start_all()
        try:
            self.assertIs(bot._supervisor, sup)
        finally:
            await orch.stop_all()


# --- 7. valuta di quotazione ---------------------------------------------------

class TestQuoteCurrency(_Base):
    async def test_non_eur_quote_bot_reads_the_right_balance(self):
        ex = FakeExchange(price=100.0, free_quote=5.0, quote="USDT")
        bot = self.make(ex, symbol="SOL/USDT")
        await bot.tick()
        health = json.loads((self.dir / "health.json").read_text())
        self.assertAlmostEqual(health["free_quote"], 5.0,
                               msg="la valuta di quotazione non e' USDT")

    async def test_quote_property(self):
        ex = FakeExchange(price=100.0)
        self.assertEqual(self.make(ex, symbol="SOL/USDT")._quote, "USDT")
        self.assertEqual(self.make(ex, symbol="SOL/EUR")._quote, "EUR")


# --- 8. VAGR: doppio feed e kill-switch ---------------------------------------

class TestVagrDefects(unittest.TestCase):
    def _cfg(self):
        from denaro.domain.vagr import VagrConfig
        return VagrConfig(symbol="SOL/EUR", capital_eur=100.0,
                          atr_window=50, kill_switch_drawdown_pct=0.02,
                          max_daily_loss_pct=0.03)

    def test_decide_does_not_double_feed_the_welford_atr(self):
        """L'orchestrator chiama \`on_price\` e poi \`decide\` (che la richiamava):
        il conteggio dei tick e l'ATR venivano alimentati DUE volte per tick."""
        from denaro.domain.vagr import VagrPolicy
        p = VagrPolicy(self._cfg())
        prices = [100.0 + 0.2 * (i % 7) for i in range(40)]
        for px in prices:
            p.on_price(px)                 # come fa l'orchestrator
            p.decide(px, {}, {}, 100.0, 100.0, 100.0, float(len(prices)))
        self.assertEqual(p.ticks, len(prices))

    def test_tick_is_ingested_exactly_once_with_or_without_on_price(self):
        from denaro.domain.vagr import VagrPolicy
        # percorso orchestrator: on_price + decide -> 1 tick
        a = VagrPolicy(self._cfg())
        a.on_price(100.0)
        a.decide(100.0, {}, {}, 0.0, 100.0, 0.0, 0.0)
        self.assertEqual(a.ticks, 1)
        # percorso decide-only (test/backtest): sempre 1 tick
        b = VagrPolicy(self._cfg())
        b.decide(100.0, {}, {}, 0.0, 100.0, 0.0, 0.0)
        self.assertEqual(b.ticks, 1)
        # due on_price consecutivi senza decide = due tick reali
        c = VagrPolicy(self._cfg())
        c.on_price(100.0)
        c.on_price(101.0)
        self.assertEqual(c.ticks, 2)

    def test_kill_switch_fires_on_realized_losses(self):
        """Prima \`_daily_loss\` restava 0.0 per sempre → kill-switch morto."""
        from denaro.domain.vagr import VagrPolicy
        p = VagrPolicy(self._cfg())
        p.on_fill("b1", "buy", 100.0, 1.0)
        p.on_fill("s1", "sell", 96.0, 1.0)      # -4.0 = 4% > 2% di 100
        d = p.decide(96.0, {}, {}, 0.0, 100.0, 0.0, 0.0)
        self.assertTrue(p.kill_switched)
        self.assertIn("kill-switch", d.reason)

    def test_kill_switch_rearms_on_a_new_utc_day(self):
        from denaro.domain.vagr import VagrPolicy
        p = VagrPolicy(self._cfg())
        p.on_fill("b1", "buy", 100.0, 1.0)
        p.on_fill("s1", "sell", 96.0, 1.0)
        p.decide(96.0, {}, {}, 0.0, 100.0, 0.0, 1000.0)
        self.assertTrue(p.kill_switched)
        p.decide(96.0, {}, {}, 0.0, 100.0, 0.0, 1000.0 + 86400.0)
        self.assertFalse(p.kill_switched)

    def test_inventory_tracks_fills(self):
        from denaro.domain.vagr import VagrPolicy
        p = VagrPolicy(self._cfg())
        p.on_fill("b1", "buy", 100.0, 2.0)
        self.assertAlmostEqual(p.inventory, 200.0)
        p.on_fill("s1", "sell", 105.0, 2.0)
        self.assertAlmostEqual(p.inventory, 0.0)


# --- 9. percorso EMERGENCY del SafeMode ---------------------------------------

class TestEmergencyPath(unittest.TestCase):
    def test_on_emergency_completes_and_signals_shutdown(self):
        """Prima \`_on_emergency\` sollevava NameError su \`time.time()\`: il
        guardian lo inghiottiva nel suo except e \`self._stop.set()\` non veniva
        MAI chiamato → nessuno shutdown controllato sotto pressione di RAM."""
        import asyncio
        from denaro.denaro_node import NodeApp

        app = NodeApp.__new__(NodeApp)          # senza costruire hub/exchange
        app.orchestrator = type("O", (), {"bots": {}})()
        app.sqlite = type("S", (), {"save": lambda self, k, v: None,
                                    "close": lambda self: None})()

        async def go():
            app._stop = asyncio.Event()
            await app._on_emergency()
            return app._stop.is_set()

        self.assertTrue(asyncio.run(go()),
                        "l'emergency non ha segnalato lo shutdown")


if __name__ == "__main__":
    unittest.main()
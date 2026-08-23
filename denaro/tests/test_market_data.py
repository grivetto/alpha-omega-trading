#!/usr/bin/env python3
"""Test MarketDataHub: broadcast, cache, fallback WS→REST (feed fake)."""
import asyncio
import unittest

from denaro.infrastructure.market_data import MarketDataHub


class FakeRest:
    def __init__(self, prices):
        self.prices = prices
        self.calls = 0

    def fetch_ticker(self, symbol):
        self.calls += 1
        return {"last": self.prices[symbol]}


class FakePro:
    """ccxt.pro fake: watch_ticker come async generator."""

    def __init__(self, feed):
        self.feed = feed  # list of (symbol, price)
        self.started = False

    async def watch_ticker(self, symbol):
        self.started = True
        for sym, price in self.feed:
            if sym == symbol:
                yield {"last": price}
        # esaurito: simula disconnessione sollevando
        raise ConnectionError("ws down")


class FakeHandler:
    def __init__(self):
        self.received = []

    async def __call__(self, symbol, price):
        self.received.append((symbol, price))


class TestMarketDataHub(unittest.IsolatedAsyncioTestCase):
    async def test_ws_broadcast_e_cache(self):
        hub = MarketDataHub(
            ex_rest=FakeRest({"SOL/EUR": 100.0}),
            ex_pro=FakePro([("SOL/EUR", 101.0), ("SOL/EUR", 102.0)]),
            ws_enabled=True, price_ttl=30.0)
        await hub.start()
        handler = FakeHandler()
        hub.subscribe("SOL/EUR", handler)
        # lascia girare il canale WS (2 tick)
        await asyncio.sleep(0.2)
        await hub.stop()

        self.assertEqual(len(handler.received), 2)
        self.assertEqual(handler.received[0], ("SOL/EUR", 101.0))
        self.assertEqual(handler.received[1], ("SOL/EUR", 102.0))
        # cache aggiornata dal broadcast
        self.assertEqual(hub.price("SOL/EUR"), 102.0)

    async def test_cache_scaduta_ritorna_none(self):
        hub = MarketDataHub(ex_rest=FakeRest({"SOL/EUR": 1.0}), ex_pro=None,
                            ws_enabled=False, price_ttl=5.0)
        hub._cache["SOL/EUR"] = (100.0, 0.0)  # vecchio
        self.assertIsNone(hub.price("SOL/EUR"))

    async def test_ws_giu_fallback_rest(self):
        """Dopo la disconnessione del WS, il canale passa a REST."""

        class FakeProDown:
            async def watch_ticker(self, symbol):
                if False:
                    yield  # pragma: no cover - rende async generator
                raise ConnectionError("ws down")

        hub = MarketDataHub(
            ex_rest=FakeRest({"SOL/EUR": 50.0}),
            ex_pro=FakeProDown(),
            ws_enabled=True, poll_interval=0.05, price_ttl=30.0,
            ws_max_retries=1, ws_retry_base_s=0.01)
        await hub.start()
        handler = FakeHandler()
        hub.subscribe("SOL/EUR", handler)
        # 1 retry fallito → fallback REST (poll 0.05)
        await asyncio.sleep(0.3)
        await hub.stop()
        self.assertGreaterEqual(len(handler.received), 2)
        self.assertTrue(all(p == 50.0 for _, p in handler.received))

    async def test_solo_rest_con_ws_disabilitato(self):
        rest = FakeRest({"SOL/EUR": 42.0})
        hub = MarketDataHub(ex_rest=rest, ex_pro=None, ws_enabled=False,
                            poll_interval=0.05, price_ttl=30.0)
        await hub.start()
        handler = FakeHandler()
        hub.subscribe("SOL/EUR", handler)
        await asyncio.sleep(0.15)
        await hub.stop()
        self.assertGreaterEqual(len(handler.received), 2)
        self.assertTrue(all(p == 42.0 for _, p in handler.received))
        self.assertGreater(rest.calls, 0)

    async def test_get_price_usa_cache_o_fetch(self):
        rest = FakeRest({"SOL/EUR": 99.0})
        hub = MarketDataHub(ex_rest=rest, ex_pro=None, ws_enabled=False)
        p = await hub.get_price("SOL/EUR")
        self.assertEqual(p, 99.0)
        # seconda chiamata: cache fresca, nessun fetch extra
        calls_before = rest.calls
        p2 = await hub.get_price("SOL/EUR")
        self.assertEqual(p2, 99.0)
        self.assertEqual(rest.calls, calls_before)

    async def test_unsubscribe_chiude_il_canale(self):
        hub = MarketDataHub(ex_rest=FakeRest({"SOL/EUR": 1.0}), ex_pro=None,
                            ws_enabled=False, poll_interval=0.05)
        await hub.start()
        h1, h2 = FakeHandler(), FakeHandler()
        hub.subscribe("SOL/EUR", h1)
        hub.subscribe("SOL/EUR", h2)
        hub.unsubscribe("SOL/EUR", h1)
        await asyncio.sleep(0.1)
        await hub.stop()
        self.assertEqual(h1.received, [])
        self.assertGreaterEqual(len(h2.received), 1)


if __name__ == "__main__":
    unittest.main()

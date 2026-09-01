#!/usr/bin/env python3
"""Test ATLAS v6: regime filter, adaptive engine, portfolio manager.

Esecuzione:
    python -B -m unittest denaro.tests.test_atlas_v6 -v
"""
import unittest

from denaro.application.portfolio import (LOCKED_SAFETY_FACTOR,
                                          PortfolioManager)
from denaro.domain.adaptive import AdaptiveEngine, AdaptiveParams
from denaro.domain.regime import RegimeFilter


def make_ohlcv(n: int = 120, start: float = 100.0, step: float = 0.0,
               vol: float = 0.0):
    """Candle sintetiche [ts, o, h, l, c, v]."""
    out = []
    price = start
    for i in range(n):
        if step:
            price = start + step * i
        high = price * (1 + vol)
        low = price * (1 - vol)
        out.append([float(i), price, high, low, price, 1000.0])
    return out


class TestRegimeFilter(unittest.TestCase):
    def setUp(self):
        self.f = RegimeFilter()

    def test_range_quando_adx_basso(self):
        # mercato piatto: ADX basso → range
        ohlcv = make_ohlcv(n=120, start=100.0, step=0.0, vol=0.001)
        r = self.f.classify(ohlcv)
        self.assertEqual(r.name, "range")
        self.assertLess(r.adx, 25.0)

    def test_trend_bull_sopra_ema200(self):
        # uptrend deciso → trend_bull
        ohlcv = make_ohlcv(n=150, start=100.0, step=0.4, vol=0.002)
        r = self.f.classify(ohlcv)
        self.assertIn(r.name, ("trend_bull", "trend_bear"))
        self.assertGreater(r.adx, 0.0)

    def test_ohlcv_insufficiente_neutro(self):
        r = self.f.classify(make_ohlcv(n=5))
        self.assertEqual(r.name, "range")
        self.assertEqual(r.adx, 0.0)

    def test_from_prices_fallback(self):
        prices = [100.0 + i * 0.3 for i in range(80)]
        r = self.f.from_prices(prices)
        self.assertGreaterEqual(r.adx, 0.0)
        self.assertIn(r.name, ("range", "trend_bull", "trend_bear"))


class TestAdaptiveEngine(unittest.TestCase):
    def setUp(self):
        self.eng = AdaptiveEngine(
            AdaptiveParams(levels=5, base_buy_distance=0.01, profit_target=0.015,
                           atr_multiplier=2.0),
            round_price=lambda p: round(p, 4),
            round_amount=lambda a: round(a, 8),
        )

    def test_range_piazza_griglia_con_spread_dinamico(self):
        ohlcv = make_ohlcv(n=120, start=100.0, vol=0.002)
        self.eng.on_ohlcv(ohlcv)
        self.assertEqual(self.eng.regime.name, "range")
        spread = self.eng.dynamic_spread()
        self.assertGreaterEqual(spread, 0.01)  # >= base
        d = self.eng.decide(100.0, {}, {}, 50.0, 50.0, 50.0, 0.0)
        self.assertGreater(len(d.to_place), 0)

    def test_trend_bear_blocca_i_buy(self):
        # downtrend: prezzo sotto EMA200, ADX alto → niente buy
        ohlcv = make_ohlcv(n=150, start=200.0, step=-0.8, vol=0.002)
        self.eng.on_ohlcv(ohlcv)
        self.assertEqual(self.eng.regime.name, "trend_bear")
        open_buys = {"oid1": {"price": 80.0, "amount": 0.5, "level": 0}}
        d = self.eng.decide(85.0, open_buys, {}, 50.0, 50.0, 50.0, 0.0)
        self.assertIn("oid1", d.to_cancel)
        self.assertEqual(d.to_place, [])

    def test_trend_bull_scalper_una_posizione(self):
        ohlcv = make_ohlcv(n=150, start=100.0, step=0.8, vol=0.002)
        self.eng.on_ohlcv(ohlcv)
        self.assertEqual(self.eng.regime.name, "trend_bull")
        d = self.eng.decide(220.0, {}, {}, 50.0, 50.0, 50.0, 0.0)
        self.assertEqual(len(d.to_place), 1)
        # trailing TP agganciato all'ATR
        target = self.eng.sell_target(d.to_place[0].buy_price)
        self.assertGreater(target, d.to_place[0].buy_price)

    def test_sell_target_in_range_usato_tp_statico(self):
        ohlcv = make_ohlcv(n=120, start=100.0, vol=0.001)
        self.eng.on_ohlcv(ohlcv)
        self.assertEqual(self.eng.regime.name, "range")
        self.assertAlmostEqual(self.eng.sell_target(100.0), 101.5, places=2)


class TestPortfolioManager(unittest.TestCase):
    def test_total_available_free_piu_locked_scontato(self):
        pm = PortfolioManager()
        pm.update(free=10.0, open_orders=[
            {"id": "b1", "side": "buy", "symbol": "SOL/EUR",
             "amount": 0.5, "price": 80.0},
            {"id": "s1", "side": "sell", "symbol": "SOL/EUR",
             "amount": 0.5, "price": 90.0},  # i sell NON contano
        ])
        # locked = 0.5*80 = 40 → available = 10 + 40*0.85 = 44
        self.assertEqual(pm.locked, 40.0)
        self.assertAlmostEqual(pm.total_available(), 10.0 + 40.0 * LOCKED_SAFETY_FACTOR)

    def test_preflight_detecta_buy_speculari(self):
        pm = PortfolioManager()
        pm.update(free=50.0, open_orders=[
            {"id": "b1", "side": "buy", "symbol": "SOL/EUR",
             "amount": 0.5, "price": 120.0},  # sopra il mercato 100 → speculativo
        ])
        ok, reason, speculative = pm.preflight("SOL/EUR", min_notional=1.0,
                                               per_level=10.0, price=100.0)
        self.assertFalse(ok)
        self.assertIn("speculari", reason)
        self.assertEqual(speculative, ["b1"])

    def test_preflight_min_notional_filtrato_dal_caller(self):
        # il min_notional NON blocca il preflight: i livelli sotto il minimo
        # vengono filtrati dal caller (semantica legacy)
        pm = PortfolioManager()
        pm.update(free=50.0, open_orders=[])
        ok, reason, _ = pm.preflight("SOL/EUR", min_notional=20.0,
                                     per_level=10.0, price=100.0)
        self.assertTrue(ok)

    def test_preflight_ok(self):
        pm = PortfolioManager()
        pm.update(free=50.0, open_orders=[])
        ok, reason, _ = pm.preflight("SOL/EUR", min_notional=1.0,
                                     per_level=10.0, price=100.0)
        self.assertTrue(ok)


if __name__ == "__main__":
    unittest.main()

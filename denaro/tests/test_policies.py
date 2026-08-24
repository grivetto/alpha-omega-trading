#!/usr/bin/env python3
"""Test delle policy multi-strategia — momentum e mean-reversion (pure).

Esecuzione:
    python -B -m unittest denaro.tests.test_policies -v
"""
import unittest

from denaro.domain.meanrev import MeanReversionParams, MeanReversionPolicy
from denaro.domain.momentum import MomentumParams, MomentumPolicy


def rsi_series(n: int, start: float, step: float, base: float = 100.0) -> list:
    """Serie sintetica di prezzi: base + n passi di `step` a partire da start."""
    return [round(base + start + i * step, 6) for i in range(n)]


def seed(policy, prices: list) -> None:
    for p in prices:
        policy.on_price(p)


class TestMomentumPolicy(unittest.TestCase):

    def setUp(self):
        self.pol = MomentumPolicy(
            MomentumParams(history=40, min_history=21),
            round_price=lambda p: round(p, 4),
            round_amount=lambda a: round(a, 8),
        )

    def test_senza_storico_nessun_segnale(self):
        d = self.pol.decide(100.0, {}, {}, 1000.0, 100.0, 100.0, 0.0)
        self.assertEqual(d.to_place, [])
        self.assertIn("neutro", d.reason)

    def test_trend_up_piazza_un_buy(self):
        # uptrend lento e costante → EMA fast > slow
        seed(self.pol, rsi_series(60, 0.0, 0.5))
        d = self.pol.decide(price=130.0, open_buys={}, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertEqual(len(d.to_place), 1)
        level = d.to_place[0]
        # entry = prezzo × (1 - slip)
        self.assertAlmostEqual(level.buy_price, 130.0 * (1 - 0.002), places=3)
        self.assertGreater(level.amount, 0)

    def test_trend_down_cancella_i_buy(self):
        seed(self.pol, rsi_series(60, 60.0, -0.5))
        open_buys = {"oid1": {"price": 90.0, "amount": 0.5, "level": 0}}
        d = self.pol.decide(price=70.0, open_buys=open_buys, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertIn("oid1", d.to_cancel)
        self.assertEqual(d.to_place, [])

    def test_gia_posizione_aperta_non_raddoppia(self):
        seed(self.pol, rsi_series(60, 0.0, 0.5))
        open_buys = {"oid1": {"price": 120.0, "amount": 0.5, "level": 0}}
        d = self.pol.decide(price=130.0, open_buys=open_buys, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertEqual(d.to_place, [])

    def test_sell_target_sopra_entry(self):
        seed(self.pol, rsi_series(60, 0.0, 0.5))
        target = self.pol.sell_target(100.0)
        self.assertGreater(target, 100.0)
        self.assertAlmostEqual(target, 100.0 * 1.02, places=3)


class TestMeanReversionPolicy(unittest.TestCase):

    def setUp(self):
        self.pol = MeanReversionPolicy(
            MeanReversionParams(history=40, min_history=21),
            round_price=lambda p: round(p, 4),
            round_amount=lambda a: round(a, 8),
        )

    def test_nessun_setup_in_mercato_flat(self):
        # prezzi piatti → RSI neutro → nessun buy
        seed(self.pol, [100.0] * 40)
        d = self.pol.decide(100.0, {}, {}, 50.0, 50.0, 50.0, 0.0)
        self.assertEqual(d.to_place, [])

    def test_oversold_piazza_buy(self):
        # discesa moderata (~4%, sotto max_dev 5%) e stabilizzazione in basso
        # → RSI oversold, prezzo < media → buy
        prices = rsi_series(30, 0.0, 0.0)          # 100 flat
        prices += [98.0, 97.0, 96.5, 96.2, 96.0]   # discesa dolce
        prices += [96.0] * 10                       # stabilizzazione bassa
        seed(self.pol, prices)
        d = self.pol.decide(price=96.0, open_buys={}, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertEqual(len(d.to_place), 1)
        level = d.to_place[0]
        self.assertAlmostEqual(level.buy_price, 96.0 * (1 - 0.001), places=3)

    def test_deviazione_estrema_skip(self):
        # caduta devastante (piu' del max_dev) → probabile trend, non reversion
        prices = rsi_series(30, 0.0, 0.0)
        prices += [80.0, 79.0, 78.0, 77.0, 76.0]
        seed(self.pol, prices)
        d = self.pol.decide(price=76.0, open_buys={}, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertEqual(d.to_place, [])

    def test_posizione_aperta_aspetta(self):
        seed(self.pol, [100.0] * 30 + [92.0] * 10)
        open_buys = {"oid1": {"price": 92.0, "amount": 0.5, "level": 0}}
        d = self.pol.decide(price=92.0, open_buys=open_buys, open_sells={},
                            cash=50.0, capital_config=50.0,
                            free_balance=50.0, now=0.0)
        self.assertEqual(d.to_place, [])

    def test_sell_target_sopra_entry(self):
        target = self.pol.sell_target(92.0)
        self.assertAlmostEqual(target, 92.0 * 1.015, places=3)


if __name__ == "__main__":
    unittest.main()

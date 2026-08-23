#!/usr/bin/env python3
"""Test PaperExchange: semantica engine_paper (fee 0.1%/lato, fill su cross)."""
import unittest

from denaro.infrastructure.exchanges.paper import PaperExchange


class TestPaperExchange(unittest.TestCase):
    def test_buy_fill_con_fee(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        ex.update_price(100.0)
        ex.create_limit_order("SOL/EUR", "buy", amount=1.0, price=99.0)
        ex.update_price(98.5)   # sotto il livello → fill
        self.assertEqual(len(ex.fill_events), 1)
        self.assertEqual(ex.fill_events[0]["side"], "buy")
        # cost = amount × price × (1 + fee) = 1.0 × 99 × 1.001
        self.assertAlmostEqual(ex.cash, 100.0 - 99.0 * 1.001, places=6)
        self.assertAlmostEqual(ex.asset, 1.0, places=9)

    def test_sell_fill_con_fee(self):
        ex = PaperExchange("SOL/EUR", capital=0.0)
        ex.asset = 1.0
        ex.price = 100.0
        ex.create_limit_order("SOL/EUR", "sell", amount=1.0, price=102.0)
        ex.update_price(103.0)  # sopra il target → fill
        self.assertEqual(ex.fill_events[-1]["side"], "sell")
        # proceeds = amount × price × (1 - fee) = 102 × 0.999
        self.assertAlmostEqual(ex.cash, 102.0 * 0.999, places=6)
        self.assertAlmostEqual(ex.asset, 0.0, places=9)

    def test_nessun_fill_senza_cross(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        o = ex.create_limit_order("SOL/EUR", "buy", amount=1.0, price=90.0)
        ex.update_price(95.0)   # sopra il livello → nessun fill
        self.assertEqual(ex.fill_events, [])
        self.assertEqual(ex.fetch_order(o["id"], "SOL/EUR")["status"], "open")
        self.assertEqual(len(ex.fetch_open_orders("SOL/EUR")), 1)
        self.assertEqual(ex.asset, 0.0)

    def test_equity(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        ex.update_price(100.0)
        ex.create_limit_order("SOL/EUR", "buy", amount=1.0, price=99.0)
        ex.update_price(99.0)   # fill
        # equity = cash + asset × prezzo
        expected = (100.0 - 99.0 * 1.001) + 1.0 * 99.0
        self.assertAlmostEqual(ex.equity(), expected, places=6)
        self.assertAlmostEqual(ex.fetch_balance()["total"]["EUR"], expected, places=6)

    def test_cancel_order(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        o = ex.create_limit_order("SOL/EUR", "buy", amount=1.0, price=99.0)
        ex.cancel_order(o["id"], "SOL/EUR")
        self.assertEqual(ex.fetch_order(o["id"], "SOL/EUR")["status"], "canceled")
        self.assertEqual(ex.fetch_open_orders("SOL/EUR"), [])

    def test_fill_history_completa(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        ex.update_price(100.0)
        ex.create_limit_order("SOL/EUR", "buy", amount=1.0, price=99.0)
        ex.update_price(98.0)
        ex.create_limit_order("SOL/EUR", "sell", amount=1.0, price=101.0)
        ex.update_price(102.0)
        sides = [f["side"] for f in ex.fill_events]
        self.assertEqual(sides, ["buy", "sell"])


if __name__ == "__main__":
    unittest.main()

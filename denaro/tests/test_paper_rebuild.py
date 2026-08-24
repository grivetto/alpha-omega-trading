#!/usr/bin/env python3
"""Test PaperExchange.rebuild: ripristino cash/asset dal journal."""
import json
import tempfile
import unittest
from pathlib import Path

from denaro.infrastructure.exchanges.paper import PaperExchange
from denaro.infrastructure.storage import Journal


def make_records():
    return [
        {"event": "buy_placed", "symbol": "ADA/EUR", "order_id": "b1"},
        {"event": "buy_filled", "symbol": "ADA/EUR", "order_id": "b1",
         "amount": 100.0, "entry": 1.0, "sell_target": 1.02},
        {"event": "sell_filled", "symbol": "ADA/EUR", "order_id": "s1",
         "amount": 100.0, "entry": 1.0, "exit": 1.02, "profit": 1.799},
        {"event": "buy_filled", "symbol": "SOL/EUR", "order_id": "b2",  # altro symbol
         "amount": 10.0, "entry": 1.0, "sell_target": 1.02},
    ]


class TestPaperRebuild(unittest.TestCase):
    def test_rebuild_da_journal(self):
        ex = PaperExchange("ADA/EUR", capital=300.0)
        ex.rebuild(make_records(), capital=300.0)
        # 1 buy_filled e 1 sell_filled (stesso amount) → asset 0, cash 300+profit
        self.assertAlmostEqual(ex.asset, 0.0, places=9)
        self.assertAlmostEqual(ex.cash, 300.0 + 1.799, places=6)
        self.assertAlmostEqual(ex.equity(), 300.0 + 1.799, places=6)

    def test_rebuild_con_asset_aperto(self):
        records = make_records()[:2]  # buy_placed + buy_filled ADA (sell NON chiuso)
        ex = PaperExchange("ADA/EUR", capital=300.0)
        ex.rebuild(records, capital=300.0)
        self.assertAlmostEqual(ex.asset, 100.0, places=9)
        self.assertAlmostEqual(ex.cash, 300.0, places=6)
        # equity con prezzo corrente
        ex.update_price(1.01)
        self.assertAlmostEqual(ex.equity(), 300.0 + 100.0 * 1.01, places=3)

    def test_rebuild_solo_symbol(self):
        ex = PaperExchange("SOL/EUR", capital=100.0)
        ex.rebuild(make_records()[:3], capital=100.0)  # solo record ADA
        # i record ADA non contano per SOL
        self.assertAlmostEqual(ex.cash, 100.0, places=6)
        self.assertAlmostEqual(ex.asset, 0.0, places=9)


if __name__ == "__main__":
    unittest.main()

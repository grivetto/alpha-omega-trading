#!/usr/bin/env python3
"""Deterministic end-to-end tests for DenaroOrchestrator with a scripted
fake engine: grid deploy → buy fill → sell fill → completed round → Kelly."""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from denaro.config import DenaroConfig
from denaro.core import DenaroCore
from denaro.orchestrator import DenaroOrchestrator


class FakeEngine:
    """Scripted-price exchange with crossing-limit fills (deterministic)."""

    def __init__(self, prices, initial_eur=100.0):
        self.prices = list(prices)
        self._i = 0
        self.eur = initial_eur
        self.base = 0.0
        self.orders = {}
        self._nid = 1
        self.ws_connected = True
        self._lockout_mode = False

    @property
    def ex(self):
        return self

    @property
    def in_lockout(self):
        return self._lockout_mode

    @property
    def lockout_remaining(self):
        return 0.0

    @property
    def ws_stale(self):
        return False

    def get_stats(self):
        return {"api_calls": 0, "cache_hits": 0, "lockout": False, "ws_connected": True}

    def _price(self):
        return self.prices[min(self._i, len(self.prices) - 1)]

    def tick(self):
        """Advance the scripted price once per trading cycle."""
        if self._i < len(self.prices) - 1:
            self._i += 1

    def fetch_ticker(self, symbol):
        return self._price()

    def get_microstructure(self):
        p = self.fetch_ticker(symbol="")
        return {"bid": p * 0.9999, "ask": p * 1.0001,
                "bid_vol": 5000.0, "ask_vol": 5000.0,
                "cum_bid": 10000.0, "cum_ask": 10000.0, "price": p}

    def fetch_balance(self, which="FULL"):
        full = {"EUR": self.eur, "DOGE": self.base,
                "total": {"EUR": self.eur, "DOGE": self.base},
                "free": {"EUR": self.eur, "DOGE": self.base}, "used": {}}
        if which == "FULL":
            return full
        if which == "EUR":
            return self.eur
        if which == "DOGE":
            return self.base
        return full.get(which, 0.0)

    def fetch_ohlcv(self, symbol, timeframe="1h", limit=24):
        return [[0, 1.0, 1.0, 1.0, 1.0, 1000.0] for _ in range(limit)]

    def _open(self, side, amount, price):
        oid = f"{side[:1]}{self._nid}"
        self._nid += 1
        o = {"id": oid, "side": side, "_side": side, "_price": price,
             "_amount": amount, "price": price, "amount": amount,
             "filled": 0.0, "status": "open"}
        self.orders[oid] = o
        return o

    def create_limit_buy_order(self, symbol, amount, price):
        return self._open("buy", amount, price)

    def create_limit_sell_order(self, symbol, amount, price):
        return self._open("sell", amount, price)

    def fetch_order(self, order_id, symbol=None):
        o = self.orders.get(order_id)
        if o is None:
            return {"status": "canceled", "filled": 0.0}
        return o

    def fetch_open_orders(self, symbol):
        p = self.fetch_ticker(symbol)
        out = []
        for oid, o in list(self.orders.items()):
            if o["status"] != "open":
                continue
            if o["_side"] == "buy" and p <= o["_price"]:
                self.eur -= o["_amount"] * o["_price"]
                self.base += o["_amount"] * 0.998
                o["status"] = "closed"
                o["filled"] = o["_amount"]
                continue
            if o["_side"] == "sell" and p >= o["_price"]:
                self.eur += o["_amount"] * o["_price"] * 0.998
                self.base -= o["_amount"]
                o["status"] = "closed"
                o["filled"] = o["_amount"]
                continue
            out.append(o)
        return out

    def cancel_order(self, order_id, symbol=None):
        self.orders.pop(order_id, None)

    def cancel_all_orders(self, symbol=None):
        self.orders.clear()

    def round_amount(self, amount):
        return round(amount, 8)

    def round_price(self, price):
        return round(price, 7)


def _make(prices, cycles=6):
    engine = FakeEngine(prices)
    core = DenaroCore(initial_capital=100.0,
                      state_path=Path(tempfile.mktemp(suffix=".json")))
    cfg = DenaroConfig(capital=100.0, shadow_mode=False, mock_mode=True,
                       cooldown=1, min_order_eur=1.0, rebalance_interval=1000)
    orch = DenaroOrchestrator(engine, core, cfg)
    for _ in range(cycles):
        orch.run()
        engine.tick()
    return engine, core, orch


def test_grid_round_completes():
    # Deploy at 1.00 (buys ~0.995), dip fills a buy, rally fills its sell
    prices = [1.00, 1.00, 1.00, 1.00, 0.994, 1.012, 1.012, 1.012]
    engine, core, orch = _make(prices, cycles=8)
    p = core.state.perf
    assert p.total_trades >= 1, f"expected >=1 completed round, got {p.total_trades}"
    assert p.win_trades >= 1
    assert core.state.dca.active is False


def test_dump_defense_cancels_buys():
    prices = [1.00, 1.00, 1.00, 1.00]
    engine, core, orch = _make(prices, cycles=3)
    # A grid should be deployed now (buy levels)
    assert len(core.state.grid_levels) >= 1
    buy_ids = [lvl.get("buy_order_id") or lvl.get("order_id")
               for lvl in core.state.grid_levels if lvl.get("stage", "buy") == "buy"]
    assert len(buy_ids) >= 1
    # Trigger dump mode on the next cycle
    core.state.regime.dump_mode = True
    core.state.regime.dump_reason = "test"
    orch.run()
    # Buy levels gone (cancelled); sell levels may remain
    assert not [lvl for lvl in core.state.grid_levels if lvl.get("stage", "buy") == "buy"]
    assert core.state.exec.dump_events >= 1

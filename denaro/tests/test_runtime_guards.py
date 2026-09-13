#!/usr/bin/env python3
"""Regressioni delle fix runtime (2026-09-11).

Coprono due difetti trovati in PRODUZIONE, entrambi silenziosi:

A. OKXAdapter/KrakenAdapter non caricavano i metadati dei mercati:
   min_amount_for() e min_notional() restituivano 0.0 e i filtri di minimo
   ordine delle policy erano di fatto DISATTIVATI (ordini dust pianificati a
   ogni tick e rifiutati dall'exchange).

B. BotTask loggava "N sell ladder piazzati" contando la DECISIONE, non gli
   ordini accettati, e azzerava _last_error a fine tick: un fallimento totale
   era indistinguibile da un successo (nei log ne' in health).
"""
from __future__ import annotations

import asyncio

import pytest

from denaro.application.orchestrator import BotConfig, BotTask
from denaro.domain.grid import GridParams, GridPolicy
from denaro.domain.risk import RiskManager


# --- fake exchange (nessuna rete, nessun file) --------------------------------

class FakeExchange:
    def __init__(self, price: float = 100.0, free_quote: float = 1000.0,
                 fail_sells: bool = False) -> None:
        self.price = price
        self.free_quote = free_quote
        self.fail_sells = fail_sells
        self.placed: list = []
        self._seq = 0

    def fetch_ticker(self, symbol):
        return {"last": self.price, "bid": self.price, "ask": self.price}

    def fetch_balance(self):
        return {"free": {"EUR": self.free_quote, "SOL": 0.0},
                "total": {"EUR": self.free_quote, "SOL": 0.0}}

    def fetch_open_orders(self, symbol):
        return []

    def fetch_order(self, oid, symbol):
        return {"id": oid, "status": "open"}

    def create_limit_order(self, symbol, side, amount, price):
        if side == "sell" and self.fail_sells:
            raise RuntimeError("ExchangeError: amount below minimum")
        self._seq += 1
        o = {"id": f"o{self._seq}", "side": side, "amount": amount, "price": price}
        self.placed.append(o)
        return o

    def cancel_order(self, oid, symbol):
        return {"id": oid}

    def sell_market(self, symbol, amount):
        return {"id": "mkt"}

    def min_amount_for(self, symbol):
        return 0.0

    def min_notional(self, symbol):
        return 0.0


def make_bot(ex, levels: int = 1, fee: float = 0.0,
             price_source=None) -> BotTask:
    """BotTask senza path di stato/journal/health: nessuna I/O su disco."""
    cfg = BotConfig(symbol="SOL/EUR", capital=30.0, levels=levels, fee=fee,
                    buy_distance=0.01, profit_target=0.015)
    return BotTask(cfg, ex, GridPolicy(GridParams(levels=levels)), RiskManager(),
                   price_source=price_source)


# --- A: i minimi dell'exchange non sono piu' invisibili ------------------------

class _FakeCcxt:
    def __init__(self) -> None:
        self.markets = {}
        self.loaded = 0

    def load_markets(self):
        self.loaded += 1
        self.markets = {"SOL/EUR": {"limits": {"amount": {"min": 0.01},
                                               "cost": {"min": 1.0}}}}
        return self.markets

    def market(self, symbol):
        if not self.markets:
            raise Exception("okx markets not loaded")
        return self.markets[symbol]


def _adapter_with_fake_ccxt(cls):
    ad = cls.__new__(cls)              # salta __init__ (niente ccxt reale)
    ad.ex = _FakeCcxt()
    ad._markets_loaded = False
    ad.bucket = None

    def _call(fn, *a, **kw):
        return fn(*a, **kw)
    ad._call = _call
    return ad


def test_okx_adapter_loads_markets_before_returning_limits():
    from denaro.infrastructure.exchanges.okx import OKXAdapter
    ad = _adapter_with_fake_ccxt(OKXAdapter)
    assert ad.min_amount_for("SOL/EUR") == pytest.approx(0.01)
    assert ad.ex.loaded == 1                      # caricato una sola volta
    assert ad.min_notional("SOL/EUR") == pytest.approx(1.0)
    assert ad.ex.loaded == 1


def test_kraken_adapter_loads_markets_before_returning_limits():
    from denaro.infrastructure.exchanges.kraken import KrakenAdapter
    ad = _adapter_with_fake_ccxt(KrakenAdapter)
    assert ad.min_amount_for("SOL/EUR") == pytest.approx(0.01)
    assert ad.ex.loaded == 1


# --- A bis: la griglia non pianifica ordini dust -------------------------------

def test_ladder_skips_dust_when_min_amount_known():
    """Con min_amount corretto la scala di vendita ignora il saldo dust."""
    p = GridPolicy(GridParams(levels=3, sell_levels=2, sell_distance=0.02,
                              sell_step=0.01), min_amount=10.0)
    d = p.decide(price=100.0, open_buys={}, open_sells={}, cash=0.0,
                 capital_config=12.0, free_balance=0.38, now=0.0,
                 free_asset=1.7e-07)     # dust: 0.00000017 SOL
    assert d.to_sell == []


def test_ladder_places_when_amount_above_minimum():
    p = GridPolicy(GridParams(levels=3, sell_levels=2, sell_distance=0.02,
                              sell_step=0.01), min_amount=0.01)
    d = p.decide(price=100.0, open_buys={}, open_sells={}, cash=0.0,
                 capital_config=12.0, free_balance=0.38, now=0.0,
                 free_asset=0.30)        # 0.15 per livello > 0.01
    assert len(d.to_sell) == 2


# --- B: il log del ladder riflette gli ordini REALI ---------------------------

def test_ladder_failure_is_visible_and_not_logged_as_success():
    ex = FakeExchange(price=100.0, fail_sells=True)
    bot = make_bot(ex)
    bot.policy = GridPolicy(GridParams(levels=1, sell_levels=2,
                                       sell_distance=0.02, sell_step=0.01),
                            min_amount=0.0)
    # balance con asset libero sufficiente a pianificare la scala
    ex.fetch_balance = lambda: {"free": {"EUR": 0.0, "SOL": 1.0},
                                "total": {"EUR": 0.0, "SOL": 1.0}}
    asyncio.run(bot.tick())
    assert bot._last_error.startswith("ladder sell rifiutati")
    assert ex.placed == []                       # nessun sell davvero piazzato


def test_ladder_success_does_not_set_error():
    ex = FakeExchange(price=100.0)
    ex.fetch_balance = lambda: {"free": {"EUR": 0.0, "SOL": 1.0},
                                "total": {"EUR": 0.0, "SOL": 1.0}}
    bot = make_bot(ex)
    bot.policy = GridPolicy(GridParams(levels=1, sell_levels=2,
                                       sell_distance=0.02, sell_step=0.01),
                            min_amount=0.0)
    asyncio.run(bot.tick())
    assert bot._last_error == ""
    assert len(ex.placed) == 2


# --- C: prezzo non disponibile -> visibile, non silenzioso --------------------

def test_tick_with_unavailable_price_reports_error_and_places_nothing():
    """Con prezzo non disponibile il tick NON decide e lo segnala in health.

    Prima: il tick proseguiva con price=0.0, la policy rispondeva "prezzo non
    valido", health restava status=running con error="" -> bot inerte e
    apparentemente sano (visto in produzione su XRP/ETH il 2026-09-13).
    """
    ex = FakeExchange(price=100.0)

    async def zero_price() -> float:
        return 0.0

    bot = make_bot(ex, price_source=zero_price)
    asyncio.run(bot.tick())
    assert "prezzo non disponibile" in bot._last_error
    assert ex.placed == []


# --- D: l'hub condivide i markets con il client REST --------------------------

class _FakeRest:
    """Client REST finto che si comporta come ccxt: senza markets, errore."""

    def __init__(self, price: float = 100.0) -> None:
        self.markets: dict = {}
        self.loads = 0
        self.price = price

    def load_markets(self):
        self.loads += 1
        self.markets = {"SOL/EUR": {}}
        return self.markets

    def fetch_ticker(self, symbol):
        if not self.markets:
            raise RuntimeError("okx markets not loaded")
        return {"last": self.price}


def test_hub_loads_markets_once_before_first_price():
    from denaro.infrastructure.market_data import MarketDataHub
    rest = _FakeRest(price=87.5)
    hub = MarketDataHub(ex_rest=rest, ws_enabled=False)
    assert asyncio.run(hub.get_price("SOL/EUR")) == pytest.approx(87.5)
    assert rest.loads == 1
    # secondo tick dalla cache: nessun nuovo load_markets
    assert asyncio.run(hub.get_price("SOL/EUR")) == pytest.approx(87.5)
    assert rest.loads == 1


def test_hub_rejects_non_positive_price():
    from denaro.infrastructure.market_data import MarketDataHub
    rest = _FakeRest(price=0.0)
    hub = MarketDataHub(ex_rest=rest, ws_enabled=False)
    assert asyncio.run(hub.get_price("SOL/EUR")) is None


def test_hub_returns_none_instead_of_raising_when_ticker_fails():
    from denaro.infrastructure.market_data import MarketDataHub

    class _Broken:
        def fetch_ticker(self, symbol):
            raise RuntimeError("boom")

    hub = MarketDataHub(ex_rest=_Broken(), ws_enabled=False)
    assert asyncio.run(hub.get_price("SOL/EUR")) is None


def test_note_error_rate_limits_and_keeps_first_message():
    bot = make_bot(FakeExchange())
    bot._note_error("primo errore")
    bot._note_error("secondo errore")
    assert bot._last_error == "primo errore"     # il primo non viene sovrascritto
    assert len(bot._err_log_ts) == 2             # entrambe le chiavi registrate

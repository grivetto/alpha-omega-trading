#!/usr/bin/env python3
"""Test del harness di backtest: correttezza del simulatore e parita' col live.

Non testano "la strategia guadagna": testano che il SIMULATORE sia onesto,
cioe' che non regali fill, non permetta saldi negativi, contabilizzi le fee e
rispetti le stesse regole del ciclo live.
"""
from __future__ import annotations

import math

import pytest

from denaro.backtest.metrics import max_drawdown, summarize
from denaro.backtest.runner import BacktestConfig, run_backtest
from denaro.backtest.sim import SimExchange, SimRejection


def bar(ts, o, h, l, c):
    return [ts, o, h, l, c, 1.0]


# --- simulatore --------------------------------------------------------------

def test_buy_fills_only_when_price_touches():
    sim = SimExchange("SOL/EUR", cash=10_000.0, fee=0.0)
    sim.create_limit_order("SOL/EUR", "buy", 1.0, 99.0)
    sim.advance_bar(bar(1000, 100, 100.5, 99.5, 100.2))     # non tocca 99
    assert sim.stats["filled"] == 0
    sim.advance_bar(bar(2000, 100.2, 100.3, 98.9, 99.4))    # tocca 98.9 < 99
    assert sim.stats["filled"] == 1
    assert sim.asset == pytest.approx(1.0)


def test_sell_fills_only_when_price_touches():
    sim = SimExchange("SOL/EUR", cash=0.0, asset=1.0, fee=0.0)
    sim.create_limit_order("SOL/EUR", "sell", 1.0, 101.0)
    sim.advance_bar(bar(1000, 100, 100.9, 99.5, 100.4))
    assert sim.stats["filled"] == 0
    sim.advance_bar(bar(2000, 100.4, 101.5, 100.3, 101.2))
    assert sim.stats["filled"] == 1
    assert sim.cash == pytest.approx(101.0)


def test_stop_loss_market_sell_applies_slippage_and_fee():
    sim = SimExchange("SOL/EUR", cash=0.0, asset=1.0, fee=0.001, slippage=0.01)
    sim.price = 100.0
    sim.sell_market("SOL/EUR", 1.0)
    # 100 * (1-0.01) * (1-0.001) = 98.901
    assert sim.cash == pytest.approx(98.901, rel=1e-9)
    assert sim.asset == 0.0


def test_order_rejected_below_min_notional():
    sim = SimExchange("SOL/EUR", cash=1000.0, fee=0.0, min_notional=5.0)
    with pytest.raises(SimRejection):
        sim.create_limit_order("SOL/EUR", "buy", 0.01, 100.0)   # 1 EUR < 5


def test_order_rejected_without_funds():
    sim = SimExchange("SOL/EUR", cash=10.0, fee=0.0)
    with pytest.raises(SimRejection):
        sim.create_limit_order("SOL/EUR", "buy", 1.0, 100.0)


def test_free_excludes_capital_locked_in_open_buys():
    sim = SimExchange("SOL/EUR", cash=100.0, fee=0.0)
    sim.create_limit_order("SOL/EUR", "buy", 0.5, 100.0)   # blocca 50 EUR
    bal = sim.fetch_balance()
    assert bal["free"]["EUR"] == pytest.approx(50.0)
    assert bal["total"]["EUR"] == pytest.approx(100.0)
    # un secondo buy che eccede il free viene rifiutato (deadlock frammentazione)
    with pytest.raises(SimRejection):
        sim.create_limit_order("SOL/EUR", "buy", 0.6, 100.0)


def test_cash_never_negative_across_paths():
    sim = SimExchange("SOL/EUR", cash=100.0, fee=0.001)
    for lvl in (99.0, 98.0, 97.0):
        try:
            sim.create_limit_order("SOL/EUR", "buy", 0.3, lvl)
        except SimRejection:
            pass
    sim.advance_bar(bar(1000, 100, 100, 90, 91))
    assert sim.cash >= 0.0
    assert sim.asset >= 0.0


def test_equity_identity_realized_plus_unrealized():
    """equity_finale - equity_iniziale == realizzato + non realizzato."""
    sim = SimExchange("SOL/EUR", cash=1000.0, fee=0.001)
    o = sim.create_limit_order("SOL/EUR", "buy", 1.0, 100.0)
    sim.advance_bar(bar(1000, 101, 101, 99, 100.5))
    assert sim.orders[o["id"]].status == "closed"
    sim.create_limit_order("SOL/EUR", "sell", 1.0, 110.0)
    sim.advance_bar(bar(2000, 100.5, 111, 100.4, 110.5))


# --- runner (parita' con il ciclo live) ---------------------------------------

def _grid_bot(**over):
    bot = {"symbol": "SOL/EUR", "capital": 100.0, "levels": 2,
           "buy_distance": 0.01, "profit_target": 0.02, "strategy": "grid"}
    bot.update(over)
    return bot


def test_grid_completes_a_cycle_and_books_it():
    cfg = BacktestConfig(symbol="SOL/EUR", capital=100.0, bot=_grid_bot(),
                         fee=0.0, min_amount=0.0, min_notional=0.0)
    bars = [
        bar(1_000_000, 100.0, 100.4, 99.9, 100.0),   # piazza la griglia
        bar(1_300_000, 100.0, 100.2, 98.8, 99.2),    # fill del buy a 99
        bar(1_600_000, 99.2, 101.4, 99.0, 101.2),    # fill del TP sell
    ]
    res = run_backtest(cfg, bars)
    assert res.fills_buy == 1
    assert res.fills_sell == 1
    assert res.cycles == 1
    assert res.realized_pnl > 0
    # identita' contabile: equity finale = equity iniziale + realizzato + non realizzato
    delta = res.end_equity - res.start_equity
    assert delta == pytest.approx(res.realized_pnl + res.unrealized_pnl, abs=1e-9)


def test_fee_not_budgeted_makes_the_last_level_unaffordable():
    """DIFETTO REALE DI PRODUZIONE (riprodotto dal simulatore).

    La griglia dimensiona i livelli con `per_level = capital / levels` SENZA
    includere la fee: con capital=100, levels=2, fee=0.1% il secondo livello
    costa 50.05 EUR ma ne restano liberi 50.00 → l'exchange lo rifiuta.
    In live questo si manifesta come "insufficient funds" sporadico e come
    griglia permanentemente incompleta.
    """
    cfg = BacktestConfig(symbol="SOL/EUR", capital=100.0, bot=_grid_bot(),
                         fee=0.001, min_amount=0.0, min_notional=0.0)
    bars = [bar(1_000_000 + i * 300_000, 100.0, 100.4, 99.9, 100.0)
            for i in range(4)]
    res = run_backtest(cfg, bars)
    assert res.orders_placed == 1                    # non 2: il secondo e' rifiutato
    assert any("fondi insufficienti" in x for x in res.rejections)


def test_no_same_bar_round_trip():
    """Un buy che si riempie in una barra NON puo' generare un TP nella stessa."""
    cfg = BacktestConfig(symbol="SOL/EUR", capital=100.0, bot=_grid_bot(),
                         fee=0.0, min_amount=0.0, min_notional=0.0)
    # una sola barra che tocca il livello buy (99) e il target TP (100.98):
    # il sell puo' nascere solo DOPO la barra del fill, quindi non si riempie
    bars = [bar(1_000_000, 100.0, 100.1, 99.9, 100.0),
            bar(1_300_000, 100.0, 102.5, 98.9, 102.0)]
    res = run_backtest(cfg, bars)
    assert res.fills_buy == 1
    assert res.fills_sell == 0


def test_min_notional_blocks_everything_and_no_order_is_placed():
    """Capitale frammentato sotto il minimo: nessun ordine, nessun PnL."""
    bot = _grid_bot(capital=4.0)
    cfg = BacktestConfig(symbol="SOL/EUR", capital=4.0, bot=bot, fee=0.001,
                         min_amount=0.0, min_notional=5.0)
    bars = [bar(1_000_000 + i * 300_000, 100.0, 100.5, 99.0, 100.0)
            for i in range(5)]
    res = run_backtest(cfg, bars)
    assert res.orders_placed == 0
    assert res.cycles == 0
    assert res.end_equity == pytest.approx(res.start_equity, abs=1e-9)


def test_max_drawdown_metric():
    assert max_drawdown([100, 120, 60, 90]) == pytest.approx(0.5)


def test_summary_flags_hodl_benchmark():
    cfg = BacktestConfig(symbol="SOL/EUR", capital=100.0, bot=_grid_bot(),
                         fee=0.0, min_amount=0.0, min_notional=0.0)
    bars = [bar(1_000_000 + i * 300_000, 100.0 + i, 100.6 + i, 99.9 + i, 100.5 + i)
            for i in range(6)]
    res = run_backtest(cfg, bars)
    s = summarize(res)
    assert "return_pct" in s and "hodl_all_in_pct" in s
    assert s["hodl_all_in_pct"] > 0      # il prezzo sale in questo scenario
    assert math.isfinite(s["sharpe_ann"])

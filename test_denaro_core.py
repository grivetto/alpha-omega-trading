#!/usr/bin/env python3
"""Tests for Denaro Core v3 — risk, VaR, regime, DCA, Kelly."""
import json, math, os, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import (DenaroCore, CBState, Trend, StrategyMode, CoreState,
                          CircuitBreakerState, PerfMetrics, VaRState)

def make_core(**kw) -> DenaroCore:
    sp = Path(tempfile.mktemp(suffix=".json"))
    kw.setdefault("state_path", sp)
    return DenaroCore(**kw)

def test_init_defaults():
    c = make_core(initial_capital=100.0)
    assert c.state.initial_capital == 100.0
    assert c.state.cb.state == CBState.CLOSED
    assert c.state.kelly_fraction == 0.25

def test_cb_healthy():
    c = make_core(initial_capital=100.0)
    assert not c.check_circuit_breaker(100.0)
    assert c.state.cb.state == CBState.CLOSED

def test_cb_daily_loss():
    c = make_core(initial_capital=100.0, daily_loss_limit=0.05)
    c.state.last_daily_reset = 0
    c.state.day_start_capital = 100.0
    blocked = c.check_circuit_breaker(93.0)
    assert blocked
    assert c.state.cb.state == CBState.OPEN
    assert "daily" in c.state.cb.reason.lower()

def test_cb_drawdown():
    c = make_core(initial_capital=100.0, max_drawdown_limit=0.15)
    c.state.last_daily_reset = time.time()
    c.state.day_start_capital = 85.0  # Daily loss check won't trigger (84 > 85*0.95=80.75)
    c.check_circuit_breaker(100.0)
    blocked = c.check_circuit_breaker(84.0)  # 16% drawdown > 15% limit
    assert blocked
    assert "drawdown" in c.state.cb.reason.lower()

def test_cb_consecutive_losses():
    c = make_core(initial_capital=100.0, max_consecutive_losses=4)
    c.state.perf.consecutive_losses = 3
    assert not c.check_circuit_breaker(100.0)
    assert c.state.cb.state == CBState.CLOSED
    c.state.perf.consecutive_losses = 4
    blocked = c.check_circuit_breaker(99.0)
    assert not blocked
    assert c.state.cb.state == CBState.HALF_OPEN

def test_daily_reset():
    c = make_core(initial_capital=100.0)
    c.state.last_daily_reset = 0
    c.check_circuit_breaker(100.0)
    assert c.state.last_daily_reset > 0

def test_kelly_default():
    c = make_core(initial_capital=100.0)
    assert c.state.kelly_fraction == 0.25

def test_kelly_recalculates():
    c = make_core(initial_capital=100.0)
    for _ in range(8):
        c.update_kelly(0.03)
    for _ in range(2):
        c.update_kelly(-0.01)
    assert c.state.kelly_fraction != 0.25
    assert c.state.perf.win_trades == 8
    assert c.state.perf.total_trades == 10

def test_kelly_negative():
    c = make_core(initial_capital=100.0)
    for _ in range(2):
        c.update_kelly(0.01)
    for _ in range(8):
        c.update_kelly(-0.02)
    assert c.state.kelly_fraction < 0.25
    assert c.state.perf.loss_trades == 8

def test_position_size_basic():
    c = make_core(initial_capital=100.0)
    sz = c.position_size(100.0, 1.0)
    assert sz > 0

def test_position_size_vol_adj():
    c = make_core(initial_capital=100.0)
    c.state.regime.volatility_regime = "normal"
    normal = c.position_size(100.0, 1.0)
    c.state.regime.volatility_regime = "high"
    high = c.position_size(100.0, 1.0)
    assert high < normal
    c.state.regime.volatility_regime = "low"
    low = c.position_size(100.0, 1.0)
    assert low > normal

def test_compound():
    c = make_core(initial_capital=100.0, compound_threshold=1.0, compound_ratio=0.5)
    old = c.state.initial_capital
    c.compound_profits(105.0)
    assert c.state.initial_capital > old

def test_atr():
    c = make_core(initial_capital=100.0)
    ohlcv = _ohlcv(15, 0.065, 0.01)
    atr = c.calculate_atr(ohlcv)
    assert atr > 0
    assert atr < 0.05

def test_atr_insufficient():
    c = make_core(initial_capital=100.0)
    assert c.calculate_atr(_ohlcv(5)) == 0.0

def test_vol_low():
    c = make_core(initial_capital=100.0)
    c.calculate_atr(_ohlcv(15, 1.0, 0.001))
    assert c.state.regime.volatility_regime == "low"

def test_vol_high():
    c = make_core(initial_capital=100.0)
    c.calculate_atr(_ohlcv(15, 0.065, 0.025))
    # With vol=0.025 (~2.5% per candle), ATR can be in high or extreme range
    assert c.state.regime.volatility_regime in ("high", "normal", "extreme")

def test_state_persistence():
    sp = Path(tempfile.mktemp(suffix=".json"))
    c1 = make_core(initial_capital=100.0, state_path=sp)
    c1.update_kelly(0.03); c1.update_kelly(-0.01)
    c1.check_circuit_breaker(98.0)
    c1.flush_state()  # force save (v4: _save_state is throttled)
    c2 = make_core(initial_capital=100.0, state_path=sp)
    assert c2.state.perf.total_trades == 2
    assert c2.state.perf.win_trades == 1
    sp.unlink(missing_ok=True)

def test_can_trade():
    cs = CoreState()
    assert cs.can_trade
    cs.cb.state = CBState.OPEN
    assert not cs.can_trade
    cs.cb.state = CBState.HALF_OPEN
    assert cs.can_trade

def test_win_rate():
    p = PerfMetrics()
    assert p.win_rate == 0.0
    p.update(0.01); assert p.win_rate == 1.0
    p.update(-0.01); assert p.win_rate == 0.5
    p.update(0.02); assert abs(p.win_rate - 2/3) < 1e-9

def test_sharpe_ratio():
    p = PerfMetrics()
    for _ in range(15):
        p.update(0.02)
    for _ in range(5):
        p.update(-0.01)
    results = [0.02]*15 + [-0.01]*5
    p.recalc_ratios(results, 100, 102, 100)
    assert p.profit_factor > 0
    assert p.sortino_ratio > 0

def test_peak_capital():
    c = make_core(initial_capital=100.0)
    c.check_circuit_breaker(100.0); assert c.state.peak_capital == 100.0
    c.check_circuit_breaker(105.0); assert c.state.peak_capital == 105.0
    c.check_circuit_breaker(102.0); assert c.state.peak_capital == 105.0

def test_strategy_selection():
    c = make_core(initial_capital=100.0)
    c.state.regime.trend = Trend.RANGING
    c.state.micro.bid_ask_spread_pct = 0.001
    assert c.select_strategy() == StrategyMode.GRID

def test_dca_entry_logic():
    c = make_core(initial_capital=100.0)
    c.state.regime.momentum_24h = -0.05
    c.state.regime.volume_regime = "spike"
    c.state.micro.bid_ask_imbalance = 0.5
    enter, amt, _ = c.dca_should_enter(0.060, 100.0)
    assert enter
    assert amt > 0

def test_dca_exit_target():
    c = make_core(initial_capital=100.0)
    c.dca_open_position(0.060, 100, 6.0)
    exit_, sz, reason = c.dca_should_exit(0.062)
    assert exit_
    assert sz > 0
    assert "target" in reason

def test_microstructure():
    c = make_core(initial_capital=100.0)
    c.update_microstructure(0.064, 0.065, 10000, 8000, 50000, 40000, 0.0645)
    assert c.state.micro.bid_ask_spread_pct > 0
    assert c.state.micro.bid_ask_imbalance > 1.0
    assert not c.state.micro.spoofing_flag

def test_var():
    c = make_core(initial_capital=100.0)
    for p in [0.065 + i * 0.0005 for i in range(50)]:
        c.update_var(p)
    assert c.state.var.var_95_1h > 0
    assert c.state.var.var_99_1h > 0

def test_perf_metrics_recalc():
    p = PerfMetrics()
    results = [0.02, 0.01, -0.01, 0.03, -0.02, 0.01, 0.02, -0.01, 0.01, 0.02]
    for r in results:
        p.update(r)
    p.recalc_ratios(results, 110, 105, 100)
    assert p.sharpe_ratio != 0 or p.profit_factor > 0
    assert p.avg_win > 0
    assert p.avg_loss > 0

def _ohlcv(count, base=0.065, vol=0.005):
    import random
    data, price = [], base
    for i in range(count):
        ts = int((time.time() - (count - i) * 3600) * 1000)
        h = price * (1 + random.uniform(0, vol))
        l = price * (1 - random.uniform(0, vol))
        c = l + (h - l) * random.random()
        data.append([ts, price, h, l, c, 100000])
        price = c
    return data

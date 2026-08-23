#!/usr/bin/env python3
"""Tests for Denaro v6 — adaptive grid, dump defense, adaptive DCA,
vol-scaled risk, compounding policy, rebalancer, state round-trip."""
import json
import math
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from denaro.config import DenaroConfig
from denaro.core import DenaroCore
from denaro.dca import AdaptiveDCA
from denaro.grid import GridPolicy
from denaro.micro import MicrostructureModel
from denaro.orchestrator import DenaroOrchestrator
from denaro.rebalancer import Rebalancer
from denaro.regime import RegimeDetector
from denaro.risk import RiskManager
from denaro.state import StateStore
from denaro.types import CBState, CoreState, RegimeState, Trend


def _make_state(initial=100.0) -> CoreState:
    return CoreState(initial_capital=initial)


def _ohlcv(n: int, atr: float = 0.01, step: float = 0.001,
           last_close: float = 1.0, last_vol: float = 1000.0,
           avg_vol: float = 1000.0) -> list:
    rows = []
    price = last_close - (n - 1) * step
    for i in range(n):
        o = price
        h = price * (1 + atr * 0.5)
        l = price * (1 - atr * 0.5)
        c = price + step
        v = last_vol if i == n - 1 else avg_vol
        rows.append([int(time.time()) - (n - i) * 3600, o, h, l, c, v])
        price = c
    return rows


# ─── Adaptive grid ───────────────────────────────────────────────────────────

def test_grid_spread_widens_with_volatility():
    c = _make_state()
    c.regime.volatility_regime = "low"
    c.regime.atr_pct = 0.003
    low = GridPolicy().compute(c, 1.0)
    c.regime.volatility_regime = "extreme"
    c.regime.atr_pct = 0.04
    extreme = GridPolicy().compute(c, 1.0)
    assert extreme["spread"] > low["spread"]
    assert extreme["levels"] < low["levels"]


def test_grid_micro_skew_widens():
    c = _make_state()
    c.regime.volatility_regime = "normal"
    c.regime.atr_pct = 0.01
    base = GridPolicy().compute(c, 1.0)["spread"]
    c.micro.bid_ask_imbalance = 0.4          # one-sided book
    skew = GridPolicy().compute(c, 1.0)["spread"]
    assert skew > base


def test_grid_dump_blocks_spend():
    c = _make_state()
    c.regime.dump_mode = True
    gp = GridPolicy().compute(c, 1.0)
    assert gp["max_spend_pct"] == 0.0


def test_grid_retarget_stale_buy():
    params = {"spread": 0.02}
    stale = {"stage": "buy", "buy_price": 0.90}
    fresh = {"stage": "buy", "buy_price": 0.99}
    sell = {"stage": "sell", "buy_price": 0.90}
    assert GridPolicy.should_retarget(stale, 1.0, params)
    assert not GridPolicy.should_retarget(fresh, 1.0, params)
    assert not GridPolicy.should_retarget(sell, 1.0, params)


def test_grid_orphan_detection():
    levels = [{"buy_order_id": "A", "sell_order_id": "B"}]
    open_orders = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    orphans = GridPolicy.orphan_orders(levels, open_orders)
    assert orphans == ["C"]


# ─── Dump defense ────────────────────────────────────────────────────────────

def _dump_ohlcv(last_close=1.0, drop_pct=0.06):
    """24h of candles ending with a sharp drop on spike volume."""
    rows = _ohlcv(23, atr=0.008, step=0.0005, last_close=last_close * 1.06,
                  avg_vol=1000.0)
    # final candle: -6% on 2.5x volume
    rows.append([int(time.time()), last_close * 1.06, last_close * 1.06,
                 last_close * 1.06 * (1 - drop_pct), last_close, 2600.0])
    return rows


def test_dump_detection_enter_and_clear():
    from denaro.types import MicroState
    r = RegimeState()
    micro = MicroState()
    detector = RegimeDetector(dump_threshold_mult=2.5, dump_volume_ratio=1.8,
                              dump_recovery_cycles=3)
    micro.bid_ask_imbalance = 0.5
    detector.update(r, micro, _dump_ohlcv())
    assert r.dump_mode
    assert "mom=" in r.dump_reason

    # Recovery: stable candles for 3 updates
    calm = _ohlcv(24, atr=0.008, step=0.0001, last_close=1.0, avg_vol=1000.0)
    for _ in range(3):
        detector.update(r, micro, calm)
    assert not r.dump_mode


def test_dump_forces_cooldown_strategy():
    c = _make_state()
    c.regime.dump_mode = True
    core = DenaroCore(initial_capital=100.0, state_path=Path(tempfile.mktemp(suffix=".json")))
    core.state = c
    from denaro.types import StrategyMode
    assert core.select_strategy() == StrategyMode.COOLDOWN


# ─── Adaptive DCA ────────────────────────────────────────────────────────────

def test_dca_params_follow_volatility():
    c = _make_state()
    c.regime.atr_pct = 0.05
    c.regime.volatility_regime = "extreme"
    p_hot = AdaptiveDCA().params(c)
    c.regime.atr_pct = 0.003
    c.regime.volatility_regime = "low"
    p_calm = AdaptiveDCA().params(c)
    assert p_hot["spacing"] > p_calm["spacing"]
    assert p_hot["max_entries"] < p_calm["max_entries"]
    assert p_hot["hard_stop"] < p_calm["hard_stop"]   # deeper stop when hot


def test_dca_dump_guard_blocks_entry():
    c = _make_state()
    c.regime.dump_mode = True
    c.dca.active = True
    c.dca.last_entry_price = 1.0
    should, _, reason = AdaptiveDCA().should_enter(c, 0.90, 100.0, 0.25)
    assert not should
    assert reason == "dump_guard"


def test_dca_distance_scaled_entry():
    c = _make_state()
    c.regime.atr_pct = 0.01
    c.regime.volatility_regime = "normal"
    c.dca.active = True
    c.dca.last_entry_price = 1.0
    c.dca.entry_spacing_pct = 0.03
    c.dca.num_entries = 1
    c.dca.max_entries = 5
    engine = AdaptiveDCA()
    should, size, reason = engine.should_enter(c, 0.95, 100.0, 0.25)
    assert should
    assert reason.startswith("dca_drop_")
    assert size > 0


def test_dca_hard_stop_scaled():
    c = _make_state()
    c.regime.atr_pct = 0.02
    c.dca.active = True
    c.dca.total_size = 100.0
    c.dca.avg_entry_price = 1.0
    engine = AdaptiveDCA()
    # ATR 2% → hard stop -max(12%, 18%) = -18%; -20% breaches it
    should, _, reason = engine.should_exit(c, 0.80)
    assert should
    assert reason.startswith("stop_")


# ─── Risk + compounding ──────────────────────────────────────────────────────

def test_daily_loss_limit_vol_scaled():
    rm = RiskManager(daily_loss_limit=0.05)
    r = RegimeState(volatility_regime="normal")
    assert rm.daily_loss_limit_effective(r) == 0.05
    r.volatility_regime = "extreme"
    assert rm.daily_loss_limit_effective(r) < 0.05
    r.volatility_regime = "low"
    assert rm.daily_loss_limit_effective(r) > 0.05


def test_compounding_bull_aggressive():
    rm = RiskManager(compound_ratio=0.5)
    s = _make_state()
    s.regime.trend = Trend.BULL
    s.regime.trend_strength = 0.7
    s.regime.regime_confidence = 0.8
    assert rm.compounding_ratio_effective(s) == 0.75
    s.regime.trend = Trend.RANGING
    assert rm.compounding_ratio_effective(s) == 0.5
    s.regime.trend = Trend.BEAR
    assert rm.compounding_ratio_effective(s) == 0.125
    s.regime.dump_mode = True
    assert rm.compounding_ratio_effective(s) == 0.0


def test_kelly_frozen_in_dump():
    c = _make_state()
    c.regime.dump_mode = True
    rm = RiskManager()
    assert rm.kelly_fraction(c) == 0.0
    c.regime.dump_mode = False
    assert rm.kelly_fraction(c) > 0.0


# ─── Rebalancer ──────────────────────────────────────────────────────────────

def test_rebalancer_targets_by_regime():
    rb = Rebalancer(tolerance=0.05, interval_cycles=10)
    s = _make_state()
    s.regime.trend = Trend.BULL
    assert rb.target_base_pct(s) == 0.55
    s.regime.trend = Trend.BEAR
    assert rb.target_base_pct(s) == 0.30
    s.regime.dump_mode = True
    assert rb.target_base_pct(s) == 0.10


def test_rebalancer_gates():
    rb = Rebalancer(tolerance=0.05, interval_cycles=10, min_order_eur=1.0)
    s = _make_state()
    s.regime.trend = Trend.BULL
    # equity=100, base_bal=0 → 55% drift ≥ 15% → immediate large-drift rebalance
    should, delta, reason = rb.compute(s, 1.0, eur=100.0, base_bal=0.0, cycle=1)
    assert should
    assert reason.startswith("buy_")
    assert delta == 25.0  # 55€ desired, capped at max_rebalance_pct × equity (25€)


def test_rebalancer_defense_holds_buys():
    rb = Rebalancer(tolerance=0.05, interval_cycles=1)
    s = _make_state()
    s.regime.dump_mode = True
    # In dump mode the target is 10% base; holding 0% → wants to BUY → blocked
    should, _, reason = rb.compute(s, 1.0, eur=100.0, base_bal=0.0, cycle=10)
    assert not should
    assert reason == "defense_hold"


# ─── State round-trip ────────────────────────────────────────────────────────

def test_state_roundtrip_v6_fields():
    sp = Path(tempfile.mktemp(suffix=".json"))
    store = StateStore(sp, min_save_interval=0.0)
    s = _make_state()
    s.regime.dump_mode = True
    s.regime.dump_reason = "test"
    s.exec.dump_events = 2
    s.exec.rebalance_count = 3
    store.save(s)
    loaded = store.load(100.0)
    assert loaded.regime.dump_mode is True
    assert loaded.regime.dump_reason == "test"
    assert loaded.exec.dump_events == 2
    assert loaded.exec.rebalance_count == 3


def test_state_loads_v4_file():
    sp = Path(tempfile.mktemp(suffix=".json"))
    v4 = {
        "initial_capital": 50.0, "current_capital": 52.0,
        "kelly_fraction": 0.3, "cb": {"state": "CLOSED", "reason": ""},
        "perf": {"total_trades": 3}, "regime": {"trend": "RANGING"},
    }
    sp.write_text(json.dumps(v4))
    loaded = StateStore(sp).load(100.0)
    assert loaded.initial_capital == 50.0
    assert loaded.kelly_fraction == 0.3
    assert loaded.regime.dump_mode is False


# ─── Orchestrator smoke (mock engine) ────────────────────────────────────────

def test_orchestrator_mock_cycles():
    from mock_runner import MockKrakenEngine
    engine = MockKrakenEngine(initial_eur=100.0, start_price=0.064)
    core = DenaroCore(initial_capital=100.0,
                      state_path=Path(tempfile.mktemp(suffix=".json")))
    cfg = DenaroConfig(capital=100.0, shadow_mode=False, mock_mode=True,
                       cooldown=1, min_order_eur=1.0)
    orch = DenaroOrchestrator(engine, core, cfg)
    for _ in range(12):
        orch.run()
    assert core.state.current_capital > 0
    assert len(core.state.grid_levels) >= 0


# ─── Facade regression (v4 API surface) ──────────────────────────────────────

def test_facade_v4_api_surface():
    c = DenaroCore(initial_capital=100.0,
                   state_path=Path(tempfile.mktemp(suffix=".json")))
    assert c.state.initial_capital == 100.0
    assert c.state.cb.state == CBState.CLOSED
    assert not c.check_circuit_breaker(100.0)
    c.update_kelly(0.03)
    c.update_microstructure(0.999, 1.001, 100, 100, 5000, 5000, 1.0)
    c.calculate_atr(_ohlcv(15))
    c.update_regime(_ohlcv(24))
    c.update_var(1.0)
    p = c.get_grid_params()
    assert "spread" in p and "levels" in p and "take_profit_mult" in p
    c.dca_open_position(1.0, 10.0, 10.0)
    assert c.state.dca.active
    pnl = c.dca_close_position(exit_price=1.05)
    assert pnl > 0
    c.compound_profits(105.0)
    c.flush_state()

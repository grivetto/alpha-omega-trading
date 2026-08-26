"""Test P2 — Risk: hard stop settimanale + Volatility Targeting (Kelly×regime)."""
import datetime
import time

import pytest

from denaro.domain.risk import RiskManager, _week_start_ts
from denaro.domain.types import CBState, CoreState


def test_week_start_ts_is_monday_utc():
    ts = _week_start_ts(1787784665.0)
    d = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
    assert d.weekday() == 0
    assert d.hour == 0 and d.minute == 0 and d.second == 0


def test_weekly_loss_triggers_open():
    rm = RiskManager(weekly_loss_limit=0.20)
    st = CoreState(initial_capital=100.0, current_capital=100.0,
                   peak_capital=100.0, day_start_capital=100.0,
                   week_start_capital=100.0,
                   last_weekly_reset=_week_start_ts(time.time()))
    now = time.time() + 3600
    blocked = rm.check_circuit_breaker(st, 79.0, now)  # -21% settimanale
    assert blocked
    assert st.cb.state == CBState.OPEN
    assert "weekly_loss" in st.cb.reason


def test_weekly_reset_on_new_week():
    rm = RiskManager(weekly_loss_limit=0.20)
    st = CoreState(initial_capital=100.0, current_capital=100.0,
                   peak_capital=100.0, day_start_capital=100.0,
                   week_start_capital=100.0,
                   last_weekly_reset=_week_start_ts(time.time()) - 7 * 86400)
    rm.check_circuit_breaker(st, 110.0, time.time())
    assert st.week_start_capital == 110.0
    assert st.cb.weekly_loss_pct == 0.0


def test_risk_sized_capital_normal_regime_neutral():
    rm = RiskManager()
    st = CoreState()  # regime normal, kelly 0.25 → ×1.0
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(100.0)


def test_risk_sized_capital_extreme_vol_shrinks():
    rm = RiskManager()
    st = CoreState()
    st.regime.volatility_regime = "extreme"
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(50.0)  # ×0.5


def test_risk_sized_capital_high_vol_shrinks():
    rm = RiskManager()
    st = CoreState()
    st.regime.volatility_regime = "high"
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(70.0)  # ×0.7


def test_risk_sized_capital_low_vol_expands():
    rm = RiskManager()
    st = CoreState()
    st.regime.volatility_regime = "low"
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(120.0)  # ×1.2


def test_risk_sized_capital_open_cb_zero():
    rm = RiskManager()
    st = CoreState()
    st.cb.state = CBState.OPEN
    st.sizing_multiplier = 0.0
    assert rm.risk_sized_capital(st, 100.0) == 0.0


def test_risk_sized_capital_kelly_boost_capped():
    rm = RiskManager()
    st = CoreState()
    st.kelly_fraction = 0.5  # → kelly_scale 2.0, clamp 1.5
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(150.0)


def test_risk_sized_capital_kelly_floor():
    rm = RiskManager()
    st = CoreState()
    st.kelly_fraction = 0.05  # → kelly_scale 0.2, clamp 0.5
    assert rm.risk_sized_capital(st, 100.0) == pytest.approx(50.0)

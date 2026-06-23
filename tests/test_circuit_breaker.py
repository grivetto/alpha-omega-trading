"""Tests for Denaro v3 Circuit Breaker."""

import json
import os
import tempfile
import pytest
from denaro_v3.config import RiskConfig
from denaro_v3.circuit_breaker import CircuitBreaker, TradeRecord


@pytest.fixture
def risk_config():
    return RiskConfig(
        max_daily_loss_pct=3.0,
        max_drawdown_pct=5.0,
        max_consecutive_losses=3,
        reduced_size_pct=50.0,
        max_risk_per_trade_pct=1.0,
    )


@pytest.fixture
def breaker(risk_config):
    """Create a fresh breaker with temp state file."""
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    cb = CircuitBreaker(risk_config, state_file=path)
    cb.update_equity(1000.0)  # $1000 initial equity
    yield cb
    os.unlink(path)


class TestCircuitBreakerInitialState:
    def test_starts_closed(self, breaker):
        assert breaker.state == CircuitBreaker.STATE_CLOSED
        assert breaker.peak_equity == 1000.0

    def test_can_trade_when_closed(self, breaker):
        allowed, reason, amount = breaker.can_trade(50.0)
        assert allowed is True
        assert reason == "CLOSED"
        assert amount == 50.0

    def test_equity_tracking(self, breaker):
        breaker.update_equity(1050.0)
        assert breaker.peak_equity == 1050.0
        breaker.update_equity(950.0)
        assert breaker.peak_equity == 1050.0  # Peak persists


class TestDrawdownProtection:
    def test_drawdown_opens_circuit(self, breaker):
        breaker.update_equity(1000.0)  # Peak at 1000
        breaker.update_equity(940.0)  # -6% drawdown > 5% max
        assert breaker.state == CircuitBreaker.STATE_OPEN
        assert "Drawdown" in breaker.reason

    def test_drawdown_blocks_trades(self, breaker):
        breaker.update_equity(940.0)
        allowed, reason, amount = breaker.can_trade(10.0)
        assert allowed is False
        assert breaker.state == CircuitBreaker.STATE_OPEN


class TestConsecutiveLosses:
    def test_three_losses_half_open(self, breaker):
        for _ in range(3):
            breaker.record_trade(TradeRecord(
                timestamp=0, symbol="SOL/USDC", side="sell",
                amount=1.0, price=100.0, pnl=-5.0, fee=0.1
            ))
        assert breaker.state == CircuitBreaker.STATE_HALF_OPEN
        assert breaker.consecutive_losses == 3

    def test_half_open_reduces_size(self, breaker):
        for _ in range(3):
            breaker.record_trade(TradeRecord(
                timestamp=0, symbol="SOL/USDC", side="sell",
                amount=1.0, price=100.0, pnl=-5.0, fee=0.1
            ))
        allowed, reason, amount = breaker.can_trade(100.0)
        assert allowed is True
        assert amount == 50.0  # 50% reduction

    def test_win_resets_consecutive(self, breaker):
        breaker.record_trade(TradeRecord(
            timestamp=0, symbol="SOL/USDC", side="sell",
            amount=1.0, price=100.0, pnl=-5.0, fee=0.1
        ))
        breaker.record_trade(TradeRecord(
            timestamp=0, symbol="SOL/USDC", side="sell",
            amount=1.0, price=100.0, pnl=10.0, fee=0.1
        ))
        assert breaker.consecutive_losses == 0


class TestStatePersistence:
    def test_save_and_load(self, risk_config):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)

        cb1 = CircuitBreaker(risk_config, state_file=path)
        cb1.update_equity(1000.0)
        cb1.record_trade(TradeRecord(0, "SOL/USDC", "sell", 1.0, 100.0, -10.0, 0.1))
        cb1.record_trade(TradeRecord(0, "SOL/USDC", "sell", 1.0, 100.0, -10.0, 0.1))
        cb1.record_trade(TradeRecord(0, "SOL/USDC", "sell", 1.0, 100.0, -10.0, 0.1))
        cb1._save_state()

        cb2 = CircuitBreaker(risk_config, state_file=path)
        cb2.update_equity(1000.0)
        assert cb2.state == CircuitBreaker.STATE_HALF_OPEN
        assert cb2.consecutive_losses == 3
        assert cb2.total_pnl == -30.3

        os.unlink(path)


class TestDailyReset:
    def test_daily_pnl_reset(self, breaker):
        breaker.record_trade(TradeRecord(0, "SOL/USDC", "sell", 1.0, 100.0, -5.0, 0.1))
        assert breaker.daily_pnl == -5.1
        # Force daily reset
        breaker._daily_date = ""
        breaker._check_daily_reset()
        assert breaker.daily_pnl == 0.0

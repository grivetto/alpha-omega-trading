"""Unit tests — Kill-Switch and Dynamic Risk Engine."""
import pytest
from core.kill_switch import KillSwitch

class TestKillSwitch:
    def setup_method(self):
        self.ks = KillSwitch()
        self.ks.reset_day(200.0)

    def test_consecutive_losses_level1(self):
        """3 consecutive losses should block new entries."""
        self.ks.update(200, 0, False)
        self.ks.update(200, 0, False)
        self.ks.update(200, 0, False)
        assert not self.ks.can_open_new()

    def test_reset_on_win(self):
        """Winning trade resets consecutive losses."""
        self.ks.update(200, 0, False)
        self.ks.update(200, 0, False)
        self.ks.update(200, 0, True)
        assert self.ks.can_open_new()

    def test_daily_loss_level2(self):
        """Daily loss > 3% should block."""
        self.ks.update(194, -6, False)  # -3%
        assert not self.ks.can_open_new()

    def test_daily_loss_level3_liquidate(self):
        """Daily loss > 5% should trigger liquidate."""
        self.ks.update(189, -11, False)  # -5.5%
        assert self.ks.should_liquidate()
        assert self.ks._halted

    def test_size_multiplier_on_losses(self):
        """Size multiplier should decrease with consecutive losses."""
        self.ks.update(200, 0, False)
        self.ks.update(200, 0, False)
        m = self.ks.size_multiplier()
        assert m < 1.0

    def test_normal_operation(self):
        """No losses, no drawdown => fully open."""
        assert self.ks.can_open_new()
        assert not self.ks.should_liquidate()
        assert self.ks.size_multiplier() == 1.0


class TestDynamicRisk:
    def test_atr_calculation(self):
        from core.dynamic_risk import DynamicRiskEngine
        eng = DynamicRiskEngine()
        # Mock OHLCV: [timestamp, open, high, low, close, volume]
        ohlcv = [[0, 100, 102, 99, 101, 1000] for _ in range(20)]
        atr = eng.calculate_atr(ohlcv)
        assert atr > 0

    def test_trailing_stop_raises(self):
        from core.dynamic_risk import DynamicRiskEngine
        eng = DynamicRiskEngine()
        eng.entry_price(100, 2.0)  # entry=100, ATR=2
        # Price goes up: stop should trail
        stop1 = eng.trailing_stop(103)
        stop2 = eng.trailing_stop(106)
        assert stop2 > stop1  # Trailing stop rises with price

    def test_break_even_trigger(self):
        from core.dynamic_risk import DynamicRiskEngine
        eng = DynamicRiskEngine(atr_period=14, trail_multiplier=1.5, break_even_r=1.0)
        eng.entry_price(100, 2.0)  # ATR=2, initial stop at 100-3=97
        # Move price up by initial risk (3 points) to trigger break-even
        stop = eng.trailing_stop(104)
        assert stop >= 100  # Break-even or better

    def test_position_sizing(self):
        from core.dynamic_risk import DynamicRiskEngine
        eng = DynamicRiskEngine(max_risk_per_trade_pct=1.0)
        size = eng.position_size(200, 72, 2.0)  # $200 equity, $72 SOL, 2 ATR
        assert size > 0
        # Should risk at most $2 (1% of $200)
        risk = size * 2.0 * 1.5  # size * ATR * trail_mult
        assert risk <= 2.5  # ~$2 with some tolerance

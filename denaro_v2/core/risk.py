#!/usr/bin/env python3
"""
DENARO V2 - Risk Manager
Portfolio-level risk controls, dynamic position sizing,
and drawdown protection.
"""
import logging
import time

logger = logging.getLogger("Denaro.Risk")


class RiskManager:
    """Portfolio-level risk management."""

    def __init__(self, config: dict = None):
        self.config = config or {}
        self.max_portfolio_risk = self.config.get('max_portfolio_risk', 0.05)  # 5%
        self.max_position_size = self.config.get('max_position_size', 0.15)  # 15% of portfolio
        self.max_drawdown = self.config.get('max_drawdown', 0.10)  # 10%
        self.max_daily_trades = self.config.get('max_daily_trades', 50)
        self.max_daily_loss = self.config.get('max_daily_loss', 0.03)  # 3%

        self.portfolio_value = 0
        self.peak_value = 0
        self.daily_trades = 0
        self.daily_pnl = 0
        self._daily_reset = time.time()

        # Per-symbol tracking
        self.symbol_exposure = {}
        self.recent_trades = []

    async def check_entry(self, symbol: str, side: str, amount: float, price: float) -> bool:
        """Check if entry passes all risk controls."""
        notional = amount * price

        # 1. Position size check
        if self.portfolio_value > 0:
            position_pct = notional / self.portfolio_value
            if position_pct > self.max_position_size:
                logger.warning(f"Position too large: {position_pct:.1%} > {self.max_position_size:.1%}")
                return False

        # 2. Portfolio risk check
        total_exposure = sum(self.symbol_exposure.values())
        if self.portfolio_value > 0:
            new_exposure = total_exposure + notional
            if new_exposure / self.portfolio_value > self.max_portfolio_risk * 3:
                logger.warning(f"Portfolio risk limit reached")
                return False

        # 3. Daily trade limit
        self._check_daily_reset()
        if self.daily_trades >= self.max_daily_trades:
            logger.warning(f"Daily trade limit reached: {self.daily_trades}")
            return False

        # 4. Daily loss limit
        if self.daily_pnl < -self.max_daily_loss * self.portfolio_value:
            logger.warning(f"Daily loss limit reached: {self.daily_pnl:.2f}")
            return False

        # 5. Drawdown check
        if self.peak_value > 0:
            drawdown = (self.peak_value - self.portfolio_value) / self.peak_value
            if drawdown > self.max_drawdown:
                logger.warning(f"Max drawdown reached: {drawdown:.1%}")
                return False

        return True

    def record_trade(self, symbol: str, pnl: float):
        """Record a completed trade."""
        self.daily_trades += 1
        self.daily_pnl += pnl
        self.recent_trades.append({
            'symbol': symbol,
            'pnl': pnl,
            'timestamp': time.time(),
        })

        # Keep only last 100 trades
        if len(self.recent_trades) > 100:
            self.recent_trades = self.recent_trades[-100:]

    def update_portfolio_value(self, value: float):
        """Update current portfolio value."""
        self.portfolio_value = value
        if value > self.peak_value:
            self.peak_value = value

    def update_exposure(self, symbol: str, notional: float):
        """Update per-symbol exposure."""
        self.symbol_exposure[symbol] = notional

    def reduce_exposure(self, symbol: str, notional: float):
        """Reduce per-symbol exposure."""
        current = self.symbol_exposure.get(symbol, 0)
        self.symbol_exposure[symbol] = max(0, current - notional)

    def get_position_size(self, symbol: str, price: float,
                           volatility: float = 0.02) -> float:
        """Calculate optimal position size using Kelly-inspired sizing."""
        if self.portfolio_value <= 0:
            return 0

        # Base size: small fraction of portfolio
        base_size = self.portfolio_value * 0.02  # 2% base

        # Adjust for volatility (higher vol = smaller position)
        vol_adjustment = max(0.5, min(2.0, 0.02 / max(volatility, 0.005)))
        adjusted_size = base_size * vol_adjustment

        # Cap at max position size
        max_size = self.portfolio_value * self.max_position_size
        adjusted_size = min(adjusted_size, max_size)

        # Convert to amount
        amount = adjusted_size / price if price > 0 else 0

        return amount

    def _check_daily_reset(self):
        """Reset daily counters if new day."""
        now = time.time()
        if now - self._daily_reset > 86400:  # 24 hours
            self.daily_trades = 0
            self.daily_pnl = 0
            self._daily_reset = now

    def get_status(self) -> dict:
        """Get risk manager status."""
        drawdown = 0
        if self.peak_value > 0:
            drawdown = (self.peak_value - self.portfolio_value) / self.peak_value

        return {
            'portfolio_value': self.portfolio_value,
            'peak_value': self.peak_value,
            'drawdown': drawdown,
            'daily_trades': self.daily_trades,
            'daily_pnl': self.daily_pnl,
            'exposure': self.symbol_exposure,
            'risk_ok': drawdown < self.max_drawdown,
        }

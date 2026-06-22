"""
Advanced Risk Manager – Monte Carlo simulation, dynamic position sizing, tail risk protection.
"""
import math, random, logging, asyncio
from typing import Optional

class AdvancedRiskManager:
    def __init__(self, initial_capital: float = 250.0):
        self.logger = logging.getLogger("AdvancedRiskManager")
        self.initial_capital = initial_capital
        self.peak_capital = initial_capital
        self.current_capital = initial_capital
        self._is_halted = False
        self._consecutive_losses = 0
        # Monte Carlo params
        self.mc_runs = 1000
        self.mc_horizon = 20  # steps ahead
        self.var_percentile = 0.05  # 95% VaR

    def update_capital(self, current: float):
        self.current_capital = current
        if current > self.peak_capital:
            self.peak_capital = current
            self._consecutive_losses = 0

    def calculate_kelly_fraction(self, win_rate: float, avg_win: float, avg_loss: float) -> float:
        """Return optimal Kelly fraction (0-1)."""
        if avg_loss <= 0 or win_rate <= 0:
            return 0.0
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p
        kelly = (p * b - q) / b
        return max(0.0, min(1.0, kelly * 0.5))  # Half-Kelly for safety

    def monte_carlo_var(self, returns: list) -> float:
        """Estimate Value at Risk (VaR) at 95% confidence via Monte Carlo."""
        if not returns:
            return -0.05
        simulated = []
        for _ in range(self.mc_runs):
            path = [self.current_capital]
            for _ in range(self.mc_horizon):
                step = random.choice(returns)
                path.append(path[-1] * (1 + step))
            simulated.append(path[-1])
        simulated.sort()
        idx = int(self.var_percentile * len(simulated))
        var_loss = (self.current_capital - simulated[idx]) / self.current_capital
        return var_loss

    def dynamic_position_size(self, base_order_eur: float, volatility_factor: float = 1.0) -> float:
        """
        Scale position size based on volatility.
        Higher volatility -> smaller positions.
        """
        if self._is_halted:
            return 0.0
        if volatility_factor > 2.0:
            return base_order_eur * 0.0  # extreme volatility = no trade
        elif volatility_factor > 1.5:
            return base_order_eur * 0.25
        elif volatility_factor > 1.0:
            return base_order_eur * 0.5
        return base_order_eur

    def tail_risk_multiplier(self, market_regime: str) -> float:
        """
        Return a multiplier (0..1) for position sizing in black-swan-prone regimes.
        """
        multipliers = {
            "volatile": 0.3,
            "bear": 0.4,
            "choppy": 0.7,
            "neutral": 0.9,
            "bull": 1.0
        }
        return multipliers.get(market_regime, 0.5)

    def check_consecutive_losses(self, max_losses: int = 3) -> bool:
        """Return True if circuit breaker should fire."""
        if self._consecutive_losses >= max_losses:
            self.logger.warning(f"AdvancedRisk: circuit breaker – {self._consecutive_losses} consecutive losses")
            self._is_halted = True
            return True
        return False

    def record_trade_result(self, pnl_pct: float):
        if pnl_pct < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

    async def stress_test(self, exchange, symbol: str) -> dict:
        """
        Simple stress test: fetch order book depth at current spread.
        Returns dict with liquidity stress score (0-1).
        """
        try:
            orderbook = await exchange.fetch_order_book(symbol, limit=20)
            bids = orderbook.get("bids", [])
            asks = orderbook.get("asks", [])
            if not bids or not asks:
                return {"stress": 1.0}
            spread = (asks[0][0] - bids[0][0]) / ((bids[0][0] + asks[0][0]) / 2)
            bid_vol = sum(b[1] for b in bids[:5])
            ask_vol = sum(a[1] for a in asks[:5])
            # stress = wide spread OR thin book
            stress = min(1.0, (spread / 0.002) + (1.0 - min((bid_vol + ask_vol) / 10.0, 1.0)))
            return {"stress": stress, "spread": spread, "bid_vol": bid_vol, "ask_vol": ask_vol}
        except Exception as e:
            self.logger.debug(f"Stress test error: {e}")
            return {"stress": 1.0}
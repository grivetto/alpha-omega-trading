"""Dynamic Risk Engine — ATR trailing stop, volatility-aware sizing, break-even trigger."""
import math
from typing import Optional
from datetime import datetime


class DynamicRiskEngine:
    """Replaces fixed -2% stop-loss with adaptive ATR-based logic."""

    def __init__(self, atr_period: int = 14, trail_multiplier: float = 1.5, 
                 break_even_r: float = 1.0, max_risk_per_trade_pct: float = 1.0):
        """
        atr_period: lookback for ATR calculation
        trail_multiplier: how many ATRs for trailing stop distance
        break_even_r: R-multiple at which stop moves to entry (1.0 = when profit equals risk)
        max_risk_per_trade_pct: max % of equity at risk per trade
        """
        self.atr_period = atr_period
        self.trail_mult = trail_multiplier
        self.break_even_r = break_even_r
        self.max_risk_pct = max_risk_per_trade_pct
        self._last_atr: Optional[float] = None
        self._trail_high: Optional[float] = None
        self._entry_price: Optional[float] = None
        self._initial_stop: Optional[float] = None
        self._break_even_triggered = False

    def calculate_atr(self, ohlcv: list) -> float:
        """Standard ATR(14) from OHLCV klines."""
        if len(ohlcv) < self.atr_period + 1:
            return 0.0
        trs = []
        for i in range(1, len(ohlcv)):
            h = float(ohlcv[i][2])
            l = float(ohlcv[i][3])
            pc = float(ohlcv[i - 1][4])
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        atr = sum(trs[-self.atr_period:]) / self.atr_period
        self._last_atr = atr
        return atr

    def entry_price(self, price: float, atr: Optional[float] = None) -> float:
        """Record entry and calculate initial stop distance."""
        self._entry_price = price
        self._break_even_triggered = False
        atr = atr or self._last_atr or (price * 0.02)
        self._initial_stop = price - (atr * self.trail_mult)
        self._trail_high = price  # For long positions
        return price

    def trailing_stop(self, current_price: float, position: str = "long") -> float:
        """Return current trailing stop level. Trails price upwards for longs."""
        if self._entry_price is None or self._last_atr is None:
            return current_price * 0.98  # Fallback -2%

        atr_dist = self._last_atr * self.trail_mult

        if position == "long":
            # Update trail high
            self._trail_high = max(self._trail_high or current_price, current_price)

            # Break-even: when profit > break_even_R * initial_risk
            if not self._break_even_triggered and self._initial_stop:
                initial_risk = self._entry_price - self._initial_stop
                if current_price - self._entry_price >= initial_risk * self.break_even_r:
                    self._break_even_triggered = True

            if self._break_even_triggered:
                return max(self._entry_price, self._trail_high - atr_dist)
            return self._trail_high - atr_dist
        else:
            # Short position
            self._trail_high = self._trail_high or current_price
            self._trail_high = min(self._trail_high, current_price)
            if not self._break_even_triggered and self._initial_stop:
                initial_risk = self._initial_stop - self._entry_price
                if self._entry_price - current_price >= initial_risk * self.break_even_r:
                    self._break_even_triggered = True
            if self._break_even_triggered:
                return min(self._entry_price, self._trail_high + atr_dist)
            return self._trail_high + atr_dist

    def position_size(self, equity: float, entry_price: float, atr: float) -> float:
        """Calculate position size such that max risk is max_risk_pct of equity."""
        if atr <= 0:
            return 0.0
        risk_amount = equity * (self.max_risk_pct / 100)
        stop_distance = atr * self.trail_mult
        size = risk_amount / stop_distance if stop_distance > 0 else 0
        return min(size, equity * 0.05 / entry_price)  # Max 5% of equity in one position

    @property
    def status(self) -> dict:
        return {
            "atr": round(self._last_atr or 0, 4),
            "trail_high": round(self._trail_high or 0, 2),
            "entry": round(self._entry_price or 0, 2),
            "initial_stop": round(self._initial_stop or 0, 2),
            "current_stop": round(self.trailing_stop(self._trail_high or 0), 2) if self._entry_price else 0,
            "break_even": self._break_even_triggered,
        }

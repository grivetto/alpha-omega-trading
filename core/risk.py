"""Global Risk Engine — unified capital tracking, drawdown limits, ATR stop-loss."""
import math, json
from pathlib import Path
from typing import Optional

CONFIG_PATH = Path(__file__).parent.parent / "config" / "config.json"


class GlobalRiskEngine:
    """Central risk authority for all strategies.
    
    Tracks total capital, current drawdown, enforces max drawdown limit,
    and provides ATR-based dynamic stop-loss calculation.
    """

    def __init__(self, initial_capital: float = None, config_path: Path = CONFIG_PATH):
        self._cfg = self._load_config(config_path)
        risk_cfg = self._cfg.get("risk", {})
        self.initial_capital = initial_capital or self._cfg.get("trading", {}).get("total_capital_usdc", 200)
        self.peak_capital = self.initial_capital
        self.current_capital = self.initial_capital
        self.max_drawdown_pct = risk_cfg.get("max_daily_loss_pct", 3.0)
        self.circuit_breaker_pct = risk_cfg.get("circuit_breaker_pct", 5.0)
        self.kelly_fraction = risk_cfg.get("kelly_fraction", 0.5)
        self.max_consecutive_losses = risk_cfg.get("max_consecutive_losses", 3)
        self.atr_period = risk_cfg.get("atr_period", 14)
        self.atr_trail_mult = risk_cfg.get("atr_trail_multiplier", 1.5)
        self.break_even_r = risk_cfg.get("break_even_r", 1.0)
        self.max_risk_pct = risk_cfg.get("max_risk_per_trade_pct", 1.0)
        # State
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._halted = False
        self._last_atr: Optional[float] = None

    def _load_config(self, path: Path) -> dict:
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return {}

    # ── Capital & Drawdown ──

    def update_capital(self, current: float, trade_pnl: float = 0.0):
        self.current_capital = current
        self._daily_pnl += trade_pnl
        if current > self.peak_capital:
            self.peak_capital = current
        if trade_pnl < -0.01:
            self._consecutive_losses += 1
        elif trade_pnl > 0.01:
            self._consecutive_losses = 0

    @property
    def drawdown_pct(self) -> float:
        if self.peak_capital <= 0:
            return 0
        return (self.peak_capital - self.current_capital) / self.peak_capital * 100

    @property
    def daily_loss_pct(self) -> float:
        return abs(self._daily_pnl) / max(self.initial_capital, 1) * 100

    # ── Risk Factor ──

    def calc_risk_factor(self, capital: float = None, drawdown: float = None) -> float:
        """Return a multiplier (0-1) for position sizing."""
        capital = capital or self.current_capital
        drawdown = drawdown or self.drawdown_pct
        factor = 1.0
        if self._consecutive_losses >= 2:
            factor *= 0.7
        if drawdown > self.max_drawdown_pct:
            factor *= 0.5
        if self._consecutive_losses >= self.max_consecutive_losses:
            factor *= 0.0  # Block
        if self.daily_loss_pct > self.circuit_breaker_pct:
            factor = 0.0  # Halt
            self._halted = True
        kelly = min(1.0, self.kelly_fraction)
        factor *= kelly
        return max(0.0, factor)

    def can_trade(self) -> bool:
        return not self._halted and self.calc_risk_factor() > 0

    # ── ATR Stop-Loss ──

    def calculate_atr(self, ohlcv: list) -> float:
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

    def apply_atr_stoploss(self, entry_price: float, current_price: float, side: str = "long") -> float:
        """Return stop-loss price based on ATR trailing logic."""
        atr = self._last_atr or (entry_price * 0.02)
        if side == "long":
            return current_price - (atr * self.atr_trail_mult)
        return current_price + (atr * self.atr_trail_mult)

    def position_size(self, equity: float, entry_price: float, atr: float = None) -> float:
        """Calculate position size such that max_risk_pct of equity is at risk."""
        atr = atr or self._last_atr or (entry_price * 0.02)
        if atr <= 0:
            return 0.0
        risk_amount = equity * (self.max_risk_pct / 100)
        stop_distance = atr * self.atr_trail_mult
        size = risk_amount / stop_distance if stop_distance > 0 else 0
        factor = self.calc_risk_factor()
        return min(size * factor, equity * 0.05 / entry_price)  # Max 5% per position

    def reset_day(self, equity: float):
        self._daily_pnl = 0.0
        self._consecutive_losses = 0
        self._halted = False
        self.current_capital = equity
        self.peak_capital = max(self.peak_capital, equity)

    @property
    def status(self) -> dict:
        return {
            "capital": round(self.current_capital, 2),
            "peak": round(self.peak_capital, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "daily_loss_pct": round(self.daily_loss_pct, 2),
            "consecutive_losses": self._consecutive_losses,
            "halted": self._halted,
            "risk_factor": round(self.calc_risk_factor(), 3),
            "atr": round(self._last_atr or 0, 4),
        }


class StrategySizeMixin:
    """Mixin for BaseStrategy to use GlobalRiskEngine sizing."""

    def __init__(self, risk_engine: GlobalRiskEngine, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.risk = risk_engine

    def _size(self, capital: float, price: float, atr: float = None) -> float:
        factor = self.risk.calc_risk_factor()
        size = self.risk.position_size(capital, price, atr)
        return size * factor

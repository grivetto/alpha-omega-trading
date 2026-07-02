#!/usr/bin/env python3
"""
DENARO CORE — Exchange-agnostic risk and position sizing logic.
Pure math, no ccxt, no exchange dependencies. EUR quote currency.
"""

import json
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, List


# ──────────────────────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────────────────────

class CBState(str, Enum):
    """Circuit breaker state."""
    CLOSED = "CLOSED"
    HALF_OPEN = "HALF_OPEN"
    OPEN = "OPEN"


class Trend(str, Enum):
    """Market trend for adaptive sizing."""
    BULL = "BULL"
    BEAR = "BEAR"
    RANGING = "RANGING"


# ──────────────────────────────────────────────────────────────
# Data classes
# ──────────────────────────────────────────────────────────────

@dataclass
class AdaptiveState:
    """Runtime adaptive parameters."""
    trend: Trend = Trend.RANGING
    volatility_regime: str = "normal"
    atr_pct: float = 0.002
    volume_spike: bool = False
    bid_ask_imbalance: float = 1.0
    last_trade_pnl: float = 0.0
    consecutive_losses: int = 0
    sizing_multiplier: float = 1.0
    cycle_count: int = 0


@dataclass
class PerfState:
    """Performance tracking."""
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    peak_capital: float = 0.0
    max_drawdown: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    last_trade_ts: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.win_trades / self.total_trades

    def record_trade(self, pnl_pct: float) -> None:
        self.total_trades += 1
        self.last_trade_ts = time.time()
        if pnl_pct > 0:
            self.win_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.loss_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        self.total_pnl += pnl_pct
        self.daily_pnl += pnl_pct


@dataclass
class CircuitBreakerState:
    """Circuit breaker persistence."""
    state: CBState = CBState.CLOSED
    reason: str = ""
    since: float = 0.0
    daily_loss_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0


@dataclass
class CoreState:
    """Persistable core state for DOGE/EUR pair."""
    initial_capital: float = 100.0
    current_capital: float = 100.0
    peak_capital: float = 100.0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    day_start_capital: float = 100.0
    last_daily_reset: float = 0.0
    trade_results: List[float] = field(default_factory=list)
    kelly_fraction: float = 0.25
    sizing_multiplier: float = 1.0
    consecutive_losses: int = 0
    cb: CircuitBreakerState = field(default_factory=CircuitBreakerState)
    perf: PerfState = field(default_factory=PerfState)
    adaptive: AdaptiveState = field(default_factory=AdaptiveState)

    @property
    def can_trade(self) -> bool:
        """Check if trading is allowed based on CB state."""
        if self.cb.state == CBState.OPEN:
            return False
        if self.cb.state == CBState.HALF_OPEN:
            return True  # Reduced sizing
        return True


# ──────────────────────────────────────────────────────────────
# Denaro Core - Risk Manager
# ──────────────────────────────────────────────────────────────

DEFAULT_CB_PATH = Path("/tmp/denaro_cb_state.json")


class DenaroCore:
    """Pure risk and position sizing logic. NO exchange dependencies."""

    def __init__(
        self,
        initial_capital: float = 100.0,
        daily_loss_limit: float = 0.05,
        max_drawdown_limit: float = 0.02,
        max_consecutive_losses: int = 4,
        compound_threshold: float = 1.0,
        compound_ratio: float = 0.5,
        state_path: Optional[Path] = DEFAULT_CB_PATH,
    ):
        self._daily_loss_limit = daily_loss_limit
        self._max_drawdown_limit = max_drawdown_limit
        self._max_consecutive_losses = max_consecutive_losses
        self._compound_threshold = compound_threshold
        self._compound_ratio = compound_ratio
        self._state_path = state_path

        self.state = self._load_state(initial_capital)
        self._kelly_updated_at: float = 0.0

    def _load_state(self, initial_capital: float) -> CoreState:
        """Load or initialize state."""
        if self._state_path and self._state_path.exists():
            try:
                with open(self._state_path, "r") as f:
                    data = json.load(f)
                    cb_data = data.get("cb", {})
                    cb_state = CircuitBreakerState(
                        state=CBState(cb_data.get("state", "CLOSED")),
                        reason=cb_data.get("reason", ""),
                        since=cb_data.get("since", 0.0),
                        daily_loss_pct=cb_data.get("daily_loss_pct", 0.0),
                        max_drawdown_pct=cb_data.get("max_drawdown_pct", 0.0),
                        consecutive_losses=cb_data.get("consecutive_losses", 0),
                    )
                    perf = PerfState(**data.get("perf", {}))
                    adaptive = AdaptiveState(**data.get("adaptive", {}))
                    trade_results = data.get("trade_results", [])
                return CoreState(
                    initial_capital=data.get("initial_capital", initial_capital),
                    current_capital=data.get("current_capital", initial_capital),
                    peak_capital=data.get("peak_capital", initial_capital),
                    total_pnl=data.get("total_pnl", 0.0),
                    daily_pnl=data.get("daily_pnl", 0.0),
                    day_start_capital=data.get("day_start_capital", initial_capital),
                    last_daily_reset=data.get("last_daily_reset", 0.0),
                    trade_results=trade_results,
                    kelly_fraction=data.get("kelly_fraction", 0.25),
                    sizing_multiplier=data.get("sizing_multiplier", 1.0),
                    consecutive_losses=data.get("consecutive_losses", 0),
                    cb=cb_state,
                    perf=perf,
                    adaptive=adaptive,
                )
            except Exception:
                pass
        # Initialize fresh state
        return CoreState(initial_capital=initial_capital)

    def _save_state(self) -> None:
        """Atomic write of state to JSON."""
        if not self._state_path:
            return
        data = {
            "initial_capital": self.state.initial_capital,
            "current_capital": self.state.current_capital,
            "peak_capital": self.state.peak_capital,
            "total_pnl": self.state.total_pnl,
            "daily_pnl": self.state.daily_pnl,
            "day_start_capital": self.state.day_start_capital,
            "last_daily_reset": self.state.last_daily_reset,
            "trade_results": self.state.trade_results,
            "kelly_fraction": self.state.kelly_fraction,
            "sizing_multiplier": self.state.sizing_multiplier,
            "consecutive_losses": self.state.consecutive_losses,
            "cb": {
                "state": self.state.cb.state.value,
                "reason": self.state.cb.reason,
                "since": self.state.cb.since,
                "daily_loss_pct": self.state.cb.daily_loss_pct,
                "max_drawdown_pct": self.state.cb.max_drawdown_pct,
                "consecutive_losses": self.state.cb.consecutive_losses,
            },
            "perf": asdict(self.state.perf),
            "adaptive": asdict(self.state.adaptive),
        }
        temp_path = self._state_path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(data, indent=2))
        temp_path.rename(self._state_path)

    # ─────────────────────────────────────
    # Daily Reset
    # ─────────────────────────────────────

    def _next_daily_reset(self) -> float:
        """UTC midnight tomorrow."""
        now = time.time()
        struct = time.gmtime(now)
        tomorrow = time.mktime((
            struct.tm_year, struct.tm_mon, struct.tm_mday + 1,
            0, 0, 0, struct.tm_wday, struct.tm_yday, struct.tm_gmtoff
        ))
        return tomorrow

    def check_daily_reset(self) -> None:
        """Reset daily counters if needed."""
        now = time.time()
        if now >= self.state.last_daily_reset:
            self.state.daily_pnl = 0.0
            self.state.day_start_capital = self.state.current_capital
            self.state.consecutive_losses = 0
            self.state.last_daily_reset = self._next_daily_reset()

    # ─────────────────────────────────────
    # Circuit Breaker
    # ─────────────────────────────────────

    def check_circuit_breaker(self, current_equity: float) -> bool:
        """Check and enforce CB rules. Returns True if CB triggered."""
        self.check_daily_reset()

        # Update capital
        self.state.current_capital = current_equity
        if current_equity > self.state.peak_capital:
            self.state.peak_capital = current_equity

        # Calculate PnL
        self.state.total_pnl = current_equity - self.state.initial_capital
        self.state.daily_pnl = current_equity - self.state.day_start_capital
        pnl_pct = self.state.total_pnl / self.state.initial_capital
        daily_pnl_pct = self.state.daily_pnl / self.state.initial_capital

        # Drawdown
        if self.state.peak_capital > 0:
            drawdown = (self.state.peak_capital - current_equity) / self.state.peak_capital
            self.state.cb.max_drawdown_pct = drawdown
        else:
            drawdown = 0.0

        self.state.cb.state = CBState.CLOSED
        self.state.cb.reason = ""
        self.state.cb.since = 0.0
        self.state.cb.consecutive_losses = 0

        if daily_pnl_pct <= -self._daily_loss_limit:
            self.state.cb.state = CBState.OPEN
            self.state.cb.reason = f"daily_loss_{self._daily_loss_limit*100:.0f}%"
            self.state.cb.since = time.time()
        elif self.state.perf.consecutive_losses >= self._max_consecutive_losses:
            self.state.cb.state = CBState.HALF_OPEN
            self.state.cb.reason = f"consecutive_losses_{self.state.perf.consecutive_losses}"
            self.state.cb.since = time.time()
        elif drawdown >= self._max_drawdown_limit:
            self.state.cb.state = CBState.OPEN
            self.state.cb.reason = f"drawdown_{self._max_drawdown_limit*100:.0f}%"
            self.state.cb.since = time.time()
        else:
            # Auto-recovery checks
            if (
                self.state.cb.state != CBState.CLOSED
                and drawdown < self._max_drawdown_limit * 0.5
                and daily_pnl_pct > -self._daily_loss_limit * 0.5
            ):
                self.state.cb.state = CBState.CLOSED
                self.state.cb.reason = ""
                self.state.cb.since = 0.0

        # Apply sizing multipliers
        if self.state.cb.state == CBState.HALF_OPEN:
            self.state.sizing_multiplier = 0.5
        elif self.state.perf.consecutive_losses >= self._max_consecutive_losses:
            self.state.sizing_multiplier = 0.5
        elif self.state.perf.consecutive_wins >= 3:
            self.state.sizing_multiplier = min(2.0, self.state.sizing_multiplier + 0.1)
        else:
            self.state.sizing_multiplier = 1.0

        triggered = self.state.cb.state == CBState.OPEN
        if triggered:
            self._save_state()
        return triggered

    # ─────────────────────────────────────
    # Kelly Sizing
    # ─────────────────────────────────────

    def update_kelly(self, pnl_pct: float) -> None:
        """Record trade and update Kelly fraction."""
        self.state.trade_results.append(pnl_pct)
        self.state.perf.record_trade(pnl_pct)

        # Update Kelly every 10 trades or hourly
        now = time.time()
        if len(self.state.trade_results) >= 10 and now - self._kelly_updated_at > 3600:
            self._calculate_kelly()
            self._kelly_updated_at = now
        self._save_state()

    def _calculate_kelly(self) -> None:
        """Calculate optimal Kelly fraction from trade history."""
        if len(self.state.trade_results) < 10:
            return

        recent = self.state.trade_results[-50:]
        wins = [p for p in recent if p > 0]
        losses = [p for p in recent if p <= 0]

        if not wins or not losses:
            return

        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        win_rate = len(wins) / len(recent)

        # Kelly formula: f* = (p * b - q) / b
        if avg_loss > 0:
            b = avg_win / avg_loss
            kelly = (win_rate * b - (1 - win_rate)) / b
            # Clamp to [0.05, 0.50] with 25% safety factor
            self.state.kelly_fraction = max(0.05, min(0.50, kelly * 0.25))

        # Boost Kelly on sustained high win rate
        if len(self.state.trade_results) >= 20 and win_rate > 0.70:
            self.state.kelly_fraction = min(0.50, self.state.kelly_fraction * 2.0)
        elif len(self.state.trade_results) >= 20 and win_rate > 0.60:
            self.state.kelly_fraction = min(0.50, self.state.kelly_fraction * 1.5)

    @property
    def kelly_fraction(self) -> float:
        """Current Kelly fraction to risk."""
        return self.state.kelly_fraction * self.state.sizing_multiplier

    # ─────────────────────────────────────
    # Position Sizing
    # ─────────────────────────────────────

    def position_size(self, capital: float, allocation_pct: float = 1.0) -> float:
        """Calculate position size: capital × allocation × Kelly × vol_adj."""
        volatility_adj = self._volatility_adjustment()
        return capital * allocation_pct * self.kelly_fraction * volatility_adj

    def _volatility_adjustment(self) -> float:
        """Adjust position size based on ATR volatility regime."""
        regime = self.state.adaptive.volatility_regime
        if regime == "low":
            return 1.5  # Larger positions in low vol
        elif regime == "high":
            return 0.5  # Smaller positions in high vol
        return 1.0  # Normal volatility

    # ─────────────────────────────────────
    # Compounding
    # ─────────────────────────────────────

    def compound_profits(self, capital: float) -> float:
        """Reinvest 50% of profits above €1 threshold."""
        profit = capital - self.state.initial_capital
        if profit > self._compound_threshold:
            reinvest = profit * self._compound_ratio
            self.state.initial_capital += reinvest
            self._save_state()
        return self.state.initial_capital

    # ─────────────────────────────────────
    # ATR Calculation
    # ─────────────────────────────────────

    def calculate_atr(self, ohlcv: List[List[float]], period: int = 14) -> float:
        """Calculate ATR from OHLCV data. Returns ATR as percentage of price."""
        if len(ohlcv) < period + 1:
            return 0.0

        tr_values = []
        prev_high = ohlcv[0][2]
        prev_low = ohlcv[0][3]
        prev_close = ohlcv[0][4]

        for i in range(1, len(ohlcv)):
            high = ohlcv[i][2]
            low = ohlcv[i][3]
            close = ohlcv[i][4]

            tr1 = high - low
            tr2 = abs(high - prev_close)
            tr3 = abs(low - prev_close)
            tr = max(tr1, tr2, tr3)
            tr_values.append(tr)

            prev_high = high
            prev_low = low
            prev_close = close

        if not tr_values:
            return 0.0

        atr = sum(tr_values[-period:]) / period
        last_close = ohlcv[-1][4]
        if last_close > 0:
            atr_pct = atr / last_close
        else:
            atr_pct = 0.0

        # Update volatility regime in adaptive state
        if atr_pct < 0.005:
            regime = "low"
        elif atr_pct > 0.02:
            regime = "high"
        else:
            regime = "normal"

        self.state.adaptive.atr_pct = atr_pct
        self.state.adaptive.volatility_regime = regime

        return atr_pct
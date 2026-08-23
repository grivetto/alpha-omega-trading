#!/usr/bin/env python3
"""Denaro v6 — domain types: enums and persistent state dataclasses.

Backward-compatible with v4/v5 state files: every new field has a default,
so old JSON state loads cleanly and the new state saves without schema drift.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import List


# --- Enums ------------------------------------------------------------------

class CBState(str, Enum):
    CLOSED = "CLOSED"
    HALF_OPEN = "HALF_OPEN"
    OPEN = "OPEN"


class Trend(str, Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    RANGING = "RANGING"


class StrategyMode(str, Enum):
    GRID = "GRID"
    DCA = "DCA"
    HYBRID = "HYBRID"
    COOLDOWN = "COOLDOWN"


# --- Market state ------------------------------------------------------------

@dataclass
class MicroState:
    """Order-book derived microstructure snapshot."""
    bid_ask_spread_pct: float = 0.001
    bid_ask_imbalance: float = 1.0
    order_book_slope: float = 0.0
    cum_bid_depth_1pct: float = 0.0
    cum_ask_depth_1pct: float = 0.0
    last_price_micro: float = 0.0
    micro_trend: float = 0.0
    micro_volatility: float = 0.0
    spoofing_flag: bool = False
    support_levels: List[float] = field(default_factory=list)
    resistance_levels: List[float] = field(default_factory=list)


@dataclass
class RegimeState:
    """Macro regime + v6 dump-defense state machine + v7 enhanced signals."""
    trend: Trend = Trend.RANGING
    trend_strength: float = 0.0
    volatility_regime: str = "normal"          # low | normal | high | extreme
    atr_pct: float = 0.002
    volume_regime: str = "normal"              # low | normal | high | spike
    volume_ratio: float = 1.0
    momentum_1h: float = 0.0
    momentum_24h: float = 0.0
    momentum_confidence: float = 0.0
    regime_confidence: float = 0.7
    regime_duration_cycles: int = 0
    # v6 — dump defense
    dump_mode: bool = False
    dump_since: float = 0.0
    dump_reason: str = ""
    recovery_cycles: int = 0
    # v7 — enhanced indicator signals
    rsi_signal: str = "neutral"
    macd_signal: str = "neutral"
    bb_signal: str = "neutral"
    volume_profile: str = "neutral"
    combined_signal: str = "neutral"
    signal_confidence: float = 0.0
    last_regime_update: int = 0


@dataclass
class VaRState:
    var_95_1h: float = 0.02
    var_99_1h: float = 0.035
    cvar_95_1h: float = 0.03
    max_drawdown: float = 0.0
    var_lookback: List[float] = field(default_factory=list)
    daily_var_breaches: int = 0


# --- Performance --------------------------------------------------------------

@dataclass
class PerfMetrics:
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    total_pnl_pct: float = 0.0
    daily_pnl_pct: float = 0.0
    peak_capital: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    wins_streak_max: int = 0
    losses_streak_max: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    recovery_factor: float = 0.0
    profit_factor: float = 0.0
    expectancy: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    win_rate: float = 0.0
    last_trade_ts: float = 0.0

    def update(self, pnl_pct: float) -> None:
        self.total_trades += 1
        self.last_trade_ts = time.time()
        if pnl_pct > 0:
            self.win_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
            self.wins_streak_max = max(self.wins_streak_max, self.consecutive_wins)
        else:
            self.loss_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
            self.losses_streak_max = max(self.losses_streak_max, self.consecutive_losses)
        self.total_pnl_pct += pnl_pct
        self.daily_pnl_pct += pnl_pct
        self.win_rate = self.win_trades / self.total_trades if self.total_trades else 0

    def recalc_ratios(self, trade_results: List[float], peak_capital: float,
                      current_capital: float, initial_capital: float) -> None:
        n = len(trade_results)
        if n < 5:
            return
        wins = [p for p in trade_results if p > 0]
        losses = [p for p in trade_results if p <= 0]
        self.avg_win = sum(wins) / len(wins) if wins else 0
        self.avg_loss = abs(sum(losses) / len(losses)) if losses else 0
        self.expectancy = self.win_rate * self.avg_win - (1 - self.win_rate) * self.avg_loss
        gross_win = sum(wins)
        gross_loss = abs(sum(losses))
        self.profit_factor = gross_win / gross_loss if gross_loss > 1e-10 else 0
        returns = trade_results[-100:]
        if len(returns) >= 10:
            mu = sum(returns) / len(returns)
            valid = [r for r in returns if abs(r) > 1e-12]
            if len(valid) >= 10:
                var_ = sum((r - mu) ** 2 for r in valid) / len(valid)
                sigma = math.sqrt(var_)
                neg = [r for r in valid if r < 0]
                dvar = sum(r ** 2 for r in neg) / len(neg) if neg else 1e-6
                downside = math.sqrt(dvar)
                self.sharpe_ratio = mu / sigma * math.sqrt(365) if sigma > 1e-10 else 0
                self.sortino_ratio = mu / downside * math.sqrt(365) if downside > 1e-10 else 0
        dd = max(0.001, (peak_capital - current_capital) / peak_capital) if peak_capital > 0 else 0.001
        total_return = (current_capital - initial_capital) / initial_capital if initial_capital > 0 else 0
        self.calmar_ratio = total_return / dd * 100 if dd > 0.001 else 0
        mdd = peak_capital - current_capital if peak_capital > current_capital else 1
        self.recovery_factor = (current_capital - initial_capital) / mdd if mdd > 0.001 else 0


# --- Execution state ----------------------------------------------------------

@dataclass
class DCAState:
    active: bool = False
    entry_price: float = 0.0
    avg_entry_price: float = 0.0
    total_size: float = 0.0
    total_cost: float = 0.0
    num_entries: int = 0
    max_entries: int = 5
    entry_spacing_pct: float = 0.03
    last_entry_price: float = 0.0
    target_pnl_pct: float = 0.03
    trailing_activation: float = 0.0
    trailing_stop_pct: float = 0.015


@dataclass
class ExecutionState:
    active_strategy: StrategyMode = StrategyMode.GRID
    grid_levels_active: int = 0
    grid_target_levels: int = 5
    dca_position_active: bool = False
    profit_take_order_id: str = ""
    last_rebalance_ts: float = 0.0
    last_cycle_ms: float = 0.0
    errors_this_hour: int = 0
    cycle_count: int = 0
    # v6 — zero-touch bookkeeping
    last_cycle_ok: bool = True
    rebalance_count: int = 0
    dump_events: int = 0
    redeploy_count: int = 0


@dataclass
class CircuitBreakerState:
    state: CBState = CBState.CLOSED
    reason: str = ""
    since: float = 0.0
    daily_loss_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0


# --- Aggregate state ----------------------------------------------------------

@dataclass
class CoreState:
    initial_capital: float = 100.0
    current_capital: float = 100.0
    peak_capital: float = 100.0
    day_start_capital: float = 100.0
    last_daily_reset: float = 0.0
    trade_results: List[float] = field(default_factory=list)
    kelly_fraction: float = 0.25
    sizing_multiplier: float = 1.0
    cb: "CircuitBreakerState" = field(default_factory=CircuitBreakerState)
    perf: PerfMetrics = field(default_factory=PerfMetrics)
    regime: RegimeState = field(default_factory=RegimeState)
    micro: MicroState = field(default_factory=MicroState)
    var: VaRState = field(default_factory=VaRState)
    dca: DCAState = field(default_factory=DCAState)
    exec: ExecutionState = field(default_factory=ExecutionState)
    grid_levels: List[dict] = field(default_factory=list)

    @property
    def can_trade(self) -> bool:
        return self.cb.state != CBState.OPEN

#!/usr/bin/env python3
"""Denaro v6 — state persistence.

Atomic (tmp + rename) throttled saves, backward-compatible load of v4/v5
state files, and the daily capital reset. Zero-touch: corruption or schema
mismatch degrades to a fresh CoreState instead of crashing.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Optional

from .types import (CBState, CircuitBreakerState, CoreState, DCAState,
                    ExecutionState, MicroState, PerfMetrics, RegimeState,
                    StrategyMode, Trend, VaRState)

log = logging.getLogger("kraken_v2")

_DAY_SEC = 86400.0


def default_state_path() -> Path:
    """XDG-style default location for the persistent state file."""
    xdg = __import__("os").environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    state_dir = base / "denaro"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "denaro_core_state.json"


DEFAULT_CB_PATH = default_state_path()


class StateStore:
    """Throttled atomic persistence + daily reset."""

    def __init__(self, path: Optional[Path] = None,
                 min_save_interval: float = 30.0) -> None:
        self.path = Path(path) if path else DEFAULT_CB_PATH
        self.min_save_interval = max(1.0, min_save_interval)
        self._last_save_at: float = 0.0
        self._save_pending: bool = False

    # --- load ----------------------------------------------------------------

    def load(self, initial_capital: float = 100.0) -> CoreState:
        if not self.path.exists():
            return CoreState(initial_capital=initial_capital)
        try:
            with open(self.path) as f:
                d = json.load(f)
            cb = d.get("cb", {})
            regime = d.get("regime", {})
            perf = d.get("perf", {})
            dca = d.get("dca", {})
            exec_ = d.get("exec", {})
            return CoreState(
                initial_capital=d.get("initial_capital", initial_capital),
                current_capital=d.get("current_capital", initial_capital),
                peak_capital=d.get("peak_capital", initial_capital),
                day_start_capital=d.get("day_start_capital", initial_capital),
                last_daily_reset=d.get("last_daily_reset", 0.0),
                trade_results=d.get("trade_results", []),
                kelly_fraction=d.get("kelly_fraction", 0.25),
                sizing_multiplier=d.get("sizing_multiplier", 1.0),
                cb=CircuitBreakerState(
                    state=CBState(cb.get("state", "CLOSED")),
                    reason=cb.get("reason", ""),
                    since=cb.get("since", 0.0),
                    daily_loss_pct=cb.get("daily_loss_pct", 0.0),
                    max_drawdown_pct=cb.get("max_drawdown_pct", 0.0),
                    consecutive_losses=int(cb.get("consecutive_losses", 0)),
                ),
                perf=PerfMetrics(
                    total_trades=int(perf.get("total_trades", 0)),
                    win_trades=int(perf.get("win_trades", 0)),
                    loss_trades=int(perf.get("loss_trades", 0)),
                    total_pnl_pct=perf.get("total_pnl_pct", 0.0),
                    daily_pnl_pct=perf.get("daily_pnl_pct", 0.0),
                    peak_capital=perf.get("peak_capital", 0.0),
                    consecutive_wins=int(perf.get("consecutive_wins", 0)),
                    consecutive_losses=int(perf.get("consecutive_losses", 0)),
                    wins_streak_max=int(perf.get("wins_streak_max", 0)),
                    losses_streak_max=int(perf.get("losses_streak_max", 0)),
                    sharpe_ratio=perf.get("sharpe_ratio", 0.0),
                    sortino_ratio=perf.get("sortino_ratio", 0.0),
                    calmar_ratio=perf.get("calmar_ratio", 0.0),
                    recovery_factor=perf.get("recovery_factor", 0.0),
                    profit_factor=perf.get("profit_factor", 0.0),
                    expectancy=perf.get("expectancy", 0.0),
                    avg_win=perf.get("avg_win", 0.0),
                    avg_loss=perf.get("avg_loss", 0.0),
                    win_rate=perf.get("win_rate", 0.0),
                    last_trade_ts=perf.get("last_trade_ts", 0.0),
                ),
                regime=RegimeState(
                    trend=Trend(regime.get("trend", "RANGING")),
                    trend_strength=regime.get("trend_strength", 0.0),
                    volatility_regime=regime.get("volatility_regime", "normal"),
                    atr_pct=regime.get("atr_pct", 0.002),
                    volume_regime=regime.get("volume_regime", "normal"),
                    volume_ratio=regime.get("volume_ratio", 1.0),
                    momentum_1h=regime.get("momentum_1h", 0.0),
                    momentum_24h=regime.get("momentum_24h", 0.0),
                    regime_confidence=regime.get("regime_confidence", 0.7),
                    regime_duration_cycles=int(regime.get("regime_duration_cycles", 0)),
                    dump_mode=regime.get("dump_mode", False),
                    dump_since=regime.get("dump_since", 0.0),
                    dump_reason=regime.get("dump_reason", ""),
                    recovery_cycles=int(regime.get("recovery_cycles", 0)),
                ),
                micro=MicroState(**{k: v for k, v in d.get("micro", {}).items()
                                    if k in MicroState.__dataclass_fields__}),
                var=VaRState(**{k: v for k, v in d.get("var", {}).items()
                                if k in VaRState.__dataclass_fields__}),
                dca=DCAState(
                    active=dca.get("active", False),
                    entry_price=dca.get("entry_price", 0.0),
                    avg_entry_price=dca.get("avg_entry_price", 0.0),
                    total_size=dca.get("total_size", 0.0),
                    total_cost=dca.get("total_cost", 0.0),
                    num_entries=int(dca.get("num_entries", 0)),
                    max_entries=int(dca.get("max_entries", 5)),
                    entry_spacing_pct=dca.get("entry_spacing_pct", 0.03),
                    last_entry_price=dca.get("last_entry_price", 0.0),
                    target_pnl_pct=dca.get("target_pnl_pct", 0.03),
                    trailing_activation=dca.get("trailing_activation", 0.0),
                    trailing_stop_pct=dca.get("trailing_stop_pct", 0.015),
                ),
                exec=ExecutionState(
                    active_strategy=StrategyMode(exec_.get("active_strategy", "GRID")),
                    grid_levels_active=int(exec_.get("grid_levels_active", 0)),
                    grid_target_levels=int(exec_.get("grid_target_levels", 5)),
                    dca_position_active=exec_.get("dca_position_active", False),
                    profit_take_order_id=exec_.get("profit_take_order_id", ""),
                    last_rebalance_ts=exec_.get("last_rebalance_ts", 0.0),
                    last_cycle_ms=exec_.get("last_cycle_ms", 0.0),
                    errors_this_hour=int(exec_.get("errors_this_hour", 0)),
                    cycle_count=int(exec_.get("cycle_count", 0)),
                    last_cycle_ok=exec_.get("last_cycle_ok", True),
                    rebalance_count=int(exec_.get("rebalance_count", 0)),
                    dump_events=int(exec_.get("dump_events", 0)),
                    redeploy_count=int(exec_.get("redeploy_count", 0)),
                ),
                grid_levels=d.get("grid_levels", []),
            )
        except Exception as e:
            log.warning(f"State load failed: {e} — starting fresh")
            return CoreState(initial_capital=initial_capital)

    # --- save ----------------------------------------------------------------

    def save(self, state: CoreState) -> None:
        """Throttled atomic save."""
        now = time.time()
        if now - self._last_save_at < self.min_save_interval:
            self._save_pending = True
            return
        self._last_save_at = now
        self._save_pending = False
        try:
            d = self._to_dict(state)
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w") as f:
                json.dump(d, f)
            tmp.replace(self.path)
        except Exception as e:
            log.warning(f"State save failed: {e}")

    def flush(self, state: CoreState) -> None:
        """Force save immediately (shutdown path)."""
        self._last_save_at = 0.0
        self._save_pending = False
        self.save(state)

    def save_pending(self) -> bool:
        return self._save_pending

    # --- daily reset ---------------------------------------------------------

    def maybe_daily_reset(self, state: CoreState, equity: float) -> bool:
        """Reset the daily loss counter at UTC-day boundaries. Returns True if reset."""
        now = time.time()
        if now - state.last_daily_reset <= _DAY_SEC:
            return False
        state.last_daily_reset = now
        state.day_start_capital = max(state.day_start_capital, equity)
        state.cb.daily_loss_pct = 0.0
        state.perf.daily_pnl_pct = 0.0
        return True

    # --- serialization -------------------------------------------------------

    @staticmethod
    def _to_dict(s: CoreState) -> dict:
        return {
            "initial_capital": s.initial_capital,
            "current_capital": s.current_capital,
            "peak_capital": s.peak_capital,
            "day_start_capital": s.day_start_capital,
            "last_daily_reset": s.last_daily_reset,
            "trade_results": s.trade_results[-500:],
            "kelly_fraction": s.kelly_fraction,
            "sizing_multiplier": s.sizing_multiplier,
            "cb": {
                "state": s.cb.state.value,
                "reason": s.cb.reason,
                "since": s.cb.since,
                "daily_loss_pct": s.cb.daily_loss_pct,
                "max_drawdown_pct": s.cb.max_drawdown_pct,
                "consecutive_losses": s.cb.consecutive_losses,
            },
            "perf": {
                "total_trades": s.perf.total_trades,
                "win_trades": s.perf.win_trades,
                "loss_trades": s.perf.loss_trades,
                "total_pnl_pct": s.perf.total_pnl_pct,
                "daily_pnl_pct": s.perf.daily_pnl_pct,
                "peak_capital": s.perf.peak_capital,
                "consecutive_wins": s.perf.consecutive_wins,
                "consecutive_losses": s.perf.consecutive_losses,
                "wins_streak_max": s.perf.wins_streak_max,
                "losses_streak_max": s.perf.losses_streak_max,
                "sharpe_ratio": s.perf.sharpe_ratio,
                "sortino_ratio": s.perf.sortino_ratio,
                "calmar_ratio": s.perf.calmar_ratio,
                "recovery_factor": s.perf.recovery_factor,
                "profit_factor": s.perf.profit_factor,
                "expectancy": s.perf.expectancy,
                "avg_win": s.perf.avg_win,
                "avg_loss": s.perf.avg_loss,
                "win_rate": s.perf.win_rate,
                "last_trade_ts": s.perf.last_trade_ts,
            },
            "regime": {
                "trend": s.regime.trend.value,
                "trend_strength": s.regime.trend_strength,
                "volatility_regime": s.regime.volatility_regime,
                "atr_pct": s.regime.atr_pct,
                "volume_regime": s.regime.volume_regime,
                "volume_ratio": s.regime.volume_ratio,
                "momentum_1h": s.regime.momentum_1h,
                "momentum_24h": s.regime.momentum_24h,
                "regime_confidence": s.regime.regime_confidence,
                "regime_duration_cycles": s.regime.regime_duration_cycles,
                "dump_mode": s.regime.dump_mode,
                "dump_since": s.regime.dump_since,
                "dump_reason": s.regime.dump_reason,
                "recovery_cycles": s.regime.recovery_cycles,
            },
            "micro": {
                "bid_ask_spread_pct": s.micro.bid_ask_spread_pct,
                "bid_ask_imbalance": s.micro.bid_ask_imbalance,
                "order_book_slope": s.micro.order_book_slope,
                "cum_bid_depth_1pct": s.micro.cum_bid_depth_1pct,
                "cum_ask_depth_1pct": s.micro.cum_ask_depth_1pct,
                "last_price_micro": s.micro.last_price_micro,
                "micro_trend": s.micro.micro_trend,
                "micro_volatility": s.micro.micro_volatility,
                "spoofing_flag": s.micro.spoofing_flag,
            },
            "var": {
                "var_95_1h": s.var.var_95_1h,
                "var_99_1h": s.var.var_99_1h,
                "cvar_95_1h": s.var.cvar_95_1h,
                "max_drawdown": s.var.max_drawdown,
                "var_lookback": s.var.var_lookback[-100:],
                "daily_var_breaches": s.var.daily_var_breaches,
            },
            "dca": {
                "active": s.dca.active,
                "entry_price": s.dca.entry_price,
                "avg_entry_price": s.dca.avg_entry_price,
                "total_size": s.dca.total_size,
                "total_cost": s.dca.total_cost,
                "num_entries": s.dca.num_entries,
                "max_entries": s.dca.max_entries,
                "entry_spacing_pct": s.dca.entry_spacing_pct,
                "last_entry_price": s.dca.last_entry_price,
                "target_pnl_pct": s.dca.target_pnl_pct,
                "trailing_activation": s.dca.trailing_activation,
                "trailing_stop_pct": s.dca.trailing_stop_pct,
            },
            "exec": {
                "active_strategy": s.exec.active_strategy.value,
                "grid_levels_active": s.exec.grid_levels_active,
                "grid_target_levels": s.exec.grid_target_levels,
                "dca_position_active": s.exec.dca_position_active,
                "profit_take_order_id": s.exec.profit_take_order_id,
                "last_rebalance_ts": s.exec.last_rebalance_ts,
                "last_cycle_ms": s.exec.last_cycle_ms,
                "errors_this_hour": s.exec.errors_this_hour,
                "cycle_count": s.exec.cycle_count,
                "last_cycle_ok": s.exec.last_cycle_ok,
                "rebalance_count": s.exec.rebalance_count,
                "dump_events": s.exec.dump_events,
                "redeploy_count": s.exec.redeploy_count,
            },
            "grid_levels": s.grid_levels[-20:],
        }

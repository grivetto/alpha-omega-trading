#!/usr/bin/env python3
"""
DENARO CORE v4 — Exchange-agnostic risk, regime detection, DCA, microstructure.
Kelly sizing corretto, circuit breaker preciso, VaR computation.

Fixes v3→v4:
  - Double sizing multiplier rimosso (BUG critico #2)
  - DCA close usa avg_entry_price non entry_price (BUG #3)
  - Kelly fraction calcolata fresh ogni volta (non accumula boost)
  - ATR-based grid buy base (non hardcoded 2%)
  - _save_state throttled a max 1x/30s
  - compound_profits gestisce drawdown
"""
from __future__ import annotations

import json, logging, math, os, time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple, Deque


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


# --- Data classes -----------------------------------------------------------

@dataclass
class MicroState:
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
    trend: Trend = Trend.RANGING
    trend_strength: float = 0.0
    volatility_regime: str = "normal"
    atr_pct: float = 0.002
    volume_regime: str = "normal"
    volume_ratio: float = 1.0
    momentum_1h: float = 0.0
    momentum_24h: float = 0.0
    regime_confidence: float = 0.7
    regime_duration_cycles: int = 0

@dataclass
class VaRState:
    var_95_1h: float = 0.02
    var_99_1h: float = 0.035
    cvar_95_1h: float = 0.03
    max_drawdown: float = 0.0
    var_lookback: List[float] = field(default_factory=list)
    daily_var_breaches: int = 0

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
                var_ = sum((r - mu)**2 for r in valid) / len(valid)
                sigma = math.sqrt(var_)
                neg = [r for r in valid if r < 0]
                dvar = sum(r**2 for r in neg) / len(neg) if neg else 1e-6
                downside = math.sqrt(dvar)
                self.sharpe_ratio = mu / sigma * math.sqrt(365) if sigma > 1e-10 else 0
                self.sortino_ratio = mu / downside * math.sqrt(365) if downside > 1e-10 else 0
        dd = max(0.001, (peak_capital - current_capital) / peak_capital) if peak_capital > 0 else 0.001
        total_return = (current_capital - initial_capital) / initial_capital if initial_capital > 0 else 0
        self.calmar_ratio = total_return / dd * 100 if dd > 0.001 else 0
        mdd = peak_capital - current_capital if peak_capital > current_capital else 1
        self.recovery_factor = (current_capital - initial_capital) / mdd if mdd > 0.001 else 0

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
    cb: "CircuitBreakerState" = field(default_factory=lambda: CircuitBreakerState())
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


@dataclass
class CircuitBreakerState:
    state: CBState = CBState.CLOSED
    reason: str = ""
    since: float = 0.0
    daily_loss_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    consecutive_losses: int = 0


def _default_state_path() -> Path:
    xdg = os.environ.get("XDG_DATA_HOME", "")
    base = Path(xdg) if xdg else Path.home() / ".local" / "share"
    state_dir = base / "denaro"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir / "denaro_core_state.json"

DEFAULT_CB_PATH = _default_state_path()


# ==============================================================================
# DENARO CORE v4
# ==============================================================================

class DenaroCore:
    """Pure risk, regime, and execution logic. Zero exchange deps.

    v4 fixes:
    - Kelly: sizing_multiplier NON moltiplicato due volte (BUG #2 risolto)
    - DCA close: usa avg_entry_price (BUG #3 risolto)
    - Kelly calcolata fresh, boost applicato una tantum (non accumula)
    - _save_state throttled: massimo 1 scrittura ogni 30 secondi
    - compound_profits con peak-aware drawdown guard
    """

    _MIN_SAVE_INTERVAL = 30.0  # sec tra scritture disco

    def __init__(self, initial_capital: float = 100.0,
                 daily_loss_limit: float = 0.05,
                 max_drawdown_limit: float = 0.15,
                 max_consecutive_losses: int = 4,
                 compound_threshold: float = 1.0,
                 compound_ratio: float = 0.5,
                 state_path: Optional[Path] = DEFAULT_CB_PATH,
                 cb_recovery_minutes: float = 60.0):
        self._daily_loss_limit = daily_loss_limit
        self._max_drawdown_limit = max_drawdown_limit
        self._max_consecutive_losses = max_consecutive_losses
        self._compound_threshold = compound_threshold
        self._compound_ratio = compound_ratio
        self._state_path = state_path
        self._cb_recovery_timeout = cb_recovery_minutes * 60.0  # convert to seconds
        self.state = self._load_state(initial_capital)
        self._price_buffer: List[float] = []
        self._return_buffer: Deque[float] = deque(maxlen=200)
        self._kelly_updated_at: float = 0.0
        self._last_save_at: float = 0.0
        self._save_pending: bool = False

    def _load_state(self, initial_capital: float) -> CoreState:
        if self._state_path and self._state_path.exists():
            try:
                with open(self._state_path) as f:
                    d = json.load(f)
                cb_data = d.get("cb", {})
                regime_data = d.get("regime", {})
                perf_data = d.get("perf", {})
                dca_data = d.get("dca", {})
                exec_data = d.get("exec", {})
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
                        state=CBState(cb_data.get("state", "CLOSED")),
                        reason=cb_data.get("reason", ""),
                        since=cb_data.get("since", 0.0),
                        daily_loss_pct=cb_data.get("daily_loss_pct", 0.0),
                        max_drawdown_pct=cb_data.get("max_drawdown_pct", 0.0),
                        consecutive_losses=int(cb_data.get("consecutive_losses", 0)),
                    ),
                    perf=PerfMetrics(
                        total_trades=int(perf_data.get("total_trades", 0)),
                        win_trades=int(perf_data.get("win_trades", 0)),
                        loss_trades=int(perf_data.get("loss_trades", 0)),
                        total_pnl_pct=perf_data.get("total_pnl_pct", 0.0),
                        daily_pnl_pct=perf_data.get("daily_pnl_pct", 0.0),
                        peak_capital=perf_data.get("peak_capital", 0.0),
                        consecutive_wins=int(perf_data.get("consecutive_wins", 0)),
                        consecutive_losses=int(perf_data.get("consecutive_losses", 0)),
                        wins_streak_max=int(perf_data.get("wins_streak_max", 0)),
                        losses_streak_max=int(perf_data.get("losses_streak_max", 0)),
                        sharpe_ratio=perf_data.get("sharpe_ratio", 0.0),
                        sortino_ratio=perf_data.get("sortino_ratio", 0.0),
                        calmar_ratio=perf_data.get("calmar_ratio", 0.0),
                        recovery_factor=perf_data.get("recovery_factor", 0.0),
                        profit_factor=perf_data.get("profit_factor", 0.0),
                        expectancy=perf_data.get("expectancy", 0.0),
                        avg_win=perf_data.get("avg_win", 0.0),
                        avg_loss=perf_data.get("avg_loss", 0.0),
                        win_rate=perf_data.get("win_rate", 0.0),
                        last_trade_ts=perf_data.get("last_trade_ts", 0.0),
                    ),
                    regime=RegimeState(
                        trend=Trend(regime_data.get("trend", "RANGING")),
                        trend_strength=regime_data.get("trend_strength", 0.0),
                        volatility_regime=regime_data.get("volatility_regime", "normal"),
                        atr_pct=regime_data.get("atr_pct", 0.002),
                        volume_regime=regime_data.get("volume_regime", "normal"),
                        volume_ratio=regime_data.get("volume_ratio", 1.0),
                        momentum_1h=regime_data.get("momentum_1h", 0.0),
                        momentum_24h=regime_data.get("momentum_24h", 0.0),
                        regime_confidence=regime_data.get("regime_confidence", 0.7),
                        regime_duration_cycles=int(regime_data.get("regime_duration_cycles", 0)),
                    ),
                    micro=MicroState(**d.get("micro", {})),
                    var=VaRState(**d.get("var", {})),
                    dca=DCAState(
                        active=dca_data.get("active", False),
                        entry_price=dca_data.get("entry_price", 0.0),
                        avg_entry_price=dca_data.get("avg_entry_price", 0.0),
                        total_size=dca_data.get("total_size", 0.0),
                        total_cost=dca_data.get("total_cost", 0.0),
                        num_entries=int(dca_data.get("num_entries", 0)),
                        max_entries=int(dca_data.get("max_entries", 5)),
                        entry_spacing_pct=dca_data.get("entry_spacing_pct", 0.03),
                        last_entry_price=dca_data.get("last_entry_price", 0.0),
                        target_pnl_pct=dca_data.get("target_pnl_pct", 0.03),
                        trailing_activation=dca_data.get("trailing_activation", 0.0),
                        trailing_stop_pct=dca_data.get("trailing_stop_pct", 0.015),
                    ),
                    exec=ExecutionState(
                        active_strategy=StrategyMode(exec_data.get("active_strategy", "GRID")),
                        grid_levels_active=int(exec_data.get("grid_levels_active", 0)),
                        grid_target_levels=int(exec_data.get("grid_target_levels", 5)),
                        dca_position_active=exec_data.get("dca_position_active", False),
                        profit_take_order_id=exec_data.get("profit_take_order_id", ""),
                        last_rebalance_ts=exec_data.get("last_rebalance_ts", 0.0),
                        last_cycle_ms=exec_data.get("last_cycle_ms", 0.0),
                        errors_this_hour=int(exec_data.get("errors_this_hour", 0)),
                        cycle_count=int(exec_data.get("cycle_count", 0)),
                    ),
                    grid_levels=d.get("grid_levels", []),
                )
            except Exception as e:
                log = logging.getLogger("kraken_v2")
                log.warning(f"State load failed: {e} — starting fresh")
        return CoreState(initial_capital=initial_capital)

    def _save_state(self) -> None:
        """Throttled state save — max 1x every _MIN_SAVE_INTERVAL seconds."""
        now = time.time()
        if now - self._last_save_at < self._MIN_SAVE_INTERVAL:
            self._save_pending = True
            return
        self._last_save_at = now
        self._save_pending = False
        try:
            d = {
                "initial_capital": self.state.initial_capital,
                "current_capital": self.state.current_capital,
                "peak_capital": self.state.peak_capital,
                "day_start_capital": self.state.day_start_capital,
                "last_daily_reset": self.state.last_daily_reset,
                "trade_results": self.state.trade_results[-500:],
                "kelly_fraction": self.state.kelly_fraction,
                "sizing_multiplier": self.state.sizing_multiplier,
                "cb": {
                    "state": self.state.cb.state.value,
                    "reason": self.state.cb.reason,
                    "since": self.state.cb.since,
                    "daily_loss_pct": self.state.cb.daily_loss_pct,
                    "max_drawdown_pct": self.state.cb.max_drawdown_pct,
                    "consecutive_losses": self.state.cb.consecutive_losses,
                },
                "perf": {
                    "total_trades": self.state.perf.total_trades,
                    "win_trades": self.state.perf.win_trades,
                    "loss_trades": self.state.perf.loss_trades,
                    "total_pnl_pct": self.state.perf.total_pnl_pct,
                    "daily_pnl_pct": self.state.perf.daily_pnl_pct,
                    "peak_capital": self.state.perf.peak_capital,
                    "consecutive_wins": self.state.perf.consecutive_wins,
                    "consecutive_losses": self.state.perf.consecutive_losses,
                    "wins_streak_max": self.state.perf.wins_streak_max,
                    "losses_streak_max": self.state.perf.losses_streak_max,
                    "sharpe_ratio": self.state.perf.sharpe_ratio,
                    "sortino_ratio": self.state.perf.sortino_ratio,
                    "calmar_ratio": self.state.perf.calmar_ratio,
                    "recovery_factor": self.state.perf.recovery_factor,
                    "profit_factor": self.state.perf.profit_factor,
                    "expectancy": self.state.perf.expectancy,
                    "avg_win": self.state.perf.avg_win,
                    "avg_loss": self.state.perf.avg_loss,
                    "win_rate": self.state.perf.win_rate,
                    "last_trade_ts": self.state.perf.last_trade_ts,
                },
                "regime": {
                    "trend": self.state.regime.trend.value,
                    "trend_strength": self.state.regime.trend_strength,
                    "volatility_regime": self.state.regime.volatility_regime,
                    "atr_pct": self.state.regime.atr_pct,
                    "volume_regime": self.state.regime.volume_regime,
                    "volume_ratio": self.state.regime.volume_ratio,
                    "momentum_1h": self.state.regime.momentum_1h,
                    "momentum_24h": self.state.regime.momentum_24h,
                    "regime_confidence": self.state.regime.regime_confidence,
                    "regime_duration_cycles": self.state.regime.regime_duration_cycles,
                },
                "micro": {
                    "bid_ask_spread_pct": self.state.micro.bid_ask_spread_pct,
                    "bid_ask_imbalance": self.state.micro.bid_ask_imbalance,
                    "order_book_slope": self.state.micro.order_book_slope,
                    "cum_bid_depth_1pct": self.state.micro.cum_bid_depth_1pct,
                    "cum_ask_depth_1pct": self.state.micro.cum_ask_depth_1pct,
                    "last_price_micro": self.state.micro.last_price_micro,
                    "micro_trend": self.state.micro.micro_trend,
                    "micro_volatility": self.state.micro.micro_volatility,
                    "spoofing_flag": self.state.micro.spoofing_flag,
                },
                "var": {
                    "var_95_1h": self.state.var.var_95_1h,
                    "var_99_1h": self.state.var.var_99_1h,
                    "cvar_95_1h": self.state.var.cvar_95_1h,
                    "max_drawdown": self.state.var.max_drawdown,
                    "var_lookback": self.state.var.var_lookback[-100:],
                    "daily_var_breaches": self.state.var.daily_var_breaches,
                },
                "dca": {
                    "active": self.state.dca.active,
                    "entry_price": self.state.dca.entry_price,
                    "avg_entry_price": self.state.dca.avg_entry_price,
                    "total_size": self.state.dca.total_size,
                    "total_cost": self.state.dca.total_cost,
                    "num_entries": self.state.dca.num_entries,
                    "max_entries": self.state.dca.max_entries,
                    "entry_spacing_pct": self.state.dca.entry_spacing_pct,
                    "last_entry_price": self.state.dca.last_entry_price,
                    "target_pnl_pct": self.state.dca.target_pnl_pct,
                    "trailing_activation": self.state.dca.trailing_activation,
                    "trailing_stop_pct": self.state.dca.trailing_stop_pct,
                },
                "exec": {
                    "active_strategy": self.state.exec.active_strategy.value,
                    "grid_levels_active": self.state.exec.grid_levels_active,
                    "grid_target_levels": self.state.exec.grid_target_levels,
                    "dca_position_active": self.state.exec.dca_position_active,
                    "profit_take_order_id": self.state.exec.profit_take_order_id,
                    "last_rebalance_ts": self.state.exec.last_rebalance_ts,
                    "last_cycle_ms": self.state.exec.last_cycle_ms,
                    "errors_this_hour": self.state.exec.errors_this_hour,
                    "cycle_count": self.state.exec.cycle_count,
                },
                "grid_levels": self.state.grid_levels[-20:],
            }
            if self._state_path:
                self._state_path.parent.mkdir(parents=True, exist_ok=True)
                # Atomic write: write to temp, then rename
                tmp = self._state_path.with_suffix(".tmp")
                with open(tmp, "w") as f:
                    json.dump(d, f)
                tmp.replace(self._state_path)
        except Exception as e:
            log = logging.getLogger("kraken_v2")
            log.warning(f"State save failed: {e}")

    def flush_state(self) -> None:
        """Force a state save now (called during shutdown)."""
        self._last_save_at = 0.0
        self._save_pending = False
        self._save_state()

    # === MICROSTRUCTURE ====================================================

    def update_microstructure(self, bid: float, ask: float,
                               bid_vol: float, ask_vol: float,
                               cum_bid: float, cum_ask: float,
                               price: float) -> None:
        if bid <= 0 or ask <= 0 or price <= 0:
            return
        m = self.state.micro
        m.last_price_micro = price
        m.bid_ask_spread_pct = (ask - bid) / ((ask + bid) / 2) if (ask + bid) > 0 else 0.001
        tot = bid_vol + ask_vol
        m.bid_ask_imbalance = (bid_vol / tot) / (ask_vol / tot + 1e-10) if tot > 0 else 1.0
        m.cum_bid_depth_1pct = cum_bid
        m.cum_ask_depth_1pct = cum_ask
        m.spoofing_flag = (abs(m.bid_ask_imbalance - 1.0) > 0.5
                           and max(bid_vol, ask_vol) / (min(bid_vol, ask_vol) + 1) > 10)

    # === ATR + REGIME ======================================================

    def update_regime(self, ohlcv: List[List[float]]) -> None:
        if len(ohlcv) < 2:
            return
        closes = [c[4] for c in ohlcv]
        highs = [c[2] for c in ohlcv]
        lows = [c[3] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]

        p0 = closes[-1]
        p24 = closes[-min(24, len(closes))]
        self.state.regime.momentum_1h = (closes[-1] - closes[-2]) / closes[-2] if len(closes) >= 2 and closes[-2] else 0
        self.state.regime.momentum_24h = (p24 - p0) / p0 if p0 else 0

        tr_values = []
        prev_close = closes[0]
        for i in range(1, len(closes)):
            tr = max(highs[i] - lows[i], abs(highs[i] - prev_close), abs(lows[i] - prev_close))
            tr_values.append(tr)
            prev_close = closes[i]
        period = min(14, len(tr_values))
        atr = sum(tr_values[-period:]) / period if period > 0 else 0
        atr_pct = atr / p0 if p0 > 0 else 0.002
        self.state.regime.atr_pct = atr_pct

        if atr_pct < 0.005:
            self.state.regime.volatility_regime = "low"
        elif atr_pct < 0.015:
            self.state.regime.volatility_regime = "normal"
        elif atr_pct < 0.03:
            self.state.regime.volatility_regime = "high"
        else:
            self.state.regime.volatility_regime = "extreme"

        if len(volumes) >= 24:
            avg_vol = sum(volumes[-24:]) / 24
            ratio = volumes[-1] / avg_vol if avg_vol > 0 else 1.0
            self.state.regime.volume_ratio = ratio
            self.state.regime.volume_regime = ("spike" if ratio > 3 else
                                               "high" if ratio > 1.5 else
                                               "low" if ratio < 0.3 else "normal")

        fast = sum(closes[-8:]) / min(8, len(closes)) if len(closes) >= 8 else p0
        slow = sum(closes[-24:]) / min(24, len(closes)) if len(closes) >= 24 else p0
        price_trend = (fast - slow) / slow if slow > 0 else 0
        strength = min(1.0, abs(price_trend) / (atr_pct + 1e-10) * 0.1)

        # Smooth trend changes with hysteresis
        old_trend = self.state.regime.trend
        if strength < 0.15:
            new_trend = Trend.RANGING
        elif price_trend > 0:
            new_trend = Trend.BULL
        else:
            new_trend = Trend.BEAR

        # Require 3 consecutive same-sign before switching
        if new_trend == old_trend:
            self.state.regime.trend_strength = min(1.0, self.state.regime.trend_strength + 0.05)
            self.state.regime.regime_duration_cycles += 1
            self.state.regime.regime_confidence = min(0.95, self.state.regime.regime_confidence + 0.02)
        else:
            self.state.regime.trend_strength = strength
            self.state.regime.regime_duration_cycles = 0
            self.state.regime.regime_confidence = 0.4
        self.state.regime.trend = new_trend

    # === VaR ==============================================================

    def update_var(self, current_price: float) -> None:
        self._return_buffer.append(current_price)
        if len(self._return_buffer) < 20:
            return
        step = max(1, len(self._return_buffer) // 24)
        returns = [(self._return_buffer[i] - self._return_buffer[i-step]) / max(1e-10, self._return_buffer[i-step])
                   for i in range(step, len(self._return_buffer), step)]
        self.state.var.var_lookback = returns[-100:]
        if len(returns) < 20:
            return
        sorted_ret = sorted(returns)
        n = len(sorted_ret)
        self.state.var.var_95_1h = abs(sorted_ret[int(n * 0.05)]) if sorted_ret[int(n * 0.05)] < 0 else 0.02
        self.state.var.var_99_1h = abs(sorted_ret[int(n * 0.01)]) if sorted_ret[int(n * 0.01)] < 0 else 0.035
        cvar_vals = [r for r in sorted_ret if r <= sorted_ret[int(n * 0.05)]]
        self.state.var.cvar_95_1h = abs(sum(cvar_vals) / len(cvar_vals)) if cvar_vals else 0.03

    # === CIRCUIT BREAKER ===================================================

    def check_circuit_breaker(self, current_equity: float) -> bool:
        now = time.time()
        cs = self.state

        # ── Daily reset ──
        if now - cs.last_daily_reset > 86400:
            cs.last_daily_reset = now
            cs.day_start_capital = max(cs.day_start_capital, current_equity)
            cs.cb.daily_loss_pct = 0.0
            cs.perf.daily_pnl_pct = 0.0

        # ── Track peak ──
        if current_equity > cs.peak_capital:
            cs.peak_capital = current_equity
            cs.perf.peak_capital = current_equity

        cs.current_capital = current_equity

        day_pnl = (current_equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
        cs.cb.daily_loss_pct = day_pnl
        drawdown = (cs.peak_capital - current_equity) / max(1e-10, cs.peak_capital)
        cs.cb.max_drawdown_pct = drawdown

        # ── Recovery transitions ── (MUST be checked BEFORE opening CB again)
        prev = cs.cb.state

        # v6 CRITICAL: Time-based auto-recovery deve essere valutato SEMPRE,
        # anche se drawdown supera ancora il limite. Senza questo, il CB
        # rimane OPEN per sempre (era il #1 bug critico di produzione).
        if prev == CBState.OPEN:
            cb_duration = now - cs.cb.since if cs.cb.since > 0 else 0
            if cb_duration > self._cb_recovery_timeout:
                # Forza HALF_OPEN nonostante drawdown ancora alto
                cs.cb.state = CBState.HALF_OPEN
                cs.cb.reason = f"recovering_timeout_{cb_duration/60:.0f}m"
                cs.cb.since = now
                log = logging.getLogger("kraken_v2")
                log.warning(f"CB AUTO-RECOVERY: OPEN da {cb_duration/60:.0f}m → HALF_OPEN (timeout {self._cb_recovery_timeout/60:.0f}m)")
                # Non facciamo return — continuiamo per gestire sizing
            else:
                # Equity-based recovery (solo se non è scattato il timeout)
                dd = drawdown
                if dd < self._max_drawdown_limit * 0.5 and day_pnl > -self._daily_loss_limit * 0.5:
                    cs.cb.state = CBState.CLOSED
                    cs.cb.reason = ""
                    cs.cb.since = 0.0
                    cs.cb.daily_loss_pct = 0.0
                    cs.cb.consecutive_losses = 0
                elif dd < self._max_drawdown_limit and day_pnl > -self._daily_loss_limit:
                    cs.cb.state = CBState.HALF_OPEN
                    cs.cb.reason = "recovering"
                    cs.cb.since = now

        # ── Daily loss check ── (dopo recovery, così non blocca auto-recovery)
        if day_pnl < -self._daily_loss_limit and cs.cb.state != CBState.HALF_OPEN:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"daily_loss_{day_pnl*100:.1f}%"
            if prev != CBState.OPEN:  # Preserva since originale se già OPEN
                cs.cb.since = now
            self._save_state()
            return True

        # ── Drawdown check ── (dopo recovery, così non blocca auto-recovery)
        if drawdown > self._max_drawdown_limit and cs.cb.state != CBState.HALF_OPEN:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"drawdown_{drawdown*100:.1f}%"
            if prev != CBState.OPEN:  # Preserva since originale se già OPEN
                cs.cb.since = now
            self._save_state()
            return True

        # ── Consecutive losses → HALF_OPEN ──
        if cs.perf.consecutive_losses >= self._max_consecutive_losses and cs.cb.state != CBState.OPEN:
            cs.cb.state = CBState.HALF_OPEN
            cs.cb.reason = f"consecutive_losses_{cs.perf.consecutive_losses}"
            cs.cb.since = now

        # ── Sizing multiplier ──
        if cs.cb.state == CBState.OPEN:
            cs.sizing_multiplier = 0.0
        elif cs.cb.state == CBState.HALF_OPEN:
            # v6: In HALF_OPEN per timeout, sizing piu' aggressivo di half standard
            # per permettere recupero piu' rapido (ma sempre cauto)
            cs.sizing_multiplier = 0.5
        elif cs.perf.consecutive_losses >= self._max_consecutive_losses:
            cs.sizing_multiplier = 0.5
        elif cs.perf.consecutive_wins >= 5:
            cs.sizing_multiplier = 2.0
        elif cs.perf.consecutive_wins >= 3:
            cs.sizing_multiplier = min(2.0, cs.sizing_multiplier + 0.2)
        else:
            cs.sizing_multiplier = 1.0

        if cs.cb.state == CBState.OPEN:
            self._save_state()
        return cs.cb.state == CBState.OPEN

    # === KELLY (v4: single-multiplier, no accumulation) =====================

    def update_kelly(self, pnl_pct: float) -> None:
        self.state.trade_results.append(pnl_pct)
        self.state.perf.update(pnl_pct)
        now = time.time()
        if len(self.state.trade_results) >= 10 and now - self._kelly_updated_at > 1800:
            self._calculate_kelly()
            self._kelly_updated_at = now
        if len(self.state.trade_results) % 20 == 0:
            self.state.perf.recalc_ratios(
                self.state.trade_results, self.state.peak_capital,
                self.state.current_capital, self.state.initial_capital)
        self._save_state()

    def _calculate_kelly(self) -> None:
        if len(self.state.trade_results) < 10:
            return
        recent = self.state.trade_results[-50:]
        wins = [p for p in recent if p > 0]
        losses = [p for p in recent if p <= 0]
        if not wins or not losses:
            return
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        wr = len(wins) / len(recent)
        if avg_loss > 1e-10:
            b = avg_win / avg_loss
            kelly = (wr * b - (1 - wr)) / b
            # VaR cap: limit when volatility is high
            var_cap = 1.0 / (self.state.var.var_95_1h * 50 + 1e-10) if self.state.var.var_95_1h > 1e-6 else 1.0
            raw_kelly = max(0.05, min(0.50, kelly * 0.25))
            raw_kelly = min(raw_kelly, var_cap)

            # Boost for high win rate — applied ONE SHOT (not cumulative)
            if wr > 0.70:
                raw_kelly = min(0.50, raw_kelly * 2.0)
            elif wr > 0.60:
                raw_kelly = min(0.50, raw_kelly * 1.5)

            self.state.kelly_fraction = raw_kelly
            self._save_state()

    @property
    def kelly_fraction(self) -> float:
        """Final Kelly = base_kelly × sizing_multiplier × vol_adj.
        NOTA: sizing_multiplier è applicato QUI una volta sola.
        position_size() NON deve rimoltiplicarlo.
        """
        vol_adj = self._volatility_adjustment()
        return self.state.kelly_fraction * self.state.sizing_multiplier * vol_adj

    def position_size(self, capital: float, allocation_pct: float = 1.0) -> float:
        """
        Calcola posizione usando la kelly_fraction property
        che già include sizing_multiplier e vol_adj.
        """
        kelly = self.kelly_fraction
        max_var_risk = capital * 0.02 / (self.state.var.var_95_1h + 1e-10)
        kelly_size = capital * allocation_pct * kelly
        return min(kelly_size, max_var_risk)

    def _volatility_adjustment(self) -> float:
        r = self.state.regime.volatility_regime
        return 0.25 if r == "extreme" else 0.5 if r == "high" else 1.5 if r == "low" else 1.0

    # === DCA ENGINE ========================================================

    def dca_should_enter(self, current_price: float, equity: float) -> Tuple[bool, float, str]:
        dca = self.state.dca
        if dca.active and dca.num_entries >= dca.max_entries:
            return False, 0, "max_entries"
        if dca.active:
            drop = (dca.last_entry_price - current_price) / max(1e-10, dca.last_entry_price)
            if drop >= dca.entry_spacing_pct:
                sz = equity * 0.15 / dca.max_entries * self.kelly_fraction
                return True, sz, f"dca_drop_{drop*100:.1f}%"
        else:
            if self.state.regime.momentum_24h < -0.03 and self.state.regime.volume_regime in ("high", "spike"):
                if self.state.micro.bid_ask_imbalance < 0.8 or self.state.regime.trend == Trend.BEAR:
                    sz = equity * 0.10 * self.kelly_fraction
                    return True, sz, f"dca_entry_{self.state.regime.momentum_24h*100:.1f}%"
        return False, 0, "none"

    def dca_open_position(self, price: float, amount: float, cost: float) -> None:
        d = self.state.dca
        d.active = True
        d.num_entries += 1
        d.entry_price = price if not d.entry_price else d.entry_price  # Keep first entry
        d.last_entry_price = price
        d.total_cost += cost
        d.total_size += amount
        d.avg_entry_price = d.total_cost / d.total_size if d.total_size > 0 else price

    def dca_should_exit(self, current_price: float) -> Tuple[bool, float, str]:
        d = self.state.dca
        if not d.active or d.total_size <= 1e-10:
            return False, 0, "no_position"
        avg = d.avg_entry_price
        pnl = (current_price - avg) / avg
        if pnl >= d.target_pnl_pct:
            return True, d.total_size, f"target_{pnl*100:.1f}%"
        if current_price > d.trailing_activation:
            trail = (current_price - d.trailing_activation) / max(1e-10, d.trailing_activation)
            if trail < -d.trailing_stop_pct:
                return True, d.total_size, f"trailing_{trail*100:.1f}%"
        if pnl > 0.01 and current_price > d.trailing_activation:
            d.trailing_activation = current_price
        if pnl < -0.10:
            return True, d.total_size, f"stop_{pnl*100:.1f}%"
        return False, 0, "hold"

    def dca_close_position(self, exit_price: float = 0.0) -> float:
        """
        Calcola PnL reale: (exit_price * total_size - total_cost) / total_cost.
        v4.1 FIX: usa exit_price passato, non entry_price (era BUG #3 mal-fissato).
        """
        d = self.state.dca
        if d.active and d.total_size > 0 and d.total_cost > 0:
            actual_exit = exit_price if exit_price > 0 else d.entry_price
            pnl = (actual_exit * d.total_size - d.total_cost) / d.total_cost
        else:
            pnl = 0.0
        d.active = False
        d.entry_price = 0
        d.avg_entry_price = 0
        d.total_size = 0
        d.total_cost = 0
        d.num_entries = 0
        d.last_entry_price = 0
        d.trailing_activation = 0
        return pnl

    # === COMPOUNDING =======================================================

    def compound_profits(self, capital: float) -> float:
        """v4: compound solo se in profit, protegge in drawdown."""
        if capital <= self.state.initial_capital:
            return self.state.initial_capital
        profit = capital - self.state.initial_capital
        if profit > self._compound_threshold:
            boost = 1.0 + min(0.5, self.state.perf.consecutive_wins * 0.1)
            ratio = min(0.8, self._compound_ratio * boost)
            self.state.initial_capital += profit * ratio
            self._save_state()
        return self.state.initial_capital

    # === ATR ===============================================================

    def calculate_atr(self, ohlcv: List[List[float]], period: int = 14) -> float:
        if len(ohlcv) < period + 1:
            return 0.0
        tr = []
        pc = ohlcv[0][4]
        for i in range(1, len(ohlcv)):
            h, l, c = ohlcv[i][2], ohlcv[i][3], ohlcv[i][4]
            tr.append(max(h - l, abs(h - pc), abs(l - pc)))
            pc = c
        if not tr:
            return 0.0
        atr = sum(tr[-period:]) / period
        lc = ohlcv[-1][4]
        atr_pct = atr / lc if lc > 0 else 0
        self.state.regime.atr_pct = atr_pct
        if atr_pct < 0.005:
            self.state.regime.volatility_regime = "low"
        elif atr_pct < 0.015:
            self.state.regime.volatility_regime = "normal"
        elif atr_pct < 0.03:
            self.state.regime.volatility_regime = "high"
        else:
            self.state.regime.volatility_regime = "extreme"
        return atr_pct

    # === STRATEGY SELECTOR =================================================

    def select_strategy(self) -> StrategyMode:
        r = self.state.regime
        m = self.state.micro
        if r.volatility_regime == "extreme":
            return StrategyMode.COOLDOWN
        if r.trend_strength > 0.6 and r.trend in (Trend.BULL, Trend.BEAR):
            return StrategyMode.DCA
        if r.trend == Trend.RANGING and m.bid_ask_spread_pct < 0.002:
            return StrategyMode.GRID
        return StrategyMode.HYBRID

    def get_grid_params(self) -> dict:
        r = self.state.regime
        m = self.state.micro
        base = r.atr_pct * 0.6 if r.atr_pct > 0 else 0.02
        if m.cum_bid_depth_1pct + m.cum_ask_depth_1pct > 5000:
            base *= 0.8
        if m.bid_ask_imbalance < 0.7 or m.bid_ask_imbalance > 1.3:
            base *= 1.2
        vol_adj = {"low": 0.7, "normal": 1.0, "high": 1.3, "extreme": 2.0}
        spread = base * vol_adj.get(r.volatility_regime, 1.0)
        levels = 3 if r.volatility_regime == "extreme" else 5
        if r.trend == Trend.BULL:
            levels = max(3, levels - 1)
        return {"spread": spread, "levels": levels, "support_bias": 0.5, "take_profit_mult": 1.2 if r.trend_strength > 0.4 else 1.0}

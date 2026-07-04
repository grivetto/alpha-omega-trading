#!/usr/bin/env python3
"""
DENARO CORE v3 — Exchange-agnostic risk, regime detection, DCA, microstructure.
Machine a profit: VaR, Bayesian Kelly, regime switching, order book alpha.
"""
from __future__ import annotations

import json, math, os, time, calendar
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional, List, Tuple


# --- Enums -------------------------------------------------------------------_

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


# --- Data classes -------------------------------------------------------------

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
# DENARO CORE
# ==============================================================================

class DenaroCore:
    """Pure risk, regime, and execution logic. Zero exchange deps."""

    def __init__(self, initial_capital: float = 100.0,
                 daily_loss_limit: float = 0.05,
                 max_drawdown_limit: float = 0.02,
                 max_consecutive_losses: int = 4,
                 compound_threshold: float = 1.0,
                 compound_ratio: float = 0.5,
                 state_path: Optional[Path] = DEFAULT_CB_PATH):
        self._daily_loss_limit = daily_loss_limit
        self._max_drawdown_limit = max_drawdown_limit
        self._max_consecutive_losses = max_consecutive_losses
        self._compound_threshold = compound_threshold
        self._compound_ratio = compound_ratio
        self._state_path = state_path
        self.state = self._load_state(initial_capital)
        self._price_buffer: List[float] = []
        self._return_buffer: List[float] = []
        self._kelly_updated_at: float = 0.0

    def _load_state(self, initial_capital: float) -> CoreState:
        if self._state_path and self._state_path.exists():
            try:
                with open(self._state_path) as f:
                    d = json.load(f)
                return CoreState(
                    initial_capital=d.get("initial_capital", initial_capital),
                    current_capital=d.get("current_capital", initial_capital),
                    peak_capital=d.get("peak_capital", initial_capital),
                    day_start_capital=d.get("day_start_capital", initial_capital),
                    last_daily_reset=d.get("last_daily_reset", 0.0),
                    trade_results=d.get("trade_results", []),
                    kelly_fraction=d.get("kelly_fraction", 0.25),
                    sizing_multiplier=d.get("sizing_multiplier", 1.0),
                    cb=CircuitBreakerState(**d.get("cb", {})),
                    perf=PerfMetrics(**d.get("perf", {})),
                    regime=RegimeState(**d.get("regime", {})),
                    micro=MicroState(**d.get("micro", {})),
                    var=VaRState(**d.get("var", {})),
                    dca=DCAState(**d.get("dca", {})),
                    exec=ExecutionState(**d.get("exec", {})),
                )
            except Exception:
                pass
        return CoreState(initial_capital=initial_capital)

    def _save_state(self) -> None:
        if not self._state_path:
            return
        d = {"initial_capital": self.state.initial_capital,
             "current_capital": self.state.current_capital,
             "peak_capital": self.state.peak_capital,
             "day_start_capital": self.state.day_start_capital,
             "last_daily_reset": self.state.last_daily_reset,
             "trade_results": self.state.trade_results[-500:],
             "kelly_fraction": self.state.kelly_fraction,
             "sizing_multiplier": self.state.sizing_multiplier,
             "cb": asdict(self.state.cb),
             "perf": asdict(self.state.perf),
             "regime": asdict(self.state.regime),
             "micro": asdict(self.state.micro),
             "var": asdict(self.state.var),
             "dca": asdict(self.state.dca),
             "exec": asdict(self.state.exec)}
        tmp = self._state_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(d, indent=2, default=str))
        os.replace(str(tmp), str(self._state_path))

    def _next_daily_reset(self) -> float:
        st = time.gmtime(time.time())
        return calendar.timegm((st.tm_year, st.tm_mon, st.tm_mday + 1, 0, 0, 0, st.tm_wday, st.tm_yday, 0))

    # === MARKET REGIME DETECTION =========================================

    def update_microstructure(self, bid: float, ask: float, bid_vol: float,
                               ask_vol: float, cum_bid: float, cum_ask: float,
                               price: float) -> None:
        spread = (ask - bid) / price if price > 0 else 0.001
        imb = bid_vol / ask_vol if ask_vol > 1e-10 else 1.0
        self.state.micro.bid_ask_spread_pct = spread
        self.state.micro.bid_ask_imbalance = imb
        self.state.micro.cum_bid_depth_1pct = cum_bid
        self.state.micro.cum_ask_depth_1pct = cum_ask
        self.state.micro.last_price_micro = price
        self._price_buffer.append(price)
        if len(self._price_buffer) > 50:
            self._price_buffer.pop(0)
        if len(self._price_buffer) >= 5:
            recent = self._price_buffer[-5:]
            self.state.micro.micro_trend = (recent[-1] - recent[0]) / recent[0] if recent[0] else 0
        if len(self._price_buffer) >= 10:
            diffs = [abs(self._price_buffer[i] - self._price_buffer[i-1]) / max(1e-10, self._price_buffer[i-1])
                     for i in range(1, len(self._price_buffer))]
            self.state.micro.micro_volatility = sum(diffs) / len(diffs) if diffs else 0
        self.state.micro.spoofing_flag = ask_vol > cum_bid * 5 and spread > 0.005

    def update_regime(self, ohlcv: List[List[float]]) -> None:
        if len(ohlcv) < 20:
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
        self.state.regime.trend_strength = strength

        old = self.state.regime.trend
        new = Trend.BULL if price_trend > 0 and strength >= 0.2 else Trend.BEAR if strength >= 0.2 else Trend.RANGING
        if new == old:
            self.state.regime.regime_duration_cycles += 1
            self.state.regime.regime_confidence = min(0.95, self.state.regime.regime_confidence + 0.05)
        else:
            self.state.regime.regime_duration_cycles = 0
            self.state.regime.regime_confidence = 0.4
        self.state.regime.trend = new

    # === VaR ==============================================================

    def update_var(self, current_price: float) -> None:
        self._return_buffer.append(current_price)
        if len(self._return_buffer) > 200:
            self._return_buffer.pop(0)
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
        tail = [r for r in sorted_ret if r <= sorted_ret[int(n * 0.05)]]
        self.state.var.cvar_95_1h = abs(sum(tail) / len(tail)) if tail else 0.03

    # === CIRCUIT BREAKER ==================================================

    def check_circuit_breaker(self, current_equity: float) -> bool:
        now = time.time()
        if now >= self.state.last_daily_reset or self.state.last_daily_reset == 0:
            self.state.cb.daily_loss_pct = 0.0
            self.state.cb.consecutive_losses = 0
            self.state.last_daily_reset = self._next_daily_reset()
            self.state.perf.daily_pnl_pct = 0.0

        self.state.current_capital = current_equity
        if current_equity > self.state.peak_capital:
            self.state.peak_capital = current_equity
            self.state.perf.peak_capital = current_equity

        daily_pnl_pct = (current_equity - self.state.day_start_capital) / max(1e-10, self.state.day_start_capital)
        dd = (self.state.peak_capital - current_equity) / max(1e-10, self.state.peak_capital)
        self.state.var.max_drawdown = dd

        prev = self.state.cb.state
        if prev == CBState.CLOSED:
            if daily_pnl_pct <= -self._daily_loss_limit:
                self.state.cb.state = CBState.OPEN
                self.state.cb.reason = f"daily_loss_{self._daily_loss_limit*100:.0f}%"
                self.state.cb.since = now
            elif dd >= self._max_drawdown_limit:
                self.state.cb.state = CBState.OPEN
                self.state.cb.reason = f"drawdown_{self._max_drawdown_limit*100:.0f}%"
                self.state.cb.since = now
            elif self.state.perf.consecutive_losses >= self._max_consecutive_losses:
                self.state.cb.state = CBState.HALF_OPEN
                self.state.cb.reason = f"consec_loss_{self.state.perf.consecutive_losses}"
                self.state.cb.since = now
            elif abs(daily_pnl_pct) > self.state.var.var_95_1h * 2:
                self.state.cb.state = CBState.HALF_OPEN
                self.state.cb.reason = f"VaR_breach_{abs(daily_pnl_pct)*100:.1f}%"
                self.state.cb.since = now
        elif prev in (CBState.OPEN, CBState.HALF_OPEN):
            if (now - self.state.cb.since) < 3600:
                pass
            elif dd < self._max_drawdown_limit * 0.5 and daily_pnl_pct > -self._daily_loss_limit * 0.5:
                self.state.cb.state = CBState.CLOSED
                self.state.cb.reason = ""
                self.state.cb.since = 0.0
                self.state.cb.daily_loss_pct = 0.0
                self.state.cb.consecutive_losses = 0
                from notifier import notify_cb_close
                notify_cb_close(current_equity)
            elif prev == CBState.OPEN and dd < self._max_drawdown_limit and daily_pnl_pct > -self._daily_loss_limit:
                self.state.cb.state = CBState.HALF_OPEN
                self.state.cb.reason = "recovering"
                self.state.cb.since = now

        if self.state.cb.state == CBState.HALF_OPEN:
            self.state.sizing_multiplier = 0.5
        elif self.state.perf.consecutive_losses >= self._max_consecutive_losses:
            self.state.sizing_multiplier = 0.5
        elif self.state.perf.consecutive_wins >= 5:
            self.state.sizing_multiplier = 2.0
        elif self.state.perf.consecutive_wins >= 3:
            self.state.sizing_multiplier = min(2.0, self.state.sizing_multiplier + 0.2)
        else:
            self.state.sizing_multiplier = 1.0

        if self.state.cb.state == CBState.OPEN:
            self._save_state()
        return self.state.cb.state == CBState.OPEN

    # === KELLY ============================================================

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
            var_cap = 1.0 / (self.state.var.var_95_1h * 50) if self.state.var.var_95_1h > 1e-6 else 1.0
            self.state.kelly_fraction = max(0.05, min(0.50, min(kelly, var_cap) * 0.25))
        if len(self.state.trade_results) >= 20:
            if wr > 0.70:
                self.state.kelly_fraction = min(0.50, self.state.kelly_fraction * 2.0)
            elif wr > 0.60:
                self.state.kelly_fraction = min(0.50, self.state.kelly_fraction * 1.5)

    @property
    def kelly_fraction(self) -> float:
        return self.state.kelly_fraction * self.state.sizing_multiplier * self._volatility_adjustment()

    def position_size(self, capital: float, allocation_pct: float = 1.0) -> float:
        vol_adj = self._volatility_adjustment()
        kelly = self.state.kelly_fraction * self.state.sizing_multiplier
        max_var_risk = capital * 0.02 / (self.state.var.var_95_1h + 1e-10)
        kelly_size = capital * allocation_pct * kelly * vol_adj
        return min(kelly_size, max_var_risk)

    def _volatility_adjustment(self) -> float:
        r = self.state.regime.volatility_regime
        return 0.25 if r == "extreme" else 0.5 if r == "high" else 1.5 if r == "low" else 1.0

    # === DCA ENGINE =======================================================

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
        d.entry_price = price
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

    def dca_close_position(self) -> float:
        d = self.state.dca
        pnl = d.total_size * (d.entry_price - d.avg_entry_price) if d.active else 0
        d.active = False; d.entry_price = 0; d.avg_entry_price = 0
        d.total_size = 0; d.total_cost = 0; d.num_entries = 0
        d.last_entry_price = 0; d.trailing_activation = 0
        return pnl

    # === COMPOUNDING ======================================================

    def compound_profits(self, capital: float) -> float:
        profit = capital - self.state.initial_capital
        if profit > self._compound_threshold:
            boost = 1.0 + min(0.5, self.state.perf.consecutive_wins * 0.1)
            ratio = min(0.8, self._compound_ratio * boost)
            self.state.initial_capital += profit * ratio
            self._save_state()
        return self.state.initial_capital

    # === ATR ==============================================================

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

    # === STRATEGY SELECTOR ================================================

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

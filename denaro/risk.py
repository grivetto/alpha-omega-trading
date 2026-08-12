#!/usr/bin/env python3
"""Denaro v6 — mathematical risk management.

* Circuit breaker with volatility-scaled daily loss limit (tighter in
  high/extreme regimes, looser in calm ones).
* Kelly sizing with a single sizing multiplier + volatility adjustment
  (the v4 anti-double-multiplier contract is preserved).
* Compounding policy: aggressively re-base capital in confirmed BULL trends,
  freeze it during dumps, and partially protect in BEAR regimes.
* Dump defense: sizing collapses to zero for NEW risk in dump mode.
"""
from __future__ import annotations

from typing import List

from . import indicators as ind
from .types import CBState, CoreState, RegimeState, Trend

# Daily-loss scaling per volatility regime (multipliers on the configured limit)
_DAILY_LOSS_VOL_FACTOR = {"low": 1.2, "normal": 1.0, "high": 0.8, "extreme": 0.6}
# Kelly volatility adjustment (multipliers on the base Kelly fraction)
_KELLY_VOL_ADJ = {"low": 1.5, "normal": 1.0, "high": 0.5, "extreme": 0.25}
# Grid exposure cap per regime (multipliers on max_deployed)
_EXPOSURE_VOL_FACTOR = {"low": 1.2, "normal": 1.0, "high": 0.7, "extreme": 0.5}
_DAY_SEC = 86400.0


class RiskManager:
    """Risk + compounding engine. Operates on CoreState; no I/O."""

    def __init__(self, daily_loss_limit: float = 0.05,
                 max_drawdown_limit: float = 0.15,
                 max_consecutive_losses: int = 4,
                 compound_threshold: float = 1.0,
                 compound_ratio: float = 0.5,
                 kelly_cap: float = 0.50,
                 kelly_floor: float = 0.05) -> None:
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown_limit = max_drawdown_limit
        self.max_consecutive_losses = max(1, max_consecutive_losses)
        self.compound_threshold = compound_threshold
        self.compound_ratio = compound_ratio
        self.kelly_cap = kelly_cap
        self.kelly_floor = kelly_floor

    # --- circuit breaker -----------------------------------------------------

    def daily_loss_limit_effective(self, regime: RegimeState) -> float:
        """Volatility-scaled daily loss limit (tighter when hot)."""
        return self.daily_loss_limit * _DAILY_LOSS_VOL_FACTOR.get(regime.volatility_regime, 1.0)

    def exposure_limit(self, regime: RegimeState, max_deployed: float) -> float:
        """Volatility-scaled max grid exposure."""
        return max_deployed * _EXPOSURE_VOL_FACTOR.get(regime.volatility_regime, 1.0)

    def check_circuit_breaker(self, state: CoreState, current_equity: float) -> bool:
        """Returns True when the breaker is OPEN (trading blocked)."""
        import time
        now = time.time()
        cs = state

        # ── Daily reset ──
        if now - cs.last_daily_reset > _DAY_SEC:
            cs.last_daily_reset = now
            cs.day_start_capital = max(cs.day_start_capital, current_equity)
            cs.cb.daily_loss_pct = 0.0
            cs.perf.daily_pnl_pct = 0.0

        # ── Track peak ──
        if current_equity > cs.peak_capital:
            cs.peak_capital = current_equity

        cs.current_capital = current_equity

        # ── Daily loss (vol-scaled limit) ──
        day_pnl = (current_equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
        cs.cb.daily_loss_pct = day_pnl
        limit = self.daily_loss_limit_effective(cs.regime)
        if day_pnl < -limit:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"daily_loss_{day_pnl * 100:.1f}%"
            cs.cb.since = now
            return True

        # ── Drawdown ──
        drawdown = (cs.peak_capital - current_equity) / max(1e-10, cs.peak_capital)
        cs.cb.max_drawdown_pct = drawdown
        if drawdown > self.max_drawdown_limit:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"drawdown_{drawdown * 100:.1f}%"
            cs.cb.since = now
            return True

        # ── Consecutive losses → HALF_OPEN ──
        if cs.perf.consecutive_losses >= self.max_consecutive_losses:
            cs.cb.state = CBState.HALF_OPEN
            cs.cb.reason = f"consecutive_losses_{cs.perf.consecutive_losses}"
            cs.cb.since = now

        # ── Recovery transitions ──
        prev = cs.cb.state
        if prev == CBState.OPEN:
            dd = drawdown
            if dd < self.max_drawdown_limit * 0.5 and day_pnl > -limit * 0.5:
                cs.cb.state = CBState.CLOSED
                cs.cb.reason = ""
                cs.cb.since = 0.0
                cs.cb.daily_loss_pct = 0.0
                cs.cb.consecutive_losses = 0
            elif dd < self.max_drawdown_limit and day_pnl > -limit:
                cs.cb.state = CBState.HALF_OPEN
                cs.cb.reason = "recovering"
                cs.cb.since = now

        # ── Sizing multiplier ladder ──
        if cs.cb.state == CBState.OPEN:
            cs.sizing_multiplier = 0.0
        elif cs.cb.state == CBState.HALF_OPEN:
            cs.sizing_multiplier = 0.5
        elif cs.perf.consecutive_losses >= self.max_consecutive_losses:
            cs.sizing_multiplier = 0.5
        elif cs.perf.consecutive_wins >= 5:
            cs.sizing_multiplier = 2.0
        elif cs.perf.consecutive_wins >= 3:
            cs.sizing_multiplier = min(2.0, cs.sizing_multiplier + 0.2)
        else:
            cs.sizing_multiplier = 1.0

        return cs.cb.state == CBState.OPEN

    # --- Kelly ---------------------------------------------------------------

    def calculate_kelly(self, state: CoreState) -> float:
        """One-shot Kelly recomputation from recent trade results."""
        recent = state.trade_results[-50:]
        wins = [p for p in recent if p > 0]
        losses = [p for p in recent if p <= 0]
        if not wins or not losses:
            return state.kelly_fraction
        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        wr = len(wins) / len(recent)
        if avg_loss <= 1e-10:
            return state.kelly_fraction
        b = avg_win / avg_loss
        kelly = (wr * b - (1 - wr)) / b
        # VaR cap: shrink when tail risk is elevated
        var_cap = 1.0 / (state.var.var_95_1h * 50 + 1e-10) if state.var.var_95_1h > 1e-6 else 1.0
        raw = max(self.kelly_floor, min(self.kelly_cap, kelly * 0.25))
        raw = min(raw, var_cap)
        # Win-rate boost — applied one shot, never accumulated
        if wr > 0.70:
            raw = min(self.kelly_cap, raw * 2.0)
        elif wr > 0.60:
            raw = min(self.kelly_cap, raw * 1.5)
        return raw

    def kelly_fraction(self, state: CoreState) -> float:
        """Final Kelly = base × sizing_multiplier × vol_adj. Applied once.

        In dump mode NEW risk is frozen (0.0); existing positions still
        manage out through their own exits.
        """
        base = state.kelly_fraction
        vol_adj = _KELLY_VOL_ADJ.get(state.regime.volatility_regime, 1.0)
        if state.regime.dump_mode:
            return 0.0
        return base * state.sizing_multiplier * vol_adj

    def position_size(self, state: CoreState, capital: float, allocation_pct: float = 1.0) -> float:
        """Position size = min(Kelly size, VaR budget)."""
        kelly = self.kelly_fraction(state)
        max_var_risk = capital * 0.02 / (state.var.var_95_1h + 1e-10)
        kelly_size = capital * allocation_pct * kelly
        return min(kelly_size, max_var_risk)

    # --- compounding policy --------------------------------------------------

    def compounding_ratio_effective(self, state: CoreState) -> float:
        """Regime-aware compounding ratio (aggressive in BULL, frozen in dump)."""
        r = state.regime
        if r.dump_mode:
            return 0.0
        if r.trend == Trend.BULL and r.trend_strength >= 0.5 and r.regime_confidence >= 0.6:
            return self.compound_ratio * 1.5
        if r.trend == Trend.BEAR:
            return self.compound_ratio * 0.25
        return self.compound_ratio

    def compound_profits(self, state: CoreState, capital: float) -> float:
        """Re-base `initial_capital` on realized profits, regime-scaled."""
        if capital <= state.initial_capital:
            return state.initial_capital
        profit = capital - state.initial_capital
        if profit <= self.compound_threshold or state.cb.state == CBState.OPEN:
            return state.initial_capital
        streak_boost = 1.0 + min(0.5, state.perf.consecutive_wins * 0.1)
        ratio = min(0.8, self.compounding_ratio_effective(state) * streak_boost)
        if ratio <= 0:
            return state.initial_capital
        state.initial_capital += profit * ratio
        return state.initial_capital

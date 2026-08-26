#!/usr/bin/env python3
"""Denaro — domain risk management (puro Python, zero I/O).

Port Fase 3 di `denaro/risk.py` nel package `denaro.domain`:
- stesso contratto matematico (CB vol-scaled, Kelly, compounding, dump defense)
- import risolti (il vecchio modulo importava `indicators` inesistente)
- nessun side effect: `check_circuit_breaker` riceve `now` opzionale per test
"""
from __future__ import annotations

from typing import Optional

from .types import CBState, CoreState, RegimeState, Trend

# Daily-loss scaling per volatility regime (multipliers on the configured limit)
_DAILY_LOSS_VOL_FACTOR = {"low": 1.2, "normal": 1.0, "high": 0.8, "extreme": 0.6}
# Kelly volatility adjustment (multipliers on the base Kelly fraction)
_KELLY_VOL_ADJ = {"low": 1.5, "normal": 1.0, "high": 0.5, "extreme": 0.25}
# Grid exposure cap per regime (multipliers on max_deployed)
_EXPOSURE_VOL_FACTOR = {"low": 1.2, "normal": 1.0, "high": 0.7, "extreme": 0.5}
_DAY_SEC = 86400.0


def _week_start_ts(now: float) -> float:
    """Timestamp del lunedi' 00:00 UTC della settimana di `now` (P2)."""
    import datetime
    d = datetime.datetime.fromtimestamp(now, tz=datetime.timezone.utc)
    monday = (d - datetime.timedelta(days=d.weekday(),
                                     hours=d.hour, minutes=d.minute,
                                     seconds=d.second,
                                     microseconds=d.microsecond))
    return monday.timestamp()


class RiskManager:
    """Risk + compounding engine. Opera su CoreState; nessun I/O."""

    def __init__(self, daily_loss_limit: float = 0.05,
                 max_drawdown_limit: float = 0.15,
                 max_consecutive_losses: int = 4,
                 compound_threshold: float = 1.0,
                 compound_ratio: float = 0.5,
                 kelly_cap: float = 0.50,
                 kelly_floor: float = 0.05,
                 weekly_loss_limit: float = 0.20,
                 v7_enabled: bool = True) -> None:
        self.daily_loss_limit = daily_loss_limit
        self.max_drawdown_limit = max_drawdown_limit
        self.max_consecutive_losses = max(1, max_consecutive_losses)
        self.compound_threshold = compound_threshold
        self.compound_ratio = compound_ratio
        self.kelly_cap = kelly_cap
        self.kelly_floor = kelly_floor
        self.weekly_loss_limit = weekly_loss_limit  # P2: hard stop settimanale
        self.v7_enabled = v7_enabled

    # --- circuit breaker -----------------------------------------------------

    def daily_loss_limit_effective(self, regime: RegimeState) -> float:
        """Daily loss limit scalato per volatilita' (piu' stretto quando e' caldo)."""
        return self.daily_loss_limit * _DAILY_LOSS_VOL_FACTOR.get(regime.volatility_regime, 1.0)

    def exposure_limit(self, regime: RegimeState, max_deployed: float) -> float:
        """Esposizione massima della griglia scalata per regime."""
        return max_deployed * _EXPOSURE_VOL_FACTOR.get(regime.volatility_regime, 1.0)

    def check_circuit_breaker(self, state: CoreState, current_equity: float,
                              now: Optional[float] = None) -> bool:
        """Ritorna True quando il breaker e' OPEN (trading bloccato).

        `now` e' iniettabile per test deterministici; default time.time().
        """
        import time
        now = time.time() if now is None else now
        cs = state
        # P2 — guardia domain: l'equity non puo' superare 30× il capitale
        # iniziale (i conti sono micro/spot); letture sporche di fetch NON
        # devono avvelenare peak/daily/weekly baseline (bug weekly_loss_-99%).
        current_equity = max(0.0, min(current_equity, cs.initial_capital * 30.0))

        # ── Daily reset ──
        if now - cs.last_daily_reset > _DAY_SEC:
            cs.last_daily_reset = now
            cs.day_start_capital = max(cs.day_start_capital, current_equity)
            cs.cb.daily_loss_pct = 0.0
            cs.perf.daily_pnl_pct = 0.0

        # ── Weekly reset (P2: lunedi' 00:00 UTC) ──
        ws = _week_start_ts(now)
        if cs.last_weekly_reset < ws:
            cs.last_weekly_reset = ws
            cs.week_start_capital = max(cs.week_start_capital, current_equity)
            cs.cb.weekly_loss_pct = 0.0

        # ── Track peak ──
        if current_equity > cs.peak_capital:
            cs.peak_capital = current_equity

        cs.current_capital = current_equity

        # ── Weekly loss (P2: hard stop settimanale, indipendente dal daily) ──
        week_pnl = (current_equity - cs.week_start_capital) / max(1e-10, cs.week_start_capital)
        cs.cb.weekly_loss_pct = week_pnl
        if week_pnl < -self.weekly_loss_limit:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"weekly_loss_{week_pnl * 100:.1f}%"
            cs.cb.since = now
            cs.sizing_multiplier = 0.0
            return True

        # ── Daily loss (vol-scaled limit) ──
        day_pnl = (current_equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
        cs.cb.daily_loss_pct = day_pnl
        limit = self.daily_loss_limit_effective(cs.regime)
        if day_pnl < -limit:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"daily_loss_{day_pnl * 100:.1f}%"
            cs.cb.since = now
            cs.sizing_multiplier = 0.0
            return True

        # ── Drawdown ──
        drawdown = (cs.peak_capital - current_equity) / max(1e-10, cs.peak_capital)
        cs.cb.max_drawdown_pct = drawdown
        if drawdown > self.max_drawdown_limit:
            cs.cb.state = CBState.OPEN
            cs.cb.reason = f"drawdown_{drawdown * 100:.1f}%"
            cs.cb.since = now
            cs.sizing_multiplier = 0.0
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
        """Ricalcolo one-shot di Kelly dai trade recenti."""
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
        # VaR cap: shrink quando il tail risk e' elevato
        var_cap = 1.0 / (state.var.var_95_1h * 50 + 1e-10) if state.var.var_95_1h > 1e-6 else 1.0
        raw = max(self.kelly_floor, min(self.kelly_cap, kelly * 0.25))
        raw = min(raw, var_cap)
        # Win-rate boost — applicato one-shot, mai accumulato
        if wr > 0.70:
            raw = min(self.kelly_cap, raw * 2.0)
        elif wr > 0.60:
            raw = min(self.kelly_cap, raw * 1.5)
        return raw

    def kelly_fraction(self, state: CoreState) -> float:
        """Kelly finale = base × sizing_multiplier × vol_adj. Applicato una volta.

        In dump mode il NUOVO rischio e' congelato (0.0); le posizioni esistenti
        escono con i loro stop.
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

        if not self.v7_enabled:
            return min(kelly_size, max_var_risk)

        r = state.regime

        # Regime-adjusted Kelly
        if r.dump_mode:
            kelly_size *= 0.0
        elif r.trend == Trend.BEAR:
            kelly_size *= 0.5
        elif r.trend == Trend.BULL and r.trend_strength > 0.6:
            kelly_size *= 1.3

        # Volatility clustering adjustment
        if r.volatility_regime == "extreme":
            kelly_size *= 0.3
        elif r.volatility_regime == "high":
            kelly_size *= 0.7

        # Volume confirmation
        if r.volume_regime == "spike" and r.momentum_24h < -0.05:
            kelly_size *= 0.8

        # Signal confidence
        signal_weight = {
            "bullish": 1.2,
            "bearish": 0.8,
            "neutral": 1.0,
            "oversold": 1.3,
            "overbought": 0.7,
        }.get(r.combined_signal, 1.0)
        kelly_size *= min(1.5, max(0.5, signal_weight * r.signal_confidence))

        return min(kelly_size, max_var_risk)

    def risk_sized_capital(self, state: CoreState, capital: float) -> float:
        """P2 — Volatility Targeting applicato alla griglia.

        Capitale effettivo = capital × exposure_factor(regime) × kelly_scale.
        - exposure_factor: {low:1.2, normal:1.0, high:0.7, extreme:0.5} → la
          griglia si restringe nei regimi caldi (vol-targeting via regime
          ladder, neutro ×1.0 se il regime filter non gira).
        - kelly_scale = clamp(kelly_eff / 0.25, 0.5, 1.5), dove kelly_eff =
          kelly_fraction_base × sizing_multiplier: Kelly/sizing sopra il
          baseline (0.25) espande fino a 1.5×, sotto si contrae; con CB
          OPEN/dump (sizing 0) la griglia si azzera. NB: kelly BASE, non
          vol-adjusted — il regime di vol entra una sola volta (vol_scale),
          evitando il doppio conteggio.
        Fondamento: N ∝ σ_target/σ_asset (vol targeting) — qui σ_asset è
        discretizzato nei regimi di volatilità già calcolati dal RegimeFilter.
        """
        if state.cb.state == CBState.OPEN or state.regime.dump_mode:
            return 0.0
        kelly_eff = state.kelly_fraction * state.sizing_multiplier
        if kelly_eff <= 0.0:
            return 0.0
        kelly_scale = max(0.5, min(1.5, kelly_eff / 0.25))
        vol_scale = _EXPOSURE_VOL_FACTOR.get(state.regime.volatility_regime, 1.0)
        return capital * vol_scale * kelly_scale

    # --- compounding policy --------------------------------------------------

    def compounding_ratio_effective(self, state: CoreState) -> float:
        """Ratio di compounding regime-aware (aggressivo in BULL, congelato in dump)."""
        r = state.regime
        if r.dump_mode:
            return 0.0
        if r.trend == Trend.BULL and r.trend_strength >= 0.5 and r.regime_confidence >= 0.6:
            return self.compound_ratio * 1.5
        if r.trend == Trend.BEAR:
            return self.compound_ratio * 0.25
        return self.compound_ratio

    def compound_profits(self, state: CoreState, capital: float) -> float:
        """Re-base di `initial_capital` sui profitti realizzati, scala per regime."""
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

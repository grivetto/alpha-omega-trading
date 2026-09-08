"""Denaro — metriche di performance SOLO dalla curva di equity.

Design anti-truffa (vedi audit_punto1_telemetria_2026-09-08).
La telemetria per-trade storica era inaffidabile: le stop-loss NON entravano
mai in wins/losses/PnL, i ratio si azzeravano a ogni riavvio e le unita' erano
mescolate (euro vs pct). Questo modulo NON ricostruisce profitti per-trade:
deriva la performance direttamente dalla serie mark-to-market dell'equity,
che e' gia' la fonte che il motore usa per gate di stop-loss e circuit-breaker.

Contratto:
- append(ts, equity): registra un campione. Se equity<=0 il campione viene
  ignorato (letture sporche non devono avvelenare le metriche).
- metriche restituite con `eq_warm=false` finche' non c'e' abbastanza storia,
  cosi' nessun numero parziale viene spacciato per significativo.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple

# Serve un minimo di campioni per non truffare con serie inerte/corte.
MIN_ROWS: int = 30            # campioni equity minimi
MIN_DAILY: int = 5            # vincolo alternativo: almeno N giorni osservati
MAX_ROWS: int = 3660          # memory cap (~2.5gg @ 1/min; ~25gg @ 6/min)

# Annualizzazione dei rendimenti della curva (passo medio stimato dalla serie):
# Sharpe/sortino "annualizzati" su scala oraria multipla, coerenti tra bot con
# lo stesso passo. drawdown/return restano mark-to-market reali.
_SECONDS_PER_YEAR = 31536000.0


def _periods_per_year(step_s: float) -> float:
    return _SECONDS_PER_YEAR / step_s if step_s > 0 else 1.0


class EquityTracker:
    """Wrappa una serie equity [(ts, eq), ...] monotona e ne estrae metriche."""

    def __init__(self, max_rows: int = MAX_ROWS) -> None:
        self._rows: List[Tuple[float, float]] = []
        self._max_rows = max_rows
        self._peak: float = 0.0
        self._peak_at: float = 0.0

    # --- registrazione ------------------------------------------------------

    def append(self, ts: float, equity: float) -> None:
        if equity <= 0:
            return
        # valori fuori scala (gia' guardati da <30x iniziale lato risk) -> comunque
        # un salto >50x in un passo e' chiaramente lettura sporca
        if self._rows:
            _, prev = self._rows[-1]
            if prev > 0 and (equity / prev > 50.0 or equity / prev < 0.01):
                return
        self._rows.append((float(ts), float(equity)))
        if len(self._rows) > self._max_rows:
            self._rows = self._rows[-self._max_rows:]
        if equity > self._peak:
            self._peak = equity
            self._peak_at = float(ts)

    def extend(self, series: List[Tuple[float, float]]) -> None:
        # ripristino da persistenza: serie pre-ordinata; ricarica
        for row in series:
            self.append(float(row[0]), float(row[1]))

    @property
    def rows(self) -> List[Tuple[float, float]]:
        return list(self._rows)

    @property
    def warm(self) -> bool:
        """True solo con storia sufficiente a dare un numero non-truffa."""
        n = len(self._rows)
        if n == 0:
            return False
        span_days = (self._rows[-1][0] - self._rows[0][0]) / 86400.0
        return n >= MIN_ROWS or span_days >= MIN_DAILY

    # --- rendimenti ---------------------------------------------------------

    def _vec(self):
        """[(ts, eq)] -> (ts list, log-returns list, equities) sano."""
        rows = self._rows
        eq = [e for _, e in rows]
        ts = [t for t, _ in rows]
        lr: List[float] = []
        for i in range(1, len(eq)):
            e0, e1 = eq[i - 1], eq[i]
            if e0 > 0 and e1 > 0:
                lr.append(math.log(e1 / e0))
        return ts, lr, eq

    def total_return(self) -> float:
        if len(self._rows) < 2:
            return 0.0
        e0 = self._rows[0][1]
        e1 = self._rows[-1][1]
        return (e1 - e0) / e0 if e0 > 0 else 0.0

    def max_drawdown(self) -> float:
        """Max drawdown sulla curva (running peak->trough), >=0 come pct."""
        peak = -1e18
        mdd = 0.0
        for _, eq in self._rows:
            if eq > peak:
                peak = eq
            elif peak > 0:
                mdd = max(mdd, (peak - eq) / peak)
        return mdd

    def risk_ratios(self) -> dict:
        """Sharpe/Sortino/... derivati dai rendimenti della serie equity."""
        ts, lr, eq = self._vec()
        out = {
            "eq_sharpe": 0.0, "eq_sortino": 0.0,
            "eq_profit_factor": 0.0, "eq_win_rate_pct": 0.0,
            "eq_session_up": 0, "eq_session_down": 0,
            "eq_calmar": 0.0,
        }
        n = len(lr)
        if n < 2:
            return out
        # passo medio in secondi per annualizzazione real
        steps = [b - a for a, b in zip(ts[:-1], ts[1:]) if b > a]
        step_s = (sum(steps) / len(steps)) if steps else 3600.0
        step_s = max(1.0, step_s)
        mu = sum(lr) / n
        # downside deviation
        neg = [r for r in lr if r < 0]
        dvar = sum(r * r for r in neg) / n if neg else 1e-12
        sd_total = math.sqrt(sum((r - mu) ** 2 for r in lr) / n)
        if sd_total > 1e-12:
            per = _periods_per_year(step_s)
            out["eq_sharpe"] = mu / sd_total * math.sqrt(per)
        if dvar > 1e-12:
            per = _periods_per_year(step_s)
            out["eq_sortino"] = mu / math.sqrt(dvar) * math.sqrt(per)
        up = sum(lr)
        dn = abs(sum(neg))
        out["eq_profit_factor"] = (up / dn) if dn > 1e-12 else (0.0 if up <= 0 else 999.0)
        ups = sum(1 for r in lr if r > 0)
        downs = sum(1 for r in lr if r <= 0)
        out["eq_session_up"], out["eq_session_down"] = ups, downs
        out["eq_win_rate_pct"] = (ups / n * 100.0) if n else 0.0
        mdd = self.max_drawdown()          # 0..~1 (pct as frac)
        ret = self.total_return()
        out["eq_calmar"] = (ret / mdd) if mdd > 0 else 0.0
        return out

    def evaluate(self) -> dict:
        """Fotografia onesta delle metriche equity per l'health JSON."""
        base = {
            "eq_n": len(self._rows),
            "eq_warm": self.warm,
            "eq_return_pct": round(self.total_return() * 100.0, 4),
            "eq_max_dd": round(self.max_drawdown() * 100.0, 4),
            "eq_first_ts": round(self._rows[0][0], 1) if self._rows else 0.0,
            "eq_last_ts": round(self._rows[-1][0], 1) if self._rows else 0.0,
        }
        base.update(self.risk_ratios())
        return base

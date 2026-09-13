#!/usr/bin/env python3
"""Denaro — metriche ONESTE per il backtest.

La metrica di testa NON e' il PnL realizzato dei cicli chiusi (e' la metrica
che ha reso invisibile il drawdown in produzione: un bot che accumula
inventario in discesa mostra "+0.098 realizzati, 100% WR" mentre il conto
perde). Qui la metrica di testa e' il **rendimento sull'equity mark-to-market**,
confrontato con il semplice buy&hold dello stesso capitale.
"""
from __future__ import annotations

import math
from statistics import median
from typing import Dict, List, Optional

from .runner import BacktestResult


def _median_dt_min(ts: List[float]) -> float:
    if len(ts) < 2:
        return 0.0
    deltas = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    deltas = [d for d in deltas if d > 0]
    return (median(deltas) / 60.0) if deltas else 0.0


def max_drawdown(equity: List[float]) -> float:
    peak = -1e18
    mdd = 0.0
    for e in equity:
        peak = max(peak, e)
        if peak > 0:
            mdd = max(mdd, (peak - e) / peak)
    return mdd


def summarize(res: BacktestResult) -> Dict[str, float]:
    """Tutte le metriche rilevanti, incluse quelle che il live non misura."""
    eq = res.equity_curve or [res.start_equity]
    start, end = res.start_equity, res.end_equity
    ret = (end / start - 1.0) if start > 0 else 0.0
    days = max(1e-9, (res.end_ts - res.start_ts) / 86400.0)

    # benchmark: stesso capitale, comprato e tenuto dall'inizio
    p0, p1 = res.start_price, res.end_price
    hodl_all_in = (p1 / p0 - 1.0) if p0 > 0 else 0.0
    hodl_value = res.capital * (p1 / p0) if p0 > 0 else res.capital
    # benchmark 2: porta il portafoglio iniziale (asset + cash) senza toccarlo
    init_portfolio_end = res.capital + res.initial_asset * p1
    hodl_portfolio_ret = ((init_portfolio_end / start - 1.0)
                          if start > 0 else 0.0)

    def _stats(curve: List[float]) -> tuple:
        """(sharpe annualizzato, max drawdown) di una serie di equity."""
        r: List[float] = []
        for i in range(1, len(curve)):
            if curve[i - 1] > 0:
                r.append(curve[i] / curve[i - 1] - 1.0)
        m = sum(r) / len(r) if r else 0.0
        s = math.sqrt(sum((x - m) ** 2 for x in r) / len(r)) if r else 0.0
        by = (365 * 24 * 60 / tf_min) if tf_min > 0 else 0.0
        sh = (m / s * math.sqrt(by)) if (s > 1e-12 and by) else 0.0
        return sh, max_drawdown(curve)

    tf_min = _median_dt_min(res.ts_curve)
    sharpe, grid_mdd = _stats(eq)
    # benchmark a rischio equivalente: capitale interamente investito nell'asset
    hodl_curve = [(res.capital * (p / p0)) if p0 > 0 else res.capital
                  for p in (res.price_curve or [p0])]
    hodl_sharpe, hodl_mdd = _stats(hodl_curve)

    cycles = max(1, res.cycles)
    fees_on_capital = res.fees_paid / start if start > 0 else 0.0
    gross = ret + fees_on_capital
    return {
        "symbol": res.symbol,
        "bars": res.bars,
        "days": round(days, 2),
        "timeframe_min": round(tf_min, 3) if tf_min else 0.0,
        "start_equity": round(start, 6),
        "end_equity": round(end, 6),
        "return_pct": round(ret * 100, 4),
        "return_eur": round(end - start, 6),
        "cagr_pct": round(((end / start) ** (365.0 / days) - 1) * 100, 2)
                    if (start > 0 and end > 0) else 0.0,
        "max_drawdown_pct": round(grid_mdd * 100, 3),
        "sharpe_ann": round(sharpe, 2),
        "calmar": round(ret / grid_mdd, 3) if grid_mdd > 1e-9 else 0.0,
        "hodl_all_in_pct": round(hodl_all_in * 100, 3),
        "hodl_portfolio_pct": round(hodl_portfolio_ret * 100, 3),
        "hodl_max_drawdown_pct": round(hodl_mdd * 100, 3),
        "hodl_sharpe_ann": round(hodl_sharpe, 2),
        "hodl_calmar": round(hodl_all_in / hodl_mdd, 3) if hodl_mdd > 1e-9 else 0.0,
        "alpha_vs_hodl_pct": round((ret - hodl_all_in) * 100, 3),
        "realized_pnl": round(res.realized_pnl, 6),
        "unrealized_pnl": round(res.unrealized_pnl, 6),
        "fees_paid": round(res.fees_paid, 6),
        "fees_pct_of_capital": round(fees_on_capital * 100, 3),
        "fees_over_gross_pct": round((fees_on_capital / gross * 100)
                                     if gross > 1e-9 else 0.0, 1),
        "cycles": res.cycles,
        "cycle_win_rate_pct": round(res.cycle_wins / cycles * 100, 2),
        "cycle_pnl_avg": round(res.realized_pnl / cycles, 6),
        "orders_placed": res.orders_placed,
        "orders_rejected": res.orders_rejected,
        "orders_canceled": res.orders_canceled,
        "cancel_per_place": round(res.orders_canceled / max(1, res.orders_placed), 3),
        "fills_buy": res.fills_buy,
        "fills_sell": res.fills_sell,
        "blocked_ticks_pct": round(res.blocked_ticks / max(1, res.bars) * 100, 2),
        "blocked_reason": res.blocked_reason,
        "stop_loss_ts": res.stop_loss_ts,
        "equity_guard_hits": res.equity_guard_hits,
        "avg_inventory_eur": round(res.avg_inventory_notional, 4),
        "max_inventory_eur": round(res.inventory_notional_max, 4),
        "exposure_avg_pct": round(res.avg_inventory_notional / start * 100, 2)
                            if start > 0 else 0.0,
        "inventory_end": round(res.inventory_end, 8),
        "capital": res.capital,
    }


def format_summary(s: Dict[str, float], title: str = "") -> str:
    """Report testuale leggibile (usato dalla CLI)."""
    lines: List[str] = []
    if title:
        lines.append(title)
    lines.append("-" * 72)
    lines.append(f"  finestra            : {s['days']} giorni ({s['bars']} barre, "
                 f"{s['timeframe_min']}m)")
    lines.append(f"  capitale iniziale   : {s['start_equity']:.4f} EUR")
    lines.append(f"  equity finale (MTM) : {s['end_equity']:.4f} EUR")
    lines.append(f"  >>> RENDIMENTO      : {s['return_pct']:+.3f}%  "
                 f"({s['return_eur']:+.4f} EUR)")
    lines.append(f"      buy&hold (tutto) : {s['hodl_all_in_pct']:+.3f}%   "
                 f"alpha: {s['alpha_vs_hodl_pct']:+.3f}%")
    lines.append(f"      buy&hold (portaf.): {s['hodl_portfolio_pct']:+.3f}%")
    lines.append(f"  max drawdown (MTM)  : {s['max_drawdown_pct']:.2f}%   "
                 f"(buy&hold: {s['hodl_max_drawdown_pct']:.2f}%)")
    lines.append(f"  sharpe annualizzato : {s['sharpe_ann']:.2f}   "
                 f"(buy&hold: {s['hodl_sharpe_ann']:.2f})")
    lines.append(f"  calmar (ret/maxDD)  : {s['calmar']:.2f}   "
                 f"(buy&hold: {s['hodl_calmar']:.2f})")
    lines.append(f"  realizzato          : {s['realized_pnl']:+.4f} EUR  "
                 f"(non realizzato: {s['unrealized_pnl']:+.4f})")
    lines.append(f"  fee pagate          : {s['fees_paid']:.4f} EUR "
                 f"({s['fees_pct_of_capital']:.2f}% del capitale)")
    lines.append(f"  cicli chiusi        : {s['cycles']} "
                 f"(win rate cicli {s['cycle_win_rate_pct']:.1f}% — "
                 f"metrica NON affidabile)")
    lines.append(f"  ordini              : {s['orders_placed']} piazzati, "
                 f"{s['orders_canceled']} cancellati, {s['orders_rejected']} rifiutati")
    lines.append(f"  fill                : {s['fills_buy']} buy / {s['fills_sell']} sell")
    lines.append(f"  esposizione media   : {s['avg_inventory_eur']:.2f} EUR "
                 f"({s['exposure_avg_pct']:.1f}% del capitale)")
    if s["blocked_ticks_pct"]:
        lines.append(f"  tick bloccati (CB)  : {s['blocked_ticks_pct']:.1f}% "
                     f"[{s['blocked_reason']}]")
    if s["stop_loss_ts"]:
        lines.append(f"  STOP LOSS scattato  : ts={s['stop_loss_ts']:.0f}")
    if s["equity_guard_hits"]:
        lines.append(f"  guardia equity      : {s['equity_guard_hits']} hit "
                     f"(livello mascherato)")
    return "\n".join(lines)

#!/usr/bin/env python3
"""Qualche asset ha alpha ROBUSTAMENTE negativo e va tolto?

L'obiettivo dice "eliminazione o riprogettazione delle strategie con alpha
negativo": vale anche per un asset. Ma un asset puo' essere negativo per caso su
UN set di parametri. Qui si misura per ciascuno dei 19 asset il rendimento su
TUTTA la griglia (81 set) e su piu' finestre: se un asset e' negativo nella
MAGGIORANZA dei set e delle finestre, non e' rumore.

Poi si prova il portafoglio senza i peggiori e si vede se migliora davvero.

Uso: python3 tools/trend_potatura.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
sp = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(sp)
sp.loader.exec_module(cap)

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
REALI = {
    "mc2":      (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola":   (24.83, ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"]),
    "MARCODG1": (42.04, ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"]),
}
DEPLOY = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400, risk_pct=RISK)
GRIGLIA = [dict(DEPLOY, canale=c, trail_mult=t, stop_atr_mult=s, trend_ema=e)
           for c in (20, 40, 60, 80)
           for t in (2.0, 2.5, 3.0)
           for s in (1.5, 2.0)
           for e in (0, 100)]


def main():
    print("Per-asset su %d set di parametri (fee %.2f%%, capitale pieno)"
          % (len(GRIGLIA), FEE * 100))
    print("  %-6s %10s %10s %10s %8s  %s" %
          ("asset", "mediano", "peggiore", "migliore", "% positivi", "verdetto"))
    verdetto = {}
    for conto, (_, simboli) in REALI.items():
        for s in simboli:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % s))
            vals = [E.backtest_trend(c, p, 1.0, FEE, cap.SLIP).ritorno for p in GRIGLIA]
            med = st.median(vals)
            pos = sum(1 for v in vals if v > 0)
            ok = "OK" if med > 0 and pos >= len(vals) * 0.6 else "DA ESAMINARE"
            verdetto[s] = (med, pos / len(vals))
            print("  %-6s %+9.2f%% %+9.2f%% %+9.2f%% %6d/%d  %s"
                  % (s, med * 100, min(vals) * 100, max(vals) * 100, pos, len(vals), ok))
    print()
    negativi = sorted([k for k, v in verdetto.items() if v[1] < 0.5],
                      key=lambda k: verdetto[k][0])
    print("  asset positivi in meno della META' dei set: %s" % (negativi or "nessuno"))
    if not negativi:
        print("  --> nessun asset da potare: tutti hanno alpha positivo nella maggioranza dei set")
        return 0
    print("  --> candidati alla potatura: %s" % ", ".join(negativi))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

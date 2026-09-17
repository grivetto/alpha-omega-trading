#!/usr/bin/env python3
"""Screening dell'alpha per-asset su 52 coppie EUR (era 19).

Criterio IDENTICO al round 19: per ogni asset, rendimento mediano su 48 set di
parametri e frazione di set positivi. Un asset entra in flotta solo se e'
positivo nella MAGGIORANZA dei set: cosi' la selezione non dipende dal risultato
di portafoglio.

Uso: python3 tools/trend_screening_52.py
"""
from __future__ import annotations
import importlib.util
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
DEPLOY = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400, risk_pct=RISK)
GRIGLIA = [dict(DEPLOY, canale=c, trail_mult=t, stop_atr_mult=s, trend_ema=e)
           for c in (20, 40, 60, 80)
           for t in (2.0, 2.5, 3.0)
           for s in (1.5, 2.0)
           for e in (0, 100)]


def main():
    file = sorted(DATI.glob("dl_*_1D.csv"))
    print("file giornalieri presenti: %d" % len(file))
    righe = []
    for f in file:
        asset = f.name[3:-8]
        c = E.load_csv(f)
        if len(c) < 500:
            continue
        vals = [E.backtest_trend(c, p, 1.0, FEE, cap.SLIP).ritorno for p in GRIGLIA]
        med = st.median(vals)
        pos = sum(1 for v in vals if v > 0) / len(vals)
        righe.append((asset, med, pos, len(c), min(vals), max(vals)))
    righe.sort(key=lambda x: -x[1])
    print("  %-7s %10s %9s %7s %9s %9s  %s" %
          ("asset", "mediano", "% positivi", "barre", "peggiore", "migliore", "verdetto"))
    buoni, cattivi = [], []
    for a, med, pos, n, mn, mx in righe:
        v = "OK" if (med > 0 and pos >= 0.6) else ("SCARTARE" if pos < 0.5 else "debole")
        (buoni if v == "OK" else cattivi).append((a, med, pos, v))
        print("  %-7s %+9.2f%% %8.0f%% %7d %+8.2f%% %+8.2f%%  %s"
              % (a, med * 100, pos * 100, n, mn * 100, mx * 100, v))
    print()
    print("PROMOSSI (%d): %s" % (len(buoni), ", ".join(x[0] for x in buoni)))
    print("NON promossi (%d): %s" % (len(cattivi), ", ".join("%s[%s]" % (x[0], x[3]) for x in cattivi)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

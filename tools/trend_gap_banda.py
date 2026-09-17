#!/usr/bin/env python3
"""Quanto pesa la gap in uno scenario REALISTICO?

Il test precedente applica la gap a OGNI uscita a stop: e' il caso peggiore.
Nella realta' solo una parte delle uscite ha una gap. Si misura la banda:
  gap 0%    -> nessuna gap (assunzione del backtest)
  gap 0.5%  -> ~1 uscita su 6 con gap del 3%
  gap 1%    -> ~1 uscita su 3 con gap del 3%
  gap 2%    -> ~2 uscite su 3 con gap del 3%
  gap 5%    -> ogni uscita con gap del 5% (catastrofico)

Serve a dare un'aspettativa onesta, non un numero unico.

Uso: python3 tools/trend_gap_banda.py
"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading/tools")
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
import trend_sim_gap as g
import trend_gap_stress as stress
from denaro.research import eval as E


def stat(gap, barre=None):
    curve = []
    for nome, capitale in stress.CONTI:
        aa = stress.serie(nome)
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        r = g.simula_gap(aa, capitale, stress.RISK, stress.FEE, g.SLIP, gap=gap,
                         **dict(stress.BASE, max_exposure=1.0))
        curve.append([e / capitale for e in r["curva"]])
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i]/port[i-1] - 1.0 for i in range(1, n) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr)/sd*math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe


def main():
    print("  %-10s %-38s %10s %10s %8s" % ("scenario", "", "storia", "12 mesi", "maxDD"))
    for gap, nome in ((0.0, "nessuna gap (backtest)"),
                      (0.005, "1 uscita su 6 con gap 3%"),
                      (0.01, "1 uscita su 3 con gap 3%"),
                      (0.02, "2 uscite su 3 con gap 3%"),
                      (0.05, "OGNI uscita con gap 5%")):
        r, d, _ = stat(gap)
        r12, _, _ = stat(gap, 365)
        print("  gap %-6s %-38s %+9.2f%% %+9.2f%% %8.2f%%"
              % ("%.1f%%" % (gap * 100), nome, r * 100, r12 * 100, d * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

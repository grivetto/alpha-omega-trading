#!/usr/bin/env python3
"""Stress di gap con simulatore GENERATO dal sorgente validato.

Con una gap avversa sulle uscite a stop: il rendimento crolla, e il tetto per
posizione aiuta o no? Ora i numeri sono affidabili (gap=0 coincide al bit).

Uso: python3 tools/trend_gap_stress.py
"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading/tools")
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
import trend_sim_gap as g
from denaro.research import eval as E

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
CONTI = [("mc2", 42.12), ("nuvola", 24.83), ("MARCODG1", 42.04)]
FLOTTA = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
          "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI", "MINA"],
          "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}
BASE = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
            trend_ema=100, entry_slip=0.0005, fee_buffer=0.01, max_barre=400)
_cache = {}


def serie(nome):
    if nome not in _cache:
        aa = []
        for a in FLOTTA[nome]:
            src = DATI / ("dl_%s_1D.csv" % a)
            aa.append((a, E.load_csv(src)))
        n = min(len(c) for _, c in aa)
        _cache[nome] = [(a, c[-n:]) for a, c in aa]
    return _cache[nome]


def misura(max_exp, gap):
    curve = []
    for nome, capitale in CONTI:
        r = g.simula_gap(serie(nome), capitale, RISK, FEE, g.SLIP, gap=gap,
                         **dict(BASE, max_exposure=max_exp))
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
    gaps = [0.0, 0.02, 0.05, 0.10]
    print("  %-8s" % "tetto" + "".join(" %19s" % ("gap %.0f%%" % (x * 100)) for x in gaps))
    print("  %-8s" % "" + "".join(" %9s %9s" % ("rend", "maxDD") for _ in gaps))
    for me in (1.0, 0.6, 0.5, 0.4, 0.3):
        riga = "  %-8s" % ("%.0f%%" % (me * 100))
        for gp in gaps:
            r, d, _ = misura(me, gp)
            riga += " %+8.2f%% %+8.2f%%" % (r * 100, -d * 100)
        print(riga)
    print()
    print("  (maxDD mostrato come valore negativo per compattezza)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

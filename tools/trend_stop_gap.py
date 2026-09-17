#!/usr/bin/env python3
"""Uno stop piu' LARGO riduce il danno delle gap?

Perche' potrebbe: la size e' rischio/(stop_mult*ATR). Con uno stop piu' largo la
posizione e' PIU' PICCOLA a pari rischio, quindi una gap che salta lo stop
colpisce meno capitale. A differenza del tetto per posizione (che mordeva solo
TRX), questo cambia TUTTE le posizioni.

Contro: stop piu' larghi escono meno spesso e piu' tardi, quindi cambiano anche
il rendimento in assenza di gap.

Uso: python3 tools/trend_stop_gap.py
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
_cache = {}


def serie(nome):
    if nome not in _cache:
        aa = [(a, E.load_csv(DATI / ("dl_%s_1D.csv" % a))) for a in FLOTTA[nome]]
        n = min(len(c) for _, c in aa)
        _cache[nome] = [(a, c[-n:]) for a, c in aa]
    return _cache[nome]


def misura(stop_mult, gap, barre=None):
    curve = []
    P = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=stop_mult,
             trend_ema=100, entry_slip=0.0005, fee_buffer=0.01, max_barre=400,
             max_exposure=1.0)
    for nome, capitale in CONTI:
        aa = serie(nome)
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        r = g.simula_gap(aa, capitale, RISK, FEE, g.SLIP, gap=gap, **P)
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
    print("gap 0% = nessuna gap (assunzione del backtest);  gap 2/5% = scenari avversi")
    print("  %-7s %20s %20s %20s" %
          ("stop", "gap 0%", "gap 2%", "gap 5%"))
    print("  %-7s %9s %10s %9s %10s %9s %10s" %
          ("(ATR)", "rend", "maxDD", "rend", "maxDD", "rend", "maxDD"))
    for sm in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        riga = "  %-7s" % ("%.1f" % sm)
        for gp in (0.0, 0.02, 0.05):
            r, d, _ = misura(sm, gp)
            riga += " %+8.2f%% %+9.2f%%" % (r * 100, -d * 100)
        print(riga)
    print()
    print("  Ultima riga: rapporto rendimento(gap 5%)/rendimento(gap 0%), quanto la gap mangia")
    for sm in (1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0):
        r0 = misura(sm, 0.0)[0]
        r5 = misura(sm, 0.05)[0]
        print("    stop %.1f ATR:  %.0f%% del rendimento sopravvive alla gap 5%%"
              % (sm, 100.0 * r5 / r0 if r0 else 0))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

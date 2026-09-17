#!/usr/bin/env python3
"""B batte A per davvero, o solo su pochi asset?

Un miglioramento aggregato puo' venire da UN asset fortunato. La prova robusta e'
per-asset: se B batte A sulla MAGGIORANZA degli asset, e su finestre diverse, non
e' un artefatto di selezione.

Uso: python3 tools/trend_perasset.py
"""
from __future__ import annotations
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]
FEE = 0.0035
BASE = dict(atr_period=14, max_exposure=1.0, entry_slip=0.0005,
            fee_buffer=0.01, max_barre=400, risk_pct=0.02)
A = dict(BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100)
B = dict(BASE, canale=20, trail_mult=4.0, stop_atr_mult=1.5, trend_ema=100)


def carica():
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("dl_%s_1D.csv" % s)
        if p.is_file():
            c = E.load_csv(p)
            if len(c) > 250:
                serie[s] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def r1(c, p):
    r = E.backtest_trend(c, p, 1.0, FEE)
    if r.errore or not r.equity:
        return None
    return r.ritorno, r.trade


def main():
    serie, n = carica()
    print("A = deployato (canale 40, trail 3.0, stop 2.0)")
    print("B = candidato (canale 20, trail 4.0, stop 1.5)")
    print("fee taker %.2f%%/lato, rischio 2%%, %d barre" % (FEE * 100, n))

    for da, nome in ((int(n * 0.6), "ultimo 40%%"), (0, "tutta la storia")):
        print()
        print("=== %s (da barra %d) ===" % (nome, da))
        print("  %-6s %10s %10s %8s %6s %6s" % ("asset", "A", "B", "B-A", "tA", "tB"))
        diff, bwin, avin, pari = [], 0, 0, 0
        for s in sorted(serie):
            ra, rb = r1(serie[s][da:], A), r1(serie[s][da:], B)
            if not ra or not rb:
                continue
            d = rb[0] - ra[0]
            diff.append(d)
            if d > 1e-9:
                bwin += 1
            elif d < -1e-9:
                avin += 1
            else:
                pari += 1
            print("  %-6s %9.2f%% %9.2f%% %+7.2f%% %6d %6d"
                  % (s, ra[0] * 100, rb[0] * 100, d * 100, ra[1], rb[1]))
        if diff:
            media = st.mean(diff)
            sd = st.stdev(diff) if len(diff) > 1 else 0.0
            t = media / (sd / (len(diff) ** 0.5)) if sd > 0 else 0.0
            print("  --> B vince %d, A vince %d, pari %d su %d asset"
                  % (bwin, avin, pari, len(diff)))
            print("      differenza media %+.2f%%  t=%+.2f" % (media * 100, t))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

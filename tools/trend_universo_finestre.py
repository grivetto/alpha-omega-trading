#!/usr/bin/env python3
"""Il vantaggio dei 19 asset regge FINESTRA PER FINESTRA?

Un miglioramento aggregato puo' venire da un solo periodo fortunato. Qui si
spezza la storia in blocchi non sovrapposti e si rifa' la simulazione a capitale
condiviso su ciascuno, per 15 e per 19 asset.

Uso: python3 tools/trend_universo_finestre.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
spec = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)
spec2 = importlib.util.spec_from_file_location("uni", str(BASE_T / "trend_universo.py"))
uni = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(uni)

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
BLOCCHI = 5
RISK = 0.02


def carica_blocchi(conti, da, a):
    out = {}
    for nome, simboli in conti.items():
        assets = []
        for s in simboli:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % s))
            assets.append((s, c))
        n = min(len(c) for _, c in assets)
        assets = [(s, c[-n:]) for s, c in assets]
        out[nome] = [(s, c[da:a]) for s, c in assets]
    return out


def sim(conti, risk=RISK, fee=FEE):
    curve, rif = [], 0
    for nome, assets in conti.items():
        r = cap.simula(assets, cap.CAPITALE, risk, fee, cap.SLIP, **cap.BASE)
        curve.append([e / cap.CAPITALE for e in r["curva"]])
        rif += r["rifiutati"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    return port[-1] - 1.0, mdd, rif


def main():
    # lunghezza comune dei due universi
    lungh = []
    for conti in (uni.ATTUALE, uni.ALLARGATO):
        n = min(len(E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for v in conti.values() for s in v)
        lungh.append(n)
    n = min(lungh)
    passo = n // BLOCCHI
    print("capitale condiviso, fee spot %.2f%%, rischio %.0f%%, %d blocchi da ~%d barre"
          % (FEE * 100, RISK * 100, BLOCCHI, passo))
    print("  %-8s" % "blocco" + "".join(" %14s" % ("15 asset", )) + " %14s" % "19 asset")
    v15, v19 = [], []
    for k in range(BLOCCHI):
        da = k * passo
        a = (k + 1) * passo if k < BLOCCHI - 1 else n
        r15, _, _ = sim(carica_blocchi(uni.ATTUALE, da, a))
        r19, _, _ = sim(carica_blocchi(uni.ALLARGATO, da, a))
        v15.append(r15); v19.append(r19)
        print("  %-8s %13.2f%% %14.2f%%" % ("b%d" % (k + 1), r15 * 100, r19 * 100))
    print()
    print("  blocchi in cui 19 batte 15 : %d/%d" % (sum(1 for a, b in zip(v15, v19) if b > a), BLOCCHI))
    print("  mediana 15 asset           : %+.2f%%" % (st.median(v15) * 100))
    print("  mediana 19 asset           : %+.2f%%" % (st.median(v19) * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

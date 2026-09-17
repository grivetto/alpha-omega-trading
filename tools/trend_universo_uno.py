#!/usr/bin/env python3
"""Ognuno dei 4 asset nuovi migliora da solo? (prova pulita)

I blocchi non sono affidabili per questa strategia: EMA100 e canale 40 non
scaldano in 173 barre, quindi meta' blocco non trada. Qui si tiene la storia
INTERA e si aggiunge UN asset alla volta: se ciascuno migliora, l'allargamento
non dipende da un singolo colpo fortunato.

Uso: python3 tools/trend_universo_uno.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
for nome_mod, file_mod in (("cap", "trend_capacita.py"), ("uni", "trend_universo.py")):
    spec = importlib.util.spec_from_file_location(nome_mod, str(BASE_T / file_mod))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    globals()[nome_mod] = m

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02


def simula(conti):
    curve, rif, tr = [], 0, 0
    for nome, assets in conti.items():
        aa = []
        for s, sim in assets:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % s))
            aa.append((s, c))
        n = min(len(c) for _, c in aa)
        aa = [(s, c[-n:]) for s, c in aa]
        r = cap.simula(aa, cap.CAPITALE, RISK, FEE, cap.SLIP, **cap.BASE)
        curve.append([e / cap.CAPITALE for e in r["curva"]])
        rif += r["rifiutati"]
        tr += r["trade"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i] / port[i-1] - 1.0 for i in range(1, n) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe, rif, tr


def conti_da(liste):
    return {(k if isinstance(k, str) else k): [(s, None) for s in v]
            for k, v in liste.items()} if False else \
           {k: [(s, None) for s in v] for k, v in liste.items()}


def main():
    base = uni.ATTUALE
    print("capitale condiviso, fee %.2f%%, rischio %.0f%%" % (FEE * 100, RISK * 100))
    r0 = simula(conti_da(base))
    print("  %-28s rend %+7.2f%%  maxDD %6.2f%%  Sharpe %5.2f  trades %4d"
          % ("BASE 15 asset", r0[0] * 100, r0[1] * 100, r0[2], r0[4]))
    for nuovo, conto in (("ALGO", "MARCODG1"), ("CRV", "mc2"),
                         ("SUI", "nuvola"), ("TRX", "mc2")):
        esteso = {k: list(v) for k, v in base.items()}
        esteso[conto] = esteso[conto] + [nuovo]
        r = simula(conti_da(esteso))
        print("  %-28s rend %+7.2f%%  maxDD %6.2f%%  Sharpe %5.2f  trades %4d   delta %+6.2fpp"
              % ("+ %s (16 asset)" % nuovo, r[0] * 100, r[1] * 100, r[2], r[4],
                 (r[0] - r0[0]) * 100))
    r19 = simula(conti_da(uni.ALLARGATO))
    print("  %-28s rend %+7.2f%%  maxDD %6.2f%%  Sharpe %5.2f  trades %4d   delta %+6.2fpp"
          % ("TUTTI E 4 (19 asset)", r19[0] * 100, r19[1] * 100, r19[2], r19[4],
             (r19[0] - r0[0]) * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

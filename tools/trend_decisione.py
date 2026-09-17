#!/usr/bin/env python3
"""A vs B nel simulatore a capitale CONDIVISO: il test decisivo.

A batte B o viceversa non si decide sul backtest per-simbolo (che ignora il
vincolo di cassa). Qui si decide dove conta: 3 conti reali da 24.83 EUR con 5
asset che CONDIVIDONO la cassa, simulatore validato al bit contro backtest_trend.

B usa posizioni piu' grandi (stop piu' stretto -> size maggiore a pari rischio),
quindi potrebbe soffrire di piu' il vincolo: va misurato, non intuito.

Uso: python3 tools/trend_decisione.py
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
spec = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

SET = {
    "A deployato (40/3.0/2.0)": dict(cap.BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "B candidato (20/4.0/1.5)": dict(cap.BASE, canale=20, trail_mult=4.0, stop_atr_mult=1.5, trend_ema=100),
}


def prova(params, risk):
    curve, rif, tr = [], 0, 0
    for nome, simboli in cap.CONTI.items():
        assets, _ = cap.carica(simboli)
        r = cap.simula(assets, cap.CAPITALE, risk, **params)
        curve.append([e / cap.CAPITALE for e in r["curva"]])
        rif += r["rifiutati"]
        tr += r["trade"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    rend, cagr, mdd, sharpe, anni = cap.metriche(port)
    return dict(rend=rend, cagr=cagr, mdd=mdd, sharpe=sharpe,
                rif=rif, tr=tr, curva=port)


def main():
    print("Simulatore a capitale condiviso — 3 conti da %.2f EUR, 5 asset ciascuno"
          % cap.CAPITALE)
    print()
    print("  %-26s %6s %10s %9s %8s %8s %9s %8s" %
          ("set", "rischio", "rend.3c", "CAGR", "maxDD", "Sharpe", "rifiutati", "trades"))
    risultati = {}
    for nome, p in SET.items():
        for risk in (0.01, 0.015, 0.02, 0.03):
            r = prova(p, risk)
            risultati[(nome, risk)] = r
            print("  %-26s %5s%% %9.2f%% %8.2f%% %7.2f%% %8.2f %9d %8d"
                  % (nome, "%.1f" % (risk * 100), r["rend"] * 100, r["cagr"] * 100,
                     r["mdd"] * 100, r["sharpe"], r["rif"], r["tr"]))

    print()
    print("CONFRONTO A PARI RISCHIO (rendimento e Sharpe)")
    for risk in (0.01, 0.015, 0.02, 0.03):
        a = risultati[("A deployato (40/3.0/2.0)", risk)]
        b = risultati[("B candidato (20/4.0/1.5)", risk)]
        print("  rischio %4s%%: B-A rendimento %+7.2f%%   Sharpe %+5.2f   (A %.2f vs B %.2f)"
              % ("%.1f" % (risk * 100), (b["rend"] - a["rend"]) * 100,
                 b["sharpe"] - a["sharpe"], a["sharpe"], b["sharpe"]))

    print()
    print("MIGLIORE CONFIGURAZIONE per rendimento assoluto:")
    best = max(risultati.items(), key=lambda kv: kv[1]["rend"])
    print("   %s a rischio %.1f%% -> %.2f%% (CAGR %.2f%%, maxDD %.2f%%, Sharpe %.2f)"
          % (best[0][0], best[0][1] * 100, best[1]["rend"] * 100,
             best[1]["cagr"] * 100, best[1]["mdd"] * 100, best[1]["sharpe"]))
    print("MIGLIORE CONFIGURAZIONE per Sharpe:")
    best = max(risultati.items(), key=lambda kv: kv[1]["sharpe"])
    print("   %s a rischio %.1f%% -> rend %.2f%%, maxDD %.2f%%, Sharpe %.2f"
          % (best[0][0], best[0][1] * 100, best[1]["rend"] * 100,
             best[1]["mdd"] * 100, best[1]["sharpe"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

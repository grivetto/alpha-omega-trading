#!/usr/bin/env python3
"""Il set canale 20 / trail 2.5 e' un miglioramento VERO o selezione su 81 set?

Tre prove indipendenti, tutte fuori dalla griglia che l'ha scelto:
  A) per-asset: vince sulla MAGGIORANZA dei 19 asset?
  B) per-finestra: vince nel periodo recente (12, 9, 6 mesi)?
  C) per-blocco: la storia spezzata in 4, chi vince dove?
Se il vantaggio venisse da un asset o da un periodo, le prove lo smascherano.

Uso: python3 tools/trend_verifica_set.py
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
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
REALI = {
    "mc2":      (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola":   (24.83, ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"]),
    "MARCODG1": (42.04, ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"]),
}
BASE = dict(atr_period=14, max_exposure=1.0, entry_slip=0.0005,
            fee_buffer=0.01, max_barre=400)
SET = {
    "DEPLOY 40/3.0/2.0/100": dict(BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "NUOVO  20/2.5/2.0/100": dict(BASE, canale=20, trail_mult=2.5, stop_atr_mult=2.0, trend_ema=100),
    "ALT    20/2.5/2.5/100": dict(BASE, canale=20, trail_mult=2.5, stop_atr_mult=2.5, trend_ema=100),
}


def serie_per_conto(barre=None):
    out = {}
    for conto, (_, simboli) in REALI.items():
        aa = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for s in simboli]
        n = min(len(c) for _, c in aa)
        aa = [(s, c[-n:]) for s, c in aa]
        if barre:
            aa = [(s, c[-barre:]) for s, c in aa]
        out[conto] = aa
    return out


def condiviso(serie, params):
    curve, rif = [], 0
    for conto, (capitale, _) in REALI.items():
        r = cap.simula(serie[conto], capitale, RISK, FEE, cap.SLIP, **params)
        curve.append([e / capitale for e in r["curva"]])
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
    print("A) PER-ASSET (capitale pieno per simbolo, fee %.2f%%)" % (FEE * 100))
    print("   %-8s %10s %10s %10s  %s" % ("asset", "DEPLOY", "NUOVO", "ALT", "chi vince"))
    tutti = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s)))
             for _, (_, sims) in REALI.items() for s in sims]
    n = min(len(c) for _, c in tutti)
    tutti = [(s, c[-n:]) for s, c in tutti]
    nomi = list(SET)
    vinte = {n_: 0 for n_ in nomi}
    for s, c in tutti:
        rr = {}
        for nome, p in SET.items():
            r = E.backtest_trend(c, dict(p, risk_pct=RISK), 1.0, FEE, cap.SLIP)
            rr[nome] = r.ritorno
        best = max(rr, key=rr.get)
        vinte[best] += 1
        print("   %-8s %+9.2f%% %+9.2f%% %+9.2f%%  %s"
              % (s, rr[nomi[0]] * 100, rr[nomi[1]] * 100, rr[nomi[2]] * 100, best))
    print("   --> vittorie per asset:")
    for n_ in nomi:
        print("       %-24s %d/19" % (n_, vinte[n_]))

    print()
    print("B) PER-FINESTRA (capitale CONDIVISO reale)")
    print("   %-16s %10s %10s %10s" % ("finestra", "DEPLOY", "NUOVO", "ALT"))
    for barre, nome in ((None, "tutta la storia"), (540, "~18 mesi"), (365, "~12 mesi"),
                        (270, "~9 mesi"), (180, "~6 mesi")):
        serie = serie_per_conto(barre)
        riga = "   %-16s" % nome
        for k in SET:
            r, _, _ = condiviso(serie, SET[k])
            riga += " %+9.2f%%" % (r * 100)
        print(riga)

    print()
    print("C) PER-BLOCCO (capitale CONDIVISO reale, 4 blocchi)")
    serie_full = serie_per_conto()
    lungh = [len(c) for aa in serie_full.values() for _, c in aa]
    n = min(lungh)
    passo = n // 4
    for k in range(4):
        da = k * passo
        a = (k + 1) * passo if k < 3 else n
        blocco = {conto: [(s, c[da:a]) for s, c in aa]
                  for conto, aa in serie_full.items()}
        riga = "   blocco %d        " % (k + 1)
        for kk in SET:
            r, _, _ = condiviso(blocco, SET[kk])
            riga += " %+9.2f%%" % (r * 100)
        print(riga)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

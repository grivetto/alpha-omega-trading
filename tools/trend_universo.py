#!/usr/bin/env python3
"""Vale la pena allargare l'universo da 15 a 19 asset?

Il capitale e' fisso (3 conti da 24.83 EUR). Aggiungere asset non aggiunge
capitale: aggiunge OCCASIONI. Sul giornaliero una posizione impegna ~17% del
conto, quindi cinque entrano e la sesta comincia a pestare i piedi.

Il test giusto e' quindi nel simulatore a capitale CONDIVISO: 15 asset (come ora,
5 per conto) contro 19 (7+6+6), a pari capitale. Se il rendimento non migliora,
allargare serve solo a spezzettare.

Uso: python3 tools/trend_universo.py
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

ATTUALE = {
    "mc2":      ["BTC", "ETH", "SOL", "XRP", "DOGE"],
    "nuvola":   ["LINK", "AVAX", "DOT", "LTC", "UNI"],
    "MARCODG1": ["ADA", "ATOM", "AAVE", "ARB", "XLM"],
}
# i 4 esclusi, distribuiti su un conto ciascuno + il quarto sul conto piu' capiente
ALLARGATO = {
    "mc2":      ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
    "nuvola":   ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"],
    "MARCODG1": ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"],
}


def carica(conti):
    out = {}
    for nome, simboli in conti.items():
        assets = []
        for s in simboli:
            p = DATI / ("dl_%s_1D.csv" % s)
            if not p.is_file():
                raise SystemExit("manca %s" % p)
            assets.append((s, E.load_csv(p)))
        n = min(len(c) for _, c in assets)
        out[nome] = [(s, c[-n:]) for s, c in assets]
    return out


def prova(conti, risk, fee=FEE):
    curve, rif, tr = [], 0, 0
    for nome, assets in conti.items():
        r = cap.simula(assets, cap.CAPITALE, risk, fee, cap.SLIP, **cap.BASE)
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
    anni = n / 365.0
    return dict(rend=port[-1] - 1.0, cagr=port[-1] ** (1/anni) - 1.0,
                mdd=mdd, sharpe=sharpe, rif=rif, tr=tr, n=n)


def main():
    print("Capitale CONDIVISO, 3 conti da %.2f EUR, fee spot %.2f%%/lato"
          % (cap.CAPITALE, FEE * 100))
    print("  %-12s %7s %10s %9s %8s %8s %9s %7s" %
          ("universo", "rischio", "rend.3c", "CAGR", "maxDD", "Sharpe", "rifiutati", "trades"))
    for etichetta, conti in (("15 asset", ATTUALE), ("19 asset", ALLARGATO)):
        dati = carica(conti)
        for risk in (0.01, 0.02, 0.03):
            m = prova(dati, risk)
            print("  %-12s %5.0f%% %9.2f%% %8.2f%% %7.2f%% %8.2f %9d %7d"
                  % (etichetta, risk * 100, m["rend"] * 100, m["cagr"] * 100,
                     m["mdd"] * 100, m["sharpe"], m["rif"], m["tr"]))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Il vantaggio del 4H a fee basse regge FINESTRA PER FINESTRA, o e' un episodio?

Il giornaliero ha tutto il rendimento in un solo blocco (round 15): +20.33%
-0.55% +0.25%. Se il 4H a fee swap fa la stessa cosa, non serve a niente.

Qui si spezza la storia in blocchi sequenziali non sovrapposti e si guarda quanti
sono positivi. E' la prova che distingue un edge da una coincidenza.

Uso: python3 tools/trend_4h_finestre.py
"""
from __future__ import annotations
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_longshort import trend_ls, BASE  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]
FEE_SPOT = 0.0035
FEE_SWAP = 0.0005

CONFIG = {
    "4H pari-barre (40/100/14)": dict(BASE, canale=40, trend_ema=100, atr_period=14),
    "4H canale-120 (120/300/42)": dict(BASE, canale=120, trend_ema=300, atr_period=42),
}


def carica(prefisso, suffisso, minimo=800):
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("%s%s_%s.csv" % (prefisso, s, suffisso))
        if not p.is_file():
            continue
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > minimo:
            serie[s] = c
    if not serie:
        return {}, 0
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def blocco(serie, p, da, a, fee, short):
    rend = []
    for s, c in serie.items():
        r = trend_ls(c[da:a], p, 1.0, fee, 0.02, permetti_short=short)
        if r.equity and r.trade >= 1:
            rend.append(r.ritorno)
    return st.mean(rend) if rend else 0.0


def analizza(serie, n, etichetta, fee, blocchi=5):
    print()
    print("=== %s  (fee %.2f%%/lato, %d blocchi)" % (etichetta, fee * 100, blocchi))
    passo = n // blocchi
    intest = "  %-28s" % "configurazione"
    for k in range(blocchi):
        intest += " %8s" % ("b%d" % (k + 1))
    intest += " %9s %8s" % ("composto", "positivi")
    print(intest)
    for nome, p in CONFIG.items():
        for short, sn in ((False, "long-only"), (True, "long/short")):
            vals, comp = [], 1.0
            for k in range(blocchi):
                da = k * passo
                a = (k + 1) * passo if k < blocchi - 1 else n
                v = blocco(serie, p, da, a, fee, short)
                vals.append(v)
                comp *= (1.0 + v)
            riga = "  %-28s" % ("%s %s" % (nome.split()[0] + " " + nome.split()[1], sn))
            for v in vals:
                riga += " %7.2f%%" % (v * 100)
            riga += " %8.2f%% %6d/%d" % ((comp - 1) * 100,
                                         sum(1 for x in vals if x > 0), blocchi)
            print(riga)


def main():
    s4, n4 = carica("uni_", "4H")
    if s4:
        analizza(s4, n4, "4H a fee SWAP (derivati)", FEE_SWAP)
        analizza(s4, n4, "4H a fee SPOT", FEE_SPOT)
    sd, nd = carica("dl_", "1D")
    if sd:
        analizza(sd, nd, "GIORNALIERO a fee SPOT (riferimento)", FEE_SPOT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

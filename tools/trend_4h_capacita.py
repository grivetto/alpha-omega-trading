#!/usr/bin/env python3
"""Il 4H regge il vincolo di CASSA reale? (3 conti da 24.83 EUR, 5 asset)

Perche' e' la verifica che manca. Sul 4H l'ATR e' ~2.4 volte piu' piccolo che sul
giornaliero (stessa volatilita' su barre piu' corte), e la size e' risk/(stop_mult
* ATR): a pari rischio la posizione diventa ~2.4 volte piu' GRANDE. Con 5 asset per
conto e 24.83 EUR, due posizioni riempiono il conto.

I +44%/+68% misurati finora davano a ogni simbolo il proprio capitale PIENO. Qui si
usa il simulatore a capitale CONDIVISO, validato al bit contro backtest_trend, e si
cerca il rischio ottimo sotto il vincolo vero.

Uso: python3 tools/trend_4h_capacita.py
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
FEE_SPOT = 0.0035
FEE_SWAP = 0.0005
CAPITALE = None      # dal modulo cap (24.83)

# parametri: giornaliero deployato, 4H a pari numero di barre, 4H a pari tempo
PARAM = {
    "GIORNALIERO 1d (deployato)": dict(canale=40, atr_period=14, trail_mult=3.0,
                                       stop_atr_mult=2.0, trend_ema=100),
    "4H pari-barre 40/14/100": dict(canale=40, atr_period=14, trail_mult=3.0,
                                    stop_atr_mult=2.0, trend_ema=100),
    "4H canale 240 ema 600 atr 84": dict(canale=240, atr_period=84, trail_mult=3.0,
                                         stop_atr_mult=2.0, trend_ema=600),
}


def carica_conti(suffisso, prefisso):
    conti = {}
    for nome, simboli in cap.CONTI.items():
        assets = []
        for s in simboli:
            p = DATI / ("%s%s_%s.csv" % (prefisso, s, suffisso))
            if not p.is_file():
                raise SystemExit("manca %s" % p)
            assets.append((s, E.load_csv(p)))
        n = min(len(c) for _, c in assets)
        conti[nome] = [(s, c[-n:]) for s, c in assets]
    return conti


def prova(conti, params, risk, fee, barre_giorno):
    curve, rif, tr = [], 0, 0
    for nome, assets in conti.items():
        r = cap.simula(assets, cap.CAPITALE, risk, fee, cap.SLIP, **params)
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
    rr = [port[i] / port[i - 1] - 1.0 for i in range(1, n) if port[i - 1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    rend = port[-1] - 1.0
    anni = n / (barre_giorno * 365.0)
    cagr = port[-1] ** (1 / anni) - 1.0 if anni > 0 and port[-1] > 0 else -1.0
    return dict(rend=rend, cagr=cagr, mdd=mdd, sharpe=sharpe, rif=rif, tr=tr,
                anni=anni, esp=None)


def main():
    print("Simulatore a CAPITALE CONDIVISO, 3 conti da %.2f EUR, 5 asset ciascuno"
          % cap.CAPITALE)
    print()
    print("  %-30s %7s %6s %10s %9s %8s %8s %9s" %
          ("configurazione", "fee", "rischio", "rend.3c", "CAGR", "maxDD", "Sharpe", "rifiutati"))
    for nome, params in PARAM.items():
        suffisso = "1D" if "GIORNALIERO" in nome else "4H"
        prefisso = "dl_" if "GIORNALIERO" in nome else "uni_"
        bg = 1.0 if "GIORNALIERO" in nome else 6.0
        conti = carica_conti(suffisso, prefisso)
        fees = [(FEE_SPOT, "spot")] if "GIORNALIERO" in nome else \
               [(FEE_SPOT, "spot"), (FEE_SWAP, "swap")]
        for fee, fname in fees:
            for risk in (0.005, 0.01, 0.02):
                m = prova(conti, params, risk, fee, bg)
                print("  %-30s %6s %5.1f%% %9.2f%% %8.2f%% %7.2f%% %8.2f %9d"
                      % (nome, fname, risk * 100, m["rend"] * 100, m["cagr"] * 100,
                         m["mdd"] * 100, m["sharpe"], m["rif"]))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

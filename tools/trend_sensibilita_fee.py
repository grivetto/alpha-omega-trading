#!/usr/bin/env python3
"""Quanto valgono i costi? Sensibilita' del portafoglio alla fee (round 30)

La strategia e' misurata con la fee TAKER dello spot OKX EEA (0.35%/lato). Ogni
riduzione dei costi — ordini maker (0.20%), derivati taker (0.05%) — si traduce
direttamente in rendimento, perche' il numero di giri e' piccolo ma il notional
e' l'intero capitale.

Stampa il portafoglio (flotta 17, capitale condiviso per conto, rischio 2%) a
fee diverse, su storia e finestre recenti, e la differenza in EURO sul capitale
vero (109.58 EUR).

Uso: python3 tools/trend_sensibilita_fee.py
"""
from __future__ import annotations

import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
spec = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cap)

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
PAR = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
           trend_ema=100, entry_slip=0.0005, max_exposure=1.0)
CAPITALI = {"mc2": 42.12, "nuvola": 24.83, "MARCODG1": 42.04}
TOTALE = sum(CAPITALI.values())
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FEES = (("taker spot 0.35%", 0.0035), ("maker spot 0.20%", 0.0020),
        ("taker derivati 0.05%", 0.0005), ("costi zero", 0.0))
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))


def conti_per(asset):
    nomi = list(CAPITALI)
    conti = {k: [] for k in nomi}
    for i, s in enumerate(asset):
        conti[nomi[i % len(nomi)]].append(s)
    return conti


def prova(dati, fee):
    curve, tr = [], 0
    for nome, lista in conti_per(FLOTTA).items():
        if not lista:
            continue
        r = cap.simula([(s, dati[s]) for s in lista], CAPITALI[nome], 0.02,
                       fee, cap.SLIP, **PAR)
        curve.append([e / CAPITALI[nome] for e in r["curva"]])
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
    return port[-1] - 1.0, mdd, sharpe, tr


def main():
    serie = {}
    for p in sorted(DATI.glob("dl_*_1D.csv")):
        base = p.name[3:-7]
        if base not in FLOTTA:
            continue
        c = E.load_csv(p)
        if len(c) > 400:
            serie[base] = c
    n = min(len(c) for c in serie.values())
    dati = {s: c[-n:] for s, c in serie.items()}
    print("flotta 17, capitale %.2f EUR, rischio 2%%, %d barre comuni"
          % (TOTALE, n))
    print("  %-20s %-7s %10s %8s %8s %8s %10s" %
          ("fee", "finestra", "rend.", "maxDD", "Sharpe", "trades", "in EUR"))
    base_fin = {}
    for etichetta, fee in FEES:
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()}
            rend, mdd, sharpe, tr = prova(sotto, fee)
            if nome_fin in ("storia", "365b"):
                if nome_fin not in base_fin:
                    base_fin[nome_fin] = rend
                delta = rend - base_fin[nome_fin]
            else:
                delta = 0.0
            print("  %-20s %-7s %9.2f%% %7.2f%% %8.2f %8d %9.2f EUR%s" %
                  (etichetta, nome_fin, rend * 100, mdd * 100, sharpe, tr,
                   rend * TOTALE,
                   ("  (%+.2f punti, %+.2f EUR)" % (delta * 100, delta * TOTALE))
                   if nome_fin in ("storia", "365b") and etichetta != FEES[0][0]
                   else ""))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

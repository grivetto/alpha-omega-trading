#!/usr/bin/env python3
"""La selezione per-asset regge FUORI CAMPIONE? (round 30, 2026-09-17)

Dalla tabella per-asset del round 30 cinque asset della flotta (SUI, DOT, ADA,
AVAX, CRV) non rendono in NESSUNA finestra recente. Toglierli sembra ovvio — ed
e' proprio il modo classico di overfittare il passato recente.

Protocollo out-of-sample:
  - il 60% iniziale della storia comune e' IN CAMPIONE: li' si decide quali asset
    tenere (rendimento > 0 con i parametri deployati);
  - il 40% finale e' FUORI CAMPIONE: li' si confronta il portafoglio "flotta
    intera" con quello "solo asset scelti". Le finestre 270b/180b stanno tutte
    dentro la parte fuori campione.
  - Se la potatura batte la flotta intera anche fuori campione, si adotta; se
    batte solo dentro, era overfitting.

Uso: python3 tools/trend_potatura_oos.py
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
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
IS_FRAZIONE = 0.60
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))


def carica():
    serie = {}
    for p in sorted(DATI.glob("dl_*_1D.csv")):
        base = p.name[3:-7]
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > 400:
            serie[base] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def conti_per(asset):
    nomi = list(CAPITALI)
    conti = {k: [] for k in nomi}
    for i, s in enumerate(asset):
        conti[nomi[i % len(nomi)]].append(s)
    return conti


def prova(dati, simboli):
    conti = conti_per(simboli)
    curve, tr = [], 0
    for nome, lista in conti.items():
        if not lista:
            continue
        r = cap.simula([(s, dati[s]) for s in lista], CAPITALI[nome], 0.02,
                       cap.FEE, cap.SLIP, **PAR)
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
    return port[-1] - 1.0, mdd, sharpe, tr, n


def main():
    dati, n = carica()
    taglio = int(n * IS_FRAZIONE)
    print("barre comuni %d -> in campione %d, fuori campione %d"
          % (n, taglio, n - taglio))
    is_dati = {s: c[:taglio] for s, c in dati.items()}
    oos_dati = {s: c[taglio - 101:] for s, c in dati.items()}   # 101 barre di warmup

    rend_is = {}
    for s, c in is_dati.items():
        r = E.backtest_trend(c, dict(PAR, fee_buffer=0.01), 1.0, cap.FEE)
        rend_is[s] = 0.0 if r.errore else r.ritorno
    print()
    print("IN CAMPIONE (primo 60%), rendimento per asset della flotta:")
    for s in FLOTTA:
        print("  %-6s %8.1f%%   %s" % (s, rend_is.get(s, 0.0) * 100,
                                       "TENUTO" if rend_is.get(s, 0.0) > 0 else "SCARTATO"))
    tenuti = [s for s in FLOTTA if rend_is.get(s, 0.0) > 0]
    scartati = [s for s in FLOTTA if rend_is.get(s, 0.0) <= 0]
    print("  tenuti %d: %s" % (len(tenuti), " ".join(tenuti)))
    print("  scartati %d: %s" % (len(scartati), " ".join(scartati)))

    print()
    print("FUORI CAMPIONE: il portafoglio migliora togliendo gli asset scartati?")
    print("  %-14s %-7s %10s %8s %8s %7s %7s" %
          ("insieme", "finestra", "rend.", "maxDD", "Sharpe", "trades", "barre"))
    insiemi = [("flotta (17)", FLOTTA), ("solo tenuti (%d)" % len(tenuti), tenuti),
               ("solo scartati (%d)" % len(scartati), scartati)]
    for etichetta, lista in insiemi:
        if not lista:
            continue
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in oos_dati.items()
                     if s in lista}
            rend, mdd, sharpe, tr, barre = prova(sotto, lista)
            print("  %-14s %-7s %9.2f%% %7.2f%% %8.2f %7d %7d" %
                  (etichetta, nome_fin, rend * 100, mdd * 100, sharpe, tr, barre))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

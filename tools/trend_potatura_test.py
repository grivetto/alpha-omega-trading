#!/usr/bin/env python3
"""Togliere LTC, AAVE e ATOM migliora il portafoglio? (misurato, non intuito)

Toglierli riduce il numero di occasioni ma alza la qualita' media. Il conto e'
condiviso, quindi la size delle altre posizioni NON cambia: si perde solo
l'occasione cattiva. Va verificato, perche' meno asset significa anche meno
diversificazione.

Uso: python3 tools/trend_potatura_test.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
sp = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(sp)
sp.loader.exec_module(cap)
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
PARAMS = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400)
CONTI_BASE = {
    "mc2":      (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola":   (24.83, ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"]),
    "MARCODG1": (42.04, ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"]),
}
SCENARI = {
    "19 (attuale)": [],
    "18 senza AAVE": ["AAVE"],
    "18 senza LTC": ["LTC"],
    "17 senza LTC/AAVE": ["LTC", "AAVE"],
    "16 senza LTC/AAVE/ATOM": ["LTC", "AAVE", "ATOM"],
    "15 senza anche DOT": ["LTC", "AAVE", "ATOM", "DOT"],
}


def conti(togli):
    out = {}
    for conto, (capitale, simboli) in CONTI_BASE.items():
        sel = [s for s in simboli if s not in togli]
        if sel:
            out[conto] = (capitale, sel)
    return out


def prova(togli, barre=None):
    curve, rif = [], 0
    for conto, (capitale, simboli) in conti(togli).items():
        aa = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for s in simboli]
        n = min(len(c) for _, c in aa)
        aa = [(s, c[-n:]) for s, c in aa]
        if barre:
            aa = [(s, c[-barre:]) for s, c in aa]
        r = cap.simula(aa, capitale, RISK, FEE, cap.SLIP, **PARAMS)
        curve.append([e / capitale for e in r["curva"]])
        rif += r["rifiutati"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i]/port[i-1] - 1.0 for i in range(1, n) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr)/sd*math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe, rif


def main():
    print("  %-26s %9s %8s %9s %8s %8s" %
          ("scenario", "storia", "maxDD", "12 mesi", "6 mesi", "Sharpe"))
    for nome, togli in SCENARI.items():
        r, mdd, sh, _ = prova(togli)
        r12, _, _, _ = prova(togli, 365)
        r6, _, _, _ = prova(togli, 180)
        print("  %-26s %+8.2f%% %7.2f%% %+8.2f%% %+7.2f%% %8.2f"
              % (nome, r * 100, mdd * 100, r12 * 100, r6 * 100, sh))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

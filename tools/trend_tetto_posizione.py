#!/usr/bin/env python3
"""Serve un TETTO alla singola posizione? (rischio di gap)

Il sizing e' sul rischio: qty = budget*rischio/(stop_mult*ATR). Con ATR molto
basso lo stop e' strettissimo e la posizione diventa enorme. TRX, con ATR all'1.45%,
impegnerebbe 17.21 EUR su un conto da 42: quattro-cinque volte le altre.

Il rischio a stop resta il 2%, ma il backtest assume di essere serviti AL PREZZO
di stop. Una GAP che salta lo stop colpisce l'intera posizione: con 17 EUR,
-10% di gap sono -6.9% del conto, non -2%.

Qui si misura quanto rendimento costa mettere un tetto (max_exposure), e quanto
riduce la posizione massima.

Uso: python3 tools/trend_tetto_posizione.py
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
sp = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(sp)
sp.loader.exec_module(cap)

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
CONTI = [("mc2", 42.12), ("nuvola", 24.83), ("MARCODG1", 42.04)]
FLOTTA = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
          "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI", "MINA"],
          "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}
BASE = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
            trend_ema=100, entry_slip=0.0005, fee_buffer=0.01, max_barre=400)


def prova(max_exp, barre=None):
    curve, rif = [], 0
    for nome, capitale in CONTI:
        aa = []
        for a in FLOTTA[nome]:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % a))
            aa.append((a, c))
        n = min(len(c) for _, c in aa)
        aa = [(a, c[-n:]) for a, c in aa]
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        r = cap.simula(aa, capitale, RISK, FEE, cap.SLIP,
                       **dict(BASE, max_exposure=max_exp))
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


def notional_trx(max_exp):
    a = 0.004219
    px = 0.2915
    budget = min(24.9, 42.03)
    dist = 2.0 * a
    q = min(budget * RISK / dist, budget * max_exp / px)
    return q * px


def main():
    print("capitale reale, fee %.2f%%, rischio %.0f%%" % (FEE * 100, RISK * 100))
    print("  %-10s %10s %8s %8s %9s %9s" %
          ("tetto", "storia", "maxDD", "Sharpe", "12 mesi", "TRX EUR"))
    for me in (1.0, 0.5, 0.4, 0.33, 0.25, 0.20):
        r, mdd, sh, _ = prova(me)
        r12, _, _, _ = prova(me, 365)
        print("  %-10s %+9.2f%% %7.2f%% %8.2f %+8.2f%% %9.2f"
              % ("%.0f%%" % (me * 100), r * 100, mdd * 100, sh, r12 * 100,
                 notional_trx(me)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

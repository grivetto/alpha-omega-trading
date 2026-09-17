#!/usr/bin/env python3
"""Cosa aspettarsi ADESSO: la configurazione a 19 asset sulle finestre recenti.

Il +65.59 EUR del backtest copre 2.4 anni e contiene il rally di fine 2024. Il
round 15 aveva mostrato che il giornaliero, spezzato in finestre, e' piatto. Con
19 asset e capitale condiviso va rifatto: e' il numero che dice cosa aspettarsi
nei prossimi mesi, non cosa e' successo una volta.

Uso: python3 tools/trend_recente_19.py
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


def prova(barre):
    curve, rif, tr = [], 0, 0
    for conto, (capitale, simboli) in REALI.items():
        aa = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for s in simboli]
        n = min(len(c) for _, c in aa)
        aa = [(s, c[-n:]) for s, c in aa]
        if barre:
            aa = [(s, c[-barre:]) for s, c in aa]
        r = cap.simula(aa, capitale, RISK, FEE, cap.SLIP, **cap.BASE)
        curve.append([e / capitale for e in r["curva"]])
        rif += r["rifiutati"]
        tr += r["trade"]
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
    return port[-1] - 1.0, mdd, sharpe, tr, n


def main():
    print("19 asset, capitale reale, rischio %.0f%%, fee %.2f%%" % (RISK*100, FEE*100))
    print("  %-22s %10s %8s %8s %8s" % ("finestra", "rend.", "maxDD", "Sharpe", "trades"))
    for barre, nome in ((None, "tutta la storia"), (540, "~18 mesi"),
                        (365, "~12 mesi"), (270, "~9 mesi"), (180, "~6 mesi")):
        rend, mdd, sharpe, tr, n = prova(barre)
        print("  %-22s %+9.2f%% %7.2f%% %8.2f %8d"
              % (nome, rend*100, mdd*100, sharpe, tr))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Qual e' il rischio per trade ottimale con il capitale VERO di adesso?

Il round 15 aveva trovato 2% ottimale con 74.5 EUR divisi in parti uguali. Ora:
  capitale per conto NON uniforme (mc2 42.12, nuvola 24.83, marcodg1 42.04)
  bot per conto 7/6/6 (prima 5/5/5)
Con 7 bot da ~17% l'uno, sette posizioni contemporanee sono il 119% del conto:
il vincolo puo' mordere dove prima non mordeva.

Si cerca il rischio che massimizza il rendimento sotto il vincolo reale, e si
guarda anche il risk-adjusted, che e' quello che conta se il conto deve durare.

Uso: python3 tools/trend_rischio_reale.py
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

# capitale REALE per conto (misurato) e distribuzione REALE dei bot
REALI = {
    "mc2":      (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola":   (24.83, ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"]),
    "MARCODG1": (42.04, ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"]),
}
RISCHI = [0.01, 0.015, 0.02, 0.025, 0.03, 0.04]


def main():
    serie = {}
    for conto, (_, simboli) in REALI.items():
        aa = []
        for s in simboli:
            aa.append((s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))))
        n = min(len(c) for _, c in aa)
        serie[conto] = [(s, c[-n:]) for s, c in aa]
    print("capitale reale per conto: %s" %
          ", ".join("%s %.2f" % (k, v[0]) for k, v in REALI.items()))
    print("bot per conto: %s" % ", ".join("%s %d" % (k, len(v[1])) for k, v in REALI.items()))
    print()
    print("  %-8s %10s %9s %8s %8s %10s %9s" %
          ("rischio", "rend.eur", "CAGR", "maxDD", "Sharpe", "rifiutati", "trades"))
    righe = []
    for risk in RISCHI:
        eur_iniziale, eur_finale, curve, rif, tr = 0.0, 0.0, [], 0, 0
        for conto, (capitale, _) in REALI.items():
            r = cap.simula(serie[conto], capitale, risk, FEE, cap.SLIP, **cap.BASE)
            curve.append([e / capitale for e in r["curva"]])
            eur_iniziale += capitale
            eur_finale += r["curva"][-1]
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
        cagr = port[-1] ** (1 / anni) - 1.0 if anni > 0 and port[-1] > 0 else -1.0
        rend_eur = eur_finale - eur_iniziale
        righe.append((risk, rend_eur, cagr, mdd, sharpe, rif, tr))
        print("  %-8s %+9.2fE %8.2f%% %7.2f%% %8.2f %10d %9d"
              % ("%.1f%%" % (risk * 100), rend_eur, cagr * 100, mdd * 100, sharpe, rif, tr))
    print()
    best_r = max(righe, key=lambda x: x[1])
    best_s = max(righe, key=lambda x: x[4])
    print("  massimo rendimento in EUR : rischio %.1f%% -> %+.2f EUR (CAGR %.2f%%, Sharpe %.2f)"
          % (best_r[0] * 100, best_r[1], best_r[2] * 100, best_r[4]))
    print("  massimo Sharpe            : rischio %.1f%% -> %+.2f EUR (maxDD %.2f%%, Sharpe %.2f)"
          % (best_s[0] * 100, best_s[1], best_s[3] * 100, best_s[4]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

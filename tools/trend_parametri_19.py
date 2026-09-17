#!/usr/bin/env python3
"""I parametri deployati sono ancora i migliori sui 19 asset?

Il set (canale 40, trail 3.0, stop 2.0, media 100) e' stato scelto quando
l'universo era di 15 asset e il capitale di 74.5 EUR. Ora sono 19 asset, 7/6/6
per conto e 109.6 EUR. Un set scelto su un universo diverso puo' non essere piu'
il migliore.

Misura: capitale CONDIVISO reale per conto, fee spot, rischio 2%. Si guarda sia
il rendimento assoluto sia lo Sharpe, e quante configurazioni battono quella
deployata — perche' se ne battono poche, cambiare sarebbe inseguire il rumore.

Uso: python3 tools/trend_parametri_19.py
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
DEPLOY = dict(canale=40, atr_period=14, trail_mult=3.0, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400)


def prepara():
    out = {}
    for conto, (_, simboli) in REALI.items():
        aa = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for s in simboli]
        n = min(len(c) for _, c in aa)
        out[conto] = [(s, c[-n:]) for s, c in aa]
    return out


def prova(serie, params):
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
    rr = [port[i]/port[i-1] - 1.0 for i in range(1, n) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr)/sd*math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe, rif


def main():
    serie = prepara()
    print("19 asset, capitale reale per conto, fee %.2f%%, rischio %.0f%%"
          % (FEE * 100, RISK * 100))
    r0, d0, s0, _ = prova(serie, DEPLOY)
    print("  DEPLOYATO (canale 40, trail 3.0, stop 2.0, ema 100): rend %+.2f%%  maxDD %.2f%%  Sharpe %.2f"
          % (r0 * 100, d0 * 100, s0))
    print()
    print("  griglia: canale 20/40/60 x trail 2.5/3/4 x stop 1.5/2/2.5 x ema 0/100/200")
    risultati = []
    for canale in (20, 40, 60):
        for trail in (2.5, 3.0, 4.0):
            for stop in (1.5, 2.0, 2.5):
                for ema in (0, 100, 200):
                    p = dict(DEPLOY, canale=canale, trail_mult=trail,
                             stop_atr_mult=stop, trend_ema=ema)
                    rend, mdd, sharpe, _ = prova(serie, p)
                    risultati.append({"p": (canale, trail, stop, ema), "rend": rend,
                                      "mdd": mdd, "sharpe": sharpe})
    rend = [x["rend"] for x in risultati]
    print("    set provati            : %d" % len(risultati))
    print("    mediano                : %+.2f%%" % (st.median(rend) * 100))
    print("    positivi               : %d/%d" % (sum(1 for x in rend if x > 0), len(rend)))
    print("    battono il deployato   : %d/%d (%.0f%%)"
          % (sum(1 for x in rend if x > r0), len(rend),
             100.0 * sum(1 for x in rend if x > r0) / len(rend)))
    migliori = sorted(risultati, key=lambda x: -x["rend"])[:5]
    print()
    print("  %-30s %10s %8s %8s" % ("migliori 5 (rendimento)", "rend.", "maxDD", "Sharpe"))
    for x in migliori:
        c, t, s, e = x["p"]
        print("  canale %-3d trail %.1f stop %.1f ema %-3d   %+9.2f%% %7.2f%% %8.2f"
              % (c, t, s, e, x["rend"] * 100, x["mdd"] * 100, x["sharpe"]))
    per_sharpe = sorted(risultati, key=lambda x: -x["sharpe"])[:5]
    print()
    print("  %-30s %10s %8s %8s" % ("migliori 5 (Sharpe)", "rend.", "maxDD", "Sharpe"))
    for x in per_sharpe:
        c, t, s, e = x["p"]
        print("  canale %-3d trail %.1f stop %.1f ema %-3d   %+9.2f%% %7.2f%% %8.2f"
              % (c, t, s, e, x["rend"] * 100, x["mdd"] * 100, x["sharpe"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

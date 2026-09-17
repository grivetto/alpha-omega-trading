#!/usr/bin/env python3
"""Quanti asset conviene davvero tenere? (16 -> 34, capitale condiviso reale)

Gli asset sono ordinati per alpha mediano (criterio indipendente dal risultato di
portafoglio). Si prova la flotta con N asset distribuiti a rotazione sui 3 conti e
si guarda dove il rendimento smette di crescere: piu' asset = piu' occasioni ma
anche piu' competizione per la cassa di ogni conto.

Uso: python3 tools/trend_quanti_asset.py
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
PARAMS = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400)
CONTI = [("mc2", 42.12), ("nuvola", 24.83), ("MARCODG1", 42.04)]

# promossi dallo screening, in ordine di alpha mediano decrescente
ORDINE = ["XLM", "SHIB", "ALGO", "XRP", "COMP", "HBAR", "XTZ", "CRV", "ETH", "CRO",
          "MINA", "EGLD", "ADA", "BAT", "1INCH", "SUSHI", "SAND", "ARB", "FLOW",
          "LINK", "TRX", "DOGE", "SOL", "AVAX", "UNI", "GRT", "SUI", "DYDX",
          "WOO", "CHZ", "SNX", "MANA", "BTC", "DOT"]
ATTUALE = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
           "LINK", "AVAX", "DOT", "UNI", "SUI",
           "ADA", "ARB", "XLM", "ALGO"]


def carica(assets):
    out = {}
    for a in assets:
        f = DATI / ("dl_%s_1D.csv" % a)
        if not f.is_file():
            return None
        out[a] = E.load_csv(f)
    n = min(len(c) for c in out.values())
    return {a: c[-n:] for a, c in out.items()}


def distribuisci(assets):
    conti = {n: [] for n, _ in CONTI}
    for i, a in enumerate(assets):
        conti[CONTI[i % 3][0]].append(a)
    return conti


def prova(assets):
    dati = carica(assets)
    if not dati:
        return None
    conti = distribuisci(assets)
    curve, rif = [], 0
    for nome, capitale in CONTI:
        aa = [(a, dati[a]) for a in conti[nome]]
        if not aa:
            continue
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
    r12 = port[-366] if n > 366 else port[0]
    return dict(rend=port[-1] - 1.0, mdd=mdd, sharpe=sharpe, rif=rif,
                r12=port[-1] / r12 - 1.0, per_conti={k: len(v) for k, v in conti.items()})


def main():
    print("capitale reale 42.12 / 24.83 / 42.04, fee %.2f%%, rischio %.0f%%"
          % (FEE * 100, RISK * 100))
    print("  %-22s %5s %9s %8s %9s %8s %9s" %
          ("flotta", "asset", "storia", "maxDD", "12 mesi", "Sharpe", "rifiutati"))
    scenari = [("ATTUALE (16)", ATTUALE)]
    for n in (18, 20, 22, 24, 26, 28, 30, 34):
        scenari.append(("%d migliori" % n, ORDINE[:n]))
    for nome, assets in scenari:
        p = prova(assets)
        if not p:
            print("  %-22s mancano dei file" % nome); continue
        print("  %-22s %5d %+8.2f%% %7.2f%% %+8.2f%% %8.2f %9d   conti %s"
              % (nome, len(assets), p["rend"] * 100, p["mdd"] * 100,
                 p["r12"] * 100, p["sharpe"], p["rif"], p["per_conti"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

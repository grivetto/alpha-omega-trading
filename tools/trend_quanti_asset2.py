#!/usr/bin/env python3
"""Quanti asset, misurato BENE: finestre risimulate e distribuzione reale.

Il test precedente misurava i "12 mesi" come port[-366] sulla curva di tutta la
storia, e distribuiva gli asset a rotazione (6/5/5) invece che come in
produzione (7/5/4). Due differenze che possono cambiare la conclusione.

Qui: la flotta attuale usa la distribuzione REALE, le altre sono bilanciate, e
ogni finestra viene RISIMULATA da zero come nel round 19.

Uso: python3 tools/trend_quanti_asset2.py
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
ORDINE = ["XLM", "SHIB", "ALGO", "XRP", "COMP", "HBAR", "XTZ", "CRV", "ETH", "CRO",
          "MINA", "EGLD", "ADA", "BAT", "1INCH", "SUSHI", "SAND", "ARB", "FLOW",
          "LINK", "TRX", "DOGE", "SOL", "AVAX", "UNI", "GRT", "SUI", "DYDX",
          "WOO", "CHZ", "SNX", "MANA", "BTC", "DOT"]
# distribuzione REALE dei 16 in produzione
ATTUALE = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
           "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI"],
           "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}


def carica_da(conti, barre=None):
    out = {}
    for nome, capitale in CONTI:
        aa = []
        for a in conti[nome]:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % a))
            aa.append((a, c))
        if not aa:
            return None
        n = min(len(c) for _, c in aa)
        aa = [(a, c[-n:]) for a, c in aa]
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        out[nome] = aa
    return out


def misura(conti, barre=None):
    dati = carica_da(conti, barre)
    if not dati:
        return None
    curve, rif = [], 0
    for nome, capitale in CONTI:
        r = cap.simula(dati[nome], capitale, RISK, FEE, cap.SLIP, **PARAMS)
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


def bilanciato(assets):
    """Distribuzione per numero di bot, ma tenendo i conti grandi piu' carichi."""
    conti = {"mc2": [], "nuvola": [], "MARCODG1": []}
    # i conti con piu' capitale prendono un asset in piu'
    ordine = ["mc2", "MARCODG1", "nuvola"]
    for i, a in enumerate(assets):
        conti[ordine[i % 3]].append(a)
    return conti


def main():
    scenari = [("ATTUALE (16)", ATTUALE)]
    for n in (18, 20, 24, 28):
        scenari.append(("%d migliori" % n, bilanciato(ORDINE[:n])))
    finestre = [(None, "storia"), (540, "18m"), (365, "12m"), (270, "9m"), (180, "6m")]
    intest = "  %-16s" % "flotta"
    for _, nome in finestre:
        intest += " %8s" % nome
    intest += " %8s %8s" % ("maxDD", "Sharpe")
    print(intest)
    for nome, conti in scenari:
        tot = sum(len(v) for v in conti.values())
        riga = "  %-16s" % ("%s" % nome)
        dd = sh = 0.0
        for barre, _ in finestre:
            try:
                r, mdd, sharpe, _ = misura(conti, barre)
            except (IndexError, ValueError):
                r, mdd, sharpe = float("nan"), float("nan"), float("nan")
            if barre is None:
                dd, sh = mdd, sharpe
            riga += " %7.2f%%" % (r * 100)
        riga += " %7.2f%% %8.2f" % (dd * 100, sh)
        print(riga + "   (%d bot: %d/%d/%d)" % (tot, len(conti["mc2"]),
                                                len(conti["nuvola"]), len(conti["MARCODG1"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

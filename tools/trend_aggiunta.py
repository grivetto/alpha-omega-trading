#!/usr/bin/env python3
"""Qualche asset NUOVO, aggiunto da solo, migliora il regime RECENTE?

Selezionare i "migliori N" per alpha mediano peggiora il presente (dominato dal
rally 2024). Ma l'opposto — aggiungere un asset specifico alla flotta attuale —
si puo' misurare uno per uno. Si tiene la flotta di produzione e si aggiunge un
candidato per volta all'account con meno bot.

Uso: python3 tools/trend_aggiunta.py
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
ATTUALE = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
           "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI"],
           "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}
CANDIDATI = ["SHIB", "COMP", "HBAR", "XTZ", "CRO", "MINA", "EGLD", "BAT", "1INCH",
             "SUSHI", "SAND", "FLOW", "GRT", "DYDX", "WOO", "CHZ", "SNX", "MANA",
             "ETC", "NEO"]
FINESTRE = [(None, "storia"), (540, "18m"), (365, "12m"), (270, "9m"), (180, "6m")]


def misura(conti, barre=None):
    cache = {}
    curve, rif = [], 0
    for nome, capitale in CONTI:
        aa = []
        for a in conti[nome]:
            f = DATI / ("dl_%s_1D.csv" % a)
            if not f.is_file():
                return None
            c = cache.get(a) or E.load_csv(f)
            cache[a] = c
            aa.append((a, c))
        n = min(len(c) for _, c in aa)
        aa = [(a, c[-n:]) for a, c in aa]
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
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
    return port[-1] - 1.0, mdd, sharpe


def base_valori():
    return {nome: misura(ATTUALE, b) for b, nome in FINESTRE}


def main():
    base = base_valori()
    print("BASE (16 bot): " + "  ".join("%s %+.2f%%" % (n, base[n][0] * 100)
                                        for _, n in FINESTRE))
    print()
    print("  %-8s %9s %8s %8s %8s   %s" % ("candidato", "18m", "12m", "9m", "6m", "esito"))
    for cand in CANDIDATI:
        if not (DATI / ("dl_%s_1D.csv" % cand)).is_file():
            print("  %-8s file assente" % cand); continue
        conti = {k: list(v) for k, v in ATTUALE.items()}
        conti["nuvola"] = conti["nuvola"] + [cand]   # il conto con meno bot
        vals = {}
        for b, n in FINESTRE:
            m = misura(conti, b)
            if m is None:
                vals = None
                break
            vals[n] = m[0]
        if vals is None:
            print("  %-8s dati mancanti" % cand); continue
        # criterio: meglio in TUTTE le finestre recenti tranne al massimo una
        peggio = sum(1 for n in ("18m", "12m", "9m", "6m") if vals[n] < base[n][0])
        esito = "MEGLIO in tutte" if peggio == 0 else ("peggio in %d/4" % peggio)
        print("  %-8s %+7.2f%% %+7.2f%% %+7.2f%% %+7.2f%%   %s"
              % (cand, vals["18m"] * 100, vals["12m"] * 100, vals["9m"] * 100,
                 vals["6m"] * 100, esito))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

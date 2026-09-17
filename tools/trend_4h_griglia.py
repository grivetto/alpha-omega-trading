#!/usr/bin/env python3
"""Griglia 4H a fee swap: quante combinazioni reggono, e in quante finestre?

Una configurazione sola che funziona puo' essere fortuna. Il criterio robusto e':
su una GRIGLIA AMPIA, quante combinazioni sono positive, e quante lo sono in
almeno 4 finestre su 5? Se e' una minoranza, l'edge non e' robusto.

Confronto diretto con lo stesso criterio applicato al GIORNALIERO a fee spot
(quello deployato oggi).

Uso: python3 tools/trend_4h_griglia.py
"""
from __future__ import annotations
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent))
from trend_longshort import trend_ls, BASE  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]


def carica(prefisso, suffisso, minimo=800):
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("%s%s_%s.csv" % (prefisso, s, suffisso))
        if p.is_file():
            try:
                c = E.load_csv(p)
            except Exception:
                continue
            if len(c) > minimo:
                serie[s] = c
    if not serie:
        return {}, 0
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def analizza(serie, n, etichetta, fee, blocchi=5):
    passo = n // blocchi
    confini = []
    for k in range(blocchi):
        da = k * passo
        a = (k + 1) * passo if k < blocchi - 1 else n
        confini.append((da, a))
    righe = []
    for canale in (20, 40, 60, 80):
        for ema_n in (50, 100, 200):
            for short in (False, True):
                p = dict(BASE, canale=canale, trend_ema=ema_n, atr_period=14)
                vals, tot = [], []
                for da, a in confini:
                    rend = []
                    for s, c in serie.items():
                        r = trend_ls(c[da:a], p, 1.0, fee, 0.02, permetti_short=short)
                        if r.equity and r.trade >= 1:
                            rend.append(r.ritorno)
                    vals.append(st.mean(rend) if rend else 0.0)
                comp = 1.0
                for v in vals:
                    comp *= (1.0 + v)
                righe.append({"canale": canale, "ema": ema_n, "short": short,
                              "vals": vals, "comp": comp - 1.0,
                              "pos": sum(1 for v in vals if v > 0)})
    tot = len(righe)
    fin_pos = sum(1 for r in righe if r["comp"] > 0)
    robusti = sum(1 for r in righe if r["pos"] >= 4)
    comp_med = st.median([r["comp"] for r in righe])
    print()
    print("=== %s  (fee %.2f%%/lato, %d configurazioni, %d finestre)"
          % (etichetta, fee * 100, tot, blocchi))
    print("    combinazioni con rendimento composto POSITIVO : %d/%d (%.0f%%)"
          % (fin_pos, tot, 100.0 * fin_pos / tot))
    print("    combinazioni positive in >= 4 finestre su 5    : %d/%d (%.0f%%)"
          % (robusti, tot, 100.0 * robusti / tot))
    print("    rendimento composto MEDIANO                     : %+.2f%%" % (comp_med * 100))
    for short in (False, True):
        sel = [r for r in righe if r["short"] == short]
        print("      %-11s composto mediano %+7.2f%%  positivi %d/%d"
              % ("long/short" if short else "long-only",
                 st.median([r["comp"] for r in sel]) * 100,
                 sum(1 for r in sel if r["comp"] > 0), len(sel)))
    return righe


def main():
    s4, n4 = carica("uni_", "4H")
    if s4:
        print("universo 4H: %d simboli, %d barre (%.1f anni)"
              % (len(s4), n4, n4 / (6 * 365.0)))
        analizza(s4, n4, "4H a fee SWAP 0.05% (derivati)", 0.0005)
        analizza(s4, n4, "4H a fee SPOT 0.35%", 0.0035)
    sd, nd = carica("dl_", "1D")
    if sd:
        print()
        print("universo DAILY: %d simboli, %d barre" % (len(sd), nd))
        analizza(sd, nd, "GIORNALIERO a fee SPOT (deployato oggi)", 0.0035)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

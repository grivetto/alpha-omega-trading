#!/usr/bin/env python3
"""Confronto fra set di parametri del trend, finestra per finestra.

Il set deployato e' canale=40 trail=3.0 stop=2.0 ema=100. Nelle prove per
finestra il set canale=20 trail=4.0 stop=1.5 risultava il MIGLIORE in tutte le
finestre, anche le piu' recenti. Ma "migliore su una finestra" e' esattamente
come nasce l'overfitting: qui si guarda se vince in MOLTE finestre, che e' una
prova molto piu' difficile da falsificare.

Uso: python3 tools/trend_confronto.py
"""
from __future__ import annotations
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]
FEE = 0.0035
BASE = dict(atr_period=14, max_exposure=1.0, entry_slip=0.0005,
            fee_buffer=0.01, max_barre=400, risk_pct=0.02)

SET = {
    "A deploy ": dict(BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "B largo  ": dict(BASE, canale=20, trail_mult=4.0, stop_atr_mult=1.5, trend_ema=100),
    "C largoE2": dict(BASE, canale=20, trail_mult=4.0, stop_atr_mult=1.5, trend_ema=200),
    "D canale6": dict(BASE, canale=60, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "E stretto": dict(BASE, canale=20, trail_mult=2.0, stop_atr_mult=2.0, trend_ema=100),
}


def carica():
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("dl_%s_1D.csv" % s)
        if p.is_file():
            c = E.load_csv(p)
            if len(c) > 250:
                serie[s] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def rend(serie, p, da, a):
    vals = []
    for s, c in serie.items():
        if a - da < 60:
            continue
        r = E.backtest_trend(c[da:a], p, 1.0, FEE)
        if not r.errore and r.equity:
            vals.append(r.ritorno)
    return st.mean(vals) if vals else 0.0


def main():
    serie, n = carica()
    print("universo %d simboli, %d barre comuni, fee taker %.2f%%/lato"
          % (len(serie), n, FEE * 100))
    print("periodo: dal %s al %s"
          % (__import__("datetime").datetime.utcfromtimestamp(
              list(serie.values())[0][0]["ts"] / 1000).strftime("%Y-%m-%d"),
             __import__("datetime").datetime.utcfromtimestamp(
              list(serie.values())[0][-1]["ts"] / 1000).strftime("%Y-%m-%d")))

    print()
    print("1) BLOCCHI SEQUENZIALI non sovrapposti (5 blocchi da ~%d barre)" % (n // 5))
    passo = n // 5
    intest = "  %-10s" % "blocco"
    for k in SET:
        intest += " %10s" % k
    print(intest)
    for k in range(5):
        da = k * passo
        a = (k + 1) * passo if k < 4 else n
        riga = "  %-10s" % ("%d" % (k + 1))
        for nome, p in SET.items():
            riga += " %9.2f%%" % (rend(serie, p, da, a) * 100)
        print(riga)

    print()
    print("2) VITTORIE su finestre scorrevoli da 180 barre (passo 60)")
    vitt = {k: 0 for k in SET}
    tot = 0
    for da in range(0, n - 180, 60):
        vals = {k: rend(serie, p, da, da + 180) for k, p in SET.items()}
        best = max(vals, key=vals.get)
        vitt[best] += 1
        tot += 1
    for k in SET:
        print("   %-10s vince %2d/%d finestre (%.0f%%)"
              % (k, vitt[k], tot, 100.0 * vitt[k] / tot if tot else 0))

    print()
    print("3) TUTTA LA STORIA")
    for nome, p in SET.items():
        print("   %-10s %+7.2f%%" % (nome, rend(serie, p, 0, n) * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

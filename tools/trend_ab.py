#!/usr/bin/env python3
"""A vs B vs D su OUT-OF-SAMPLE ancorato, con il numero di trade.

Trappola da evitare (vista in tools/trend_confronto.py): un set con EMA200 che
non scalda su finestre corte produce 0.00% e "vince" ogni volta che gli altri
sono negativi. Qui si riportano SEMPRE i trade: zero trade = risultato non
valido, non una vittoria.

Uso: python3 tools/trend_ab.py
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
    "A deploy": dict(BASE, canale=40, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
    "B largo ": dict(BASE, canale=20, trail_mult=4.0, stop_atr_mult=1.5, trend_ema=100),
    "D can60 ": dict(BASE, canale=60, trail_mult=3.0, stop_atr_mult=2.0, trend_ema=100),
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


def blocco(serie, p, da, a):
    vals, tr, esp = [], 0, []
    for s, c in serie.items():
        if a - da < 80:
            continue
        r = E.backtest_trend(c[da:a], p, 1.0, FEE)
        if r.errore or not r.equity:
            continue
        vals.append(r.ritorno)
        tr += r.trade
        esp.append(r.esposizione_pct)
    if not vals:
        return None
    return st.mean(vals), tr, st.mean(esp)


def riga(titolo, serie, p, da, a):
    b = blocco(serie, p, da, a)
    if not b:
        return "  %-10s %s" % (titolo, "n/d")
    return "  %-10s %+7.2f%%   trade %3d   espos %4.1f%%" % (titolo, b[0] * 100, b[1], b[2])


def main():
    serie, n = carica()
    print("universo %d simboli, %d barre, fee taker %.2f%%/lato, rischio 2%%"
          % (len(serie), n, FEE * 100))

    for frac, nome in ((0.40, "ULTIMO 40% (OOS)"), (0.30, "ULTIMO 30% (OOS)"),
                       (0.20, "ULTIMO 20% (OOS)"), (1.00, "TUTTA LA STORIA")):
        da = int(n * (1.0 - frac))
        print()
        print("%s  [barre %d-%d]" % (nome, da, n))
        for k, p in SET.items():
            print(riga(k, serie, p, da, n))

    print()
    print("VITTORIE su 12 finestre scorrevoli da 180 barre (solo se il set TRADA)")
    vitt, tot = {k: 0 for k in SET}, 0
    for da in range(0, n - 180, 60):
        vals = {}
        for k, p in SET.items():
            b = blocco(serie, p, da, da + 180)
            if b and b[1] >= 2:
                vals[k] = b[0]
        if len(vals) < 2:
            continue
        best = max(vals, key=vals.get)
        if vals[best] > 0:
            vitt[best] += 1
        tot += 1
    for k in SET:
        print("   %-10s %2d/%d" % (k, vitt[k], tot))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

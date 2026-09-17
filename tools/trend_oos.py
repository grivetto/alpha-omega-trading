#!/usr/bin/env python3
"""Prova OUT-OF-SAMPLE per una strategia che trada POCO.

Il walk-forward standard scarta un fold se un simbolo fa meno di 2 trade nel
train: con ~7 trade per simbolo in 2.4 anni e finestre di 400 barre, il vincolo
e' troppo severo e non produce nessun fold. Qui si usa una misura adatta:

1. SPLIT ANCORATO: si valuta solo sull'ULTIMA parte della storia (dati mai usati
   per scegliere i parametri), con i parametri FISSI.
2. FINESTRE SEQUENZIALI non sovrapposte: si spezza la storia in N blocchi e si
   misura quanti sono positivi.

Uso: python3 tools/trend_oos.py
"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
UNIVERSO = ["AAVE", "ADA", "ALGO", "ARB", "ATOM", "AVAX", "BTC", "CRV", "DOGE",
            "DOT", "ETH", "LINK", "LTC", "SOL", "SUI", "TRX", "UNI", "XLM", "XRP"]
PARAMS = dict(canale=40, atr_period=14, trail_mult=3.0, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400)
FEE = 0.0035      # taker REALE per lato
RISK = 0.02


def carica():
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("dl_%s_1D.csv" % s)
        if p.is_file():
            c = E.load_csv(p)
            if len(c) > 200:
                serie[s] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def ritorno_blocco(serie, da, a):
    """Rendimento medio equal-weight dei simboli sul blocco [da, a)."""
    vals, trades, esp = [], 0, []
    for s, c in serie.items():
        if a - da < 60:
            continue
        r = E.backtest_trend(c[da:a], dict(PARAMS, risk_pct=RISK), 1.0, FEE)
        if r.errore or not r.equity:
            continue
        vals.append(r.ritorno)
        esp.append(r.esposizione_pct)
        trades += r.trade
    if not vals:
        return None
    return {"rend": st.mean(vals), "trades": trades, "esp": st.mean(esp),
            "n": len(vals)}


def main():
    serie, n = carica()
    print("universo: %d simboli, %d barre comuni" % (len(serie), n))
    print("parametri FISSI, fee taker %.2f%%/lato, rischio %.0f%%" % (FEE * 100, RISK * 100))

    print()
    print("1) SPLIT ANCORATO — si valuta solo sull'ultima parte della storia")
    print("   %-26s %10s %8s %8s %8s" % ("finestra OOS", "rend.medio", "trades", "simboli", "espos%"))
    for frac in (0.30, 0.40, 0.50):
        da = int(n * (1.0 - frac))
        b = ritorno_blocco(serie, da, n)
        if b:
            print("   ultimo %2.0f%% (%3d barre)      %9.2f%% %8d %8d %7.1f%%"
                  % (frac * 100, n - da, b["rend"] * 100, b["trades"], b["n"], b["esp"]))

    print()
    print("2) FINESTRE SEQUENZIALI — la storia spezzata in blocchi non sovrapposti")
    for nblocchi in (3, 4, 5):
        passo = n // nblocchi
        righe, comp, pos = [], 1.0, 0
        for k in range(nblocchi):
            da, a = k * passo, (k + 1) * passo if k < nblocchi - 1 else n
            b = ritorno_blocco(serie, da, a)
            if not b:
                continue
            righe.append("%+.2f%%" % (b["rend"] * 100))
            comp *= (1.0 + b["rend"])
            if b["rend"] > 0:
                pos += 1
        print("   %d blocchi da ~%d barre: %s" % (nblocchi, passo, "  ".join(righe)))
        print("      composto %.2f%%   blocchi positivi %d/%d"
              % ((comp - 1) * 100, pos, len(righe)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

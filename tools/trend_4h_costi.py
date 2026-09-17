#!/usr/bin/env python3
"""Il 4H diventa redditizio quando il costo scende da 0.70% a 0.10%?

Il 4H era stato RIFIUTATO perche' il costo per giro si mangiava il segnale. Ma
quel costo (0.70% round trip) e' quello dello SPOT. Sui derivati OKX EEA il taker
e' 0.05%, quindi il giro costa 0.10%: SETTE volte meno.

Qui si misura, sulle stesse 19 coppie e sullo stesso periodo del giornaliero:
  - 4H con parametri "a pari tempo" (canale 240 = 40 giorni, ema 600 = 100 giorni);
  - 4H con parametri "a pari numero di barre" (canale 40, ema 100);
  - long-only e long/short, a fee spot e a fee swap.

Uso: python3 tools/trend_4h_costi.py
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
FEE_SPOT = 0.0035
FEE_SWAP = 0.0005
BARRE_GIORNO = 6.0     # barre 4H per giorno


def carica_4h(minimo=800):
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("uni_%s_4H.csv" % s)
        if not p.is_file():
            continue
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


def misura(serie, p, fee, short, barre_giorno):
    rend, esp, tr, pos = [], [], 0, 0
    for s, c in serie.items():
        r = trend_ls(c, p, 1.0, fee, 0.02, permetti_short=short)
        if not r.equity:
            continue
        rend.append(r.ritorno)
        esp.append(r.esposizione_pct)
        tr += r.trade
        if r.ritorno > 0:
            pos += 1
    if not rend:
        return None
    medio = st.mean(rend)
    anni = len(next(iter(serie.values()))) / (barre_giorno * 365.0)
    return {"rend": medio, "med": st.median(rend), "esp": st.mean(esp),
            "trade": tr, "cagr": (1 + medio) ** (1 / anni) - 1 if medio > -1 else -1,
            "pos": pos, "n": len(rend), "anni": anni}


def riga(serie, nome, p, fee, short, bg):
    m = misura(serie, p, fee, short, bg)
    if not m:
        return
    print("  %-40s %9.2f%% %8.2f%% %7.1f%% %7d %6d/%d"
          % (nome, m["rend"] * 100, m["cagr"] * 100, m["esp"], m["trade"],
             m["pos"], m["n"]))


def main():
    serie, n = carica_4h()
    if not serie:
        print("nessun dato 4H"); return 1
    print("universo 4H: %d simboli, %d barre comuni (%.1f anni)"
          % (len(serie), n, n / (BARRE_GIORNO * 365.0)))
    print("(giornaliero di confronto: 19 simboli, 865 barre, 2.4 anni, +19.82% long-only spot)")
    print()
    print("  %-40s %9s %8s %7s %7s %8s" %
          ("configurazione", "rend.medio", "CAGR", "espos%", "trades", "positivi"))

    configurazioni = [
        ("pari TEMPO  (canale 240, ema 600, atr 84)",
         dict(BASE, canale=240, trend_ema=600, atr_period=84)),
        ("pari BARRE  (canale 40, ema 100, atr 14)",
         dict(BASE, canale=40, trend_ema=100, atr_period=14)),
        ("canale 120, ema 300, atr 42",
         dict(BASE, canale=120, trend_ema=300, atr_period=42)),
    ]
    for nome, p in configurazioni:
        for fee, fname in ((FEE_SPOT, "spot 0.35%"), (FEE_SWAP, "swap 0.05%")):
            for short, sname in ((False, "long-only"), (True, "long/short")):
                riga(serie, "%s | %s | %s" % (nome.split("(")[0].strip(), fname, sname),
                     p, fee, short, BARRE_GIORNO)
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

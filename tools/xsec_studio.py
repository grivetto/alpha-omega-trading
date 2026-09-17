#!/usr/bin/env python3
"""Momentum CROSS-SEZIONALE: mai misurato su questi dati (round 32, 2026-09-17).

Il motore esiste da tempo in denaro/research/eval.py:backtest_xsec ma nessun tool
e nessun doc l'aveva mai usato. E' una scommessa DIVERSA dal trend: non "questo
sale?", ma "quale sale piu' degli altri?" — ribilanciamento raro, turnover basso,
costi proporzionali al turnover invece che al numero di giri.

Perche' vale la pena misurarlo ora: il trend ha un edge EPISODICO, quindi lascia
il capitale fermo per mesi (esposizione bassa). Una strategia relativa, sempre
investita nel paniere migliore, userebbe proprio quel capitale.

Metodo (nessun tuning): parametri di default del motore, piu' una griglia di
robustezza per capire se la REGIONE e' positiva, non il singolo punto. Due
universi: la flotta (17) e tutti i 52 asset con dati. Fee taker reale 0.35%
per lato (e maker 0.20% come controprova). Benchmark: buy&hold equal-weight.

Uso: python3 tools/xsec_studio.py
"""
from __future__ import annotations

import itertools
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE_TAKER = 0.0035
FEE_MAKER = 0.0020
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))
DEFAULT = dict(lookback=180, k=5, rebalance=42, cash_filter_ma=0)


def carica():
    serie = {}
    for p in sorted(DATI.glob("dl_*_1D.csv")):
        base = p.name[3:-7]
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > 400:
            serie[base] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def metriche(eq):
    if len(eq) < 3:
        return 0.0, 0.0, 0.0
    rend = eq[-1] / eq[0] - 1.0
    picco, mdd = -1e18, 0.0
    for e in eq:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [eq[i] / eq[i - 1] - 1.0 for i in range(1, len(eq)) if eq[i - 1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    return rend, mdd, sharpe


def xsec(dati, simboli, par, fee):
    sotto = {s: dati[s] for s in simboli}
    r = E.backtest_xsec(sotto, par, 1.0, fee)
    if r.errore or not r.equity:
        return None
    rend, mdd, sharpe = metriche(r.equity)
    return dict(rend=rend, mdd=mdd, sharpe=sharpe,
                rib=len(r.trade_pnls), barre=len(r.equity),
                esp=(r.esposizione_bar / max(1, len(r.equity))))


def bnh(dati, simboli, w):
    """Buy&hold equal-weight del paniere, stesso orizzonte."""
    rend = []
    for s in simboli:
        c = dati[s] if w == 0 else dati[s][-w:]
        if len(c) > 2 and c[0]["c"] > 0:
            rend.append(c[-1]["c"] / c[0]["c"] - 1.0)
    return st.mean(rend) if rend else 0.0


def main():
    dati, n = carica()
    universo52 = sorted(dati)
    print("dati: %d asset, %d barre comuni" % (len(dati), n))
    print("default motore: %s" % DEFAULT)
    print()
    for etichetta, simboli in (("flotta (17)", [s for s in FLOTTA if s in dati]),
                               ("52 asset", universo52)):
        for nome_fee, fee in (("taker 0.35%", FEE_TAKER), ("maker 0.20%", FEE_MAKER)):
            print("%s | fee %s" % (etichetta, nome_fee))
            print("  %-7s %10s %8s %8s %6s %8s %10s %10s" %
                  ("finestra", "rend.", "maxDD", "Sharpe", "rib.", "esposto",
                   "trades", "buy&hold"))
            for nome_fin, w in FINESTRE:
                sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()
                         if s in simboli}
                m = xsec(sotto, simboli, DEFAULT, fee)
                if m is None:
                    print("  %-7s errore" % nome_fin)
                    continue
                print("  %-7s %9.2f%% %7.2f%% %8.2f %6d %7.0f%% %10d %9.2f%%" %
                      (nome_fin, m["rend"] * 100, m["mdd"] * 100, m["sharpe"],
                       m["rib"], m["esp"] * 100,
                       sum(len(dati[s]) for s in simboli) // max(1, len(simboli)),
                       bnh(dati, simboli, w) * 100))
            print()
    print("GRIGLIA DI ROBUSTEZZA (fee taker): quanti set su 18 sono positivi")
    griglia = [dict(lookback=lb, k=k, rebalance=rb, cash_filter_ma=cf)
               for lb, k, rb, cf in itertools.product((90, 180, 270), (3, 5, 8),
                                                      (21, 42, 63), (0,))
               ][:27]
    print("  %-12s %-7s %10s %10s %8s" %
          ("universo", "finestra", "mediana", "peggiore", "positivi"))
    for etichetta, simboli in (("flotta (17)", [s for s in FLOTTA if s in dati]),
                               ("52 asset", universo52)):
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()
                     if s in simboli}
            res = []
            for par in griglia:
                m = xsec(sotto, simboli, par, FEE_TAKER)
                if m:
                    res.append(m["rend"])
            if not res:
                continue
            print("  %-12s %-7s %9.2f%% %9.2f%% %6d/%d" %
                  (etichetta, nome_fin, st.median(res) * 100,
                   min(res) * 100, sum(1 for x in res if x > 0), len(res)))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

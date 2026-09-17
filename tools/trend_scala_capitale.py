#!/usr/bin/env python3
"""Fin dove regge l'edge se il capitale cresce? (round 33, 2026-09-17)

Il vincolo del progetto e' il capitale, non la strategia (docs/30-33). Prima di
dire "aggiungi capitale" serve sapere DOVE l'edge si rompe:

  - in basso: i minimi d'ordine dell'exchange (gia' verificati: a 42 EUR per
    conto ogni bot puo' piazzare);
  - in alto: lo SLIPPAGE. Il simulatore lo modella (k*sqrt(notional/volume)):
    piu' capitale significa posizioni piu' grandi e impatto sul book.

Il capitale dei 3 conti viene scalato in proporzione (42.12 / 24.83 / 42.04),
stessa flotta, stesso rischio 2%, fee taker reale. Rendimento percentuale,
drawdown, Sharpe e rendimento in EURO per livello.

Uso: python3 tools/trend_scala_capitale.py
"""
from __future__ import annotations

import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro.research import eval as E  # noqa: E402
import trend_capacita as cap  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
PAR = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
           trend_ema=100, entry_slip=0.0005, max_exposure=1.0)
BASE_CONT = {"mc2": 42.12, "nuvola": 24.83, "MARCODG1": 42.04}
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("180b", 180))
# totale investito per livello (il capitale dei conti viene scalato in proporzione)
LIVELLI = (109, 250, 500, 1_000, 2_500, 5_000, 10_000, 25_000, 100_000)


def carica():
    serie = {}
    for s in FLOTTA:
        p = DATI / ("dl_%s_1D.csv" % s)
        if p.is_file():
            c = E.load_csv(p)
            if len(c) > 400:
                serie[s] = c
    n = min(len(c) for c in serie.values())
    return {s: c[-n:] for s, c in serie.items()}, n


def conti_per(asset, fattore):
    nomi = list(BASE_CONT)
    conti = {k: [] for k in nomi}
    for i, s in enumerate(asset):
        conti[nomi[i % len(nomi)]].append(s)
    return {k: v for k, v in conti.items()}, {k: v * fattore for k, v in BASE_CONT.items()}


def prova(dati, simboli, capitali):
    conti, _ = conti_per(simboli, 1.0)
    curve, tr = [], 0
    for nome, lista in conti.items():
        if not lista:
            continue
        r = cap.simula([(s, dati[s]) for s in lista], capitali[nome], 0.02,
                       cap.FEE, cap.SLIP, **PAR)
        curve.append([e / capitali[nome] for e in r["curva"]])
        tr += r["trade"]
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i] / port[i - 1] - 1.0 for i in range(1, n) if port[i - 1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe, tr


def main():
    dati, n = carica()
    simboli = [s for s in FLOTTA if s in dati]
    base_tot = sum(BASE_CONT.values())
    print("flotta %d asset, %d barre comuni, rischio 2%%, fee taker %.2f%%"
          % (len(simboli), n, cap.FEE * 100))
    print("  %-10s %-9s %10s %9s %8s %8s %11s" %
          ("capitale", "finestra", "rend.", "maxDD", "Sharpe", "trades", "in EUR"))
    print("  " + "-" * 72)
    for livello in LIVELLI:
        fattore = livello / base_tot
        _, capitali = conti_per(simboli, fattore)
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()}
            rend, mdd, sharpe, tr = prova(sotto, simboli, capitali)
            print("  %-10s %-9s %9.2f%% %8.2f%% %8.2f %8d %10.2f EUR" %
                  ("%d EUR" % livello, nome_fin, rend * 100, mdd * 100, sharpe,
                   tr, rend * livello))
        print()
    print("PARTECIPAZIONE AL VOLUME (nozionale tipico su volume medio giornaliero)")
    for livello in (1_000, 10_000, 100_000):
        fattore = livello / base_tot
        _, capitali = conti_per(simboli, fattore)
        print("  capitale totale %d EUR (per conto ~%d EUR)"
              % (livello, capitali["mc2"]))
        partecipazione(dati, capitali)
        print()
    return 0


def partecipazione(dati, capitali, rischio=0.02, stop_mult=2.0):
    """Quanto pesa una posizione sul volume giornaliero dell'asset?

    E' il vincolo di capacita' VERO, oltre allo slippage parametrico del
    simulatore: sopra l'1%% del volume giornaliero il book di un exchange retail
    comincia a muoversi davvero.
    """
    cap_medio = sum(capitali.values()) / max(1, len(capitali))
    righe = []
    for s, c in dati.items():
        closes = [x["c"] for x in c]
        atr = E.atr_wilder([x["h"] for x in c], [x["l"] for x in c], closes, 14)
        atr_pct = (atr[-1] / closes[-1]) if closes[-1] > 0 else 0.0
        vol = E._media_volumi(c, len(c) - 1)
        noz = cap_medio * rischio / (stop_mult * atr_pct) if atr_pct > 0 else 0.0
        part = (noz / vol) if vol > 0 else 0.0
        righe.append((part, s, noz, vol, atr_pct))
    righe.sort(reverse=True)
    print("  %-8s %12s %14s %12s %10s" %
          ("asset", "nozionale", "volume/gg EUR", "ATR%%", "partecip."))
    for part, s, noz, vol, atr_pct in righe[:8]:
        print("  %-8s %11.0f EUR %13.0f EUR %11.2f%% %9.3f%%" %
              (s, noz, vol, atr_pct * 100, part * 100))
    return righe


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""L'edge del trend esiste ANCORA, o era un episodio?

Contesto: sul totale 2024-05 -> 2026-09 la strategia rende ~+20%, ma tutto in un
solo blocco (il rally di fine 2024). Sulle finestre recenti e' piatta.

Domanda secca: su un GRIGLIA AMPIA di parametri, quanti sono POSITIVI nel
periodo recente? Se quasi nessuno, l'edge non sta pagando adesso e va detto.

Uso: python3 tools/trend_recente.py [barre]
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
RISK = 0.02

GRIGLIA = [
    dict(canale=ca, atr_period=14, trail_mult=tr, stop_atr_mult=stp,
         trend_ema=em, max_exposure=1.0, entry_slip=0.0005, fee_buffer=0.01,
         max_barre=400, risk_pct=RISK)
    for ca in (20, 40, 60)
    for tr in (2.0, 3.0, 4.0)
    for stp in (1.5, 2.0, 3.0)
    for em in (0, 100, 200)
]


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


def valuta(serie, p):
    vals, trades = [], 0
    for s, c in serie.items():
        r = E.backtest_trend(c, p, 1.0, FEE)
        if r.errore or not r.equity:
            continue
        vals.append(r.ritorno)
        trades += r.trade
    if not vals:
        return None
    return st.mean(vals), st.median(vals), trades


def report(serie, barre, etichetta):
    sott = {s: c[-barre:] for s, c in serie.items()}
    out = []
    for p in GRIGLIA:
        v = valuta(sott, p)
        if v:
            out.append((v[0], v[1], v[2], p))
    if not out:
        print("  nessun risultato")
        return
    rend = [o[0] for o in out]
    pos = sum(1 for x in rend if x > 0)
    print("  %-22s %d set | mediano %+7.2f%% | medio %+7.2f%% | positivi %d/%d (%.0f%%) | best %+.2f%% peggiore %+.2f%%"
          % (etichetta, len(out), st.median(rend) * 100, st.mean(rend) * 100,
             pos, len(out), 100.0 * pos / len(out), max(rend) * 100, min(rend) * 100))
    out.sort(key=lambda x: x[0], reverse=True)
    b = out[0]
    print("     miglior set: canale=%d trail=%.1f stop=%.1f ema=%d"
          % (b[3]["canale"], b[3]["trail_mult"], b[3]["stop_atr_mult"], b[3]["trend_ema"]))


def main():
    barre = int(sys.argv[1]) if len(sys.argv) > 1 else 365
    serie, n = carica()
    print("universo %d simboli, %d barre comuni, fee taker %.2f%%/lato, rischio %.0f%%"
          % (len(serie), n, FEE * 100, RISK * 100))
    print("griglia: %d set di parametri" % len(GRIGLIA))
    print()
    report(serie, n, "TUTTA la storia (%d)" % n)
    report(serie, 550, "ultimi ~18 mesi")
    report(serie, 365, "ultimi ~12 mesi")
    report(serie, 250, "ultimi ~8 mesi")
    report(serie, 180, "ultimi ~6 mesi")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

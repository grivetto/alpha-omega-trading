#!/usr/bin/env python3
"""La PIRAMIDE migliora il trend? (round 33, 2026-09-17)

Variante mai provata in questa sessione: aggiungere una SECONDA unita' quando la
posizione e' gia' in profitto (prezzo >= entry + p*ATR). E' la costruzione
classica del trend following: si lascia correre il vincitore invece di
accontentarsi del primo breakout. Ha anche un effetto pratico sul conto: usa la
cassa libera nei trend forti, che oggi resta ferma.

Contro: il rischio a posizione raddoppia e la size della seconda unita' e'
calcolata sullo STESSO stop, quindi il rischio totale cresce. Va misurato.

Prima la VALIDAZIONE: con piramide_atr=0 il simulatore modificato deve
riprodurre backtest_trend al bit (altrimenti i numeri non valgono).

Uso: python3 tools/trend_piramide.py
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
import trend_sim_piramide as pir  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
PAR = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
           trend_ema=100, entry_slip=0.0005, max_exposure=1.0)
CAPITALI = {"mc2": 42.12, "nuvola": 24.83, "MARCODG1": 42.04}
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))
VARIANTI = (("base (1 unita')", 0.0, 1), ("piramide 0.5 ATR", 0.5, 2),
            ("piramide 1.0 ATR", 1.0, 2), ("piramide 1.5 ATR", 1.5, 2),
            ("piramide 1.0 ATR x3", 1.0, 3))


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


def conti_per(asset):
    nomi = list(CAPITALI)
    conti = {k: [] for k in nomi}
    for i, s in enumerate(asset):
        conti[nomi[i % len(nomi)]].append(s)
    return conti


def prova(dati, simboli, atr_pir, maxu):
    conti = conti_per(simboli)
    curve, tr, unita = [], 0, 0
    for nome, lista in conti.items():
        if not lista:
            continue
        r = pir.simula_piramide([(s, dati[s]) for s in lista], CAPITALI[nome],
                                0.02, cap.FEE, cap.SLIP, piramide_atr=atr_pir,
                                piramide_max=maxu, **PAR)
        curve.append([e / CAPITALI[nome] for e in r["curva"]])
        tr += r["trade"]
        unita += sum(p.get("unita", 0) for p in r["prep"])
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
    return port[-1] - 1.0, mdd, sharpe, tr, unita


def valida(dati):
    print("VALIDAZIONE: piramide spenta vs backtest_trend (capitale 1.0)")
    ok = True
    for s in sorted(dati):
        r = pir.simula_piramide([(s, dati[s])], 1.0, 0.02, tetto_capitale=False,
                                piramide_atr=0.0, piramide_max=1, **PAR)
        sim = r["curva"][-1] / 1.0 - 1.0
        bt = E.backtest_trend(dati[s], dict(PAR, risk_pct=0.02, fee_buffer=0.01),
                              1.0, cap.FEE, cap.SLIP)
        d = sim - bt.ritorno
        if abs(d) > 1e-9:
            ok = False
            print("   %-6s DIVERGE %+.6f" % (s, d))
    print("   --> %s" % ("COINCIDONO al bit" if ok else "NON COINCIDONO"))
    return ok


def main():
    dati, n = carica()
    print("flotta %d asset, %d barre comuni, capitale condiviso per conto"
          % (len(dati), n))
    if not valida(dati):
        return 1
    print()
    simulazione = [s for s in FLOTTA if s in dati]
    print("  %-18s %-7s %10s %8s %8s %7s %8s" %
          ("variante", "finestra", "rend.", "maxDD", "Sharpe", "trades", "unita'"))
    print("  " + "-" * 74)
    for etichetta, atr_pir, maxu in VARIANTI:
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()}
            rend, mdd, sharpe, tr, unita = prova(sotto, simulazione, atr_pir, maxu)
            print("  %-18s %-7s %9.2f%% %7.2f%% %8.2f %7d %8d" %
                  (etichetta, nome_fin, rend * 100, mdd * 100, sharpe, tr, unita))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

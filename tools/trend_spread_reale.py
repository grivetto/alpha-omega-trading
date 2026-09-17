#!/usr/bin/env python3
"""Lo SPREAD reale mangia l'edge? (round 34, 2026-09-17)

Il backtest paga solo la fee (0.35%/lato) piu' uno slippage parametrico. Ma su
un book reale si compra all'ASK e si vende al BID: ogni giro paga anche lo
SPREAD, che il backtest non vede. Su OKX EEA lo spread mediano della flotta e'
~0.10%, ma MINA sta a 0.50%: su un giro completo sono 0.50 punti di rendimento
in piu' di costo.

Misura: spread bid/ask reale (mediana di 3 letture) e simulatore a capitale
condiviso GENERATO da quello validato, con fee + meta' spread per lato. Con
spread vuoto deve riprodurre backtest_trend al bit (validazione).

Uso: python3 tools/trend_spread_reale.py
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
import trend_sim_spread as sp  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
PAR = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
           trend_ema=100, entry_slip=0.0005, max_exposure=1.0)
CAPITALI = {"mc2": 42.12, "nuvola": 24.83, "MARCODG1": 42.04}
FLOTTA = ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV",
          "LINK", "AVAX", "DOT", "UNI", "SUI", "MINA",
          "ADA", "ARB", "XLM", "ALGO"]
FINESTRE = (("storia", 0), ("540b", 540), ("365b", 365), ("270b", 270),
            ("180b", 180))
SOGLIA_LIQUIDO = 0.0011      # 0.11%: sopra, lo spread pesa piu' della meta'


def misura_spread(simboli, letture=3):
    import ccxt
    ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com",
                   "options": {"defaultType": "spot"}})
    ex.load_markets()
    fuori = {}
    for s in simboli:
        sym = s + "/EUR"
        if sym not in ex.markets:
            continue
        inst = ex.markets[sym]["id"]
        campioni = []
        for _ in range(letture):
            t = ex.publicGetMarketTicker({"instId": inst})["data"][0]
            bid, ask = float(t["bidPx"]), float(t["askPx"])
            if bid > 0 and ask > 0:
                campioni.append((ask - bid) / ((ask + bid) / 2.0))
        if campioni:
            fuori[s] = st.median(campioni)
    return fuori


def carica(simboli):
    serie = {}
    for s in simboli:
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


def prova(dati, simboli, spread, usa_spread):
    conti = conti_per(simboli)
    curve, tr = [], 0
    for nome, lista in conti.items():
        if not lista:
            continue
        r = sp.simula_spread([(s, dati[s]) for s in lista], CAPITALI[nome],
                             0.02, cap.FEE, cap.SLIP,
                             spread=(spread if usa_spread else {}), **PAR)
        curve.append([e / CAPITALI[nome] for e in r["curva"]])
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
    spread = misura_spread(FLOTTA)
    print("SPREAD REALE OKX EEA (mediana di 3 letture, %s)" % "bid/ask")
    for s, v in sorted(spread.items(), key=lambda kv: -kv[1]):
        print("  %-6s %6.3f%%" % (s, v * 100))
    if spread:
        print("  mediana %.3f%% | media %.3f%%"
              % (st.median(spread.values()) * 100, st.mean(spread.values()) * 100))
    dati, n = carica(FLOTTA)
    print()
    print("VALIDAZIONE (spread vuoto vs backtest_trend):")
    ok = True
    for s in ("BTC", "MINA"):
        r = sp.simula_spread([(s, dati[s])], 1.0, 0.02, tetto_capitale=False,
                             spread={}, **PAR)
        bt = E.backtest_trend(dati[s], dict(PAR, risk_pct=0.02, fee_buffer=0.01),
                              1.0, cap.FEE, cap.SLIP)
        d = (r["curva"][-1] - 1.0) - bt.ritorno
        ok = ok and abs(d) < 1e-9
    print("   %s" % ("COINCIDONO al bit" if ok else "DIVERGONO"))
    if not ok:
        return 1
    liquidi = [s for s in FLOTTA if spread.get(s, 0.0) <= SOGLIA_LIQUIDO]
    illiquidi = [s for s in FLOTTA if s not in liquidi]
    print()
    print("PORTAFOGLIO (capitale condiviso, rischio 2%%)")
    print("  %-28s %-7s %10s %8s %8s %7s" %
          ("configurazione", "finestra", "rend.", "maxDD", "Sharpe", "trades"))
    for etichetta, lista, usa in (
            ("flotta 17, solo fee", FLOTTA, False),
            ("flotta 17, fee + spread", FLOTTA, True),
            ("solo liquidi (%d), fee+spread" % len(liquidi), liquidi, True),
            ("solo illiquidi (%d), fee+spread" % len(illiquidi), illiquidi, True)):
        for nome_fin, w in FINESTRE:
            sotto = {s: (c if w == 0 else c[-w:]) for s, c in dati.items()}
            rend, mdd, sharpe, tr = prova(sotto, lista, spread, usa)
            print("  %-28s %-7s %9.2f%% %7.2f%% %8.2f %7d" %
                  (etichetta, nome_fin, rend * 100, mdd * 100, sharpe, tr))
        print()
    print("PER ASSET: rendimento con spread reale (capitale pieno)")
    print("  %-6s %8s %10s %10s %8s" %
          ("asset", "spread", "storia", "365b", "delta storia"))
    for s in sorted(dati, key=lambda x: -spread.get(x, 0.0)):
        c = dati[s]
        base = E.backtest_trend(c, dict(PAR, risk_pct=0.02, fee_buffer=0.01), 1.0, cap.FEE)
        eff = E.backtest_trend(c, dict(PAR, risk_pct=0.02, fee_buffer=0.01), 1.0,
                               cap.FEE + spread.get(s, 0.0) / 2.0)
        r365 = E.backtest_trend(c[-365:], dict(PAR, risk_pct=0.02, fee_buffer=0.01),
                                1.0, cap.FEE + spread.get(s, 0.0) / 2.0)
        print("  %-6s %7.3f%% %9.2f%% %9.2f%% %+9.2f%%" %
              (s, spread.get(s, 0.0) * 100, eff.ritorno * 100, r365.ritorno * 100,
               (eff.ritorno - base.ritorno) * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
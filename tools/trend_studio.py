#!/usr/bin/env python3
"""Quanto rende DAVVERO il trend, e quanto capitale usa.

Perche' esiste: il rig di ricerca era tarato a fee 0.20% per lato (maker). Ma
l'ingresso e' un limite SOPRA il mercato e l'uscita e' a mercato: entrambi
crossano lo spread, quindi sono TAKER a 0.35%. Il round trip reale e' 0.70%, non
0.40%. Qui si misura se l'edge sopravvive al costo vero.

Seconda domanda, altrettanto importante: il trend dimensiona sul RISCHIO, quindi
impegna poco capitale. Il rendimento che conta e' quello sul capitale TOTALE, non
sul nozionale impiegato. Si misura anche l'utilizzo e si esplora il rischio per
trade come leva (e il suo costo in drawdown).

Uso: python3 tools/trend_studio.py [--walk-forward]
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

# Parametri FISSI misurati robusti (36/36 set con alpha positivo).
PARAMS = dict(canale=40, atr_period=14, trail_mult=3.0, stop_atr_mult=2.0,
              trend_ema=100, max_exposure=1.0, entry_slip=0.0005,
              fee_buffer=0.01, max_barre=400)

RISCHI = [0.01, 0.02, 0.04, 0.06, 0.08, 0.12]
FEE_MAKER = 0.002    # se si riuscisse a entrare e uscire da maker
FEE_TAKER = 0.0035   # costo REALE: ingresso e uscita crossano lo spread


def carica():
    serie = {}
    for s in UNIVERSO:
        p = DATI / ("dl_%s_1D.csv" % s)
        if not p.is_file():
            continue
        try:
            c = E.load_csv(p)
        except Exception:
            continue
        if len(c) > 200:
            serie[s] = c
    n = min(len(c) for c in serie.values())
    # coda comune: stesse date, cosi' gli indici coincidono
    return {s: c[-n:] for s, c in serie.items()}, n


def curva(serie, risk, fee):
    """Curva di equity del portafoglio equal-weight + statistiche per simbolo."""
    per_simbolo, esp, trade, rets = [], [], 0, []
    for s, c in serie.items():
        try:
            r = E.backtest_trend(c, dict(PARAMS, risk_pct=risk), 1.0, fee)
        except Exception:
            continue
        if r.errore or not r.equity:
            continue
        giorni = {}
        for t, e in zip(r.ts, r.equity):
            giorni[t // E.GIORNO_MS] = e
        per_simbolo.append(giorni)
        esp.append(r.esposizione_pct)
        rets.append(r.ritorno)
        trade += r.trade
    if not per_simbolo:
        return None
    comuni = sorted(set.intersection(*(set(g) for g in per_simbolo)))
    n = len(per_simbolo)
    port = [sum(g[d] for g in per_simbolo) / n for d in comuni]
    return {"port": port, "esp": st.mean(esp), "trade": trade,
            "rets": rets, "giorni": len(comuni)}


def metriche(cur, capitale=1.0):
    port = cur["port"]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i] / port[i - 1] - 1.0 for i in range(1, len(port)) if port[i - 1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365.0)) if sd > 0 else 0.0
    rend = port[-1] / capitale - 1.0
    anni = len(port) / 365.0
    cagr = ((port[-1] / capitale) ** (1.0 / anni) - 1.0) if anni > 0 and port[-1] > 0 else -1.0
    return {"rend": rend, "cagr": cagr, "mdd": mdd, "sharpe": sharpe,
            "anni": anni}


def tabella(serie, fee, titolo):
    print()
    print("=" * 88)
    print("%s   (fee %.2f%% per lato, round trip %.2f%%)"
          % (titolo, fee * 100, 2 * fee * 100))
    print("=" * 88)
    print("  %-7s %9s %9s %8s %8s %8s %7s %6s" %
          ("rischio", "rend.tot", "CAGR", "maxDD", "Sharpe", "espos%", "trades", "anni"))
    for risk in RISCHI:
        cur = curva(serie, risk, fee)
        if not cur:
            continue
        m = metriche(cur)
        print("  %-7s %8.2f%% %8.2f%% %7.2f%% %8.2f %7.1f%% %7d %6.1f"
              % ("%.0f%%" % (risk * 100), m["rend"] * 100, m["cagr"] * 100,
                 m["mdd"] * 100, m["sharpe"], cur["esp"], cur["trade"], m["anni"]))


def buy_hold(serie):
    vals = []
    for s, c in serie.items():
        if c[0]["c"] > 0:
            vals.append(c[-1]["c"] / c[0]["c"] - 1.0)
    return st.mean(vals) if vals else 0.0


def main():
    serie, n = carica()
    print("universo: %d simboli, %d barre giornaliere comuni" % (len(serie), n))
    bh = buy_hold(serie)
    anni = n / 365.0
    print("periodo: %.1f anni" % anni)
    print("buy & hold equal-weight sul periodo: %.2f%% (CAGR %.2f%%)"
          % (bh * 100, ((1 + bh) ** (1 / anni) - 1) * 100))
    print("simboli:", ", ".join(sorted(serie)))

    tabella(serie, FEE_MAKER, "A) fee MAKER 0.20%/lato (ipotesi del rig originale)")
    tabella(serie, FEE_TAKER, "B) fee TAKER 0.35%/lato (costo REALE di ingresso+uscita)")

    if "--walk-forward" in sys.argv:
        print()
        print("=" * 88)
        print("C) WALK-FORWARD OUT-OF-SAMPLE (fee taker, parametri fissi)")
        print("=" * 88)
        griglia = [dict(PARAMS, risk_pct=0.02)]
        for fee in (FEE_MAKER, FEE_TAKER):
            folds, _, err = E.walk_forward_portafoglio(
                serie, "trend", griglia, capitale=1.0, fee=fee,
                barre_train=400, barre_test=200)
            if err or not folds:
                print("  fee %.4f: %s" % (fee, err or "nessun fold"))
                continue
            comp = 1.0
            for f in folds:
                comp *= (1.0 + f.ritorno_test)
            pos = sum(1 for f in folds if f.ritorno_test > 0)
            print("  fee %.4f: %d fold, OOS composto %.2f%%, fold positivi %d/%d (%.0f%%)"
                  % (fee, len(folds), (comp - 1) * 100, pos, len(folds),
                     100.0 * pos / len(folds)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Quanto costa davvero una GAP attraverso lo stop, e il tetto la riduce?

Il backtest assume di essere servito AL PREZZO di stop. Nella realta' una gap
notturna salta lo stop e si esce molto peggio. Con il sizing sul rischio, gli
asset a bassa volatilita' hanno stop strettissimi e posizioni enormi: TRX, ATR
1.45%, posizione 29 EUR su un conto da 42. Una gap del 10% su quella posizione
vale il 6.9% del conto invece del 2% previsto.

Si simula con una gap AVVERSA sulle uscite a stop e si guarda se il tetto per
posizione (max_exposure) aiuta. Con gap=0 il simulatore deve coincidere con
quello gia' validato.

Uso: python3 tools/trend_gap_stress.py
"""
from __future__ import annotations
import importlib.util
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
sp = importlib.util.spec_from_file_location("cap", str(BASE_T / "trend_capacita.py"))
cap = importlib.util.module_from_spec(sp)
sp.loader.exec_module(cap)

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
RISK = 0.02
CONTI = [("mc2", 42.12), ("nuvola", 24.83), ("MARCODG1", 42.04)]
FLOTTA = {"mc2": ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"],
          "nuvola": ["LINK", "AVAX", "DOT", "UNI", "SUI", "MINA"],
          "MARCODG1": ["ADA", "ARB", "XLM", "ALGO"]}
BASE = dict(canale=40, atr_period=14, trail_mult=2.5, stop_atr_mult=2.0,
            trend_ema=100, entry_slip=0.0005, fee_buffer=0.01, max_barre=400)


def simula_gap(assets, capitale, max_exp, gap):
    """Come cap.simula ma l'uscita a stop subisce una gap avversa."""
    prep = []
    for nome, c in assets:
        closes = [x["c"] for x in c]
        prep.append({"c": c, "atr": E.atr_wilder([x["h"] for x in c],
                                                 [x["l"] for x in c], closes, 14),
                     "ema": E.ema(closes, 100), "qty": 0.0, "basis": 0.0,
                     "stop": 0.0, "pending": False})
    n = min(len(p["c"]) for p in prep)
    inizio = 141
    cash = capitale
    curva, rifiutati = [], 0
    for i in range(inizio, n):
        for x in prep:
            if not (x["pending"] and x["qty"] <= 1e-12):
                continue
            x["pending"] = False
            a = x["atr"][i - 1]
            c = x["c"]
            if a <= 0 or c[i]["o"] <= 0:
                continue
            budget = max(0.0, min(capitale, cash))
            entry = c[i]["o"] * 1.0005
            dist = 2.0 * a
            q = min(budget * RISK / dist, budget * max_exp / entry)
            vm = E._media_volumi(c, i)
            notional = q * entry
            sl = E.slippage(notional, vm, cap.SLIP)
            costo = notional * (1.0 + FEE + sl)
            if costo > cash and costo > 0:
                q *= cash / costo
                notional = q * entry
                sl = E.slippage(notional, vm, cap.SLIP)
                costo = notional * (1.0 + FEE + sl)
            if q > 1e-12 and costo <= cash * (1.0 + 1e-9):
                cash -= costo
                x["qty"] = q
                x["basis"] = costo / q
                x["stop"] = entry - dist
            else:
                rifiutati += 1
        for x in prep:
            if x["qty"] <= 1e-12:
                continue
            c = x["c"]
            if c[i]["l"] <= x["stop"]:
                # GAP: si esce PIU' IN BASSO del prezzo di stop
                uscita = x["stop"] * (1.0 - gap)
                vm = E._media_volumi(c, i)
                sl = E.slippage(x["qty"] * uscita, vm, cap.SLIP)
                cash += x["qty"] * uscita * (1.0 - FEE - sl)
                x["qty"], x["stop"] = 0.0, 0.0
            else:
                a = x["atr"][i]
                if a > 0:
                    ns = c[i]["c"] - 2.5 * a
                    if ns > x["stop"]:
                        x["stop"] = ns
        for x in prep:
            c = x["c"]
            price = c[i]["c"]
            if x["qty"] <= 1e-12 and not x["pending"] and i >= 40:
                massimo = max(y["h"] for y in c[i - 40:i])
                if price > massimo and price > x["ema"][i] and x["atr"][i] > 0:
                    x["pending"] = True
        curva.append(cash + sum(x["qty"] * x["c"][i]["c"] for x in prep))
    return curva, rifiutati


def misura(max_exp, gap, barre=None):
    curve = []
    for nome, capitale in CONTI:
        aa = []
        for a in FLOTTA[nome]:
            c = E.load_csv(DATI / ("dl_%s_1D.csv" % a))
            aa.append((a, c))
        n = min(len(c) for _, c in aa)
        aa = [(a, c[-n:]) for a, c in aa]
        if barre:
            aa = [(a, c[-barre:]) for a, c in aa]
        cv, _ = simula_gap(aa, capitale, max_exp, gap)
        curve.append([e / capitale for e in cv])
    n = min(len(c) for c in curve)
    port = [sum(c[i] for c in curve) / len(curve) for i in range(n)]
    picco, mdd = -1e18, 0.0
    for e in port:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [port[i]/port[i-1] - 1.0 for i in range(1, n) if port[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr)/sd*math.sqrt(365)) if sd > 0 else 0.0
    return port[-1] - 1.0, mdd, sharpe


def main():
    aa = [(x, E.load_csv(DATI / ("dl_%s_1D.csv" % x))) for x in FLOTTA["mc2"]]
    n = min(len(c) for _, c in aa)
    aa = [(x, c[-n:]) for x, c in aa]
    print("VALIDAZIONE con gap=0 contro il simulatore gia' validato (conto mc2):")
    for me in (1.0, 0.5):
        cv_g, _ = simula_gap(aa, 42.12, me, 0.0)
        r = cap.simula(aa, 42.12, RISK, FEE, cap.SLIP,
                       **dict(BASE, max_exposure=me))
        a1 = cv_g[-1] / 42.12 - 1.0
        a2 = r["curva"][-1] / 42.12 - 1.0
        print("   tetto %3.0f%%: gap-sim %+9.4f%%   cap.simula %+9.4f%%   delta %.2e"
              % (me * 100, a1 * 100, a2 * 100, a1 - a2))
    print()
    print("  %-8s %10s %8s %8s   %10s %8s   %10s %8s" %
          ("tetto", "rend g0", "DD g0", "rend g2", "DD g2", "rend g5", "DD g5", ""))
    for me in (1.0, 0.6, 0.5, 0.4, 0.3):
        r0, d0, _ = misura(me, 0.0)
        r2, d2, _ = misura(me, 0.02)
        r5, d5, _ = misura(me, 0.05)
        print("  %-8s %+9.2f%% %7.2f%% %+9.2f%% %7.2f%% %+9.2f%% %7.2f%%"
              % ("%.0f%%" % (me * 100), r0 * 100, d0 * 100, r2 * 100, d2 * 100,
                 r5 * 100, d5 * 100))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

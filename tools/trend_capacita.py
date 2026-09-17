#!/usr/bin/env python3
"""Il capitale basta? Simulatore a CAPITALE CONDIVISO per conto.

Perche' serve: il rig di ricerca da' a ogni simbolo il proprio capitale pieno
(backtest_trend con capitale=1.0). In produzione i 5 asset di un conto
CONDIVIDONO 24.8 EUR: quando 3 posizioni sono aperte il conto e' quasi pieno e
la quarta viene dimensionata sul poco cash rimasto. Quel vincolo non e' mai
stato misurato — e determina quale rischio per trade si puo' permettere.

VALIDAZIONE: con capitale illimitato il simulatore DEVE riprodurre esattamente
backtest_trend simbolo per simbolo. Se non lo fa, non e' credibile.

Uso: python3 tools/trend_capacita.py
"""
from __future__ import annotations
import math
import statistics as st
import sys
from pathlib import Path

sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E  # noqa: E402

DATI = Path("/home/sergio/alpha-omega-trading/backtest_data")
FEE = 0.0035
SLIP = 0.02

# Ripartizione REALE dei conti (dai config in produzione)
CONTI = {
    "mc2":      ["BTC", "ETH", "SOL", "XRP", "DOGE"],
    "nuvola":   ["LINK", "AVAX", "DOT", "LTC", "UNI"],
    "MARCODG1": ["ADA", "ATOM", "AAVE", "ARB", "XLM"],
}
CAPITALE = 24.83

BASE = dict(canale=40, atr_period=14, trail_mult=3.0, stop_atr_mult=2.0,
            trend_ema=100, entry_slip=0.0005, max_exposure=1.0)


def carica(simboli):
    out = []
    for s in simboli:
        p = DATI / ("dl_%s_1D.csv" % s)
        if not p.is_file():
            raise SystemExit("dati mancanti: %s" % p)
        out.append((s, E.load_csv(p)))
    n = min(len(c) for _, c in out)
    return [(s, c[-n:]) for s, c in out], n


def simula(assets, capitale, risk, fee=FEE, slip_k=SLIP, tetto_capitale=True, **kw):
    """Un conto con capitale CONDIVISO fra gli asset.

    tetto_capitale=True  -> budget = min(capitale, cash): e' cio' che fa la
        PRODUZIONE (Policy._available = min(capital_config, free_balance)). Dopo
        un trade in profitto il cash supera il capitale configurato, ma la size
        resta ancorata al capitale configurato.
    tetto_capitale=False -> budget = cash: e' cio' che fa backtest_trend, che
        quindi COMPONE la size. Serve solo per validare il simulatore contro il
        motore esistente.
    """
    canale = int(kw.get("canale", 40))
    atr_n = int(kw.get("atr_period", 14))
    trail = float(kw.get("trail_mult", 3.0))
    stop_mult = float(kw.get("stop_atr_mult", 2.0))
    ema_n = int(kw.get("trend_ema", 100))
    esp_max = float(kw.get("max_exposure", 1.0))
    slip_entry = float(kw.get("entry_slip", 0.0005))

    prep = []
    for nome, c in assets:
        closes = [x["c"] for x in c]
        prep.append({
            "nome": nome, "c": c,
            "atr": E.atr_wilder([x["h"] for x in c], [x["l"] for x in c], closes, atr_n),
            "ema": E.ema(closes, ema_n) if ema_n else [],
            "asset": 0.0, "basis": 0.0, "stop": 0.0, "pending": False,
            "trade": 0, "pnl": 0.0, "in_pos": 0,
        })
    n = min(len(p["c"]) for p in prep)
    inizio = max(canale, atr_n, ema_n) + 1
    cash = capitale
    curva = []
    rifiutati = 0
    for i in range(inizio, n):
        # 1) ingressi decisi ieri, eseguiti all'open di oggi
        for p in prep:
            c = p["c"]
            if not (p["pending"] and p["asset"] <= 1e-12):
                continue
            p["pending"] = False
            a = p["atr"][i - 1]
            if a <= 0 or c[i]["o"] <= 0:
                continue
            # BUDGET = min(capitale del conto, cash LIBERO): e' esattamente
            # _available() della policy in produzione.
            budget = max(0.0, min(capitale, cash)) if tetto_capitale else cash
            entry = c[i]["o"] * (1.0 + slip_entry)
            dist = stop_mult * a
            qty = min(budget * risk / dist, budget * esp_max / entry)
            vm = E._media_volumi(c, i)
            notional = qty * entry
            sl = E.slippage(notional, vm, slip_k)
            costo = notional * (1.0 + fee + sl)
            if costo > cash and costo > 0:
                qty *= cash / costo
                notional = qty * entry
                sl = E.slippage(notional, vm, slip_k)
                costo = notional * (1.0 + fee + sl)
            if qty > 1e-12 and costo <= cash * (1.0 + 1e-9):
                cash -= costo
                p["asset"] = qty
                p["basis"] = costo / qty
                p["stop"] = entry - dist
            else:
                rifiutati += 1
        # 2) trailing stop / uscite
        for p in prep:
            c = p["c"]
            if p["asset"] <= 1e-12:
                continue
            if c[i]["l"] <= p["stop"]:
                sl = E.slippage(p["asset"] * p["stop"], E._media_volumi(c, i), slip_k)
                incasso = p["asset"] * p["stop"] * (1.0 - fee - sl)
                cash += incasso
                p["pnl"] += incasso - p["asset"] * p["basis"]
                p["trade"] += 1
                p["asset"] = 0.0
                p["stop"] = 0.0
            else:
                a = p["atr"][i]
                if a > 0:
                    ns = c[i]["c"] - trail * a
                    if ns > p["stop"]:
                        p["stop"] = ns
        # 3) segnali sul close di oggi -> ingresso domani
        for p in prep:
            c = p["c"]
            price = c[i]["c"]
            if p["asset"] <= 1e-12 and not p["pending"] and i >= canale:
                massimo = max(x["h"] for x in c[i - canale:i])
                sopra = (not p["ema"]) or price > p["ema"][i]
                if price > massimo and sopra and p["atr"][i] > 0:
                    p["pending"] = True
            if p["asset"] > 1e-12:
                p["in_pos"] += 1
        eq = cash + sum(p["asset"] * p["c"][i]["c"] for p in prep)
        curva.append(eq)
    return {"curva": curva, "cash": cash, "rifiutati": rifiutati,
            "trade": sum(p["trade"] for p in prep), "prep": prep}


def metriche(curva):
    picco, mdd = -1e18, 0.0
    for e in curva:
        picco = max(picco, e)
        if picco > 0:
            mdd = max(mdd, 1.0 - e / picco)
    rr = [curva[i] / curva[i-1] - 1.0 for i in range(1, len(curva)) if curva[i-1] > 0]
    sd = st.stdev(rr) if len(rr) > 10 else 0.0
    sharpe = (st.mean(rr) / sd * math.sqrt(365)) if sd > 0 else 0.0
    rend = curva[-1] / curva[0] - 1.0
    anni = len(curva) / 365.0
    cagr = (curva[-1] / curva[0]) ** (1 / anni) - 1.0 if anni > 0 and curva[-1] > 0 else -1.0
    return rend, cagr, mdd, sharpe, anni


def valida():
    print("VALIDAZIONE: simulatore a capitale illimitato vs backtest_trend per asset")
    print("  %-6s %12s %12s %8s %6s %6s" % ("asset", "simulatore", "backtest", "delta", "t.sim", "t.bt"))
    ok = True
    tutti = [s for v in CONTI.values() for s in v]
    assets, _ = carica(tutti)
    for nome, c in assets:
        # NB: capitale 1.0, NON illimitato. Lo slippage dipende dal notional
        # (k*sqrt(notional/volume)): con un capitale enorme il notional esplode,
        # lo slippage satura al cap e i rendimenti divergono. Per confrontarsi
        # con backtest_trend(c, p, 1.0, fee) serve lo STESSO notional.
        r = simula([(nome, c)], 1.0, 0.02, tetto_capitale=False, **BASE)
        eq0 = 1.0
        sim_ret = r["curva"][-1] / eq0 - 1.0
        bt = E.backtest_trend(c, dict(BASE, risk_pct=0.02), 1.0, FEE, SLIP)
        d = sim_ret - bt.ritorno
        if abs(d) > 1e-6:
            ok = False
        print("  %-6s %11.4f%% %11.4f%% %+7.5f %6d %6d"
              % (nome, sim_ret * 100, bt.ritorno * 100, d * 100,
                 r["trade"], bt.trade))
    print("  --> %s" % ("COINCIDONO" if ok else "DIVERGONO: simulatore NON credibile"))
    return ok


def main():
    if not valida():
        return 1

    print()
    print("=" * 84)
    print("CAPITALE REALE: 3 conti da %.2f EUR, 5 asset ciascuno, capitale CONDIVISO"
          % CAPITALE)
    print("=" * 84)
    print("  %-7s %10s %9s %8s %8s %8s %9s" %
          ("rischio", "rend.3c", "CAGR", "maxDD", "Sharpe", "rifiutati", "trades"))
    for risk in (0.01, 0.02, 0.03, 0.04, 0.06, 0.08):
        curve_totali, rif, tr = [], 0, 0
        for nome, simboli in CONTI.items():
            assets, _ = carica(simboli)
            r = simula(assets, CAPITALE, risk, **BASE)
            curve_totali.append([e / CAPITALE for e in r["curva"]])
            rif += r["rifiutati"]
            tr += r["trade"]
        n = min(len(c) for c in curve_totali)
        port = [sum(c[i] for c in curve_totali) / len(curve_totali) for i in range(n)]
        rend, cagr, mdd, sharpe, anni = metriche(port)
        print("  %-7s %9.2f%% %8.2f%% %7.2f%% %8.2f %8d %9d"
              % ("%.0f%%" % (risk * 100), rend * 100, cagr * 100, mdd * 100,
                 sharpe, rif, tr))

    print()
    print("=" * 84)
    print("QUANTO CAPITALE SERVE perche' il vincolo smetta di mordere")
    print("(stesso schema: 3 conti, 5 asset ciascuno; il rischio per trade e' una")
    print(" scelta LIBERA solo finche' il conto riesce a finanziare le posizioni)")
    print("=" * 84)
    print("  %9s %7s %10s %9s %8s %8s %10s %11s" %
          ("capitale", "rischio", "rend.3c", "CAGR", "maxDD", "Sharpe", "rifiutati", "EUR/2.4a"))
    for cap in (24.83, 50.0, 100.0, 250.0, 500.0, 1000.0):
        for risk in (0.01, 0.02, 0.04, 0.06):
            curve_totali, rif, tr = [], 0, 0
            for nome, simboli in CONTI.items():
                assets, _ = carica(simboli)
                r = simula(assets, cap, risk, **BASE)
                curve_totali.append([e / cap for e in r["curva"]])
                rif += r["rifiutati"]
                tr += r["trade"]
            n = min(len(c) for c in curve_totali)
            port = [sum(c[i] for c in curve_totali) / len(curve_totali) for i in range(n)]
            rend, cagr, mdd, sharpe, anni = metriche(port)
            eur = cap * 3 * rend
            print("  %8.0f  %6s %9.2f%% %8.2f%% %7.2f%% %8.2f %10d %10.2f"
                  % (cap, "%.0f%%" % (risk * 100), rend * 100, cagr * 100,
                     mdd * 100, sharpe, rif, eur))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

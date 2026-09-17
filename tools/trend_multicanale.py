#!/usr/bin/env python3
"""Ingresso MULTI-ORIZZONTE: rompere piu' canali invece di uno solo.

Perche': oggi l'ingresso dipende da UN numero (canale 40). Se quel numero e'
sbagliato per il regime, la strategia tace o sbaglia. Un ingresso che chiede la
rottura di PIU' orizzonti (20, 40, 80 barre) e' meno dipendente da un singolo
parametro — e' la costruzione classica del time-series momentum multi-lookback.

Varianti provate:
  tutti   : la chiusura batte il massimo di TUTTI i canali (piu' selettivo)
  almeno2 : batte almeno 2 dei 3 (intermedio)
  media   : batte la MEDIA dei massimi (piu' permissivo)
  singolo : solo canale 40 (il deployato) — deve coincidere con backtest_trend

DISCIPLINA: il percorso a canale singolo deve riprodurre backtest_trend al bit,
altrimenti il confronto non vale nulla.

Uso: python3 tools/trend_multicanale.py
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
FEE_SPOT = 0.0035
FEE_SWAP = 0.0005
RISK = 0.02
REALI = {
    "mc2":      (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola":   (24.83, ["LINK", "AVAX", "DOT", "LTC", "UNI", "SUI"]),
    "MARCODG1": (42.04, ["ADA", "ATOM", "AAVE", "ARB", "XLM", "ALGO"]),
}
BASE = dict(atr_period=14, trail_mult=2.5, stop_atr_mult=2.0, trend_ema=100,
            max_exposure=1.0, entry_slip=0.0005, fee_buffer=0.01, max_barre=400,
            risk_pct=RISK)


def trend_multi(candles, p, capitale=1.0, fee=FEE_SPOT, slippage_k=0.02):
    """Trend long-only con ingresso multi-canale. canali=[40], modo='tutti'
    deve coincidere con backtest_trend."""
    canali = list(p.get("canali", [40]))
    modo = p.get("modo", "tutti")
    atr_n = int(p.get("atr_period", 14))
    trail = float(p.get("trail_mult", 2.5))
    rischio = float(p.get("risk_pct", RISK))
    ema_n = int(p.get("trend_ema", 100))
    esp_max = float(p.get("max_exposure", 1.0))
    stop_mult = float(p.get("stop_atr_mult", 2.0))
    slip_in = float(p.get("entry_slip", 0.0005))
    cmax = max(canali)

    closes = [c["c"] for c in candles]
    highs = [c["h"] for c in candles]
    lows = [c["l"] for c in candles]
    atr_l = E.atr_wilder(highs, lows, closes, atr_n)
    ema_l = E.ema(closes, ema_n) if ema_n else []
    inizio = max(cmax, atr_n, ema_n) + 1

    r = E.Risultato(nome="multi", capitale=capitale)
    cash = capitale
    qty = 0.0
    basis = 0.0
    stop = 0.0
    pending = False
    for i in range(inizio, len(candles)):
        c = candles[i]
        price, lo = c["c"], c["l"]
        vol_med = E._media_volumi(candles, i)
        if pending and qty <= 1e-12:
            a = atr_l[i - 1]
            if a > 0 and c["o"] > 0:
                dist = stop_mult * a
                entry = c["o"] * (1.0 + slip_in)
                q = min((cash * rischio) / dist, (cash * esp_max) / entry)
                notional = q * entry
                sl = E.slippage(notional, vol_med, slippage_k)
                costo = notional * (1.0 + fee + sl)
                if costo > cash and costo > 0:
                    q *= cash / costo
                    notional = q * entry
                    sl = E.slippage(notional, vol_med, slippage_k)
                    costo = notional * (1.0 + fee + sl)
                if q > 1e-12 and costo <= cash * (1.0 + 1e-9):
                    cash -= costo
                    qty = q
                    basis = costo / q
                    stop = entry - dist
            pending = False
        if qty > 1e-12:
            if lo <= stop:
                sl = E.slippage(qty * stop, vol_med, slippage_k)
                incasso = qty * stop * (1.0 - fee - sl)
                cash += incasso
                r.trade_pnls.append(incasso - qty * basis)
                r.fee_pagate += qty * stop * fee
                qty, stop = 0.0, 0.0
            else:
                a = atr_l[i]
                if a > 0:
                    ns = price - trail * a
                    if ns > stop:
                        stop = ns
        if qty <= 1e-12 and not pending and i >= cmax:
            livelli = [max(highs[i - k:i]) for k in canali]
            sopra = (not ema_l) or price > ema_l[i]
            if modo == "tutti":
                rotto = all(price > L for L in livelli)
            elif modo == "media":
                rotto = price > (sum(livelli) / len(livelli))
            elif modo == "almeno2":
                rotto = sum(1 for L in livelli if price > L) >= 2
            else:
                rotto = price > livelli[0]
            if rotto and sopra and atr_l[i] > 0:
                pending = True
        eq = cash + qty * price
        r.equity.append(eq)
        r.ts.append(c["ts"])
        if qty > 0:
            r.esposizione_bar += 1
    r.barre = len(r.equity)
    r.lordo = sum(r.trade_pnls) + r.fee_pagate
    return r


def valida():
    print("VALIDAZIONE: canali=[40], modo='tutti' deve coincidere con backtest_trend")
    ok = True
    for s in ("BTC", "ADA", "XLM", "CRV", "SOL"):
        c = E.load_csv(DATI / ("dl_%s_1D.csv" % s))
        p = dict(BASE, canali=[40], modo="tutti")
        a = trend_multi(c, p, 1.0, FEE_SPOT, cap.SLIP)
        b = E.backtest_trend(c, dict(BASE, canale=40), 1.0, FEE_SPOT, cap.SLIP)
        d = a.ritorno - b.ritorno
        if abs(d) > 1e-9:
            ok = False
        print("   %-5s multi %+9.4f%%  backtest %+9.4f%%  delta %+.2e  trade %d/%d"
              % (s, a.ritorno * 100, b.ritorno * 100, d, a.trade, b.trade))
    print("   --> %s" % ("COINCIDONO" if ok else "DIVERGONO"))
    return ok


def serie_per_conto(barre=None):
    out = {}
    for conto, (_, simboli) in REALI.items():
        aa = [(s, E.load_csv(DATI / ("dl_%s_1D.csv" % s))) for s in simboli]
        n = min(len(c) for _, c in aa)
        aa = [(s, c[-n:]) for s, c in aa]
        if barre:
            aa = [(s, c[-barre:]) for s, c in aa]
        out[conto] = aa
    return out


def condiviso(serie, p, fee):
    curve, rif = [], 0
    for conto, (capitale, _) in REALI.items():
        aa = [(s, c) for s, c in serie[conto]]
        r = cap.simula_multi(aa, capitale, fee, p) if hasattr(cap, "simula_multi") else None
        if r is None:
            # simulatore locale: stessa logica, capitale condiviso
            r = _condiviso_conto(aa, capitale, p, fee)
        curve.append([e / capitale for e in r["curva"]])
        rif += r["rifiutati"]
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
    return port[-1] - 1.0, mdd, sharpe, rif


def _condiviso_conto(assets, capitale, p, fee):
    """Capitale condiviso fra gli asset del conto, stessa logica della policy."""
    prep = []
    for nome, c in assets:
        closes = [x["c"] for x in c]
        prep.append({"nome": nome, "c": c,
                     "atr": E.atr_wilder([x["h"] for x in c], [x["l"] for x in c], closes,
                                         int(p.get("atr_period", 14))),
                     "ema": E.ema(closes, int(p.get("trend_ema", 100))),
                     "qty": 0.0, "basis": 0.0, "stop": 0.0, "pending": False})
    canali = list(p.get("canali", [40]))
    modo = p.get("modo", "tutti")
    cmax = max(canali)
    n = min(len(x["c"]) for x in prep)
    inizio = max(cmax, int(p.get("atr_period", 14)), int(p.get("trend_ema", 100))) + 1
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
            entry = c[i]["o"] * (1.0 + float(p.get("entry_slip", 0.0005)))
            dist = float(p.get("stop_atr_mult", 2.0)) * a
            q = min(budget * float(p.get("risk_pct", RISK)) / dist,
                    budget * float(p.get("max_exposure", 1.0)) / entry)
            vm = E._media_volumi(c, i)
            notional = q * entry
            sl = E.slippage(notional, vm, cap.SLIP)
            costo = notional * (1.0 + fee + sl)
            if costo > cash and costo > 0:
                q *= cash / costo
                notional = q * entry
                sl = E.slippage(notional, vm, cap.SLIP)
                costo = notional * (1.0 + fee + sl)
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
                sl = E.slippage(x["qty"] * x["stop"], E._media_volumi(c, i), cap.SLIP)
                incasso = x["qty"] * x["stop"] * (1.0 - fee - sl)
                cash += incasso
                x["qty"], x["stop"] = 0.0, 0.0
            else:
                a = x["atr"][i]
                if a > 0:
                    ns = c[i]["c"] - float(p.get("trail_mult", 2.5)) * a
                    if ns > x["stop"]:
                        x["stop"] = ns
        for x in prep:
            c = x["c"]
            price = c[i]["c"]
            if x["qty"] <= 1e-12 and not x["pending"] and i >= cmax:
                livelli = [max(y["h"] for y in c[i - k:i]) for k in canali]
                sopra = (not x["ema"]) or price > x["ema"][i]
                if modo == "tutti":
                    rotto = all(price > L for L in livelli)
                elif modo == "media":
                    rotto = price > sum(livelli) / len(livelli)
                elif modo == "almeno2":
                    rotto = sum(1 for L in livelli if price > L) >= 2
                else:
                    rotto = price > livelli[0]
                if rotto and sopra and x["atr"][i] > 0:
                    x["pending"] = True
        curva.append(cash + sum(x["qty"] * x["c"][i]["c"] for x in prep))
    return {"curva": curva, "rifiutati": rifiutati}


def main():
    if not valida():
        return 1
    print()
    print("capitale CONDIVISO reale, fee %.2f%%, trail 2.5" % (FEE_SPOT * 100))
    prove = {
        "singolo 40 (deployato)": dict(BASE, canali=[40], modo="tutti"),
        "multi 20/40/80 tutti": dict(BASE, canali=[20, 40, 80], modo="tutti"),
        "multi 20/40/80 almeno2": dict(BASE, canali=[20, 40, 80], modo="almeno2"),
        "multi 20/40/80 media": dict(BASE, canali=[20, 40, 80], modo="media"),
        "multi 10/20/40/80 tutti": dict(BASE, canali=[10, 20, 40, 80], modo="tutti"),
    }
    cache = {}
    for barre in (None, 540, 365, 270, 180):
        cache[barre] = serie_per_conto(barre)
    intest = "  %-26s" % "costruzione"
    for b in (None, 540, 365, 270, 180):
        intest += " %8s" % ("storia" if b is None else "%db" % b)
    intest += " %8s %8s" % ("maxDD", "Sharpe")
    print(intest)
    for nome, p in prove.items():
        riga = "  %-26s" % nome
        dd = sh = 0.0
        for b in (None, 540, 365, 270, 180):
            try:
                r, mdd, sharpe, _ = condiviso(cache[b], p, FEE_SPOT)
            except (IndexError, ValueError):
                r, mdd, sharpe = float("nan"), float("nan"), float("nan")
            if b is None:
                dd, sh = mdd, sharpe
            riga += " %7.2f%%" % (r * 100)
        riga += " %7.2f%% %8.2f" % (dd * 100, sh)
        print(riga)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

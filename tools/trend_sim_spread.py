"""GENERATO da trend_capacita.simula: fee + META SPREAD per lato."""
import sys
from pathlib import Path
sys.path.insert(0, "/home/sergio/alpha-omega-trading")
from denaro.research import eval as E
FEE = 0.0035
SLIP = 0.02
def simula_spread(assets, capitale, risk, fee=FEE, slip_k=SLIP, tetto_capitale=True,                  spread=None, **kw):
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
    spread = spread or {}

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
            costo = notional * (1.0 + fee + sl + spread.get(p["nome"], 0.0) / 2.0)
            if costo > cash and costo > 0:
                qty *= cash / costo
                notional = qty * entry
                sl = E.slippage(notional, vm, slip_k)
                costo = notional * (1.0 + fee + sl + spread.get(p["nome"], 0.0) / 2.0)
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
                incasso = p["asset"] * p["stop"] * (1.0 - fee - sl - spread.get(p["nome"], 0.0) / 2.0)
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

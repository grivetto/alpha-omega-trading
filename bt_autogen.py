# -*- coding: utf-8 -*-
"""Backtest harness per le auto_gen tick-dict di Denaro (mc2)."""
import glob, importlib.util, json, math, os, sys, time, urllib.request

SYMBOL = os.environ.get("BT_SYMBOL", "SOL/EUR")
LIMIT = int(os.environ.get("BT_LIMIT", "400"))
FEE = 0.001  # maker/taker OKX spot
MIN_BARS = 50

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36"}

def fetch_ohlcv(symbol, bar="1H", limit=400):
    inst = symbol.replace("/", "-")
    rows = []
    after = None
    while len(rows) < limit:
        url = "https://eea.okx.com/api/v5/market/candles?instId=%s&bar=%s&limit=300" % (inst, bar)
        if after: url += "&after=%d" % after
        req = urllib.request.Request(url, headers=_UA)
        d = json.loads(urllib.request.urlopen(req, timeout=25).read().decode())
        batch = d.get("data", [])
        if not batch: break
        rows.extend(batch)
        after = int(batch[-1][0])
        if len(batch) < 300: break
    out = []
    for r in rows[:limit]:
        ts, o, h, l, c, vol = int(r[0]), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5])
        out.append({"ts": ts, "o": o, "h": h, "l": l, "c": c, "vol": vol})
    out.reverse()
    return out

def load_module(path):
    name = "st_" + os.path.basename(path).replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def find_strategy(mod):
    for k in dir(mod):
        v = getattr(mod, k)
        if isinstance(v, type) and v.__module__ == mod.__name__:
            bases = [b.__name__ for b in v.__mro__[1:3]]
            if "StrategyBase" in bases or any("Strategy" in b for b in bases):
                return v
    return None

def sim(strategy_cls, bars, capital=20.0):
    """Simula: per ogni barra genera tick (o/h/l/c), chiama on_tick, fill limit, fee."""
    try:
        st = strategy_cls()
    except Exception:
        try:
            st = strategy_cls({"capital": capital})
        except Exception:
            return None
    cash = capital
    pos = 0.0
    pos_cost = 0.0
    peak = capital
    max_dd = 0.0
    trades = 0
    wins = 0
    pnls = []
    for i, bar in enumerate(bars):
        path = [bar["o"], bar["h"], bar["l"], bar["c"]]
        for price in path:
            tick = {"best_bid": price, "best_ask": price, "price": price,
                    "timestamp": bar["ts"], "volume": bar["vol"],
                    "equity": cash + pos * price}
            try:
                r = st.on_tick(tick)
            except Exception:
                return None
            if r is None: continue
            orders = r if isinstance(r, list) else [r]
            for od in orders:
                if not isinstance(od, dict): continue
                side = str(od.get("side", "")).lower()
                qty = float(od.get("qty", od.get("size", 0)) or 0)
                pr = float(od.get("price", price))
                if qty <= 0: continue
                if side == "buy":
                    cost = qty * pr * (1 + FEE)
                    if cost <= cash * 1.001:
                        cash -= cost
                        pos += qty
                        pos_cost += cost
                        trades += 1
                elif side == "sell" and pos > 0:
                    proceeds = qty * pr * (1 - FEE)
                    cash += proceeds
                    pnl = proceeds - (qty * pos_cost / pos if pos else 0)
                    pos = max(0.0, pos - qty)
                    if pos <= 0: pos_cost = 0.0
                    trades += 1
                    pnls.append(pnl)
                    wins += 1 if pnl > 0 else 0
    eq = cash + pos * bars[-1]["c"]
    ret = (eq - capital) / capital if capital else 0.0
    # drawdown approssimato sul percorso
    eq_peak = capital
    for bar in bars:
        e = cash + pos * bar["c"]
        eq_peak = max(eq_peak, e)
        if eq_peak > 0: max_dd = max(max_dd, (eq_peak - e) / eq_peak)
    n = len(pnls)
    mean = sum(pnls) / n if n else 0.0
    var = sum((p - mean) ** 2 for p in pnls) / n if n else 0.0
    sharpe = (mean / math.sqrt(var)) * math.sqrt(252) if var > 0 and n > 1 else 0.0
    return {"ret": round(ret, 4), "max_dd": round(max_dd, 4), "sharpe": round(sharpe, 2),
            "win_rate": round(wins / n, 3) if n else 0.0, "trades": trades, "final_eq": round(eq, 2)}

def main():
    files = sorted(glob.glob("/home/sergio/denaro/strategies/auto_gen_*.py"))
    print("strategie trovate:", len(files), flush=True)
    bars = fetch_ohlcv(SYMBOL, limit=LIMIT)
    print("barre OHLCV %s: %d" % (SYMBOL, len(bars)), flush=True)
    if len(bars) < MIN_BARS:
        print("dati insufficienti"); return
    results = []
    for f in files:
        try:
            mod = load_module(f)
            sc = find_strategy(mod)
            if sc is None:
                continue
            r = sim(sc, bars)
            if r is None:
                continue
            r["file"] = os.path.basename(f)
            results.append(r)
        except Exception:
            continue
    results.sort(key=lambda x: x["ret"], reverse=True)
    print("backtest completati: %d" % len(results), flush=True)
    print("=== TOP 10 (per ritorno) ===")
    for i, r in enumerate(results[:10], 1):
        print("%2d. %-34s ret=%7.4f dd=%6.4f sharpe=%5.2f win=%5.3f trades=%4d eq=%s" % (
            i, r["file"], r["ret"], r["max_dd"], r["sharpe"], r["win_rate"], r["trades"], r["final_eq"]))

if __name__ == "__main__":
    main()
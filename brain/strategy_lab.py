"""Brain — Strategy Lab: sviluppo continuo di strategie di trading.

Pipeline (autonoma, iterativa):
1. fetch OHLCV 1h (OKX EEA public + Kraken public) — cache su disco;
2. backtest del GRID BILATERALE + regime filter su un grid di parametri;
3. ranking (ret - 1.5*maxDD + 0.05*sharpe, minimo 10 trade);
4. registry su config/strategies/registry.json (committato);
5. promozione: top candidato → PAPER (override del bot paper), validazione
   24h → se batte il baseline → LIVE (override del bot live + restart nodo);
   altrimenti → scartato (history con motivo).
Tutto SOLO stdlib.
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from pathlib import Path

from . import config

FEES = {"okx": 0.001, "kraken": 0.0026, "paper": 0.001}
SLIPPAGE = 0.0005
MIN_TRADES = 10
SYMBOLS = ["SOL/EUR", "DOGE/EUR", "ETH/EUR", "ADA/EUR", "XRP/EUR"]

# ── data ─────────────────────────────────────────────────────────────────────

def fetch_ohlcv_okx(symbol: str, bar: str = "1H", limit: int = 300) -> list[dict]:
    inst = symbol.replace("/", "-")
    url = (f"https://www.eea.okx.com/api/v5/market/candles"
           f"?instId={inst}&bar={bar}&limit={limit}")
    with urllib.request.urlopen(url, timeout=25) as r:
        data = json.loads(r.read())
    out = []
    for row in reversed(data.get("data", [])):  # OKX ritorna desc
        out.append({"ts": int(row[0]), "o": float(row[1]), "h": float(row[2]),
                    "l": float(row[3]), "c": float(row[4]), "v": float(row[5])})
    return out


def fetch_ohlcv_kraken(symbol: str, interval: int = 60) -> list[dict]:
    pair = symbol.replace("/", "").upper()
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    with urllib.request.urlopen(url, timeout=25) as r:
        data = json.loads(r.read())
    result = data.get("result", {})
    rows = next(iter(result.values())) if result else []
    out = []
    for row in rows:  # [time, open, high, low, close, ...]
        out.append({"ts": int(row[0]), "o": float(row[1]), "h": float(row[2]),
                    "l": float(row[3]), "c": float(row[4]), "v": float(row[6])})
    return out


def load_or_fetch(symbol: str, source: str = "okx") -> list[dict]:
    """Cache OHLCV su disco (brain/data/ohlcv_<src>_<sym>.json), TTL 2h."""
    cache = config.DATA_DIR / f"ohlcv_{source}_{symbol.replace('/', '_')}.json"
    if cache.exists():
        try:
            data = json.loads(cache.read_text(encoding="utf-8"))
            if time.time() - data.get("_ts", 0) < 2 * 3600 and data.get("candles"):
                return data["candles"]
        except Exception:  # noqa: BLE001
            pass
    candles = (fetch_ohlcv_okx(symbol) if source == "okx"
               else fetch_ohlcv_kraken(symbol))
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"_ts": time.time(), "candles": candles}),
                     encoding="utf-8")
    return candles

# ── indicatori ───────────────────────────────────────────────────────────────

def ema(values: list[float], period: int) -> list[float]:
    if not values:
        return []
    k = 2.0 / (period + 1)
    out = [values[0]]
    for v in values[1:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def wilder_adx(closes: list[float], period: int = 14) -> list[float]:
    """ADX di Wilder allineato (valori validi solo dopo ~2×period)."""
    n = len(closes)
    if n < period * 2 + 2:
        return [0.0] * n
    tr, dm_p, dm_m = [], [], []
    for i in range(1, n):
        hi, lo = closes[i], closes[i]
        prev = closes[i - 1]
        tr.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
        up, down = hi - prev, prev - lo
        dm_p.append(up if (up > down and up > 0) else 0.0)
        dm_m.append(down if (down > up and down > 0) else 0.0)
    def sma_first(xs):
        return sum(xs[:period]) / period
    atr, pdi, mdi, dx = [], [], [], []
    a = sma_first(tr); p = sma_first(dm_p); m = sma_first(dm_m)
    atr.append(a); pdi.append(100 * p / a if a else 0); mdi.append(100 * m / a if a else 0)
    dx.append(abs(pdi[-1] - mdi[-1]) / (pdi[-1] + mdi[-1]) * 100 if (pdi[-1] + mdi[-1]) else 0)
    for i in range(period, len(tr)):
        a = (a * (period - 1) + tr[i]) / period
        p = (p * (period - 1) + dm_p[i]) / period
        m = (m * (period - 1) + dm_m[i]) / period
        atr.append(a)
        pdi.append(100 * p / a if a else 0)
        mdi.append(100 * m / a if a else 0)
        dx.append(abs(pdi[-1] - mdi[-1]) / (pdi[-1] + mdi[-1]) * 100 if (pdi[-1] + mdi[-1]) else 0)
    adx = [0.0] * (period * 2 - 1) + [sma_first(dx[:period])]
    for i in range(period, len(dx)):
        adx.append((adx[-1] * (period - 1) + dx[i]) / period)
    # adx ora ha lunghezza = len(tr) = n-1; riallinea a n con pad iniziale
    pad = n - len(adx)
    return [0.0] * pad + adx

# ── backtest ─────────────────────────────────────────────────────────────────

def backtest_grid(candles: list[dict], params: dict, fee: float,
                  capital: float = 100.0, start_all_in: bool = True) -> dict:
    """Grid bilaterale + regime filter (ADX/EMA200) su barre 1h.
    start_all_in=True → si parte con l'asset in mano (come i conti live)."""
    if len(candles) < 220:
        return {"ret": 0.0, "max_dd": 1.0, "sharpe": 0.0, "trades": 0,
                "win_rate": 0.0, "n_bars": 0}
    buy_distance = float(params.get("buy_distance", 0.01))
    profit_target = float(params.get("profit_target", 0.015))
    levels = int(params.get("levels", 3))
    sell_levels = int(params.get("sell_levels", 2))
    sell_distance = float(params.get("sell_distance", 0.02))
    sell_step = float(params.get("sell_step", 0.01))
    adx_th = float(params.get("adx_threshold", 25))
    stop_loss = float(params.get("stop_loss", 0.0))
    level_step = float(params.get("level_step", 0.005))

    closes = [c["c"] for c in candles]
    ema200 = ema(closes, 200)
    adx = wilder_adx(closes, 14)

    p0 = candles[0]["c"]
    cash = 0.0 if start_all_in else capital
    asset = capital / p0 if start_all_in else 0.0
    avg_cost = p0 if start_all_in else 0.0
    total_cost = capital if start_all_in else 0.0
    per_level = capital / levels
    open_buys: list[dict] = []
    open_sells: list[dict] = []
    trades = wins = 0
    peak = capital
    equity_curve: list[float] = []

    for i in range(200, len(candles)):
        p = candles[i]["c"]
        ema_v = ema200[i]
        adx_v = adx[i] if i < len(adx) else 0.0

        # fill buy limit
        for ob in list(open_buys):
            if p <= ob["price"]:
                cost = ob["amount"] * ob["price"] * (1 + fee + SLIPPAGE)
                if cash >= cost:
                    cash -= cost
                    asset += ob["amount"]
                    total_cost += cost
                    avg_cost = total_cost / asset if asset else 0.0
                    open_buys.remove(ob)
        # fill sell limit
        for os_ in list(open_sells):
            if p >= os_["price"]:
                proceeds = os_["amount"] * os_["price"] * (1 - fee - SLIPPAGE)
                asset -= os_["amount"]
                cash += proceeds
                profit = proceeds - os_["amount"] * avg_cost
                trades += 1
                wins += 1 if profit >= 0 else 0
                open_sells.remove(os_)
        if asset > 0:
            total_cost = avg_cost * asset

        # regime
        bear = adx_v >= adx_th and p < ema_v
        bull = adx_v >= adx_th and p > ema_v

        # buy ladder (bloccata in regime bear)
        if not bear:
            depth = len(open_buys)
            for lvl in range(depth, levels):
                price = p * (1 - buy_distance - lvl * level_step)
                if price > p * 0.85:
                    open_buys.append({"price": price,
                                      "amount": per_level / price})
        # sell ladder (grid bilaterale: vende l'asset sopra)
        if sell_levels > 0 and asset > 0 and not bull:
            for lvl in range(sell_levels):
                price = p * (1 + sell_distance + lvl * sell_step)
                if any(abs(s["price"] - price) / price < 1e-9 for s in open_sells):
                    continue
                amount = asset / sell_levels
                if amount > 0:
                    open_sells.append({"price": price, "amount": amount})

        equity = cash + asset * p
        equity_curve.append(equity)
        if equity > peak:
            peak = equity
        if stop_loss > 0 and equity < peak * (1 - stop_loss):
            break

    if not equity_curve:
        return {"ret": 0.0, "max_dd": 1.0, "sharpe": 0.0, "trades": 0,
                "win_rate": 0.0, "n_bars": 0}
    final_equity = equity_curve[-1]
    ret = final_equity / capital - 1
    max_dd = max((1 - e / peak) for e in equity_curve) if peak > 0 else 1.0
    rets = [equity_curve[i] / equity_curve[i - 1] - 1
            for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0]
    mean_r = sum(rets) / len(rets) if rets else 0.0
    std_r = (sum((r - mean_r) ** 2 for r in rets) / len(rets)) ** 0.5 if rets else 0.0
    sharpe = (mean_r / std_r * math.sqrt(24 * 365)) if std_r > 0 else 0.0
    return {"ret": ret, "max_dd": max_dd, "sharpe": sharpe, "trades": trades,
            "win_rate": wins / trades if trades else 0.0,
            "n_bars": len(equity_curve)}


def score(m: dict) -> float:
    if m["trades"] < MIN_TRADES:
        return -1e9
    return (m["ret"] - 1.5 * m["max_dd"]) * 100 + 0.05 * m["sharpe"]

# ── parametri candidati ──────────────────────────────────────────────────────

def param_grid(symbol: str) -> list[dict]:
    """Grid di parametri per simbolo (ridotto: ~200 combo per runda)."""
    grid = []
    for buy_distance in (0.005, 0.01, 0.015, 0.02):
        for profit_target in (0.01, 0.015, 0.02, 0.03):
            for levels in (2, 3, 5):
                for sell_levels in (2, 3, 4):
                    for sell_distance in (0.01, 0.02, 0.03):
                        for stop_loss in (0.10, 0.20):
                            grid.append({
                                "strategy": "grid",
                                "buy_distance": buy_distance,
                                "profit_target": profit_target,
                                "levels": levels,
                                "sell_levels": sell_levels,
                                "sell_distance": sell_distance,
                                "sell_step": 0.01,
                                "adx_threshold": 25,
                                "stop_loss": stop_loss,
                            })
    return grid

# ── registry + promozione ────────────────────────────────────────────────────

def load_registry() -> dict:
    try:
        reg = json.loads(config.REGISTRY_PATH.read_text(encoding="utf-8"))
        if "symbols" in reg:
            return reg
    except Exception:  # noqa: BLE001
        pass
    reg = {"updated": time.time(), "symbols": {}}
    for sym in SYMBOLS:
        reg["symbols"][sym] = {"live": {}, "best_candidate": None,
                               "paper": None, "history": []}
    return reg


def save_registry(reg: dict) -> None:
    config.REGISTRY_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.REGISTRY_PATH.write_text(json.dumps(reg, indent=2), encoding="utf-8")


def run_round(symbols: list[str] | None = None) -> dict:
    """Una runda di backtest per i simboli; aggiorna registry e paper override."""
    reg = load_registry()
    summary = {}
    for sym in (symbols or SYMBOLS):
        try:
            candles = load_or_fetch(sym)
            results = []
            for params in param_grid(sym):
                m = backtest_grid(candles, params, FEES["okx"])
                results.append((score(m), params, m))
            results.sort(key=lambda x: -x[0])
            top_params, top_metrics = None, None
            if results and results[0][0] > -1e8:
                _, top_params, top_metrics = results[0]
            sym_reg = reg["symbols"].setdefault(sym, {
                "live": {}, "best_candidate": None, "paper": None, "history": []})
            if top_params:
                cand = {"params": top_params, "metrics": top_metrics, "ts": time.time()}
                if sym_reg.get("best_candidate"):
                    sym_reg["history"].append({"params": sym_reg["best_candidate"]["params"],
                                               "metrics": sym_reg["best_candidate"]["metrics"],
                                               "ts": sym_reg["best_candidate"]["ts"],
                                               "status": "tested"})
                sym_reg["best_candidate"] = cand
                summary[sym] = {"ret": round(top_metrics["ret"], 4),
                                "trades": top_metrics["trades"],
                                "params": top_params}
        except Exception as e:  # noqa: BLE001
            summary[sym] = {"error": str(e)}
    reg["updated"] = time.time()
    save_registry(reg)
    return summary

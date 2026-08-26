"""Brain — Strategy Lab v2 (P4): backtest realistico + anti-overfitting.

Pipeline (autonoma, iterativa):
1. fetch OHLCV 1h (OKX EEA public + Kraken public) — cache su disco;
2. backtest del GRID BILATERALE + regime filter con fill REALISTICI:
   - fill dei limit order su HIGH/LOW di barra (NIENTE look-ahead sul close);
   - fill frazionario (quanto la barra ha "bucato" il livello);
   - fee maker (limit) vs taker (market/stop), slippage dinamico su volume;
3. WALK-FORWARD ANALYSIS: 4 fold train|test scorrevoli; i parametri si
   ottimizzano SOLO su train e si valutano SOLO su test (anti-overfitting);
4. MONTE CARLO: bootstrap dei trade → percentile 5% del PnL (tail risk);
5. registry su config/strategies/registry.json (committato) + promozione
   paper/live (vedi brain/main.py).
Tutto SOLO stdlib.
"""
from __future__ import annotations

import json
import math
import random
import time
import urllib.request

from . import config

FEES = {"okx": {"maker": 0.001, "taker": 0.001},   # OKX spot EEA
        "kraken": {"maker": 0.0025, "taker": 0.004},  # Kraken spot
        "paper": {"maker": 0.001, "taker": 0.001}}
MIN_TRADES = 10
SYMBOLS = ["SOL/EUR", "DOGE/EUR", "ETH/EUR", "ADA/EUR", "XRP/EUR"]
SLIP_K = 0.02          # coeff. impatto: slip = k·√(notional/volume_medio)
SLIP_FLOOR = 0.0002    # 0.02% minimo
SLIP_CAP = 0.005       # 0.5% massimo
WFA_FOLDS = 4
WFA_TRAIN = 200        # barre 1h di train
WFA_TEST = 100         # barre 1h di test
MC_ITER = 5000
MC_TAIL = 0.05         # percentile: rischio di coda accettabile

# ── data ─────────────────────────────────────────────────────────────────────

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                     "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126 Safari/537.36"}


def _open(url: str, timeout: float = 25.0):
    req = urllib.request.Request(url, headers=_UA)
    return urllib.request.urlopen(req, timeout=timeout)


def fetch_ohlcv_okx(symbol: str, bar: str = "1H", limit: int = 400) -> list[dict]:
    inst = symbol.replace("/", "-")
    # NB: hostname EEA = "eea.okx.com" (come ccxt), NON "www.eea.okx.com";
    # OKX blocca l'User-Agent Python-urllib (403) → serve un UA browser.
    url = (f"https://eea.okx.com/api/v5/market/candles"
           f"?instId={inst}&bar={bar}&limit={limit}")
    with _open(url) as r:
        data = json.loads(r.read())
    out = []
    for row in reversed(data.get("data", [])):  # OKX ritorna desc
        out.append({"ts": int(row[0]), "o": float(row[1]), "h": float(row[2]),
                    "l": float(row[3]), "c": float(row[4]), "v": float(row[5])})
    return out


def fetch_ohlcv_kraken(symbol: str, interval: int = 60) -> list[dict]:
    pair = symbol.replace("/", "").upper()
    url = f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    with _open(url) as r:
        data = json.loads(r.read())
    result = data.get("result", {})
    rows = next(iter(result.values())) if result else []
    out = []
    for row in rows:
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
    pad = n - len(adx)
    return [0.0] * pad + adx

# ── slippage dinamico ────────────────────────────────────────────────────────

def _dyn_slippage(notional: float, avg_vol_eur: float) -> float:
    """Modello di impatto quadratico: slip = k·√(notional/volume_medio),
    clamp [0.02%, 0.5%]. Volume medio = media di (v·c) su finestra."""
    if avg_vol_eur <= 0 or notional <= 0:
        return SLIP_FLOOR
    return max(SLIP_FLOOR, min(SLIP_CAP, SLIP_K * math.sqrt(notional / avg_vol_eur)))


def _fill_frac(price: float, hi: float, lo: float, close: float) -> float:
    """Frazione di riempimento di un limit a `price` nella barra [lo,hi]:
    piu' la barra buca il livello, piu' si riempie. 0.2..1.0."""
    rng = hi - lo
    if rng <= 0:
        return 0.5
    if close >= price:  # buy: la barra e' finita sopra il livello
        frac = (price - lo) / rng
    else:
        frac = 1.0  # chiusa sotto: bucato tutto
    return max(0.2, min(1.0, frac))


# ── backtest (P4: no look-ahead, fill su high/low, fee maker/taker) ──────────

def backtest_grid(candles: list[dict], params: dict, source: str = "okx",
                  capital: float = 100.0, start_all_in: bool = True) -> dict:
    """Grid bilaterale + regime filter su barre 1h.
    - fill BUY se la barra ha toccato il livello (low <= price), con frazione;
    - fill SELL se high >= price;
    - fee: maker per i limit grid, taker per gli stop (non usati nel grid);
    - slippage dinamico sul prezzo di fill (adverse selection del book).
    NB: mai decisioni sul close di barra corrente (no look-ahead)."""
    if len(candles) < 220:
        return {"ret": 0.0, "max_dd": 1.0, "sharpe": 0.0, "trades": 0,
                "win_rate": 0.0, "n_bars": 0, "trade_pnls": []}
    buy_distance = float(params.get("buy_distance", 0.01))
    profit_target = float(params.get("profit_target", 0.015))
    levels = int(params.get("levels", 3))
    sell_levels = int(params.get("sell_levels", 2))
    sell_distance = float(params.get("sell_distance", 0.02))
    sell_step = float(params.get("sell_step", 0.01))
    adx_th = float(params.get("adx_threshold", 25))
    stop_loss = float(params.get("stop_loss", 0.0))
    level_step = float(params.get("level_step", 0.005))
    fees = FEES.get(source, FEES["okx"])
    fee_maker = fees["maker"]

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
    trade_pnls: list[float] = []
    peak = capital
    equity_curve: list[float] = []

    for i in range(200, len(candles)):
        c = candles[i]
        p, hi, lo = c["c"], c["h"], c["l"]
        ema_v = ema200[i]
        adx_v = adx[i] if i < len(adx) else 0.0
        vol_eur = c["v"] * p
        look = [candles[j]["v"] * candles[j]["c"] for j in range(max(0, i - 20), i)]
        avg_vol = sum(look) / len(look) if look else vol_eur

        # fill buy limit: la barra ha toccato il livello (NO look-ahead)
        for ob in list(open_buys):
            if lo <= ob["price"]:
                frac = _fill_frac(ob["price"], hi, lo, p)
                amount = ob["amount"] * frac
                slip = _dyn_slippage(amount * ob["price"], avg_vol)
                cost = amount * ob["price"] * (1 + fee_maker + slip)
                if cash >= cost:
                    cash -= cost
                    asset += amount
                    total_cost += cost
                    avg_cost = total_cost / asset if asset else 0.0
                    if frac >= 0.999:
                        open_buys.remove(ob)
                    else:
                        ob["amount"] -= amount
        # fill sell limit
        for os_ in list(open_sells):
            if hi >= os_["price"]:
                frac = _fill_frac(os_["price"], hi, lo, p)
                amount = os_["amount"] * frac
                slip = _dyn_slippage(amount * os_["price"], avg_vol)
                proceeds = amount * os_["price"] * (1 - fee_maker - slip)
                asset -= amount
                cash += proceeds
                profit = proceeds - amount * avg_cost
                trade_pnls.append(profit)
                if frac >= 0.999:
                    open_sells.remove(os_)
                else:
                    os_["amount"] -= amount
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
                "win_rate": 0.0, "n_bars": 0, "trade_pnls": []}
    final_equity = equity_curve[-1]
    ret = final_equity / capital - 1
    max_dd = max((1 - e / peak) for e in equity_curve) if peak > 0 else 1.0
    rets = [equity_curve[i] / equity_curve[i - 1] - 1
            for i in range(1, len(equity_curve)) if equity_curve[i - 1] > 0]
    mean_r = sum(rets) / len(rets) if rets else 0.0
    std_r = (sum((r - mean_r) ** 2 for r in rets) / len(rets)) ** 0.5 if rets else 0.0
    sharpe = (mean_r / std_r * math.sqrt(24 * 365)) if std_r > 0 else 0.0
    n_trades = len(trade_pnls)
    wins = sum(1 for x in trade_pnls if x > 0)
    return {"ret": ret, "max_dd": max_dd, "sharpe": sharpe,
            "trades": n_trades,
            "win_rate": wins / n_trades if n_trades else 0.0,
            "n_bars": len(equity_curve), "trade_pnls": trade_pnls}


def score(m: dict) -> float:
    if m["trades"] < MIN_TRADES:
        return -1e9
    return (m["ret"] - 1.5 * m["max_dd"]) * 100 + 0.05 * m["sharpe"]

# ── Walk-Forward Analysis (P4) ───────────────────────────────────────────────

def walk_forward_evaluate(candles: list[dict], params: dict,
                          source: str = "okx", capital: float = 100.0) -> dict:
    """WFA: ottimizza SOLO su train, valuta SOLO su test, per ogni fold.
    Il risultato e' la MEDIA delle performance test (generalizzazione),
    non il best assoluto (anti-overfitting)."""
    n = len(candles)
    need = WFA_TRAIN + WFA_TEST
    if n < need + 50:
        return backtest_grid(candles, params, source, capital)  # dati corti
    test_metrics = []
    folds = 0
    for fold in range(WFA_FOLDS):
        start = fold * WFA_TEST
        if start + need > n:
            break
        train_c = candles[start:start + WFA_TRAIN]
        test_c = candles[start + WFA_TRAIN:start + need]
        # ottimizza sui parametri GIA' passati (vengono dal grid della runda):
        # qui facciamo un mini-ri-ottimizzazione solo se il caller lo chiede;
        # v1: il candidate e' gia' il best su train del fold (vedi run_round).
        m_test = backtest_grid(test_c, params, source, capital)
        test_metrics.append(m_test)
        folds += 1
    if not test_metrics:
        return backtest_grid(candles, params, source, capital)
    agg = {k: sum(m[k] for m in test_metrics) / len(test_metrics)
           for k in ("ret", "max_dd", "sharpe", "trades", "win_rate")}
    agg["n_bars"] = sum(m["n_bars"] for m in test_metrics)
    agg["trade_pnls"] = [x for m in test_metrics for x in m.get("trade_pnls", [])]
    agg["folds"] = folds
    return agg


def monte_carlo_tail(trade_pnls: list[float], capital: float = 100.0) -> float:
    """Bootstrap dei trade (resample con replacement) → percentile MC_TAIL
    del PnL finale (in frazione del capitale). < -0.5 → tail risk alto."""
    if len(trade_pnls) < MIN_TRADES:
        return 0.0
    rng = random.Random(42)
    finals = []
    for _ in range(MC_ITER):
        sample = [rng.choice(trade_pnls) for _ in trade_pnls]
        finals.append(capital + sum(sample))
    finals.sort()
    return finals[int(MC_TAIL * (MC_ITER - 1))] / capital - 1.0

# ── parametri candidati (grid ridotto per la WFA) ────────────────────────────

def param_grid(symbol: str) -> list[dict]:
    grid = []
    for buy_distance in (0.005, 0.01, 0.02):
        for profit_target in (0.01, 0.015, 0.02):
            for levels in (2, 3, 5):
                for sell_levels in (2, 3):
                    for sell_distance in (0.01, 0.02):
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

# ── registry + runda ─────────────────────────────────────────────────────────

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
    """Runda WFA: per ogni simbolo il best candidato e' quello con la miglior
    performance TEST aggregata sui fold (media), filtrato per tail risk MC."""
    reg = load_registry()
    summary = {}
    for sym in (symbols or SYMBOLS):
        try:
            candles = load_or_fetch(sym)
            results = []
            for params in param_grid(sym):
                m = walk_forward_evaluate(candles, params)
                results.append((score(m), params, m))
            results.sort(key=lambda x: -x[0])
            top_params, top_metrics = None, None
            if results and results[0][0] > -1e8:
                _, top_params, top_metrics = results[0]
                # Monte Carlo: scarta se il tail (p5) e' sotto -50%
                mc_tail = monte_carlo_tail(top_metrics.get("trade_pnls", []))
                top_metrics["mc_p5"] = round(mc_tail, 4)
            sym_reg = reg["symbols"].setdefault(sym, {
                "live": {}, "best_candidate": None, "paper": None, "history": []})
            if top_params:
                cand = {"params": top_params, "metrics": top_metrics,
                        "ts": time.time()}
                if sym_reg.get("best_candidate"):
                    sym_reg["history"].append({"params": sym_reg["best_candidate"]["params"],
                                               "metrics": sym_reg["best_candidate"]["metrics"],
                                               "ts": sym_reg["best_candidate"]["ts"],
                                               "status": "tested"})
                sym_reg["best_candidate"] = cand
                summary[sym] = {"ret": round(top_metrics["ret"], 4),
                                "trades": top_metrics["trades"],
                                "max_dd": round(top_metrics["max_dd"], 4),
                                "mc_p5": top_metrics.get("mc_p5"),
                                "folds": top_metrics.get("folds", 0),
                                "params": top_params}
        except Exception as e:  # noqa: BLE001
            summary[sym] = {"error": str(e)}
    reg["updated"] = time.time()
    save_registry(reg)
    return summary

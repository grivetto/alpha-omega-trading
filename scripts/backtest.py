#!/usr/bin/env python3
"""ATLAS Backtest Harness v3 — multi-regime reale, grid re-centering, metrica RT.

Dati: OHLCV pubblici via ccxt (Kraken), fee reali, slippage, min notional.
Nessuna chiave richiesta, nessun ordine piazzato. Puro backtest offline.

Problema v2 (FIXATO): Kraken restituisce max ~720 candele per chiamata; la
paginazione non avanzava -> 365d e 90d erano la stessa finestra di 30 giorni.
v3 usa timeframe 1d (720 candele ~= 2 anni) -> finestre multi-regime REALI,
etichettate dai dati (bull/bear/sideways), con sanity-check su date/count.

Fix simulatore: la griglia v2 era ancorata al primo close (trade identici tra
asset = artefatto). v3 re-centra i livelli buy attorno al close di ogni candela
quando il livello e' libero — comportamento fedele all'engine ATLAS (piazza
ordini attorno al mid corrente quando open orders < levels).

Metrica a priori aggiunta: margine per round-trip = spread - 2*(fee+slippage).
Se < 0 la griglia perde strutturalmente, indipendentemente dalla storia.

Strategie: buy_hold, dca (config reale, capitale-vincolato), dca_cad,
grid (sweep spread x livelli, re-centering).
"""
from __future__ import annotations

import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt

# ─── Parametri (reali) ───────────────────────────────────────────────────────
EXCHANGE_ID = "kraken"
FEE_MAKER = 0.0016          # Kraken 0.16% maker
FEE_TAKER = 0.0026          # Kraken 0.26% taker
SLIPPAGE = 0.0005           # 0.05% per fill
CAPITAL = 100.0             # EUR (micro-capital ~100 EUR totale)
MIN_NOTIONAL = 5.0          # min notional Kraken (EUR)
SYMBOLS = ["SOL/EUR", "DOGE/EUR", "BTC/EUR"]

# Timeframe dati: 1d ~= 2 anni (720 candele) — multi-regime in una chiamata
TF_DAILY = "1d"
TF_4H = "4h"

# Sweep griglia
SWEEP_SPREADS = [0.005, 0.01, 0.02, 0.03]
SWEEP_LEVELS = [2, 5, 10]

# DCA (config reale dca.py)
DCA_INTERVAL_H = 12
DCA_BASE_EUR = 8.0
DCA_DIP_PCT = 0.03
DCA_DIP_MULT = 2.0
DCA_MAX_EUR = 15.0
DCA_CAD_EUR = 5.0

# Finestre (in candele daily) — tagliate sui dati reali
WINDOWS = [(None, "full_2y"), (240, "240d"), (480, "480d")]


def fetch_ohlcv(exchange, symbol, timeframe, limit=None) -> list:
    """Una chiamata (Kraken cap ~720/call). Ritorna candele recenti ordinate."""
    batch = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    seen = {}
    for c in batch:
        seen[c[0]] = c
    candles = [seen[k] for k in sorted(seen)]
    if len(candles) < 200:
        raise RuntimeError(f"{symbol} {timeframe}: solo {len(candles)} candele")
    return candles


def regime_label(candles) -> str:
    ret = candles[-1][4] / candles[0][4] - 1
    if ret > 0.10:
        return f"bull (+{ret*100:.0f}%)"
    if ret < -0.10:
        return f"bear ({ret*100:.0f}%)"
    return f"sideways ({ret*100:+.1f}%)"


def rt_margin(spread: float) -> float:
    """Margine per round-trip: spread - 2*(fee+slippage), in %."""
    return spread - 2 * (FEE_MAKER + SLIPPAGE)


# ─── Strategie ───────────────────────────────────────────────────────────────
def sim_buy_hold(candles, fee, slippage, capital):
    first_close = candles[0][4]
    base = capital / first_close * (1 - fee - slippage)
    eq = [base * c[4] for c in candles]
    return {"final": eq[-1], "eq": eq, "trades": 1, "fees": capital * fee,
            "buys": 1, "sells": 0, "inventory_base": base, "cash": 0.0}


def sim_grid(candles, levels, spread, fee, slippage, capital, min_notional):
    """Griglia bilaterale GTC-persistente — NIENTE lookahead, niente
    same-candle round-trip.

    - Al close della candela t: piazza ordini buy GTC per i livelli liberi.
    - Nelle candele SUCCESSIVE: se low <= buy_target -> fill buy -> piazza sell
      GTC a +spread. Il sell NON puo' riempirsi nella stessa candela del buy
      (con OHLC aggregato non sappiamo se low precede high).
    - Gli ordini GTC RESTANO finche' non si riempiono (come su exchange).
    - Invariante ad ogni passo: cash + base*close + fees_total == capital.
    """
    notional = capital / levels
    if notional < min_notional:
        notional = min_notional
    buy_target: list[float | None] = [None] * levels
    state: list[tuple[float, float, float] | None] = [None] * levels  # (qty, buy_price, sell_price)
    bought_this_candle: list[bool] = [False] * levels
    base_bal, quote_bal = 0.0, capital
    inventory_cost = 0.0          # costo storico dell'inventario detenuto
    realized_pnl = 0.0            # pnl realizzato
    fee_buy = fee + slippage
    eq, fills_buy, fills_sell, fees_total = [], 0, 0, 0.0
    round_trips = 0
    inv_ok = True

    for c in candles:
        low, high, close = c[3], c[2], c[4]
        bought_this_candle = [False] * levels
        # 1) Fill check su ordini piazzati in candele PRECEDENTI
        for i in range(levels):
            bt = buy_target[i]
            if bt is not None and low <= bt:
                cost = notional * (1 + fee_buy)
                if quote_bal >= cost:
                    quote_bal -= cost
                    qty = notional / bt
                    base_bal += qty
                    inventory_cost += qty * bt
                    state[i] = (qty, bt, bt * (1 + spread))
                    buy_target[i] = None
                    bought_this_candle[i] = True
                    fills_buy += 1
                    fees_total += notional * fee_buy
            st = state[i]
            if st is not None and not bought_this_candle[i]:
                qty, bp, sp = st
                if high >= sp:
                    quote_bal += qty * sp * (1 - fee_buy)
                    base_bal -= qty
                    inventory_cost -= qty * bp
                    realized_pnl += qty * (sp - bp)
                    state[i] = None
                    fills_sell += 1
                    fees_total += qty * sp * fee_buy
                    round_trips += 1
        # 2) Al close: piazza buy GTC per i livelli liberi (fill solo da t+1)
        for i in range(levels):
            if buy_target[i] is None and state[i] is None:
                buy_target[i] = close * (1 - spread * (i + 1))
        eq.append(quote_bal + base_bal * close)
        # Invariante a costo storico: cash + costo inventario + fee - pnl realizzato == capital
        if abs(quote_bal + inventory_cost + fees_total - realized_pnl - capital) > 1e-6:
            inv_ok = False

    if not inv_ok:
        print(f"  [WARN] sim_grid: invariante violato (levels={levels} spread={spread})")

    return {"final": eq[-1], "eq": eq, "trades": fills_buy + fills_sell,
            "fees": fees_total, "buys": fills_buy, "sells": fills_sell,
            "round_trips": round_trips, "inventory_base": base_bal,
            "cash": quote_bal}


def sim_dca(candles, interval_h, base_eur, dip_pct, dip_mult, max_eur, fee,
            slippage, capital):
    """DCA config reale: acquisto periodico, dip x2, vincolato al capitale."""
    step = max(1, int(interval_h * 3600 / (candles[1][0] - candles[0][0])))
    base_bal, quote_bal = 0.0, capital
    spent, fees_total, buys, eq = 0.0, 0.0, 0, []
    hwm = candles[0][4]

    for idx, c in enumerate(candles):
        close = c[4]
        hwm = max(hwm, close)
        if idx % step == 0:
            drop = (hwm - close) / hwm if hwm > 0 else 0.0
            value = min(base_eur * dip_mult, max_eur) if drop >= dip_pct else base_eur
            value = min(value, quote_bal)
            if value >= 1e-9:
                base_bal += value / close * (1 - fee - slippage)
                quote_bal -= value
                spent += value
                fees_total += value * fee
                buys += 1
        eq.append(quote_bal + base_bal * close)
    return {"final": eq[-1], "eq": eq, "trades": buys, "fees": fees_total,
            "buys": buys, "sells": 0, "deployed": spent,
            "inventory_base": base_bal, "cash": quote_bal}


def sim_dca_cad(candles, cad_eur, fee, slippage, capital, n_buys):
    step = max(1, (len(candles) - 1) // max(1, n_buys))
    base_bal, quote_bal = 0.0, capital
    spent, fees_total, buys, eq = 0.0, 0.0, 0, []
    for idx, c in enumerate(candles):
        close = c[4]
        if idx % step == 0 and quote_bal >= cad_eur:
            base_bal += cad_eur / close * (1 - fee - slippage)
            quote_bal -= cad_eur
            spent += cad_eur
            fees_total += cad_eur * fee
            buys += 1
        eq.append(quote_bal + base_bal * close)
    return {"final": eq[-1], "eq": eq, "trades": buys, "fees": fees_total,
            "buys": buys, "sells": 0, "deployed": spent,
            "inventory_base": base_bal, "cash": quote_bal}


def metrics(eq, final, trades, fees, annualization, extra=None):
    """Metriche. annualization = bar_per_year (es. 365 per 1d, 2190 per 4h)."""
    peak, maxdd = -1e18, 0.0
    rets = []
    for e in eq:
        peak = max(peak, e)
        if peak > 0:
            maxdd = max(maxdd, (peak - e) / peak)
    for a, b in zip(eq[:-1], eq[1:]):
        if a > 0:
            rets.append(b / a - 1)
    mean = sum(rets) / len(rets) if rets else 0.0
    var = sum((r - mean) ** 2 for r in rets) / len(rets) if rets else 0.0
    sharpe = (mean / math.sqrt(var)) * math.sqrt(annualization) if var > 0 else 0.0
    m = {"final_eur": round(final, 2),
         "pnl_pct": round((final / CAPITAL - 1) * 100, 2),
         "maxdd_pct": round(maxdd * 100, 2),
         "sharpe_ann": round(sharpe, 2),
         "trades": trades, "fees_eur": round(fees, 2),
         "fee_drag_pct": round(fees / CAPITAL * 100, 2)}
    if extra:
        m.update(extra)
    return m


def run_window(candles, symbol, window_name, results):
    start = datetime.fromtimestamp(candles[0][0] / 1000, tz=timezone.utc).date()
    end = datetime.fromtimestamp(candles[-1][0] / 1000, tz=timezone.utc).date()
    regime = regime_label(candles)
    key = f"{symbol} {window_name}"
    strat = {}
    # bar per anno per annualizzazione Sharpe (1d=365, 4h=2190)
    ann = 365 * 24 * 3600 / (candles[1][0] - candles[0][0])

    bh = sim_buy_hold(candles, FEE_TAKER, SLIPPAGE, CAPITAL)
    strat["buy_hold"] = metrics(bh["eq"], bh["final"], bh["trades"], bh["fees"], ann,
                                {"inventory": round(bh["inventory_base"], 6), "cash": round(bh["cash"], 2)})

    for spread in SWEEP_SPREADS:
        for levels in SWEEP_LEVELS:
            g = sim_grid(candles, levels, spread, FEE_MAKER, SLIPPAGE, CAPITAL, MIN_NOTIONAL)
            name = f"grid_{int(spread*1000)}p_{levels}l"
            m = metrics(g["eq"], g["final"], g["trades"], g["fees"], ann,
                        {"RT": g["round_trips"],
                         "rt_margin_pct": round(rt_margin(spread) * 100, 2),
                         "inventory": round(g["inventory_base"], 6), "cash": round(g["cash"], 2)})
            strat[name] = m

    d = sim_dca(candles, DCA_INTERVAL_H, DCA_BASE_EUR, DCA_DIP_PCT,
                DCA_DIP_MULT, DCA_MAX_EUR, FEE_TAKER, SLIPPAGE, CAPITAL)
    strat["dca"] = metrics(d["eq"], d["final"], d["trades"], d["fees"], ann,
                           {"deployed": round(d["deployed"], 2),
                            "inventory": round(d["inventory_base"], 6), "cash": round(d["cash"], 2)})

    n_buys = max(2, int(CAPITAL // MIN_NOTIONAL))
    dc = sim_dca_cad(candles, DCA_CAD_EUR, FEE_TAKER, SLIPPAGE, CAPITAL, n_buys)
    strat["dca_cad"] = metrics(dc["eq"], dc["final"], dc["trades"], dc["fees"], ann,
                               {"deployed": round(dc["deployed"], 2),
                                "inventory": round(dc["inventory_base"], 6), "cash": round(dc["cash"], 2)})

    results["windows"][key] = {"period": f"{start}→{end}", "regime": regime,
                               "strategies": strat}
    return key, regime, start, end


def main() -> None:
    exchange = getattr(ccxt, EXCHANGE_ID)()
    exchange.enableRateLimit = True
    results = {"meta": {"exchange": EXCHANGE_ID, "capital": CAPITAL,
                        "fee_maker": FEE_MAKER, "fee_taker": FEE_TAKER,
                        "slippage": SLIPPAGE, "min_notional": MIN_NOTIONAL,
                        "run_utc": datetime.now(timezone.utc).isoformat()},
               "windows": {}}

    for symbol in SYMBOLS:
        print(f"\n=== {symbol} — fetch {TF_DAILY} (2y) + {TF_4H} (recente)...")
        daily = fetch_ohlcv(exchange, symbol, TF_DAILY)
        h4 = fetch_ohlcv(exchange, symbol, TF_4H)
        # sanity: date count
        d0 = datetime.fromtimestamp(daily[0][0] / 1000, tz=timezone.utc).date()
        d1 = datetime.fromtimestamp(daily[-1][0] / 1000, tz=timezone.utc).date()
        print(f"  1d: {len(daily)} candele [{d0} → {d1}]  |  4h: {len(h4)} candele "
              f"[{datetime.fromtimestamp(h4[0][0]/1000, tz=timezone.utc).date()} → "
              f"{datetime.fromtimestamp(h4[-1][0]/1000, tz=timezone.utc).date()}]")

        # Finestre su dati daily: full, ultimi 240, ultimi 480 (multi-regime)
        for last_n, name in WINDOWS:
            c = daily[-last_n:] if last_n else daily
            if len(c) < 200:
                continue
            key, regime, s, e = run_window(c, symbol, name, results)
            print(f"  window {name}: [{s} → {e}] {len(c)} candele regime={regime}")

        # Finestra 4h recente (ultime ~540 candele = 90d)
        c = h4[-540:]
        if len(c) >= 400:
            key, regime, s, e = run_window(c, symbol, "90d_4h", results)
            print(f"  window 90d_4h: [{s} → {e}] {len(c)} candele regime={regime}")

    # Stampa top-3 per window
    for key, asset in results["windows"].items():
        ranked = sorted(asset["strategies"].items(), key=lambda kv: kv[1]["pnl_pct"], reverse=True)
        print(f"\n  TOP {asset['regime']} ({key} [{asset['period']}]):")
        for sname, m in ranked[:3]:
            extra = f" RT={m.get('RT')} marginRT={m.get('rt_margin_pct')}%" if m.get("RT") is not None else ""
            print(f"    {sname:<22} PnL {m['pnl_pct']:>7}%  maxDD {m['maxdd_pct']:>6}%  "
                  f"Sharpe {m['sharpe_ann']:>5}  trades {m['trades']:>4}  fee {m['fees_eur']:>5.2f}€{extra}")

    OUT = Path(__file__).resolve().parent / "backtest_results.json"
    OUT.write_text(json.dumps(results, indent=2))
    print(f"\nRisultati salvati in {OUT}")


if __name__ == "__main__":
    main()

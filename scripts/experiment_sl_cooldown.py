#!/usr/bin/env python3
"""Esperimento FINALE: grid 2% + stop-loss 30% + cooldown vs grid 2% baseline.

DELTA PURO rispetto a sim_grid (scripts/backtest.py): stessa identica logica
(notional=capital/levels fisso, fee_buy=fee+slippage, sell a buy_price*(1+spread),
bought_this_candle anti same-candle, re-placement buy_target al close).
La variante aggiunge SOLO:
  (a) peak equity tracking (mark-to-market a ogni candela)
  (b) se drawdown da picco > sl_pct -> liquida inventario al close (fee taker)
  (c) cooldown di N candele senza ordini/fill
  (d) al termine del cooldown, ri-centra buy_target sul close corrente
"""
import sys, importlib.util, json

spec = importlib.util.spec_from_file_location("bt", "/home/sergio/alpha-omega-trading/scripts/backtest.py")
if spec is None or spec.loader is None:
    sys.exit("Impossibile caricare backtest.py")
bt = importlib.util.module_from_spec(spec)
sys.modules["bt"] = bt
spec.loader.exec_module(bt)

FEE = 0.0016          # Kraken maker
SLIPPAGE = 0.0005
CAPITAL = 100.0
MIN_NOTIONAL = 5.0
SPREAD = 0.02
LEVELS = 5
SL_PCT = 0.30
COOLDOWN_CANDLES = {"1d": 10, "4h": 30}


def sim_grid_sl_cooldown(candles, levels, spread, fee, slippage, capital,
                         min_notional, sl_pct, cooldown):
    """Replica ESATTA di sim_grid + stop-loss con cooldown (delta puro)."""
    notional = capital / levels
    if notional < min_notional:
        notional = min_notional
    fee_buy = fee + slippage
    buy_target: list[float | None] = [None] * levels
    state: list[tuple[float, float, float] | None] = [None] * levels
    base_bal, quote_bal = 0.0, capital
    inventory_cost, realized_pnl = 0.0, 0.0
    eq, fills_buy, fills_sell, fees_total, round_trips = [], 0, 0, 0.0, 0
    peak, cooldown_left = -1e18, 0

    for c in candles:
        low, high, close = c[3], c[2], c[4]

        # --- (a) equity mark-to-market + peak tracking ---
        equity = quote_bal + base_bal * close
        peak = max(peak, equity)

        # --- (b) stop-loss: drawdown da picco > sl_pct -> liquida al close ---
        if cooldown_left == 0 and peak > 0 and (peak - equity) / peak > sl_pct:
            if base_bal > 0:
                quote_bal += base_bal * close * (1 - fee_buy)
                fees_total += base_bal * close * fee_buy
                base_bal = 0.0
            state = [None] * levels
            buy_target = [None] * levels
            inventory_cost = 0.0
            cooldown_left = cooldown
            peak = quote_bal  # nuovo riferimento: capitale liquido
            eq.append(quote_bal)
            continue

        # --- (c) cooldown: nessun ordine, nessun fill ---
        if cooldown_left > 0:
            cooldown_left -= 1
            if cooldown_left == 0:
                # (d) ri-centra la griglia sul close corrente
                buy_target = [close * (1 - spread * (i + 1)) for i in range(levels)]
                state = [None] * levels
            eq.append(quote_bal + base_bal * close)
            continue

        bought_this_candle = [False] * levels
        # 1) Fill buy (ordini piazzati in candele precedenti)
        for i in range(levels):
            bt_ = buy_target[i]
            if bt_ is not None and low <= bt_:
                cost = notional * (1 + fee_buy)
                if quote_bal >= cost:
                    quote_bal -= cost
                    qty = notional / bt_
                    base_bal += qty
                    inventory_cost += qty * bt_
                    state[i] = (qty, bt_, bt_ * (1 + spread))
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
        # 2) Al close: piazza buy GTC per i livelli liberi (fill da t+1)
        for i in range(levels):
            if buy_target[i] is None and state[i] is None:
                buy_target[i] = close * (1 - spread * (i + 1))
        eq.append(quote_bal + base_bal * close)

    return {"eq": eq, "round_trips": round_trips, "fees": fees_total,
            "buys": fills_buy, "sells": fills_sell}


def metrics(eq, capital):
    p, mdd = -1e18, 0.0
    for e in eq:
        p = max(p, e)
        if p > 0:
            mdd = max(mdd, (p - e) / p * 100)
    final = eq[-1]
    pnl = (final - capital) / capital * 100
    calmar = pnl / mdd if mdd > 0 else 0.0
    return {"final": round(final, 2), "pnl_pct": round(pnl, 2),
            "maxdd_pct": round(mdd, 2), "calmar": round(calmar, 2)}


results = {}
for tf, label in [("1d", "2y"), ("4h", "90d")]:
    candles = bt.fetch_ohlcv(bt.ccxt.kraken(), "SOL/EUR", tf, 721)
    cd = COOLDOWN_CANDLES[tf]

    base = bt.sim_grid(candles, LEVELS, SPREAD, FEE, SLIPPAGE, CAPITAL, MIN_NOTIONAL)
    sl = sim_grid_sl_cooldown(candles, LEVELS, SPREAD, FEE, SLIPPAGE, CAPITAL,
                              MIN_NOTIONAL, SL_PCT, cd)

    mb = metrics(base["eq"], CAPITAL)
    ms = metrics(sl["eq"], CAPITAL)
    results[tf] = {"baseline": {**mb, "RT": base["round_trips"], "fees_eur": round(base["fees"], 2)},
                   "sl_cooldown": {**ms, "RT": sl["round_trips"], "fees_eur": round(sl["fees"], 2)}}

    print(f"\n=== SOL/EUR {tf} ({label}, {len(candles)} candele) — spread {SPREAD*100:.0f}%, {LEVELS} liv, SL {SL_PCT*100:.0f}%, cooldown {cd} ===")
    print(f"  BASELINE grid:  final={mb['final']}€ pnl={mb['pnl_pct']}% maxDD={mb['maxdd_pct']}% Calmar={mb['calmar']} RT={base['round_trips']} fees={base['fees']:.2f}€")
    print(f"  SL+cooldown:    final={ms['final']}€ pnl={ms['pnl_pct']}% maxDD={ms['maxdd_pct']}% Calmar={ms['calmar']} RT={sl['round_trips']} fees={sl['fees']:.2f}€")
    winner = "SL+COOLDOWN" if ms["calmar"] > mb["calmar"] else "BASELINE"
    print(f"  VERDICT (risk-adjusted): {winner}")

with open("/home/sergio/alpha-omega-trading/scripts/experiment_sl_cooldown_results.json", "w") as f:
    json.dump({"meta": {"symbol": "SOL/EUR", "spread_pct": SPREAD, "levels": LEVELS,
                        "sl_pct": SL_PCT, "cooldown_candles": COOLDOWN_CANDLES,
                        "fee": FEE, "slippage": SLIPPAGE, "capital": CAPITAL},
               "results": results}, f, indent=2)
print("\nSalvato: scripts/experiment_sl_cooldown_results.json")

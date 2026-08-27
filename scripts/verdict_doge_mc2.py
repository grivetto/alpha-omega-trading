#!/usr/bin/env python3
"""Verdict numerico sul bot LIVE DOGE mc2sub1 — parametri reali da node_mc2.yaml.

Config live: DOGE/EUR, mode okx, capital 1.9, levels 2, buy 2%, sell 3%,
fee 0.001 (OKX), tick 30s. Confronto: grid asimmetrica (compra -2%, vende +3%)
vs buy_hold, su 1d 2y Kraken (proxy). Nessuna chiave, nessun ordine.
"""
import sys, json, importlib.util

spec = importlib.util.spec_from_file_location("bt", "/home/sergio/alpha-omega-trading/scripts/backtest.py")
if spec is None or spec.loader is None:
    sys.exit("Impossibile caricare backtest.py")
bt = importlib.util.module_from_spec(spec)
sys.modules["bt"] = bt
spec.loader.exec_module(bt)

# Parametri LIVE da node_mc2.yaml (DOGE/EUR)
CAPITAL = 1.9          # capital reale del bot
LEVELS = 2             # livelli
BUY_DIST = 0.02        # compra 2% sotto
SELL_DIST = 0.03       # vende 3% sopra (asimmetrica)
FEE = 0.001            # OKX taker/maker flat
SLIPPAGE = 0.0005
MIN_NOTIONAL = 0.4     # ~10 DOGE (~0.35 EUR) su OKX

# Grid asimmetrica: livelli DISTINTI (lvl 1 a -2%, lvl 2 a -4% dal mid);
# ogni livello vende a buy_price*(1 + sell_dist + buy_dist) (+3% dal mid).
def sim_grid_asym(candles, levels, buy_dist, sell_dist, fee, slippage, capital, min_notional):
    mid0 = candles[0][4]
    buy_prices = [mid0 * (1 - buy_dist * (lv + 1)) for lv in range(levels)]
    sell_prices = [bp * (1 + sell_dist + buy_dist) for bp in buy_prices]
    base, quote = 0.0, capital
    state = [None] * levels  # (qty, buy_price, sell_price)
    fees_total = 0.0
    rt = 0
    for i in range(1, len(candles)):
        low, high = candles[i][3], candles[i][2]
        for lv in range(levels):
            if state[lv] is None and low <= buy_prices[lv] and quote >= min_notional:
                notional = quote * 0.5
                qty = notional / buy_prices[lv] * (1 - fee)
                base += qty
                quote -= notional
                fees_total += notional * fee
                state[lv] = (qty, buy_prices[lv], buy_prices[lv] * (1 + sell_dist + buy_dist))
            elif state[lv] is not None and high >= state[lv][2]:
                qty, bp, sp = state[lv]
                gross = qty * sp * (1 - fee)
                quote += gross
                base -= qty
                fees_total += qty * sp * fee
                rt += 1
                state[lv] = None
    close = candles[-1][4]
    equity = quote + base * close
    return {"final_eur": round(equity, 2), "pnl_pct": round((equity - capital) / capital * 100, 2),
            "rt": rt, "fees_eur": round(fees_total, 4)}

candles = bt.fetch_ohlcv(bt.ccxt.kraken(), "DOGE/EUR", "1d", 721)
print(f"DOGE/EUR 1d: {len(candles)} candele [{candles[0][0]} -> {candles[-1][0]}]")

bh = bt.sim_buy_hold(candles, FEE, SLIPPAGE, CAPITAL)
bh_pnl = (bh["final"] - CAPITAL) / CAPITAL * 100
print(f"\nBUY_HOLD (fee OKX 0.1%): final={bh['final']:.2f}€ pnl={bh_pnl:+.2f}%")

g = sim_grid_asym(candles, LEVELS, BUY_DIST, SELL_DIST, FEE, SLIPPAGE, CAPITAL, MIN_NOTIONAL)
print(f"GRID LIVE DOGE (2 liv, buy 2%/sell 3%, cap 1.9€): final={g['final_eur']}€ pnl={g['pnl_pct']}% RT={g['rt']} fees={g['fees_eur']}€")

# Quanto ci mette a fare 1€? (tempo per guadagnare 1€ con cap 1.9)
pnl_eur = g['final_eur'] - CAPITAL
print(f"\nVERDICT: PnL = {pnl_eur:+.2f}€ su 2 anni con cap 1.9€. "
      f"{'REDDITIZIO ma rumore (sotto 1€/2y)' if pnl_eur > 0 else 'PERDENTE dopo fee'}")

# Stessa grid ma con capital 100€ (scalato) per vedere se il design regge
g100 = sim_grid_asym(candles, LEVELS, BUY_DIST, SELL_DIST, FEE, SLIPPAGE, 100.0, MIN_NOTIONAL)
print(f"\nSTESSA GRID cap 100€ (scalato): final={g100['final_eur']}€ pnl={g100['pnl_pct']}% RT={g100['rt']}")

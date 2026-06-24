#!/usr/bin/env python3
"""Debug Nuvola grid: trace why orders aren't placed."""
import sys, os, ccxt, math

sys.path.insert(0, '/home/sergio/denaro')

key = os.environ.get("BINANCE_API_KEY", "").strip()
sec = os.environ.get("BINANCE_API_SECRET", "").strip()

from denaro_v3.config import GridConfig, PRODUCTION
from denaro_v3.data_feeder import DataFeeder
from denaro_v3.circuit_breaker import CircuitBreaker
from denaro_v3.grid_engine import GridEngine

e = ccxt.binance({
    "apiKey": key, "secret": sec,
    "enableRateLimit": True,
    "options": {"defaultType": "spot"},
})
feeder = DataFeeder(e, PRODUCTION.api)
breaker = CircuitBreaker(PRODUCTION.risk)

# Check balances
b = feeder.get_balance()
print("=== BALANCE ===")
for k, v in sorted(b.items()):
    if isinstance(v, dict) and v.get("total", 0):
        print(f"  {k}: free={v.get('free',0)} total={v.get('total',0)}")

# Check market
e.load_markets()
mkt = e.market("DOGE/USDC")
print(f"\n=== MARKET ===")
print(f"  min_amount: {mkt['limits']['amount']['min']}")
print(f"  min_cost: {mkt['limits']['cost']['min']}")
print(f"  amount_step: {mkt['precision']['amount']}")
print(f"  price_step: {mkt['precision']['price']}")

# Test CB
breaker.update_equity(feeder.get_total_balance("USDC"))
print(f"\n=== CB ===")
print(f"  state: {breaker.state}")
print(f"  equity: {breaker._current_equity}")
print(f"  peak: {breaker._peak_equity}")

# Calculate levels
cfg = GridConfig(symbol="DOGE/USDC", base_asset="DOGE", quote_asset="USDC")
engine = GridEngine(cfg, feeder, breaker)
levels = engine.calculate_levels()
print(f"\n=== LEVELS ({len(levels)}) ===")
for lv in levels:
    print(f"  {lv.side.value:4s} {lv.amount:.1f} @ {lv.price:.5f}")

# Try placing each level manually
print("\n=== TRYING PLACEMENT ===")
for lv in levels:
    if lv.side.value == "buy":
        needed = lv.amount * lv.price
        bal = feeder.get_free_balance("USDC")
        print(f"  BUY: need={needed:.3f} USDC, have={bal:.3f} -> {'OK' if bal >= needed else 'SKIP (no USDC)'}")
        if bal < needed:
            continue
    else:
        bal = feeder.get_free_balance("DOGE")
        print(f"  SELL: need={lv.amount:.1f} DOGE, have={bal:.1f} -> {'OK' if bal >= lv.amount else 'SKIP'}")
        if bal < lv.amount:
            continue
    
    allowed, reason, max_amt = breaker.can_trade(lv.amount * lv.price)
    print(f"    CB: allowed={allowed} reason={reason} max_amt={max_amt}")
    if not allowed:
        continue
    
    try:
        if lv.side.value == "buy":
            o = e.create_limit_buy_order("DOGE/USDC", lv.amount, lv.price)
        else:
            o = e.create_limit_sell_order("DOGE/USDC", lv.amount, lv.price)
        print(f"    PLACED: id={o.get('id')} status={o.get('status')}")
    except Exception as ex:
        print(f"    FAILED: {ex}")

# Summary
open_orders = e.fetch_open_orders("DOGE/USDC")
print(f"\n=== OPEN ORDERS: {len(open_orders)} ===")
for o in open_orders:
    print(f"  {o['side']} {o['amount']} @ {o['price']} | id={o['id']}")

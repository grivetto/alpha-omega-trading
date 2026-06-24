#!/usr/bin/env python3
"""Sell all of a crypto asset into USDC via market order."""
import ccxt, os, sys

asset = sys.argv[1]  # e.g. SOL, DOGE, ADA
key = os.environ.get("BINANCE_API_KEY", "").strip()
sec = os.environ.get("BINANCE_API_SECRET", "").strip()

e = ccxt.binance({
    "apiKey": key, "secret": sec,
    "enableRateLimit": True,
    "options": {"defaultType": "spot"},
})

pair = f"{asset}/USDC"
b = e.fetch_balance()
free = float(b.get(asset, {}).get("free", 0) or 0)

if free <= 0:
    print(f"No {asset} to sell")
    sys.exit(0)

# Get current price
ticker = e.fetch_ticker(pair)
price = ticker["last"]
value = free * price
print(f"Selling {free:.6f} {asset} @ ~${price:.4f} = ~${value:.2f}")

# Round amount to exchange precision
mkt = e.market(pair)
step = mkt["precision"]["amount"]
min_amt = mkt["limits"]["amount"]["min"] or 0

if step and step < 1:
    amount = (free // step) * step  # floor to step
else:
    amount = free

amount = max(min_amt, amount)
print(f"Rounded amount: {amount:.6f}")

try:
    order = e.create_market_sell_order(pair, amount)
    print(f"SOLD: {order['side']} {order['amount']} {asset} @ avg {order.get('price', 'market')} | status={order['status']}")
    
    # Check new USDC balance
    b2 = e.fetch_balance()
    usdc = b2.get("USDC", {}).get("total", 0)
    print(f"USDC after: ${usdc:.2f}")
except Exception as ex:
    print(f"FAILED: {ex}")

#!/usr/bin/env python3
"""Test sell order on Nuvola."""
import ccxt, os, math

key = os.environ.get("BINANCE_API_KEY", "").strip()
sec = os.environ.get("BINANCE_API_SECRET", "").strip()

e = ccxt.binance({
    "apiKey": key, "secret": sec,
    "enableRateLimit": True,
    "options": {"defaultType": "spot"},
})
e.load_markets()
mkt = e.market("DOGE/USDC")
print("min_amount:", mkt["limits"]["amount"]["min"])
print("min_cost:", mkt["limits"]["cost"]["min"])
print("amount_precision:", mkt["precision"]["amount"])
print("price_precision:", mkt["precision"]["price"])

amt = 100.0
price = 0.075
step = mkt["precision"]["amount"]
if step and step < 1:
    amt = math.floor(amt / step) * step
print(f"Test SELL: {amt} DOGE @ {price}")

try:
    o = e.create_limit_sell_order("DOGE/USDC", amt, price)
    print(f"Order placed: id={o.get('id')} status={o.get('status')}")
    e.cancel_order(o["id"], "DOGE/USDC")
    print("Cancelled test order")
except Exception as ex:
    print(f"FAILED: {ex}")

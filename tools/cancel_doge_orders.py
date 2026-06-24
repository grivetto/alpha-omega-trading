import ccxt, os
key = os.environ.get("BINANCE_API_KEY", "").strip()
sec = os.environ.get("BINANCE_API_SECRET", "").strip()
e = ccxt.binance({"apiKey": key, "secret": sec, "enableRateLimit": True, "options": {"defaultType": "spot"}})
ords = e.fetch_open_orders("DOGE/USDC")
for o in ords:
    e.cancel_order(o["id"], "DOGE/USDC")
    print(f"Cancelled {o['side']} {o['amount']} @ {o['price']}")
print(f"Total: {len(ords)}")

import ccxt, os, sys
key = os.environ.get("BINANCE_API_KEY", "").strip()
sec = os.environ.get("BINANCE_API_SECRET", "").strip()
pair = sys.argv[1] if len(sys.argv) > 1 else None
e = ccxt.binance({"apiKey": key, "secret": sec, "enableRateLimit": True, "options": {"defaultType": "spot"}})
if pair:
    orders = e.fetch_open_orders(pair)
else:
    orders = e.fetch_open_orders()
for o in orders:
    e.cancel_order(o["id"], o.get("symbol", pair))
    print(f"Cancelled {o.get('symbol','?')} {o['side']} {o['amount']} @ {o['price']}")
print(f"Total cancelled: {len(orders)}")

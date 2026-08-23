#!/usr/bin/env python3
"""Quick Kraken API key verification — loads .env, checks balance + ticker."""
import os, sys, json
from pathlib import Path
try:
    import ccxt
except ImportError:
    print("ERR: ccxt not installed")
    sys.exit(1)

# Load .env from script directory
env = {}
env_path = Path(__file__).parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")

api_key = env.get("KRAKEN_API", "")
api_secret = env.get("KRAKEN_SECRET", "")

if not api_key or not api_secret:
    print("ERR: KRAKEN_API or KRAKEN_SECRET missing from .env")
    sys.exit(1)

try:
    ex = ccxt.kraken({"apiKey": api_key, "secret": api_secret, "enableRateLimit": True})
    ex.load_markets()
except Exception as e:
    print(f"ERR: exchange init failed: {e}")
    sys.exit(1)

errors = []

# Balance
try:
    bal = ex.fetch_balance()
    eur = float(bal.get("total", {}).get("EUR", 0) or 0)
    doge = float(bal.get("total", {}).get("DOGE", 0) or 0)
    print(f"BALANCE: EUR={eur:.2f} DOGE={doge:.0f}")
except Exception as e:
    errors.append(f"balance: {e}")
    eur, doge = 0.0, 0.0

# Ticker
try:
    ticker = ex.fetch_ticker("DOGE/EUR")
    price = float(ticker["last"])
    equity = eur + doge * price
    print(f"DOGE/EUR: price={price:.6f} equity=€{equity:.2f}")
except Exception as e:
    errors.append(f"ticker: {e}")

# Open orders
try:
    orders = ex.fetch_open_orders("DOGE/EUR")
    print(f"OPEN ORDERS: {len(orders)}")
    for o in orders[:5]:
        print(f"  {o['side']} {o['amount']} @ {o['price']} id={o['id']}")
except Exception as e:
    errors.append(f"orders: {e}")

if errors:
    print(f"\nWARNINGS: {'; '.join(errors)}")
else:
    print("\nKRAKEN API: OK ✓")

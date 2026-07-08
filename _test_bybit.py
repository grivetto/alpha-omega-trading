#!/usr/bin/env python3
"""Test Bybit API key on MARCODG1."""
import sys, os
sys.path.insert(0, '/home/marco/denaro')
from pathlib import Path

env_path = Path('/home/marco/denaro/.env')
env = {}
for line in env_path.read_text().splitlines():
    line = line.strip()
    if line and not line.startswith('#') and '=' in line:
        k, v = line.split('=', 1)
        env[k.strip()] = v.strip().strip("'\"")

api_key = env.get('BYBIT_API', '')
api_secret = env.get('BYBIT_SECRET', '')

if not api_key or not api_secret:
    print('ERR: missing BYBIT_API or BYBIT_SECRET')
    sys.exit(1)

print(f'API Key: {api_key[:8]}...')
print(f'Secret: {api_secret[:8]}...')

import ccxt
try:
    ex = ccxt.bybit({'apiKey': api_key, 'secret': api_secret, 'enableRateLimit': True})
    ex.load_markets()
    bal = ex.fetch_balance()
    usdt = float(bal.get('total', {}).get('USDT', 0) or 0)
    print(f'BALANCE: USDT={usdt:.2f}')
    ticker = ex.fetch_ticker('SOL/USDT')
    price = float(ticker['last'])
    print(f'SOL/USDT: price={price:.2f}')
    orders = ex.fetch_open_orders('SOL/USDT') or []
    print(f'OPEN ORDERS: {len(orders)}')
    print()
    print('BYBIT API: OK')
except ccxt.AuthenticationError as e:
    print(f'ERR: AuthenticationError: {e}')
except Exception as e:
    print(f'ERR: {type(e).__name__}: {e}')

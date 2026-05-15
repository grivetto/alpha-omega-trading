#!/usr/bin/env python3
"""Sell remaining assets to EUR."""
import ccxt, os, time
from dotenv import load_dotenv
load_dotenv(os.path.expanduser('~/denaro/.env'))

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

pairs = [('SOL', 0.307), ('ETH', 0.01), ('BNB', 0.08)]
for asset, qty in pairs:
    try:
        o = exchange.create_market_sell_order(f'{asset}/EUR', qty)
        print(f'{asset}/EUR: venduto {qty} OK order {o["id"][:10]}')
    except Exception as e:
        print(f'{asset}/EUR: {str(e)[:120]}')
    time.sleep(0.5)

time.sleep(2)
b = exchange.fetch_balance()
tot = b.get('total', {})
eur = float(tot.get('EUR', 0))
usdt = float(tot.get('USDT', 0))
remaining = [(a, float(v)) for a,v in tot.items() if float(v) > 0.001 and a not in ('EUR', 'USDT')]

print(f'\nEUR: {eur:.2f}')
print(f'USDT: {usdt:.2f}')
for a,v in remaining:
    print(f'  {a}: {v}')

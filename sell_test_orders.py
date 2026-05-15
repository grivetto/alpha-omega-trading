#!/usr/bin/env python3
"""Sell test positions opened during debugging."""
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
import ccxt, os

ex = ccxt.binance({
    'apiKey': os.environ['BINANCE_API_KEY'],
    'secret': os.environ['BINANCE_API_SECRET'],
    'options': {'defaultType': 'spot'}
})

balance = ex.fetch_balance()
bns = float(balance.get('BNB', {}).get('free', 0))
doge = float(balance.get('DOGE', {}).get('free', 0))
ada = float(balance.get('ADA', {}).get('free', 0))
eur = float(balance.get('EUR', {}).get('free', 0))
print(f'BALANCE - BNB: {bns}, DOGE: {doge}, ADA: {ada}, EUR free: {eur:.2f}')

sold = 0
if bns > 0.001:
    r = ex.create_market_sell_order('BNB/EUR', bns)
    filled = r['filled'] if 'filled' in r else bns
    print(f'SOLD BNB: {filled}')
    sold += 1
if doge > 10:
    r = ex.create_market_sell_order('DOGE/EUR', doge)
    filled = r['filled'] if 'filled' in r else doge
    print(f'SOLD DOGE: {filled}')
    sold += 1
if ada > 1:
    r = ex.create_market_sell_order('ADA/EUR', ada)
    filled = r['filled'] if 'filled' in r else ada
    print(f'SOLD ADA: {filled}')
    sold += 1

if sold == 0:
    print('No test positions to sell')
else:
    balance = ex.fetch_balance()
    eur = float(balance.get('EUR', {}).get('free', 0))
    print(f'FINAL EUR free: {eur:.2f}')

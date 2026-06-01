#!/usr/bin/env python3
"""Quick status check using Denaro's actual API keys from .env"""
import os, sys, json
sys.path.insert(0, '/home/sergio/denaro')
os.chdir('/home/sergio/denaro')

from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')

import ccxt
from datetime import datetime

exchange = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'},
})

# Fetch balances
bal = exchange.fetch_balance()
prices = {}

# Get EUR/USDT for stablecoin conversion
try:
    eurusd_ticker = exchange.fetch_ticker('EUR/USDT')
    eurusd = eurusd_ticker['last']
except:
    eurusd = 1.08  # fallback

# Tracked assets
assets = ['EUR', 'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'DOGE', 'XRP', 'DOT', 'AVAX', 'LINK', 'ATOM', 'NEAR', 'APT', 'USDC', 'USDT']

for sym in assets:
    if sym == 'EUR':
        prices[sym] = 1.0
        continue
    if sym in ['USDC', 'USDT']:
        prices[sym] = 1.0 / eurusd
        continue
    try:
        t = exchange.fetch_ticker(f'{sym}/EUR')
        prices[sym] = t['last']
    except:
        try:
            t = exchange.fetch_ticker(f'{sym}/USDT')
            prices[sym] = t['last'] / eurusd
        except:
            prices[sym] = 0

# Build portfolio
total_eur = 0.0
holdings = []
for sym in assets:
    free = bal['free'].get(sym, 0)
    used = bal.get('used', {}).get(sym, 0) if isinstance(bal.get('used'), dict) else 0
    total_hold = free + used
    if total_hold > 0.00001:
        price = prices.get(sym, 0)
        val = total_hold * price
        total_eur += val
        holdings.append({
            'asset': sym,
            'free': round(free, 6),
            'locked': round(used, 6),
            'total': round(total_hold, 6),
            'price_eur': round(price, 6),
            'value_eur': round(val, 2)
        })

# Open orders
try:
    open_orders = exchange.fetch_open_orders()
except Exception as e:
    open_orders = []
    print(f"Order fetch error: {e}", file=sys.stderr)

buy_orders = [o for o in open_orders if o['side'] == 'buy']
sell_orders = [o for o in open_orders if o['side'] == 'sell']

# Trades today
today = datetime.utcnow().strftime('%Y-%m-%d')
try:
    all_trades = exchange.fetch_my_trades('ETH/BTC', limit=50)
    today_trades = [t for t in all_trades if t['datetime'].startswith(today)]
except:
    today_trades = []

result = {
    'timestamp': datetime.utcnow().isoformat() + 'Z',
    'total_eur': round(total_eur, 2),
    'total_crypto_eur': round(sum(h['value_eur'] for h in holdings if h['asset'] != 'EUR'), 2),
    'eur_free': round(next((h['free'] for h in holdings if h['asset'] == 'EUR'), 0), 2),
    'eur_locked': round(next((h['locked'] for h in holdings if h['asset'] == 'EUR'), 0), 2),
    'holdings': holdings,
    'open_orders': {
        'total': len(open_orders),
        'buy': len(buy_orders),
        'sell': len(sell_orders),
        'buy_eur_locked': round(sum(float(o['price']) * float(o['remaining']) / eurusd for o in buy_orders), 2),
    },
    'prices': {k: round(v, 6) for k, v in prices.items() if v > 0},
    'today_trades': len(today_trades),
    'eurusd': round(eurusd, 4),
}

print(json.dumps(result, indent=2))

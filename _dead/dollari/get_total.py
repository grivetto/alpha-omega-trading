import ccxt
import os
import requests
from dotenv import load_dotenv

load_dotenv('/home/sergio/denaro/.env')
load_dotenv('/home/sergio/denaro/.env.bitget')
load_dotenv('/home/sergio/denaro/.env.mexc')

# --- PREZZI ---
try:
    btc_price = float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT").json()['price'])
except: btc_price = 65000

# --- BINANCE ---
binance = ccxt.binance({
    'apiKey': os.getenv('BINANCE_API_KEY'),
    'secret': os.getenv('BINANCE_API_SECRET'),
})
try:
    bal_b = binance.fetch_balance()
    eur = float(bal_b.get('EUR', {}).get('total', 0))
    btc = float(bal_b.get('BTC', {}).get('total', 0))
    usdt = float(bal_b.get('USDT', {}).get('total', 0))
    # Prendi tutte le altcoins rilevanti
    b_total = 0
    for coin, info in bal_b.get('total', {}).items():
        if float(info) > 0:
            if coin == 'EUR': b_total += float(info) * 1.08
            elif coin == 'USDT' or coin == 'USDC' or coin == 'FDUSD': b_total += float(info)
            else:
                try: p = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT").json()['price'])
                except: p = 0
                b_total += float(info) * p
    print(f"Binance Total USDT: {b_total:.2f}")
except Exception as e: print("Binance Error:", e)

# --- MEXC ---
mexc = ccxt.mexc({
    'apiKey': os.getenv('MEXC_API_KEY'),
    'secret': os.getenv('MEXC_API_SECRET'),
})
try:
    bal_m = mexc.fetch_balance()
    m_total = 0
    for coin, info in bal_m.get('total', {}).items():
        if float(info) > 0:
            if coin == 'USDT' or coin == 'USDC': m_total += float(info)
            else:
                try: p = float(mexc.fetch_ticker(f"{coin}/USDT")['last'])
                except: p = 0
                m_total += float(info) * p
    print(f"MEXC Total USDT: {m_total:.2f}")
except Exception as e: print("MEXC Error:", e)

# --- BITGET ---
bitget = ccxt.bitget({
    'apiKey': os.getenv('BITGET_API_KEY'),
    'secret': os.getenv('BITGET_API_SECRET'),
    'password': os.getenv('BITGET_PASSWORD'),
    'options': {'defaultType': 'swap'}
})
try:
    bg_total = bitget.fetch_balance()['USDT']['total']
    print(f"Bitget Total USDT: {bg_total:.2f}")
except Exception as e: print("Bitget Error:", e)


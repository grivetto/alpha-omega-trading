import ccxt, requests, time, json, os
from dotenv import load_dotenv

load_dotenv('/home/sergio/denaro/.env')
load_dotenv('/home/sergio/denaro/.env.bitget')
load_dotenv('/home/sergio/denaro/.env.mexc')

binance = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
mexc = ccxt.mexc({'apiKey': os.getenv('MEXC_API_KEY'), 'secret': os.getenv('MEXC_API_SECRET'), 'enableRateLimit': True})
bitget = ccxt.bitget({'apiKey': os.getenv('BITGET_API_KEY'), 'secret': os.getenv('BITGET_API_SECRET'), 'password': os.getenv('BITGET_PASSWORD'), 'options': {'defaultType': 'swap'}, 'enableRateLimit': True})

while True:
    total_usdt = 0.0
    try:
        try:
            btc_price = float(requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT", timeout=5).json()['price'])
        except: btc_price = 65000
        
        try:
            bal_b = binance.fetch_balance()
            for coin, info in bal_b.get('total', {}).items():
                if float(info) > 0:
                    if coin == 'EUR': total_usdt += float(info) * 1.08
                    elif coin in ['USDT', 'USDC', 'FDUSD']: total_usdt += float(info)
                    else:
                        try: p = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=2).json()['price'])
                        except: p = 0
                        total_usdt += float(info) * p
        except: pass
        
        try:
            bal_m = mexc.fetch_balance()
            for coin, info in bal_m.get('total', {}).items():
                if float(info) > 0:
                    if coin in ['USDT', 'USDC']: total_usdt += float(info)
                    else:
                        try: p = float(requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={coin}USDT", timeout=2).json()['price'])
                        except: p = 0
                        total_usdt += float(info) * p
        except: pass
        
        try:
            total_usdt += float(bitget.fetch_balance()['USDT']['total'])
        except: pass
        
        with open("/home/sergio/denaro/total_usdt_cache.json", "w") as cf:
            json.dump({'total_usdt': total_usdt, 'ts': time.time()}, cf)
            
    except Exception as e:
        print("Error cache:", e)
        
    time.sleep(30)
# CACHE_UPD.log

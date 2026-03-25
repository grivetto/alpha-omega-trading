import time
import json
import os
from datetime import datetime
from binance.client import Client
from dotenv import load_dotenv

# VWAP Reversion Sniper - Zero OOM
# Cerca deviazioni eccessive dal VWAP intraday per mean-reversion.

SYMBOL = "BTCEUR"
DEV_THRESHOLD = 0.02 # 2% deviation
POLL_INTERVAL = 30
STATUS_FILE = "vwap_status.json"

BASE_DIR = '/home/sergio/.openclaw/workspace/denaro'
load_dotenv(os.path.join(BASE_DIR, '.env'))
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

def get_vwap_and_price():
    try:
        # Fetching 1m candles for the current day to approximate VWAP
        klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_1MINUTE, limit=500)
        if not klines: return None, None
        
        cumulative_vp = 0
        cumulative_v = 0
        current_price = float(klines[-1][4])
        
        for candle in klines:
            high = float(candle[2])
            low = float(candle[3])
            close = float(candle[4])
            volume = float(candle[5])
            typical_price = (high + low + close) / 3
            cumulative_vp += typical_price * volume
            cumulative_v += volume
            
        vwap = cumulative_vp / cumulative_v if cumulative_v > 0 else current_price
        return vwap, current_price
    except Exception as e:
        print(f"Error fetching data: {e}")
        return None, None

def main():
    print(f"[{datetime.now()}] Starting VWAP Reversion Sniper on {SYMBOL}")
    while True:
        vwap, price = get_vwap_and_price()
        if vwap and price:
            deviation = (price - vwap) / vwap
            signal = "NEUTRAL"
            if deviation > DEV_THRESHOLD:
                signal = "SHORT_SIGNAL"
            elif deviation < -DEV_THRESHOLD:
                signal = "LONG_SIGNAL"
                
            status = {
                "symbol": SYMBOL,
                "price": price,
                "vwap": round(vwap, 2),
                "deviation_pct": round(deviation * 100, 2),
                "signal": signal,
                "timestamp": str(datetime.now())
            }
            with open(os.path.join(BASE_DIR, STATUS_FILE), "w") as f:
                json.dump(status, f)
            print(f"[{datetime.now()}] {SYMBOL} Price: {price}, VWAP: {round(vwap,2)}, Dev: {round(deviation*100,2)}% -> {signal}")
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()

import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

# CONFIGURAZIONE FLASH (1 MINUTO)
SYMBOLS = ["AVAXBTC", "DOGEBTC", "SOLBTC", "ETHBTC", "PEPEBTC", "SHIBBTC", "FETBTC", "AGIXBTC"]
RISK_BTC = 0.0012 # ~70 EUR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger("FLASH")

def main():
    logger.info("⚡ FLASH SURGE UNIT ACTIVATED - TARGET: 10 MIN PROFIT")
    positions = {}
    
    while True:
        try:
            for s in SYMBOLS:
                klines = client.get_klines(symbol=s, interval='1m', limit=20)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                
                # Segnale Flash: Prezzo > EMA 9 + RSI > 50 (Momento puro)
                ema = ta.ema(df['c'], length=9).iloc[-1]
                rsi = ta.rsi(df['c'], length=7).iloc[-1]
                price = df['c'].iloc[-1]
                
                if rsi > 55 and price > ema and s not in positions:
                    logger.info(f"🚀 FLASH ENTRY: {s} @ {price}")
                    try:
                        client.create_order(symbol=s, side='BUY', type='MARKET', quoteOrderQty=round(RISK_BTC, 6))
                        positions[s] = {'entry': price, 'time': time.time()}
                    except: pass

                if s in positions:
                    pnl = (price - positions[s]['entry']) / positions[s]['entry']
                    # Uscita rapidissima: 0.8% profit o 5 minuti di vita
                    if pnl >= 0.008 or pnl <= -0.012 or (time.time() - positions[s]['time'] > 300):
                        try:
                            asset = s.replace('BTC', '')
                            bal = float(client.get_asset_balance(asset=asset)['free'])
                            client.create_order(symbol=s, side='SELL', type='MARKET', quantity=bal)
                            logger.info(f"✅ FLASH EXIT: {s} PnL: {pnl:.2%}")
                            del positions[s]
                            with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                f.write(f"{(RISK_BTC * pnl * 59000):.2f}")
                        except: pass
            time.sleep(15)
        except: time.sleep(30)

if __name__ == "__main__":
    main()

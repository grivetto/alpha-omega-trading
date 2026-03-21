import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime
import sys

# --- CONFIGURAZIONE ---
load_dotenv()

API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Symbols to trade
SYMBOLS = ["BTCEUR", "ETHEUR", "SOLEUR", "BNBEUR"]

# Technical Parameters (AGGRESSIVE SCALPING)
TIMEFRAME = Client.KLINE_INTERVAL_3MINUTE
BB_PERIOD = 20
BB_STD = 1.8

# Risk Management
POSITION_SIZE_EUR = 20.0  # UPDATED to 20.0 EUR per Sergey's capital allocation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('quant_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

STATUS_FILE = '/root/.openclaw/workspace/quant_status.json'

def update_status(data):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error updating status: {e}")

def get_data(client, symbol):
    try:
        klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=100)
        df = pd.DataFrame(klines, columns=['ts', 'open', 'high', 'low', 'close', 'volume', 'close_ts', 'qav', 'num_trades', 'taker_base', 'taker_quote', 'ignore'])
        df['close'] = pd.to_numeric(df['close'])
        df['volume'] = pd.to_numeric(df['volume'])
        return df
    except Exception as e:
        logger.error(f"Error fetching data for {symbol}: {e}")
        return None

def get_eur_balance(client):
    try:
        balance = client.get_asset_balance(asset='EUR')
        return float(balance['free']) if balance else 0.0
    except Exception as e:
        logger.error(f"Error getting EUR balance: {e}")
        return 0.0

def main():
    if not API_KEY or not API_SECRET:
        logger.error("API Keys missing")
        sys.exit(1)
        
    client = Client(API_KEY, API_SECRET)
    logger.info("Quant Bot Started")
    
    while True:
        try:
            eur_bal = get_eur_balance(client)
            for symbol in SYMBOLS:
                df = get_data(client, symbol)
                if df is not None:
                    price = df['close'].iloc[-1]
                    logger.info(f"{symbol}: {price}")
            
            update_status({
                "last_run": datetime.now().isoformat(),
                "status": "running",
                "balance": eur_bal
            })
            time.sleep(60)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

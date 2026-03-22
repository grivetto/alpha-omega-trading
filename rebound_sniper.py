import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

# --- CONFIGURAZIONE ---
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Monete solide in iper-venduto (Oversold)
SNIPE_LIST = ["BTCEUR", "ETHEUR", "SOLEUR", "BNBEUR"]
TIMEFRAME = '5m'
RSI_BUY = 32.0          # Iper-venduto
RSI_PERIOD = 14
TARGET_REBOUND = 0.025  # 2.5% rimbalzo
STOP_LOSS = 0.035      # 3.5% sicurezza
RISK_EUR = 60.0        # Alzato da 20.0 a 60.0 per trade

STATUS_FILE = '/root/.openclaw/workspace/sniper_status.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler('rebound_sniper.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def update_status(data):
    try:
        with open(STATUS_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Error status: {e}")

def main():
    client = Client(API_KEY, API_SECRET)
    logger.info("🎯 REBOUND SNIPER ACTIVATED - OVERSOLD SNIPING")
    
    positions = {}

    while True:
        try:
            for symbol in SNIPE_LIST:
                # Recupero dati
                klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=100)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                
                # Calcolo RSI con pandas_ta
                rsi = ta.rsi(df['c'], length=RSI_PERIOD).iloc[-1]
                price = df['c'].iloc[-1]
                
                # SNIPE DETECTION
                if rsi <= RSI_BUY and symbol not in positions:
                    logger.info(f"🎯 SNIPE! {symbol} RSI: {rsi:.1f} (Iper-venduto)")
                    # Esecuzione finta per ora, logga come live se Sergio conferma fondi
                    logger.info(f"🛒 BUY {symbol} @ {price} (Fondi permettendo - Risk {RISK_EUR}€)")
                    positions[symbol] = {'entry': price, 'qty': RISK_EUR / price}

                # GESTIONE POSIZIONI ESISTENTI
                if symbol in positions:
                    entry = positions[symbol]['entry']
                    pnl = (price - entry) / entry
                    if pnl >= TARGET_REBOUND or pnl <= -STOP_LOSS:
                        reason = "TAKE PROFIT" if pnl >= TARGET_REBOUND else "STOP LOSS"
                        logger.info(f"✅ {reason} {symbol} @ {price} | PnL: {pnl:.2%}")
                        del positions[symbol]
            
            update_status({
                "time": datetime.now().isoformat(),
                "active_snipes": len(positions),
                "targets": SNIPE_LIST,
                "status": "Waiting for dip..."
            })
            time.sleep(30)
        except Exception as e:
            logger.error(f"Sniper Loop Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

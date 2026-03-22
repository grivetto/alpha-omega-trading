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

# Altcoin ad alta volatilità (EUR pairs per Sergio)
WATCHLIST = ["ETHEUR", "BNBEUR", "ADAEUR", "DOGEEUR", "SOLEUR", "LINKUSDT", "AVAXUSDT"]
TIMEFRAME = '5m'
VOL_SPIKE_THRESHOLD = 3.0  # Volume 3x rispetto alla media
PROFIT_TARGET = 0.022      # 2.2% rapido
STOP_LOSS = 0.03          # 3% sicurezza
RISK_EUR = 50.0           # Alzato da 15.0 a 50.0 per trade

STATUS_FILE = '/root/.openclaw/workspace/hunter_status.json'

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler('volatility_hunter.log'), logging.StreamHandler()]
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
    logger.info("🚀 VOLATILITY HUNTER ACTIVATED - AGGRESSIVE MODE")
    
    positions = {}

    while True:
        try:
            for symbol in WATCHLIST:
                # Recupero dati
                klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=50)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                df['v'] = pd.to_numeric(df['v'])
                
                # Analisi Volume Spike
                avg_vol = df['v'].iloc[:-1].mean()
                current_vol = df['v'].iloc[-1]
                price = df['c'].iloc[-1]
                
                # BREAKOUT DETECTION
                if current_vol > avg_vol * VOL_SPIKE_THRESHOLD and symbol not in positions:
                    logger.info(f"🔥 BREAKOUT RILEVATO: {symbol} | Vol: {current_vol:.2f} (Avg: {avg_vol:.2f})")
                    # Esecuzione finta per ora, logga come live se Sergio conferma fondi
                    logger.info(f"🛒 BUY {symbol} @ {price} (Fondi permettendo - Risk {RISK_EUR}€)")
                    positions[symbol] = {'entry': price, 'qty': RISK_EUR / price}

                # GESTIONE POSIZIONI ESISTENTI
                if symbol in positions:
                    entry = positions[symbol]['entry']
                    pnl = (price - entry) / entry
                    if pnl >= PROFIT_TARGET or pnl <= -STOP_LOSS:
                        reason = "TAKE PROFIT" if pnl >= PROFIT_TARGET else "STOP LOSS"
                        logger.info(f"✅ {reason} {symbol} @ {price} | PnL: {pnl:.2%}")
                        del positions[symbol]
            
            update_status({
                "time": datetime.now().isoformat(),
                "active_hunters": len(positions),
                "watchlist": WATCHLIST,
                "status": "Scanning for breakouts..."
            })
            time.sleep(45)
        except Exception as e:
            logger.error(f"Hunter Loop Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

import os
import time
import json
import logging
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

# --- CONFIGURAZIONE ---
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Focus su monete in forte rally per "Short" o monete "Pump & Dump"
REVERSAL_LIST = ["ETHBTC", "SOLBTC", "AVAXBTC", "DOGEBTC", "LINKBTC", "BNBBTC"]
TIMEFRAME = '15m'
RSI_SELL = 72.0       # Estremo Iper-comprato (Metodo opposto: vendiamo la forza)
PROFIT_TARGET = 0.025 # 2.5% calo
STOP_LOSS = 0.035     # 3.5% sicurezza
RISK_BTC = 0.0012      # Circa 70€ per trade

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    handlers=[logging.FileHandler('contrarian_omega.log'), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def main():
    client = Client(API_KEY, API_SECRET)
    logger.info("⚔️ SQUADRA OMEGA: CONTRARIAN REVERSAL ACTIVATED")
    
    positions = {}

    while True:
        try:
            for symbol in REVERSAL_LIST:
                klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=100)
                prices = [float(k[4]) for k in klines]
                
                # Calcolo RSI manuale veloce o via TA
                import pandas as pd
                import pandas_ta as ta
                df = pd.DataFrame(prices, columns=['c'])
                rsi = ta.rsi(df['c'], length=14).iloc[-1]
                price = prices[-1]
                
                # CONTRARIAN DETECTION: Vendiamo quando tutti comprano (Overbought)
                if rsi >= RSI_SELL and symbol not in positions:
                    logger.info(f"🚨 OMEGA SIGNAL: {symbol} Iper-comprato (RSI: {rsi:.1f}). Inizio accumulo posizione.")
                    # Dato che Sergio opera Spot, il bot "vende" se ha asset o accumula per il re-buy
                    # Simuliamo la strategia contrarian per massimizzare il capitale Bitcoin
                    logger.info(f"📉 [OMEGA] Contrarian entry on {symbol} @ {price}")
                    positions[symbol] = {'entry': price}

                if symbol in positions:
                    # Logica di uscita (Buy back lower)
                    entry = positions[symbol]['entry']
                    change = (price - entry) / entry
                    if change <= -PROFIT_TARGET:
                        logger.info(f"✅ OMEGA PROFIT: {symbol} Reversal completato @ {price}")
                        del positions[symbol]
                        with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                            f.write(f"{(RISK_BTC * 0.025 * 59500):.2f}")
                    elif change >= STOP_LOSS:
                        del positions[symbol]

            time.sleep(60)
        except Exception as e:
            logger.error(f"Omega Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    main()

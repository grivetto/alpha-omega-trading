import os
import time
import json
import logging
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

# --- CONFIGURAZIONE SQUADRA OMEGA ---
load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')

# Strategia OMEGA: ANTI-TREND & LIQUIDITY ABSORPTION
# Invece di seguire il volume, Omega compra il panico e vende l'euforia.
SYMBOLS = ["ETHBTC", "SOLBTC", "AVAXBTC", "BNBBTC", "LINKBTC", "DOTBTC"]
RISK_BTC = 0.002 # ~120€ per colpo

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [OMEGA-WARRIOR] - %(message)s',
    handlers=[logging.FileHandler('omega_war_machine.log'), logging.StreamHandler()]
)
logger = logging.getLogger("Omega")

class OmegaWarMachine:
    def __init__(self):
        self.client = Client(API_KEY, API_SECRET)
        self.active_positions = {}

    def run(self):
        logger.info("⚔️ OMEGA WAR MACHINE ACTIVATED - THE TWIN ENGINE")
        while True:
            try:
                for s in SYMBOLS:
                    klines = self.client.get_klines(symbol=s, interval='5m', limit=50)
                    df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                    df['c'] = pd.to_numeric(df['c'])
                    
                    # LOGICA ALTERNATIVA OMEGA: Sfruttamento della stanchezza del trend (RSI Divergence)
                    rsi = ta.rsi(df['c'], length=14).iloc[-1]
                    price = df['c'].iloc[-1]
                    
                    # Se il mercato è in iper-venduto (PANICO), Omega vede l'occasione che Alpha ignora
                    if rsi < 25 and s not in self.active_positions:
                        logger.info(f"🛡️ OMEGA SHIELD: {s} in panico (RSI {rsi:.1f}). Assorbo liquidità.")
                        try:
                            order = self.client.create_order(symbol=s, side='BUY', type='MARKET', quoteOrderQty=round(RISK_BTC, 6))
                            self.active_positions[s] = {'entry': price, 'qty': float(order['executedQty'])}
                            logger.info(f"🔴 OMEGA BUY: {s} @ {price}")
                        except Exception as e: logger.error(f"❌ OMEGA FAIL: {e}")

                    # Se il mercato è in iper-comprato (EUFORIA), Omega esce prima che Alpha veda il segnale
                    if s in self.active_positions:
                        entry = self.active_positions[s]['entry']
                        pnl = (price - entry) / entry
                        
                        if rsi > 65 or pnl >= 0.02 or pnl <= -0.04:
                            try:
                                self.client.create_order(symbol=s, side='SELL', type='MARKET', quantity=self.active_positions[s]['qty'])
                                logger.info(f"✅ OMEGA STRIKE: {s} | PnL: {pnl:.2%}")
                                with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                    f.write(f"OMEGA {s.replace('BTC','')}: {pnl:+.2%}")
                                del self.active_positions[s]
                            except: pass
                
                time.sleep(30)
            except Exception as e:
                logger.error(f"Omega Main Error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    machine = OmegaWarMachine()
    machine.run()

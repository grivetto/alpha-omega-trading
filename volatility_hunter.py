import gc
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

# Altcoin ad alta volatilità (Coppie BTC per usare il capitale appena arrivato)
WATCHLIST = ["ETHBTC", "SOLBTC", "BNBBTC", "ADABTC", "DOGEBTC", "LINKBTC", "AVAXBTC"]
TIMEFRAME = '5m'
VOL_SPIKE_THRESHOLD = 2.5  # Sensibilità aumentata
PROFIT_TARGET = 0.022      # 2.2% rapido
STOP_LOSS = 0.04          # 4% sicurezza
RISK_BTC = 0.001           # Circa 60€ per trade

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
    logger.info("🚀 VOLATILITY HUNTER LIVE - BTC PAIRS MODE")
    
    positions = {}

    while True:
        try:
            for symbol in WATCHLIST:
                klines = client.get_klines(symbol=symbol, interval=TIMEFRAME, limit=50)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                df['v'] = pd.to_numeric(df['v'])
                
                avg_vol = df['v'].iloc[:-1].mean()
                current_vol = df['v'].iloc[-1]
                price = df['c'].iloc[-1]
                
                # BREAKOUT DETECTION (LIVE ORDERS ENABLED)
                if current_vol > avg_vol * VOL_SPIKE_THRESHOLD and symbol not in positions:
                    logger.info(f"🔥 BREAKOUT RILEVATO: {symbol} | Vol: {current_vol:.2f} (Avg: {avg_vol:.2f})")
                    try:
                        # Calcolo quantità in base alla moneta base (BTC)
                        # qty = 0.001 BTC / prezzo moneta (es. ETHBTC)
                        qty_to_buy = RISK_BTC / price
                        # Arrotondamento prudente (Binance richiede precisione specifica)
                        order = client.create_order(
                            symbol=symbol,
                            side='BUY',
                            type='MARKET',
                            quoteOrderQty=round(RISK_BTC, 6)
                        )
                        logger.info(f"🟢 LIVE BUY EXECUTED: {symbol} @ {price} BTC")
                        positions[symbol] = {'entry': price, 'qty': RISK_BTC / price}
                    except Exception as e:
                        logger.error(f"❌ FAILED BUY {symbol}: {e}")

                # GESTIONE POSIZIONI ESISTENTI
                if symbol in positions:
                    entry = positions[symbol]['entry']
                    pnl = (price - entry) / entry
                    if pnl >= PROFIT_TARGET or pnl <= -STOP_LOSS:
                        reason = "TAKE PROFIT" if pnl >= PROFIT_TARGET else "STOP LOSS"
                        try:
                            # Vendita al mercato
                            # Recuperiamo il saldo reale per sicurezza
                            asset_name = symbol.replace('BTC', '')
                            bal = float(client.get_asset_balance(asset=asset_name)['free'])
                            client.create_order(symbol=symbol, side='SELL', type='MARKET', quantity=bal)
                            logger.info(f"✅ {reason} {symbol} @ {price} | PnL: {pnl:.2%}")
                            del positions[symbol]
                            # Creiamo il flag per lo strike su Telegram
                            with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                f.write(f"{(RISK_BTC * pnl * 1.0):.2f}")
                        except Exception as e:
                            logger.error(f"❌ FAILED SELL {symbol}: {e}")
            
            update_status({
                "time": datetime.now().isoformat(),
                "active_hunters": len(positions),
                "watchlist": WATCHLIST,
                "status": "LIVE SCANNING (BTC PAIRS)"
            })
            gc.collect()
            time.sleep(30)
        except Exception as e:
            logger.error(f"Hunter Loop Error: {e}")
            gc.collect()
            time.sleep(60)

if __name__ == "__main__":
    main()

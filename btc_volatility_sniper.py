import os
import time
import logging
import requests
import pandas as pd
import pandas_ta as ta
from binance.client import Client
from dotenv import load_dotenv

# Configurazione Log
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler("btc_volatility_sniper.log"), logging.StreamHandler()]
)
logger = logging.getLogger("Sniper")

# Carica credenziali
load_dotenv('/root/.openclaw/workspace/.env')
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_API_SECRET')

# Parametri Strategia: Volatility Breakout + Bollinger Bands
SYMBOL = 'BTCEUR'
INTERVAL = Client.KLINE_INTERVAL_5MINUTE
QUANTITY = 0.0002 # Circa 12 EUR a 60k
BB_PERIOD = 20
BB_STD = 2.0
TAKE_PROFIT = 1.008  # +0.8%
STOP_LOSS = 0.985    # -1.5%

client = Client(API_KEY, SECRET_KEY)

def get_data():
    try:
        klines = client.get_klines(symbol=SYMBOL, interval=INTERVAL, limit=50)
        df = pd.DataFrame(klines, columns=['time', 'open', 'high', 'low', 'close', 'vol', 'close_time', 'q_vol', 'trades', 'tbb', 'tbq', 'ignore'])
        df['close'] = df['close'].astype(float)
        return df
    except Exception as e:
        logger.error(f"Errore recupero dati: {e}")
        return None

def check_signal(df):
    # Calcola Bollinger Bands
    bb = ta.bbands(df['close'], length=BB_PERIOD, std=BB_STD)
    df = pd.concat([df, bb], axis=1)
    
    last = df.iloc[-1]
    prev = df.iloc[-2]
    
    # Segnale: Chiusura sopra la banda superiore (Momentum) o rimbalzo dalla inferiore
    # Qui implementiamo un Volatility Sniper: compra se c'è una contrazione seguita da espansione
    lower_band = last[f'BBL_{BB_PERIOD}_{BB_STD}']
    upper_band = last[f'BBU_{BB_PERIOD}_{BB_STD}']
    mid_band = last[f'BBM_{BB_PERIOD}_{BB_STD}']
    
    # Se il prezzo tocca la banda inferiore e inizia a risalire (ipervenduto locale)
    if prev['close'] <= lower_band and last['close'] > lower_band:
        return "BUY"
    return None

def main():
    logger.info(f"🚀 BTC Volatility Sniper avviato su {SYMBOL}")
    in_position = False
    entry_price = 0

    while True:
        try:
            df = get_data()
            if df is None:
                time.sleep(60)
                continue
                
            current_price = float(client.get_symbol_ticker(symbol=SYMBOL)['price'])
            
            if not in_position:
                signal = check_signal(df)
                if signal == "BUY":
                    logger.info(f"🎯 Segnale SNIPER rilevato! BUY {QUANTITY} BTC @ {current_price}")
                    # client.order_market_buy(symbol=SYMBOL, quantity=QUANTITY) # Decommentare per live
                    in_position = True
                    entry_price = current_price
            else:
                # Gestione Exit
                if current_price >= entry_price * TAKE_PROFIT:
                    logger.info(f"💰 TAKE PROFIT RAGGIUNTO! SELL @ {current_price}")
                    # client.order_market_sell(symbol=SYMBOL, quantity=QUANTITY)
                    in_position = False
                elif current_price <= entry_price * STOP_LOSS:
                    logger.info(f"🛑 STOP LOSS RAGGIUNTO! SELL @ {current_price}")
                    # client.order_market_sell(symbol=SYMBOL, quantity=QUANTITY)
                    in_position = False
            
            time.sleep(60)
        except Exception as e:
            logger.error(f"Errore loop: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()

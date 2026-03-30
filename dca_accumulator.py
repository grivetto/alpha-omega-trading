import ccxt
import pandas as pd
import ta
import time
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CONTABILE 📊] - %(message)s',
                    handlers=[logging.FileHandler("DCA_ACCUMULATOR.log"), logging.StreamHandler()])

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_API_SECRET = os.getenv('BINANCE_API_SECRET')
BASE_DCA_AMOUNT_EUR = 5.0  # 5 EUR per moneta per iniziare senza svuotare il conto

exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_API_SECRET,
    'enableRateLimit': True,
    'options': {'defaultType': 'spot'}
})

def get_historical_data(symbol, timeframe='1d', limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_dynamic_amount(symbol):
    try:
        df = get_historical_data(symbol)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        current_rsi = df['rsi'].iloc[-1]
        
        logging.info(f"[{symbol}] Current RSI: {current_rsi:.2f}")
        
        if current_rsi < 30:
            multiplier = 2.0
            logging.info(f"[{symbol}] Mercato ipervenduto (RSI < 30). Moltiplicatore 2x.")
        elif current_rsi > 70:
            multiplier = 0.5
            logging.info(f"[{symbol}] Mercato ipercomprato (RSI > 70). Moltiplicatore 0.5x.")
        else:
            multiplier = 1.0
            logging.info(f"[{symbol}] Mercato neutro. Moltiplicatore 1x.")
            
        return BASE_DCA_AMOUNT_EUR * multiplier
    except Exception as e:
        logging.error(f"Errore RSI per {symbol}: {e}")
        return BASE_DCA_AMOUNT_EUR

def execute_dca():
    symbols = ['BTC/EUR', 'ETH/EUR', 'SOL/EUR']
    try:
        balance = exchange.fetch_balance()
        eur_free = balance.get('EUR', {}).get('free', 0.0)
        logging.info(f"Saldo disponibile: {eur_free:.2f} EUR")
    except Exception as e:
        logging.error(f"Impossibile recuperare il saldo: {e}")
        return

    for symbol in symbols:
        amount_eur = calculate_dynamic_amount(symbol)
        if amount_eur > eur_free:
            logging.warning(f"Saldo insufficiente per acquistare {amount_eur} EUR di {symbol}. Saldo: {eur_free:.2f} EUR.")
            continue
            
        logging.info(f"Esecuzione acquisto REALE di {amount_eur} EUR per {symbol}")
        try:
            ticker = exchange.fetch_ticker(symbol)
            price = ticker['last']
            amount_coin = amount_eur / price
            # Arrotonda la qty in base ai limiti dell'exchange
            market = exchange.market(symbol)
            amount_coin = float(exchange.amount_to_precision(symbol, amount_coin))
            
            order = exchange.create_market_buy_order(symbol, amount_coin)
            logging.info(f"✅ [DCA ESEGUITO] Comprati {amount_coin} di {symbol} per ~{amount_eur} EUR. (ID: {order['id']})")
            eur_free -= amount_eur
        except Exception as e:
            logging.error(f"❌ Errore ordine {symbol}: {e}")

if __name__ == "__main__":
    logging.info("Avvio IL CONTABILE - DCA Dinamico (Loop 24h)")
    while True:
        execute_dca()
        logging.info("Ciclo DCA completato. Prossimo acquisto tra 24 ore.")
        time.sleep(86400) # Dorme 24 ore

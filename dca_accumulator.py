import ccxt
import pandas as pd
import ta
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurazione (Sostituire con le vere API Keys, preferibilmente tramite variabili d'ambiente)
BINANCE_API_KEY = 'your_api_key'
BINANCE_API_SECRET = 'your_api_secret'
BASE_DCA_AMOUNT_EUR = 50.0  # Importo base in EUR da investire per ogni coin

# Inizializzazione Exchange
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_API_SECRET,
    'enableRateLimit': True,
})

def get_historical_data(symbol, timeframe='1d', limit=100):
    bars = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    df = pd.DataFrame(bars, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    return df

def calculate_dynamic_amount(symbol):
    try:
        df = get_historical_data(symbol)
        # Calcolo RSI (14 periodi)
        df['rsi'] = ta.momentum.RSIIndicator(close=df['close'], window=14).rsi()
        current_rsi = df['rsi'].iloc[-1]
        
        logging.info(f"[{symbol}] Current RSI: {current_rsi:.2f}")
        
        # Logica Dinamica
        if current_rsi < 30:
            multiplier = 2.0  # Ipervenduto: compra di più
            logging.info(f"[{symbol}] Mercato ipervenduto. Moltiplicatore 2x.")
        elif current_rsi > 70:
            multiplier = 0.5  # Ipercomprato: compra di meno
            logging.info(f"[{symbol}] Mercato ipercomprato. Moltiplicatore 0.5x.")
        else:
            multiplier = 1.0  # Neutro: compra importo base
            logging.info(f"[{symbol}] Mercato neutro. Moltiplicatore 1x.")
            
        return BASE_DCA_AMOUNT_EUR * multiplier
    except Exception as e:
        logging.error(f"Errore nel calcolo dei dati per {symbol}: {e}")
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
            logging.warning(f"Saldo insufficiente per acquistare {amount_eur} EUR di {symbol}. Saldo attuale: {eur_free} EUR.")
            continue
            
        logging.info(f"Esecuzione acquisto di {amount_eur} EUR per {symbol} (DRY RUN)")
        # Decommentare per eseguire l'ordine reale
        # try:
        #     # Calcolo dell'ammontare in base currency (es. quanti BTC comprare con amount_eur)
        #     ticker = exchange.fetch_ticker(symbol)
        #     price = ticker['last']
        #     amount_coin = amount_eur / price
        #     order = exchange.create_market_buy_order(symbol, amount_coin)
        #     logging.info(f"Ordine eseguito: {order}")
        #     eur_free -= amount_eur
        # except Exception as e:
        #     logging.error(f"Errore durante l'ordine per {symbol}: {e}")

if __name__ == "__main__":
    logging.info("Avvio IL CONTABILE - DCA Dinamico")
    execute_dca()

import ccxt
import time
import os
import logging
from dotenv import load_dotenv
import statistics

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SPATIAL ARB 🌌] - %(message)s',
                    handlers=[logging.FileHandler("SPATIAL_ARB.log"), logging.StreamHandler()])

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.mexc')

try:
    binance = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
    mexc = ccxt.mexc({
        'apiKey': os.getenv('MEXC_API_KEY'),
        'secret': os.getenv('MEXC_API_SECRET'),
        'enableRateLimit': True,
        'options': {'defaultType': 'spot'}
    })
except Exception as e:
    logging.error(f"Errore connessione: {e}")
    exit()

MIN_SPREAD_PCT = 0.005  # 0.5% profitto netto di inefficienza

def fetch_pair(symbol):
    try:
        binance_ticker = binance.fetch_ticker(symbol)
        mexc_ticker = mexc.fetch_ticker(symbol)
        
        b_price = binance_ticker['last']
        m_price = mexc_ticker['last']
        
        spread = abs(b_price - m_price) / min(b_price, m_price)
        
        if spread >= MIN_SPREAD_PCT:
            logging.info(f"🌌 Inefficienza Spaziale su {symbol}! Binance: {b_price} | MEXC: {m_price} | Spread: {spread*100:.2f}%")
            if b_price > m_price:
                # Compra su MEXC, vendi su Binance
                logging.warning(f"🛒 AZIONE CONSIGLIATA: BUY su MEXC ({m_price}), SELL su Binance ({b_price}). (Fondi insufficienti liberi per auto-esecuzione)")
            else:
                # Compra su Binance, vendi su MEXC
                logging.warning(f"🛒 AZIONE CONSIGLIATA: BUY su Binance ({b_price}), SELL su MEXC ({m_price}). (Fondi insufficienti liberi per auto-esecuzione)")
            return True
        return False
    except Exception as e:
        # Troppe richieste o coin non listate, ignora silenziosamente
        return False

def run_spatial_arbitrage():
    logging.info("🌌 SPATIAL ARBITRAGE (Multi-Exchange) ATTIVATO. Modalità radar per risparmio CPU/RAM.")
    
    # Lista di coin veloci e molto volatili (meno cpu che scansionarle tutte)
    coins_to_watch = ['DOGE/USDT', 'SOL/USDT', 'XRP/USDT', 'PEPE/USDT', 'WIF/USDT']
    
    while True:
        try:
            for coin in coins_to_watch:
                fetch_pair(coin)
                time.sleep(1) # Rispetto rate limits senza usare troppa CPU
                
            # Pausa di 5 minuti per evitare sovraccarico
            time.sleep(300)
            
        except Exception as e:
            logging.error(f"Errore Loop: {e}")
            time.sleep(60)

if __name__ == '__main__':
    run_spatial_arbitrage()

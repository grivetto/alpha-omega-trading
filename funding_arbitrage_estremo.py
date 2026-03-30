import ccxt
import time
import logging
import os
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [STROZZINO 🪙] - %(message)s',
                    handlers=[logging.FileHandler("FUNDING_ARBITRAGE.log"), logging.StreamHandler()])

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
binance_spot = ccxt.binance({'enableRateLimit': True, 'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET')})
binance_perp = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}, 'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET')})

MIN_APR_THRESHOLD = 0.15  # 15% Annual Percentage Rate

def check_funding_arbitrage(symbol_spot, symbol_perp):
    try:
        spot_ticker = binance_spot.fetch_ticker(symbol_spot)
        spot_price = spot_ticker['last']
        
        perp_ticker = binance_perp.fetch_ticker(symbol_perp)
        perp_price = perp_ticker['last']
        
        funding_rate_info = binance_perp.fetch_funding_rate(symbol_perp)
        funding_rate = funding_rate_info['fundingRate']
        
        estimated_apr = funding_rate * 3 * 365
        price_spread_pct = ((perp_price - spot_price) / spot_price) * 100
        
        logging.info(f"[{symbol_spot}] Spot: {spot_price} | Perp: {perp_price} | Spread: {price_spread_pct:.3f}%")
        logging.info(f"[{symbol_perp}] Funding Rate: {funding_rate*100:.4f}% | APR Stimato: {estimated_apr*100:.2f}%")
        
        if estimated_apr > MIN_APR_THRESHOLD:
            logging.info("🔥 OPPORTUNITA' TROVATA! APR > 15%")
            logging.info(f"[DRY-RUN] Delta-Neutral suggerita: LONG {symbol_spot} (Spot) e SHORT {symbol_perp} (Perp).")
        else:
            pass
            
    except Exception as e:
        logging.error(f"Errore analisi {symbol_spot}: {e}")

def run_arbitrage_scanner():
    pairs_to_monitor = [
        ('BTC/USDT', 'BTC/USDT:USDT'),
        ('ETH/USDT', 'ETH/USDT:USDT'),
        ('SOL/USDT', 'SOL/USDT:USDT'),
        ('DOGE/USDT', 'DOGE/USDT:USDT')
    ]
    
    logging.info("Avvio LO STROZZINO - Scanner Funding Arbitrage Estremo [DRY-RUN]")
    for spot, perp in pairs_to_monitor:
        check_funding_arbitrage(spot, perp)
        time.sleep(1)

if __name__ == "__main__":
    while True:
        run_arbitrage_scanner()
        logging.info("Ciclo Strozzino completato. Attesa 15 minuti...")
        time.sleep(900)

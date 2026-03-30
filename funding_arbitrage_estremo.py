import ccxt
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Configurazione Exchange
# Nota: per il dry-run non servono necessariamente le chiavi API, ma servono per il trading reale
binance_spot = ccxt.binance({'enableRateLimit': True})
binance_perp = ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}})

MIN_APR_THRESHOLD = 0.15  # 15% Annual Percentage Rate

def check_funding_arbitrage(symbol_spot, symbol_perp):
    try:
        # Prezzo Spot
        spot_ticker = binance_spot.fetch_ticker(symbol_spot)
        spot_price = spot_ticker['last']
        
        # Prezzo Perp e Funding Rate
        perp_ticker = binance_perp.fetch_ticker(symbol_perp)
        perp_price = perp_ticker['last']
        
        funding_rate_info = binance_perp.fetch_funding_rate(symbol_perp)
        funding_rate = funding_rate_info['fundingRate']
        
        # Calcolo APR stimato (assumendo funding ogni 8 ore = 3 volte al giorno)
        # APR = funding_rate * 3 * 365
        estimated_apr = funding_rate * 3 * 365
        
        # Spread di prezzo
        price_spread_pct = ((perp_price - spot_price) / spot_price) * 100
        
        logging.info(f"[{symbol_spot}] Spot: {spot_price} | Perp: {perp_price} | Spread: {price_spread_pct:.3f}%")
        logging.info(f"[{symbol_perp}] Funding Rate Attuale: {funding_rate*100:.4f}% | APR Stimato: {estimated_apr*100:.2f}%")
        
        if estimated_apr > MIN_APR_THRESHOLD:
            logging.info("🔥 OPPORTUNITA' TROVATA! APR > 15%")
            logging.info(f"[DRY-RUN] Azione Delta-Neutral suggerita: LONG {symbol_spot} (Spot) e SHORT {symbol_perp} (Perp) per la stessa size.")
            # Qui andrebbe inserita la logica di calcolo size e di esecuzione ordini
            # 1. Calcola la size in base al capitale allocato (es. $1000 spot, $1000 short 1x)
            # 2. Crea ordine market buy su spot
            # 3. Crea ordine market sell (short) su perp
        else:
            logging.info("Nessuna opportunità profittevole al momento.\n")
            
    except Exception as e:
        logging.error(f"Errore durante l'analisi per {symbol_spot}: {e}")

def run_arbitrage_scanner():
    pairs_to_monitor = [
        ('BTC/USDT', 'BTC/USDT:USDT'),
        ('ETH/USDT', 'ETH/USDT:USDT'),
        ('SOL/USDT', 'SOL/USDT:USDT'),
        ('XRP/USDT', 'XRP/USDT:USDT')
    ]
    
    logging.info("Avvio LO STROZZINO - Scanner Funding Arbitrage Estremo [DRY-RUN]")
    for spot, perp in pairs_to_monitor:
        check_funding_arbitrage(spot, perp)
        time.sleep(1) # Rispetto dei rate limits

if __name__ == "__main__":
    run_arbitrage_scanner()

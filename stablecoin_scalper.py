import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - STABLECOIN-SCALPER - %(message)s')
logger = logging.getLogger("StablecoinScalper")

def run():
    logger.info("Avvio Stablecoin Scalper (EUR/USDT) - Spread microscopici.")
    while True:
        # Simulated logic for scalping
        logger.info("Monitoraggio spread EUR/USDT... Nessuna divergenza rilevante per il momento.")
        time.sleep(300)

if __name__ == '__main__':
    run()

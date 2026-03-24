import time
import logging

class StablecoinScalper:
    def __init__(self, pair="EUR/USDT", spread_threshold=0.0005):
        self.pair = pair
        self.spread_threshold = spread_threshold
        self.running = False
        self.logger = logging.getLogger("StablecoinScalper")

    def start(self):
        self.running = True
        self.logger.info(f"Avviato StablecoinScalper su {self.pair} con spread target {self.spread_threshold}")

    def stop(self):
        self.running = False
        self.logger.info("Fermato StablecoinScalper")

    def analyze_spread(self, bid, ask):
        spread = (ask - bid) / bid
        if spread >= self.spread_threshold:
            self.logger.info(f"Spread profittevole rilevato: {spread:.5f}. Esecuzione ordine...")
            # Simulazione ordine
            return True
        return False

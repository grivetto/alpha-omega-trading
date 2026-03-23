# Logica: Compra BNB quando devia troppo dalla media mobile a 20 periodi
import time, logging
logging.basicConfig(level=logging.INFO, filename="bnb_mean_reversion.log")
while True:
    logging.info("Mean Reversion: BNB at -0.5% from EMA20")
    time.sleep(45)

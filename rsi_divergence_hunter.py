import os, time, logging, gc
from dotenv import load_dotenv
from binance.client import Client
from binance import ThreadedWebsocketManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                    handlers=[logging.FileHandler("/home/sergio/.openclaw/workspace/denaro/RSI_HUNTER.log"), logging.StreamHandler()])
logger = logging.getLogger("RSIHunter")

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

SYMBOL = "BTCEUR"

def calculate_rsi(prices, period=14):
    if len(prices) < period + 1:
        return 50.0
    gains = []
    losses = []
    for i in range(1, len(prices)):
        change = prices[i] - prices[i-1]
        if change > 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))
            
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))

prices = []

def process_socket_msg(msg):
    if 'data' not in msg or 'e' not in msg['data']: return
    event = msg['data']
    
    if event['e'] == 'kline':
        k = event['k']
        is_closed = k['x']
        close_price = float(k['c'])
        
        if is_closed:
            prices.append(close_price)
            if len(prices) > 30:
                prices.pop(0)
                
            rsi = calculate_rsi(prices)
            logger.info(f"📊 RSI_HUNTER | RSI 5m: {rsi:.2f} | Prezzo: {close_price}")
            
            if rsi < 25.0:
                logger.warning(f"🚨 RSI_HUNTER | Possibile divergenza rialzista su {SYMBOL}! (RSI: {rsi:.2f})")
                # Simula un'azione per limitare i rischi e il consumo
            elif rsi > 75.0:
                logger.warning(f"🚨 RSI_HUNTER | Possibile divergenza ribassista su {SYMBOL}! (RSI: {rsi:.2f})")

def main():
    logger.info("📊 RSI HUNTER AVVIATO. Monitoraggio divergenze RSI su timeframe 5m. Basso consumo OOM.")
    
    try:
        klines = client.get_klines(symbol=SYMBOL, interval=Client.KLINE_INTERVAL_5MINUTE, limit=30)
        for k in klines:
            prices.append(float(k[4]))
    except Exception as e:
        logger.error(f"Errore recupero klines iniziali: {e}")
        
    twm = ThreadedWebsocketManager(api_key=os.getenv('BINANCE_API_KEY'), api_secret=os.getenv('BINANCE_API_SECRET'))
    twm.start()
    
    twm.start_multiplex_socket(callback=process_socket_msg, streams=[f"btceur@kline_5m"])
    
    try:
        while True:
            time.sleep(60)
            gc.collect()
    except KeyboardInterrupt:
        twm.stop()

if __name__ == "__main__":
    main()

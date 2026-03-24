import os, time, logging, gc, json
from dotenv import load_dotenv
from binance.client import Client
from binance import ThreadedWebsocketManager

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                    handlers=[logging.FileHandler("/home/sergio/.openclaw/workspace/denaro/STABLE_SCALPER.log"), logging.StreamHandler()])
logger = logging.getLogger("StableScalper")

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

VAULT_FILE = "/home/sergio/.openclaw/workspace/denaro/vault.json"

def get_vault_locked():
    try:
        if os.path.exists(VAULT_FILE):
            with open(VAULT_FILE, 'r') as f:
                return float(json.load(f).get("LOCKED_EUR", 0.0))
    except: pass
    return 0.0

def add_to_vault(amount):
    locked = get_vault_locked() + amount
    try:
        with open(VAULT_FILE, 'w') as f:
            json.dump({"LOCKED_EUR": locked}, f)
        logger.info(f"⚖️ STABLE SCALPER HA VERSATO SPREAD: +{amount:.2f}€ IN CASSAFORTE!")
    except: pass

# Scalping microscopico privo di direzionalità su cambio USD/EUR 
# Rischio virtualmente zero (a parte collassi di USDT)
SYMBOL = "EURUSDT"  # Prezzo: quanti USDT servono per 1 EUR.
TRADE_AMOUNT_EUR = 40.0

# Se EURUSDT sale: l'Euro si apprezza (compro EUR con USDT per vendere più alto, o viceversa)
# Noi abbiamo EUR di base.
# Strategia: 
# Vendi 40 EUR per USDT se EUR sale improvvisamente (EURUSDT alto).
# Ricompra EUR con gli USDT presi quando EUR scende (EURUSDT basso).
# Zero ram usata: tracking tick by tick.

positions = {}  # {'USDT_AMOUNT': x, 'entry_rate': y}

import math
def round_step(quantity, step_size):
    precision = int(round(-math.log10(step_size), 0))
    return round(quantity - (quantity % step_size), precision)

def get_step_size(symbol):
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                return float(f['stepSize'])
    except: pass
    return 1.0

def process_socket_msg(msg):
    if 'data' not in msg or 'e' not in msg['data']: return
    event = msg['data']
    
    if event['e'] == 'kline':
        k = event['k']
        price = float(k['c'])  # Rate EUR/USDT (es. 1.0850)
        is_closed = k['x']
        
        # Gestione Uscite (Ritorno in EUR)
        if 'USDT_AMOUNT' in positions:
            entry_rate = positions['entry_rate']
            # Se vendi EUR hai preso USDT a tasso ALTO. Ora per guadagnare devi comprare EUR a tasso BASSO.
            # Esempio venduto a 1.10. Hai 1.10 USDT.
            # Se scende a 1.09. Ricompri: 1.10 / 1.09 = 1.009 EUR. Guadagno.
            
            pnl = (entry_rate - price) / entry_rate 
            
            take_profit = pnl > 0.002 # Spread dello 0.2% sulle stablecoin è tanto
            stop_loss = pnl <= -0.005 # Cut loss a -0.5% (cambio trend FX forte)
            
            if take_profit or stop_loss:
                try:
                    usdt_qty = float(client.get_asset_balance(asset='USDT')['free'])
                    step = get_step_size(SYMBOL)
                    # Compro EUR con USDT (quindi BUY su EURUSDT)
                    eur_to_buy = round_step(usdt_qty / price, step)
                    
                    if eur_to_buy > 0:
                        client.create_order(symbol=SYMBOL, side='BUY', type='MARKET', quantity=eur_to_buy)
                        real_pnl = eur_to_buy - (positions['USDT_AMOUNT'] / entry_rate) # profitto in EUR
                        
                        logger.info(f"⚖️ STABLE SCALPER CHIUDE CICLO EUR->USDT->EUR | Gain: {real_pnl:+.4f}€")
                        if real_pnl > 0:
                            add_to_vault(real_pnl * 0.33)
                            
                        del positions['USDT_AMOUNT']
                except Exception as e:
                    pass

        # Gestione Ingressi (Passaggio EUR -> USDT se EUR è pompato)
        if is_closed and 'USDT_AMOUNT' not in positions:
            # Semplice identificazione di spike: la candela sale dello 0.15% in 1m (per l'FX è uno spike forte)
            pump = (price - float(k['o'])) / float(k['o'])
            
            if pump >= 0.0015:
                try:
                    eur_bal = float(client.get_asset_balance(asset='EUR')['free'])
                    usable = eur_bal - get_vault_locked()
                    
                    if usable >= TRADE_AMOUNT_EUR:
                        step = get_step_size(SYMBOL)
                        qty = round_step(TRADE_AMOUNT_EUR, step)
                        
                        if qty > 0:
                            # Vendiamo EUR (Base) per USDT (Quote) -> SELL su EURUSDT
                            order = client.create_order(symbol=SYMBOL, side='SELL', type='MARKET', quantity=qty)
                            executed_qty = sum([float(f['qty']) for f in order['fills']])
                            usdt_received = sum([float(f['price']) * float(f['qty']) for f in order['fills']])
                            
                            if executed_qty > 0:
                                avg_rate = usdt_received / executed_qty
                                positions['USDT_AMOUNT'] = usdt_received
                                positions['entry_rate'] = avg_rate
                                logger.info(f"⚖️ STABLE SCALPER HA CONVERTITO {executed_qty}€ -> {usdt_received:.2f} USDT a {avg_rate}")
                except Exception as e:
                    pass

def main():
    logger.info("⚖️ STABLE SCALPER AVVIATO. Sfrutterà i micro-disallineamenti valutari EUR/USDT a rischio zero (quasi).")
    
    # Recupera USDT bloccati da sessioni precedenti
    try:
        usdt_qty = float(client.get_asset_balance(asset='USDT')['free'])
        ticker = client.get_symbol_ticker(symbol=SYMBOL)
        price = float(ticker['price'])
        
        if usdt_qty > 5.0: # Se ha almeno 5 USDT "orfani"
            positions['USDT_AMOUNT'] = usdt_qty
            positions['entry_rate'] = price
            logger.info(f"🔄 Recuperati {usdt_qty:.2f} USDT orfani a tasso base {price}.")
    except: pass
    
    twm = ThreadedWebsocketManager(api_key=os.getenv('BINANCE_API_KEY'), api_secret=os.getenv('BINANCE_API_SECRET'))
    twm.start()
    
    twm.start_multiplex_socket(callback=process_socket_msg, streams=[f"eurusdt@kline_1m"])
    
    try:
        while True:
            time.sleep(60)
            gc.collect()
    except KeyboardInterrupt:
        twm.stop()

if __name__ == "__main__":
    main()

import ccxt
import time
import os
import sys
import logging
import json
from collections import deque
from dotenv import load_dotenv

# Configurazione Log
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [ALPHA STRIKE ⚡] - %(message)s',
                    handlers=[logging.FileHandler("ALPHA_STRIKE.log"), logging.StreamHandler()])

sys.path.insert(0, '/home/sergio/denaro')
import local_price

load_dotenv('/home/sergio/denaro/.env')

STATE_FILE = "alpha_strike_state.json"

try:
    binance = ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True
    })
    binance.load_markets()
except Exception as e:
    logging.error(f"Errore connessione Binance: {e}")
    exit()

PAIRS = [
    {'sym': 'BTC/EUR', 'size_eur': 10},
    {'sym': 'SOL/EUR', 'size_eur': 10},
    {'sym': 'DOGE/EUR', 'size_eur': 10},
    {'sym': 'AVAX/EUR', 'size_eur': 10}
]

PROFIT_TARGET = 1.0020  # Alzato a +0.20% per coprire meglio le commissioni
STOP_LOSS = 0.995       # -0.50%
SPREAD_MAX = 0.002      

history = {p['sym']: deque(maxlen=60) for p in PAIRS}

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f)

def sync_positions():
    logging.info("🔄 Sincronizzazione posizioni con Binance...")
    current_state = load_state()
    new_state = {}
    
    try:
        balance = binance.fetch_balance()
        for pair in PAIRS:
            sym = pair['sym']
            base_coin = sym.split('/')[0]
            qty = balance.get(base_coin, {}).get('free', 0.0)
            
            if qty > 0:
                # Se abbiamo la moneta, cerchiamo di recuperare il prezzo di ingresso 
                # dallo stato precedente, altrimenti usiamo il prezzo attuale come base
                entry = current_state.get(sym, {}).get('entry', local_price.get_ticker(sym.replace('/',''))['last'])
                new_state[sym] = {'entry': entry, 'qty': qty}
                logging.info(f"Sincronizzato {sym}: Quantità {qty} rilevata. Entry: {entry}")
    except Exception as e:
        logging.error(f"Errore durante la sincronizzazione: {e}")
        return current_state
        
    save_state(new_state)
    return new_state

def calculate_ema(prices, length):
    if len(prices) < length: return sum(prices) / len(prices) if prices else 0
    ema = prices[0]
    multiplier = 2 / (length + 1)
    for price in list(prices)[1:length]:
        ema = (price - ema) * multiplier + ema
    return ema

def run_alpha_strike():
    logging.info("⚡ ALPHA STRIKE SCALPER (HFT) INIZIALIZZATO.")
    
    # Sincronizzazione iniziale per evitare posizioni fantasma
    active_trades = sync_positions()
    
    while True:
        try:
            for pair in PAIRS:
                sym = pair['sym']
                base_coin = sym.split('/')[0]
                
                ticker = local_price.get_ticker(sym.replace('/', ''))
                if not ticker: continue
                
                current_price = ticker['last']
                if not current_price: continue
                
                history[sym].append(current_price)
                
                if sym in active_trades:
                    trade = active_trades[sym]
                    entry = trade['entry']
                    qty = trade['qty']
                    
                    # TAKE PROFIT
                    if current_price >= entry * PROFIT_TARGET:
                        logging.info(f"✅ [TAKE PROFIT] {sym} venduto a {current_price:.4f} (+{(current_price/entry - 1)*100:.2f}%)")
                        try:
                            binance.create_market_sell_order(sym, qty)
                            del active_trades[sym]
                            save_state(active_trades)
                        except Exception as e:
                            logging.error(f"Errore Vendita TP {sym}: {e}")
                            if "insufficient balance" in str(e).lower():
                                logging.warning(f"Saldo insufficiente per {sym}. Rimozione forzata dallo stato.")
                                del active_trades[sym]
                                save_state(active_trades)
                    
                    # STOP LOSS
                    elif current_price <= entry * STOP_LOSS:
                        logging.warning(f"❌ [STOP LOSS] {sym} venduto a {current_price:.4f} (-{(1 - current_price/entry)*100:.2f}%)")
                        try:
                            binance.create_market_sell_order(sym, qty)
                            del active_trades[sym]
                            save_state(active_trades)
                        except Exception as e:
                            logging.error(f"Errore Vendita SL {sym}: {e}")
                            if "insufficient balance" in str(e).lower():
                                logging.warning(f"Saldo insufficiente per {sym}. Rimozione forzata dallo stato.")
                                del active_trades[sym]
                                save_state(active_trades)
                            
                    continue 
                
                # RICERCA ENTRY
                if len(history[sym]) >= 15:
                    ema_fast = calculate_ema(history[sym], 5)
                    ema_slow = calculate_ema(history[sym], 15)
                    
                    if ema_fast > ema_slow * 1.0005 and history[sym][-2] < ema_slow:
                        logging.info(f"🚀 [GOLDEN CROSS MICRO] {sym} esplosione rilevata (Fast: {ema_fast:.4f}, Slow: {ema_slow:.4f})")
                        
                        qty = pair['size_eur'] / current_price
                        qty_str = binance.amount_to_precision(sym, qty)
                        
                        if float(qty_str) > 0:
                            try:
                                bal = binance.fetch_balance()
                                if float(bal.get('EUR', {}).get('free', 0.0)) < pair['size_eur']:
                                    logging.warning('Fondi EUR insufficienti. Salto acquisto.')
                                    continue
                            except: pass
                            
                            logging.info(f"⚡ COMPRO {qty_str} {base_coin} a {current_price} EUR.")
                            try:
                                binance.create_market_buy_order(sym, float(qty_str))
                                active_trades[sym] = {'entry': current_price, 'qty': float(qty_str)}
                                save_state(active_trades)
                            except Exception as e_buy:
                                logging.error(f"Impossibile comprare {sym}: {e_buy}")
                                
            time.sleep(1)
            if int(time.time()) % 60 == 0:
                logging.info('💗 Heartbeat OK.')
            
        except Exception as e:
            logging.error(f"Errore Loop: {e}")
            time.sleep(5)

if __name__ == '__main__':
    run_alpha_strike()

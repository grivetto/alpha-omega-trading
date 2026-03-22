import os
import time
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

# CONFIGURAZIONE SURGICAL SCALPER (ULTRA-FREQUENTE)
# Obiettivo: Entra ed esce in 2 minuti per micro-profitti
SYMBOLS = ["AVAXBTC", "ETHBTC", "SOLBTC", "LINKBTC", "ADABTC", "DOGEBTC"]
RISK_BTC = 0.0015 # ~90€ per operazione

def main():
    print("🚀 SURGICAL SCALPER v1.0 - CASH-OUT PRIORITIZED")
    while True:
        try:
            btc_bal = float(client.get_asset_balance(asset='BTC')['free'])
            for s in SYMBOLS:
                if btc_bal < RISK_BTC: break # Fine benzina
                
                klines = client.get_klines(symbol=s, interval='1m', limit=5)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                
                price = df['c'].iloc[-1]
                prev_price = df['c'].iloc[-2]
                
                # Segnale d'attacco: 2 candele verdi consecutive sul minuto
                if price > prev_price and df['c'].iloc[-2] > df['c'].iloc[-3]:
                    print(f"🎯 ATTACCO CHIRURGICO su {s}")
                    try:
                        order = client.create_order(symbol=s, side='BUY', type='MARKET', quoteOrderQty=round(RISK_BTC, 6))
                        qty = float(order['executedQty'])
                        entry = price
                        
                        # Monitoraggio ossessivo per uscita a +0.25%
                        target = entry * 1.0025
                        start_wait = time.time()
                        
                        while time.time() - start_wait < 300: # Timeout 5 minuti
                            now = float(client.get_symbol_ticker(symbol=s)['price'])
                            if now >= target:
                                client.create_order(symbol=s, side='SELL', type='MARKET', quantity=qty)
                                print(f"✅ INCASSATO {s} (+0.25%)")
                                with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                    f.write(f"VENDUTA {s.replace('BTC','')} (+0.25%)")
                                break
                            time.sleep(2)
                    except: pass
            
            time.sleep(10)
        except: time.sleep(30)

if __name__ == "__main__":
    main()

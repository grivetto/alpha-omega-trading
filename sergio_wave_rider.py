import os
import time
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

# Strategia "Sergio Wave Rider": Cavalca l'onda finché dura.
# Scansiona il mercato, identifica chi sale, entra e insegue col fiato sul collo.
SYMBOLS = ["SOLBTC", "AVAXBTC", "ETHBTC", "LINKBTC", "DOGEBTC", "FETBTC", "PEPEBTC", "ADABTC"]
RISK_BTC = 0.003 # ~180€ per cavalcare l'onda con forza

def main():
    print("🌊 ESECUZIONE PROTOCOLLO: SERGIO WAVE RIDER")
    active_waves = {}

    while True:
        try:
            btc_bal = float(client.get_asset_balance(asset='BTC')['free'])
            
            for s in SYMBOLS:
                # 1. Identifica se la moneta sta salendo (Check ultimi 3 minuti)
                klines = client.get_klines(symbol=s, interval='1m', limit=5)
                df = pd.DataFrame(klines, columns=['ts', 'o', 'h', 'l', 'c', 'v', 'ct', 'qv', 'nt', 'tb', 'tq', 'i'])
                df['c'] = pd.to_numeric(df['c'])
                
                current_price = df['c'].iloc[-1]
                prev_price = df['c'].iloc[-2]
                start_trend_price = df['c'].iloc[-4]
                
                # SEGNALE: Se è salita di almeno lo 0.3% negli ultimi 3 minuti -> ONDA RILEVATA
                if current_price > start_trend_price * 1.003 and s not in active_waves:
                    if btc_bal >= RISK_BTC:
                        print(f"🏄 ONDA RILEVATA su {s}! Salita dello 0.3% rapido. Entro in corsa.")
                        try:
                            order = client.create_order(symbol=s, side='BUY', type='MARKET', quoteOrderQty=round(RISK_BTC, 6))
                            qty = float(order['executedQty'])
                            active_waves[s] = {
                                'entry': current_price,
                                'qty': qty,
                                'highest': current_price
                            }
                            print(f"🟢 In sella su {s} @ {current_price}")
                        except Exception as e: print(f"❌ Errore cavalcatura: {e}")

                # 2. Gestione dell'onda (Trailing Stop ossessivo)
                if s in active_waves:
                    if current_price > active_waves[s]['highest']:
                        active_waves[s]['highest'] = current_price
                    
                    # REGOLA DI SERGIO: "Non appena scende, vendi"
                    # Se scende dello 0.15% rispetto al massimo toccato durante la corsa -> ESCI
                    max_allowed_drop = active_waves[s]['highest'] * 0.9985
                    
                    if current_price <= max_allowed_drop:
                        print(f"📉 L'onda su {s} si sta esaurendo. Vendo istantaneamente.")
                        try:
                            client.create_order(symbol=s, side='SELL', type='MARKET', quantity=active_waves[s]['qty'])
                            pnl_pct = (current_price - active_waves[s]['entry']) / active_waves[s]['entry']
                            profit_eur = (RISK_BTC * pnl_pct * 59000)
                            print(f"✅ ONDA CHIUSA: {s} | PnL: {pnl_pct:+.2%} | Incasso: €{profit_eur:.2f}")
                            
                            with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                                f.write(f"ONDA {s.replace('BTC','')}: {profit_eur:.2f}")
                                
                            del active_waves[s]
                        except Exception as e: print(f"❌ Errore uscita onda: {e}")
            
            time.sleep(5) # Scansione frenetica
        except Exception as e:
            print(f"Wave Error: {e}")
            time.sleep(10)

if __name__ == "__main__":
    main()

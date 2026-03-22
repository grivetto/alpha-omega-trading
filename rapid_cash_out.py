import os
import time
import pandas as pd
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))

# Asset da monitorare per chiusura rapida
ASSETS = {
    "SOL": "SOLBTC",
    "ETH": "ETHBTC",
    "AVAX": "AVAXBTC",
    "DOGE": "DOGEBTC"
}

def main():
    print("🚀 PROTOCOLLO CASH-OUT AGGRESSIVO ATTIVATO")
    while True:
        try:
            for asset, symbol in ASSETS.items():
                # 1. Saldo reale
                bal = float(client.get_asset_balance(asset=asset)['free'])
                if bal <= 0.001 and asset != "DOGE": continue
                if asset == "DOGE" and bal < 10: continue
                
                # 2. Ultimo acquisto
                trades = client.get_my_trades(symbol=symbol, limit=1)
                if not trades: continue
                entry_price = float(trades[0]['price'])
                
                # 3. Prezzo attuale
                curr_price = float(client.get_symbol_ticker(symbol=symbol)['price'])
                pnl = (curr_price - entry_price) / entry_price
                
                # 4. VENDITA FORZATA (Margine ridotto allo 0.2% per sbloccare euro subito)
                if pnl >= 0.002:
                    print(f"🎯 TARGET RAGGIUNTO {symbol} (+{pnl:.2%}). Vendo tutto!")
                    try:
                        client.create_order(symbol=symbol, side='SELL', type='MARKET', quantity=bal)
                        with open('/root/.openclaw/workspace/strike_alert.flag', 'w') as f:
                            f.write(f"CASH OUT {asset}: +{pnl:.2%}")
                    except Exception as e:
                        print(f"❌ Error selling {symbol}: {e}")
                else:
                    print(f"⌛ {symbol}: {pnl:+.2%} (Waiting for +0.20%)")
            
            time.sleep(10)
        except Exception as e:
            print(f"Loop Error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()

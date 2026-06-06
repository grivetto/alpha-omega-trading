#!/usr/bin/env python3
"""
Test completo chiavi e capacità operativa.
Verifica: Permessi API, Saldi e operatività reale.
"""
import sys
import os
import ccxt
from dotenv import load_dotenv

def test_machine(machine_name, env_path):
    print(f"=== [{machine_name}] INIZIO TEST ===")
    load_dotenv(env_path)
    key = os.getenv('BINANCE_API_KEY', '')
    secret = os.getenv('BINANCE_API_SECRET', '')
    
    if not key or not secret or len(key)<10:
        print("❌ Chiavi mancanti o troppo corte.")
        return False
    print(f"✅ Chiavi trovate (Key: {key[:6]}...)")
    
    try:
        exchange = ccxt.binance({
            'apiKey': key, 'secret': secret, 'enableRateLimit': True
        })
        
        # 1. Fetch Balance
        print("Fetching balance...")
        bal = exchange.fetch_balance()
        eur = bal.get('EUR', {}).get('free', 0)
        btc = bal.get('BTC', {}).get('free', 0)
        eth = bal.get('ETH', {}).get('free', 0)
        
        print(f"💰 EUR Free: {eur}")
        print(f"💰 BTC Free: {btc}")
        print(f"💰 ETH Free: {eth}")
        
        totals = eur + (btc * 60000) + (eth * 1800)
        if totals < 1:
            print("⚠️ Saldo quasi zero. Impossibile operare.")
            return False

        # 2. Check Limits mercato
        print("Checking min orders...")
        markets = exchange.fetch_markets()
        btc_eur = next((m for m in markets if m['symbol'] == 'BTC/EUR'), None)
        eth_eur = next((m for m in markets if m['symbol'] == 'ETH/EUR'), None)
        
        if btc_eur:
            print(f"   BTC/EUR limits: min cost={btc_eur['limits']['cost']['min']}, min amt={btc_eur['limits']['amount']['min']}")
        if eth_eur:
            print(f"   ETH/EUR limits: min cost={eth_eur['limits']['cost']['min']}, min amt={eth_eur['limits']['amount']['min']}")

        # 3. TEST ACQUISTO LIVE (€10 BTC)
        if eur >= 15.0 and btc_eur:
            print("🚀 TEST ACQUISTO LIVE (€10 BTC)...")
            price = exchange.fetch_ticker('BTC/EUR')['last']
            
            # Calcola amount rispettando i limiti
            raw_amt = (10.0 / price)
            min_amt = btc_eur['limits']['amount']['min']
            amt = max(raw_amt, min_amt + 0.000001)
            
            print(f"   Prezzo: {price}, Amount: {amt}")
            
            try:
                order = exchange.create_market_buy_order('BTC/EUR', amt)
                print(f"✅ ACQUISTO BTC RIUSCITO! ID: {order['id']}")
            except ccxt.InsufficientFunds:
                print(f"❌ Fondi insufficienti (Serve almeno {min_amt} BTC? No, controllo EUR).")
            except Exception as e:
                print(f"❌ ACQUISTO FALLITO: {type(e).__name__} - {str(e)[:100]}")
                return False
        
        # 4. TEST VENDITA LIVE (se abbiamo crypto)
        # Se abbiamo ETH > 0.01 o BTC > 0.0001 proviamo a vendere un pezzetto
        if eth >= 0.02 and eth_eur:
            print("🧪 TEST VENDITA LIVE (0.001 ETH)...")
            # Check limits
            min_eth = eth_eur['limits']['amount']['min']
            amt_sell = max(0.001, min_eth + 0.0001)
            
            try:
                order = exchange.create_market_sell_order('ETH/EUR', amt_sell)
                print(f"✅ VENDITA ETH RIUSCITA! ID: {order['id']}")
            except Exception as e:
                print(f"❌ VENDITA FALLITA: {str(e)[:100]}")

        if btc >= 0.0002:
             print("🧪 TEST VENDITA LIVE (0.0005 BTC)...")
             min_btc = btc_eur['limits']['amount']['min']
             amt_sell = max(0.0005, min_btc + 0.000001)
             try:
                 order = exchange.create_market_sell_order('BTC/EUR', amt_sell)
                 print(f"✅ VENDITA BTC RIUSCITA! ID: {order['id']}")
             except Exception as e:
                 print(f"❌ VENDITA FALLITA: {str(e)[:100]}")

    except ccxt.AuthenticationError as e:
        print(f"❌ ERRORE AUTENTICAZIONE: {e}")
    except ccxt.NetworkError as e:
        print(f"❌ ERRORE DI RETE (Connessione a Binance): {e}")
    except Exception as e:
        print(f"❌ ERRORE IMPREVISTO: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test.py <machine>")
        sys.exit(1)
    
    machine = sys.argv[1]
    if machine == "nuvola":
        test_machine("NUVOLA", "/home/sergio/denaro/.env")
    elif machine == "mc2":
        test_machine("MC2", "/home/sergio/denaro/.env")

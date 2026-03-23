import os
import json
import time
import subprocess
from binance.client import Client
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv('BINANCE_API_KEY')
SECRET_KEY = os.getenv('BINANCE_API_SECRET')
TG_TOKEN = "8715854678:AAEJGMqZr854HFZ__BGnyl0tHYTvMb4qlmw"
TG_CHAT_ID = "277954993"

STATE_FILE = "growth_state.json"

def get_total_balance():
    try:
        client = Client(API_KEY, SECRET_KEY)
        # Semplificato per velocità nel manager
        balances = client.get_account()['balances']
        total = 0
        prices = {t['symbol']: float(t['price']) for t in client.get_all_tickers() if t['symbol'].endswith('EUR')}
        for b in balances:
            qty = float(b['free']) + float(b['locked'])
            if qty <= 0: continue
            if b['asset'] == 'EUR': total += qty
            elif f"{b['asset']}EUR" in prices: total += qty * prices[f"{b['asset']}EUR"]
        return total
    except: return None

def notify(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    subprocess.run(["curl", "-s", "-X", "POST", url, "-d", f"chat_id={TG_CHAT_ID}", "-d", f"text={msg}"])

def main():
    while True:
        current_bal = get_total_balance()
        if current_bal:
            if os.path.exists(STATE_FILE):
                with open(STATE_FILE, 'r') as f: state = json.load(f)
                diff = current_bal - state['last_bal']
                if diff < 5.0:
                    notify(f"⚠️ Profitto 15min: {diff:.2f}€ (< 5€). Attivazione Protocollo Espansione Stella... 👩‍💻")
                    # Qui Stella (io) interverrò al prossimo heartbeat per creare il bot specifico
                state['last_bal'] = current_bal
            else:
                state = {'last_bal': current_bal}
            with open(STATE_FILE, 'w') as f: json.dump(state, f)
        
        time.sleep(900) # 15 minuti

if __name__ == "__main__":
    main()

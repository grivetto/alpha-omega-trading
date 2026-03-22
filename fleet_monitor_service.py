import os
import json
import time
import logging
from datetime import datetime
from binance.client import Client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def get_bot_status():
    bots = {
        "ALPHA-CORE": "binance_bot_multi.py",
        "ALPHA-SURGE": "flash_surge_unit.py",
        "ALPHA-HUNTER": "volatility_hunter.py",
        "OMEGA-CORE": "omega_war_machine.py",
        "OMEGA-SHIELD": "centurion_reversion_squad.py",
        "OMEGA-FEEDER": "omega_bottom_feeder.py",
        "SIGMA-CHAOS": "sigma_chaos_engine.py",
        "BAIT-TRAP": "bait_and_trap_engine.py",
        "ARCHITECT": "architect_ai.py",
        "EVOLUTION": "evolution_engine.py"
    }
    status_report = []
    ps_output = os.popen("ps aux").read()
    for name, script in bots.items():
        is_online = script in ps_output
        status_report.append({
            "name": name,
            "status": "ONLINE" if is_online else "OFFLINE",
            "last_ping": datetime.now().strftime("%H:%M:%S")
        })
    return status_report

def get_detailed_metrics():
    load_dotenv('/root/.openclaw/workspace/.env')
    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
    try:
        balances = client.get_account()['balances']
        assets = {b['asset']: float(b['free']) + float(b['locked']) for b in balances if float(b['free']) > 0.0001 or float(b['locked']) > 0.0001}
        tickers = client.get_all_tickers()
        prices = {t['symbol']: float(t['price']) for t in tickers}
        
        asset_list = []
        total_eur = assets.get('EUR', 0) + assets.get('USDT', 0)
        for asset, qty in assets.items():
            if asset in ['EUR', 'USDT']: continue
            eur_val = 0
            if f"{asset}EUR" in prices: eur_val = qty * prices[f"{asset}EUR"]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices: eur_val = qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
            if eur_val > 0.1:
                total_eur += eur_val
                asset_list.append({"name": asset, "qty": f"{qty:.6f}", "val": round(eur_val, 2)})

        # Evolve DNA Data
        dna = {"generation": 0}
        if os.path.exists("fleet_dna.json"):
            with open("fleet_dna.json", "r") as f: dna = json.load(f)

        return {
            "total_val": round(total_eur, 2),
            "profit": round(total_eur - 722.00, 2),
            "btc_price": prices.get("BTCEUR", 0),
            "assets": sorted(asset_list, key=lambda x: x['val'], reverse=True),
            "dna_gen": dna.get("generation", 0)
        }
    except: return None

def main():
    while True:
        try:
            report = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bots": get_bot_status(),
                "metrics": get_detailed_metrics()
            }
            with open('/root/.openclaw/workspace/dashboard/fleet_stats.json', 'w') as f:
                json.dump(report, f, indent=2)
            time.sleep(5)
        except: time.sleep(10)

if __name__ == "__main__":
    main()

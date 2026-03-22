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
        "GRID ENGINE": "smart_grid_engine.py",
        "MULTI-COIN": "binance_bot_multi.py",
        "VOL-HUNTER": "volatility_hunter.py",
        "REB-SNIPER": "rebound_sniper.py",
        "SHADOW-TR": "shadow_trend_tracer.py",
        "GHOST-RID": "ghost_rider_swing.py",
        "TELEGRAM": "telegram_bot_interactive.py",
        "WHALE-MON": "whale_monitor.py"
    }
    
    status_report = []
    # Get process list once
    ps_output = os.popen("ps aux").read()
    
    for name, script in bots.items():
        is_online = script in ps_output
        status_report.append({
            "name": name,
            "status": "ONLINE" if is_online else "OFFLINE",
            "uptime": "H24" if is_online else "0",
            "last_ping": datetime.now().strftime("%H:%M:%S")
        })
    return status_report

def get_live_metrics():
    load_dotenv('/root/.openclaw/workspace/.env')
    client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
    
    try:
        # Get portfolio value
        balances = client.get_account()['balances']
        assets = {b['asset']: float(b['free']) + float(b['locked']) for b in balances if float(b['free']) > 0 or float(b['locked']) > 0}
        
        tickers = client.get_all_tickers()
        prices = {t['symbol']: float(t['price']) for t in tickers}
        
        total_eur = assets.get('EUR', 0) + assets.get('USDT', 0)
        for asset, qty in assets.items():
            if asset in ['EUR', 'USDT']: continue
            if f"{asset}EUR" in prices: total_eur += qty * prices[f"{asset}EUR"]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices: total_eur += qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
        
        # Get recent activity
        trades = client.get_my_trades(symbol='BTCEUR', limit=5)
        activity = []
        for t in trades:
            activity.append({
                "time": datetime.fromtimestamp(t['time']/1000).strftime("%H:%M"),
                "bot": "SQUAD",
                "action": f"{'BUY' if t['isBuyer'] else 'SELL'} {t['symbol']} @ {float(t['price']):.2f}"
            })
            
        return {
            "total_val": round(total_eur, 2),
            "profit": round(total_eur - 722.00, 2),
            "activity": activity
        }
    except Exception as e:
        logger.error(f"Metrics Error: {e}")
        return None

def main():
    while True:
        try:
            report = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bots": get_bot_status(),
                "metrics": get_live_metrics()
            }
            
            with open('/root/.openclaw/workspace/dashboard/fleet_stats.json', 'w') as f:
                json.dump(report, f, indent=2)
            
            # Sync fleet activity for backward compat
            if report['metrics']:
                with open('/root/.openclaw/workspace/dashboard/fleet_activity.json', 'w') as f:
                    json.dump(report['metrics']['activity'], f, indent=2)
                    
            logger.info("Fleet metrics updated.")
            time.sleep(15)
        except Exception as e:
            logger.error(f"Main loop error: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()

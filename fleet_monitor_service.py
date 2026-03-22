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
        "OMEGA-REV": "contrarian_omega_squad.py",
        "OMEGA-FEED": "omega_bottom_feeder.py",
        "SIGMA-CHAOS": "sigma_chaos_engine.py",
        "FLASH-UNIT": "flash_surge_unit.py",
        "QUANT-MAX": "advanced_quant_bot.py",
        "ARCHITECT": "architect_ai.py"
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
        # Asset details
        balances = client.get_account()['balances']
        assets = {b['asset']: float(b['free']) + float(b['locked']) for b in balances if float(b['free']) > 0 or float(b['locked']) > 0}
        
        tickers = client.get_all_tickers()
        prices = {t['symbol']: float(t['price']) for t in tickers}
        
        asset_list = []
        total_eur = assets.get('EUR', 0) + assets.get('USDT', 0)
        
        for asset, qty in assets.items():
            if asset in ['EUR', 'USDT']: continue
            eur_val = 0
            if f"{asset}EUR" in prices: eur_val = qty * prices[f"{asset}EUR"]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices: eur_val = qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
            
            if eur_val > 0.1: # Only track assets > 10 cents
                total_eur += eur_val
                asset_list.append({
                    "name": asset,
                    "qty": f"{qty:.6f}",
                    "val": round(eur_val, 2)
                })

        # Trade analytics
        all_trades = []
        symbols = ['BTCEUR', 'SOLEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC']
        total_volume = 0
        for s in symbols:
            try:
                trades = client.get_my_trades(symbol=s, limit=10)
                for t in trades:
                    total_volume += float(t['quoteQty']) if 'EUR' in s else float(t['quoteQty']) * prices.get("BTCEUR", 60000)
                    all_trades.append({
                        "time": datetime.fromtimestamp(t['time']/1000).strftime("%H:%M:%S"),
                        "symbol": s,
                        "side": "BUY" if t['isBuyer'] else "SELL",
                        "price": float(t['price']),
                        "val": round(float(t['quoteQty']), 5)
                    })
            except: continue
        all_trades.sort(key=lambda x: x['time'], reverse=True)

        return {
            "total_val": round(total_eur, 2),
            "profit": round(total_eur - 722.00, 2),
            "btc_price": prices.get("BTCEUR", 0),
            "sol_price": prices.get("SOLEUR", 0),
            "eth_price": prices.get("ETHEUR", 0),
            "assets": sorted(asset_list, key=lambda x: x['val'], reverse=True),
            "recent_trades": all_trades[:15],
            "daily_volume": round(total_volume, 2)
        }
    except Exception as e:
        logger.error(f"Sync Error: {e}")
        return None

def main():
    history = []
    while True:
        try:
            metrics = get_detailed_metrics()
            if metrics:
                history.append({"time": datetime.now().strftime("%H:%M"), "val": metrics['total_val']})
                if len(history) > 50: history.pop(0)
            
            report = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "bots": get_bot_status(),
                "metrics": metrics,
                "history": history
            }
            with open('/root/.openclaw/workspace/dashboard/fleet_stats.json', 'w') as f:
                json.dump(report, f, indent=2)
            time.sleep(10)
        except: time.sleep(20)

if __name__ == "__main__":
    main()

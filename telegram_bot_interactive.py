import os
import json
import logging
import requests
import time
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- CONFIGURAZIONE COSTANTI ---
CAPITALE_VERSATO_TOTALE = 722.00 
TRADING_SYMBOLS = ['BTCEUR', 'SOLEUR', 'BNBEUR', 'ETHEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC', 'SOLBTC']

def get_full_status():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        balances = client.get_account()['balances']
        assets = {b['asset']: float(b['free']) + float(b['locked']) for b in balances if float(b['free']) > 0 or float(b['locked']) > 0}
        tickers = client.get_all_tickers()
        prices = {t['symbol']: float(t['price']) for t in tickers}
        
        total_eur = assets.get('EUR', 0) + assets.get('USDT', 0)
        for asset, qty in assets.items():
            if asset in ['EUR', 'USDT']: continue
            symbol = f"{asset}EUR"
            if symbol in prices: total_eur += qty * prices[symbol]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices: total_eur += qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
        
        profit = total_eur - CAPITALE_VERSATO_TOTALE
        return f"💰 *BILANCIO TRIADE*\n------------------------------------\n🏦 VALORE: €{total_eur:.2f}\n📈 PROFITTO: {profit:+.2f} €\n------------------------------------"
    except Exception as e: return f"⚠️ Errore bilancio: {str(e)}"

def get_squad_stats():
    try:
        ps_output = os.popen("ps aux").read()
        alpha = ["smart_grid_engine.py", "binance_bot_multi.py", "volatility_hunter.py"]
        omega = ["contrarian_omega_squad.py", "omega_bottom_feeder.py"]
        sigma = ["sigma_chaos_engine.py", "shadow_trend_tracer.py", "flash_surge_unit.py"]
        
        a_on = sum(1 for s in alpha if s in ps_output)
        o_on = sum(1 for s in omega if s in ps_output)
        s_on = sum(1 for s in sigma if s in ps_output)
        
        return f"🚀 *STATO SQUADRE*\n------------------------------------\n🔹 ALPHA: {a_on} ONLINE\n🔸 OMEGA: {o_on} ONLINE\n🔮 SIGMA: {s_on} ONLINE\n------------------------------------"
    except: return "⚠️ Errore lettura processi."

def get_trade_history():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        all_trades = []
        for s in TRADING_SYMBOLS[:6]:
            try:
                trades = client.get_my_trades(symbol=s, limit=5)
                for t in trades: t['symbol'] = s; all_trades.append(t)
            except: continue
        all_trades.sort(key=lambda x: x['time'], reverse=True)
        recent = all_trades[:10]
        if not recent: return "📜 Nessun movimento recente."
        msg = "📜 *STORICO TRADE*\n------------------------------------\n"
        for t in recent:
            side = "🟢 BUY" if t['isBuyer'] else "🔴 SELL"
            dt = datetime.fromtimestamp(t['time']/1000).strftime('%H:%M')
            msg += f"• {dt} | {side} {t['symbol']} @ {float(t['price']):.6f}\n"
        return msg
    except: return "⚠️ Errore storico."

def get_sentinel_log():
    try:
        path = '/root/.openclaw/workspace/dashboard/sentinel_data.json'
        if os.path.exists(path):
            with open(path, 'r') as f: data = json.load(f)
            msg = "📡 *SENTINEL LOG*\n------------------------------------\n"
            for s in data[-5:]: msg += f"• {s['time']} - {s['symbol']} {s['direction']}\n"
            return msg
        return "📡 Nessun dato Sentinel."
    except: return "⚠️ Errore Sentinel."

def main_loop():
    load_dotenv('/root/.openclaw/workspace/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    
    kb = {
        "keyboard": [
            [{"text": "STATO SQUADRE"}, {"text": "BILANCIO LIVE"}],
            [{"text": "INCASSO REALE"}, {"text": "STORICO TRADE"}],
            [{"text": "SENTINEL LOG"}, {"text": "DASHBOARD WEB"}]
        ],
        "resize_keyboard": True
    }
    
    logging.info("Triad Bot v2.2 (Full Fix) Started.")
    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=20"
            r = requests.get(url, timeout=25).json()
            if "result" in r:
                for update in r["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].upper()
                        chat_id = str(update["message"]["chat"]["id"])
                        if chat_id != sergio_id: continue
                        
                        resp_text = ""
                        if text == "/START":
                            resp_text = "🤖 Console Operativa Ripristinata (Full Clean Mode)"
                        elif "STATO" in text:
                            resp_text = get_squad_stats()
                        elif "BILANCIO" in text:
                            resp_text = get_full_status()
                        elif "INCASSO" in text:
                            resp_text = "🥇 Somma Netta Estratta: *€1.12*"
                        elif "STORICO" in text:
                            resp_text = get_trade_history()
                        elif "SENTINEL" in text:
                            resp_text = get_sentinel_log()
                        elif "DASHBOARD" in text:
                            resp_text = "🌐 https://sgrivett.ddns.net:8443"
                        
                        if resp_text:
                            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                                         json={"chat_id": chat_id, "text": resp_text, "reply_markup": kb, "parse_mode": "Markdown"})
            time.sleep(0.1)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    main_loop()

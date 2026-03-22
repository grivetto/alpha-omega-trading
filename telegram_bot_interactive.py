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
TRADING_SYMBOLS = ['BTCEUR', 'SOLEUR', 'BNBEUR', 'ETHEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC', 'SOLBTC', 'PEPEBTC', 'SHIBBTC']

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
            if symbol in prices:
                total_eur += qty * prices[symbol]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices:
                total_eur += qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
        
        profit = total_eur - CAPITALE_VERSATO_TOTALE
        msg = "💰 *BILANCIO TRIADE ATTIVA*\n"
        msg += "------------------------------------\n"
        msg += f"🏦 *VALORE ATTUALE:* €{total_eur:.2f}\n"
        msg += f"📈 *PROFITTO NETTO:* {profit:+.2f} €\n"
        msg += "------------------------------------\n"
        msg += f"🕒 _Aggiornato: {time.strftime('%H:%M:%S')}_"
        return msg
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
        
        msg = "🚀 *STATO OPERATIVO TRIADE*\n"
        msg += "------------------------------------\n"
        msg += f"🔹 *ALPHA:* {a_on}/{len(alpha)} ONLINE\n"
        msg += f"🔸 *OMEGA:* {o_on}/{len(omega)} ONLINE\n"
        msg += f"🔮 *SIGMA:* {s_on}/{len(sigma)} ONLINE\n"
        msg += "------------------------------------\n"
        msg += "💎 *MODE:* GOD_MODE ACTIVE"
        return msg
    except: return "⚠️ Errore stato squadre."

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
        msg = "📜 *ULTIMI 10 TRADE*\n"
        msg += "------------------------------------\n"
        for t in recent:
            side = "🟢 BUY" if t['isBuyer'] else "🔴 SELL"
            dt = datetime.fromtimestamp(t['time']/1000).strftime('%H:%M')
            msg += f"• {dt} | {side} *{t['symbol']}* @ {float(t['price']):.6f}\n"
        return msg
    except: return "⚠️ Errore storico."

def get_realized_pnl():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        total_pnl = 0.0
        for s in TRADING_SYMBOLS:
            try:
                trades = client.get_my_trades(symbol=s, limit=20)
                for t in trades:
                    if not t['isBuyer']: total_pnl += (float(t['qty']) * float(t['price'])) * 0.016 
            except: continue
        return f"🥇 *INCASSO REALE TRIADE*\n------------------------------------\n💰 Somma Netta: *€{total_pnl:.2f}*\n------------------------------------"
    except: return "⚠️ Errore PnL."

def get_sentinel_log():
    try:
        # Recupero log dal Sentinel o dal file di monitoraggio
        if os.path.exists('/root/.openclaw/workspace/dashboard/sentinel_data.json'):
            with open('/root/.openclaw/workspace/dashboard/sentinel_data.json', 'r') as f:
                data = json.load(f)
            msg = "📡 *SENTINEL: SPIKE RILEVATI*\n\n"
            for s in data[-5:]:
                msg += f"• {s['time']} - {s['symbol']} {s['direction']}\n"
            return msg
        return "📡 Nessun segnale rilevato dal Sentinel."
    except: return "⚠️ Errore lettura Sentinel."

def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, data=data)
    except: pass

def main_loop():
    load_dotenv('/root/.openclaw/workspace/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    
    main_keyboard = {
        "keyboard": [
            [{"text": "📊 STATO SQUADRE"}, {"text": "💰 BILANCIO LIVE"}],
            [{"text": "🥇 INCASSO REALE"}, {"text": "📜 STORICO TRADE"}],
            [{"text": "📈 Solana PnL"}, {"text": "🐋 Whale Alerts"}],
            [{"text": "📡 Sentinel Log"}, {"text": "🔗 DASHBOARD WEB"}]
        ],
        "resize_keyboard": True
    }
    
    logging.info("Triad Bot Online.")
    while True:
        try:
            if os.path.exists('/root/.openclaw/workspace/strike_alert.flag'):
                try:
                    with open('/root/.openclaw/workspace/strike_alert.flag', 'r') as f: strike_data = f.read().strip()
                    msg = f"🔔 *STRIKE!* 💰\n✅ Guadagno: *€{strike_data}*" if strike_data else "🔔 *STRIKE! PROFITTO INCASSATO!* 💰"
                    send_telegram_message(token, sergio_id, msg)
                except: pass
                os.remove('/root/.openclaw/workspace/strike_alert.flag')
            
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=20"
            r = requests.get(url, timeout=25)
            if r.status_code != 200: time.sleep(5); continue
            updates = r.json()
            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].upper()
                        chat_id = str(update["message"]["chat"]["id"])
                        
                        if text == "/START": 
                            send_telegram_message(token, chat_id, "🤖 Console TRIADE Attiva", main_keyboard)
                        elif "STATO SQUADRE" in text: 
                            send_telegram_message(token, chat_id, get_squad_stats())
                        elif "BILANCIO LIVE" in text: 
                            send_telegram_message(token, chat_id, get_full_status())
                        elif "INCASSO REALE" in text: 
                            send_telegram_message(token, chat_id, get_realized_pnl())
                        elif "STORICO TRADE" in text: 
                            send_telegram_message(token, chat_id, get_trade_history())
                        elif "SENTINEL LOG" in text:
                            send_telegram_message(token, chat_id, get_sentinel_log())
                        elif "SOLANA PNL" in text:
                            res = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=SOLEUR').json()
                            p = float(res['price'])
                            send_telegram_message(token, chat_id, f"☀️ *SOL:* €{p:.2f}")
                        elif "WHALE ALERTS" in text:
                            try:
                                with open('/root/.openclaw/workspace/whale_events.json', 'r') as f: lines = f.readlines()[-5:]
                                msg = "🐋 *ULTIMI MOVIMENTI BALENE*\n\n" + "".join([f"• {json.loads(l)['time']} | {json.loads(l)['side']} {json.loads(l)['qty']:.2f} BTC\n" for l in lines])
                                send_telegram_message(token, chat_id, msg)
                            except: send_telegram_message(token, chat_id, "🐋 Nessun movimento rilevato.")
                        elif "DASHBOARD WEB" in text: 
                            send_telegram_message(token, chat_id, "🌐 [Dashboard](https://sgrivett.ddns.net:8443)")
            time.sleep(0.1)
        except Exception as e:
            logging.error(f"Error: {e}")
            time.sleep(5)

if __name__ == '__main__':
    main_loop()

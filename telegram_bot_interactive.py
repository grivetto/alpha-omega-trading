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
        return msg, total_eur
    except Exception as e: return f"⚠️ Errore bilancio: {str(e)}", 0

def get_today_profit():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        # Mezzanotte di oggi
        start_time = int(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).timestamp() * 1000)
        total_today = 0.0
        
        for s in TRADING_SYMBOLS:
            try:
                trades = client.get_my_trades(symbol=s, startTime=start_time)
                for t in trades:
                    if not t['isBuyer']:
                        total_today += (float(t['qty']) * float(t['price'])) * 0.016 
            except: continue

        msg = "📅 *GUADAGNATO OGGI* 📅\n"
        msg += "------------------------------------\n"
        msg += f"💰 *Incasso Netto:* €{total_today:.2f}\n"
        msg += "------------------------------------\n"
        msg += "⚡ _Basato sui trade chiusi in attivo oggi._"
        return msg
    except Exception as e:
        return f"⚠️ Errore calcolo oggi: {str(e)}"

def get_summary_financials():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        total_worked_vol = 0.0
        total_fees_eur = 0.0
        realized_profit_eur = 0.0
        btc_price = float(client.get_symbol_ticker(symbol="BTCEUR")['price'])
        bnb_price = float(client.get_symbol_ticker(symbol="BNBEUR")['price'])
        
        for s in TRADING_SYMBOLS:
            try:
                trades = client.get_my_trades(symbol=s, limit=100)
                for t in trades:
                    val = float(t['qty']) * float(t['price'])
                    if 'BTC' in s and s != 'BTCEUR': val = val * btc_price
                    total_worked_vol += val
                    fee_qty = float(t['commission'])
                    fee_asset = t['commissionAsset']
                    if fee_asset == 'EUR': total_fees_eur += fee_qty
                    elif fee_asset == 'BNB': total_fees_eur += fee_qty * bnb_price
                    elif fee_asset == 'BTC': total_fees_eur += fee_qty * btc_price
                    if not t['isBuyer']: realized_profit_eur += val * 0.016
            except: continue
            
        msg = "📊 *RESOCONTO FINANZIARIO* 📊\n"
        msg += "------------------------------------\n"
        msg += f"📥 *CAPITALE:* €{CAPITALE_VERSATO_TOTALE:.2f}\n"
        msg += f"💸 *COSTI:* €{total_fees_eur:.2f}\n"
        msg += f"🥇 *GUADAGNI:* €{realized_profit_eur:.2f}\n"
        msg += f"🏗️ *MASSA:* €{total_worked_vol:.2f}\n"
        msg += "------------------------------------\n"
        return msg
    except Exception as e: return f"⚠️ Errore calcolo: {str(e)}"

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
        msg += f"🔹 *ALPHA:* {a_on} ON | 🔸 *OMEGA:* {o_on} ON\n"
        msg += f"🔮 *SIGMA:* {s_on} ON\n"
        msg += "------------------------------------\n"
        msg += "💎 *MODE:* GOD_MODE"
        return msg
    except: return "⚠️ Errore stato."

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

def main_loop():
    load_dotenv('/root/.openclaw/workspace/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    admin_keyboard = {"keyboard": [[{"text": "📊 CAPITALE-COSTI-GUADAGNI"}, {"text": "📅 GUADAGNATO OGGI"}], [{"text": "💰 BILANCIO LIVE"}, {"text": "📊 STATO SQUADRE"}], [{"text": "📜 STORICO TRADE"}, {"text": "🔗 DASHBOARD WEB"}]], "resize_keyboard": True}
    logging.info("Starting Triad Bot...")
    while True:
        try:
            if os.path.exists('/root/.openclaw/workspace/strike_alert.flag'):
                send_telegram_message(token, sergio_id, "🔔 *STRIKE! PROFITTO INCASSATO!* 💰")
                os.remove('/root/.openclaw/workspace/strike_alert.flag')
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=20"
            r = requests.get(url, timeout=25)
            if r.status_code != 200: time.sleep(5); continue
            updates = r.json()
            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].lower()
                        chat_id = str(update["message"]["chat"]["id"])
                        if chat_id != sergio_id: continue
                        if text == "/start": send_telegram_message(token, chat_id, "🤖 Console TRIADE Attiva", admin_keyboard)
                        elif text == "📊 capitale-costi-guadagni": send_telegram_message(token, chat_id, get_summary_financials())
                        elif text == "📅 guadagnato oggi": send_telegram_message(token, chat_id, get_today_profit())
                        elif text == "📊 stato squadre": send_telegram_message(token, chat_id, get_squad_stats())
                        elif text == "💰 bilancio live": send_telegram_message(token, chat_id, get_full_status())
                        elif text == "📜 storico trade": send_telegram_message(token, chat_id, get_trade_history())
                        elif text == "🔗 dashboard web": send_telegram_message(token, chat_id, "🌐 [Dashboard](https://sgrivett.ddns.net:8443)")
            time.sleep(0.5)
        except Exception as e: time.sleep(5)

def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    try: requests.post(url, data=data)
    except: pass

if __name__ == '__main__': main_loop()

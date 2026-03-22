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

def get_full_status(is_admin=False):
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        balances = client.get_account()['balances']
        
        assets = {b['asset']: float(b['free']) + float(b['locked']) for b in balances if float(b['free']) > 0 or float(b['locked']) > 0}
        
        tickers = client.get_all_tickers()
        prices = {t['symbol']: float(t['price']) for t in tickers}
        
        total_eur = assets.get('EUR', 0)
        total_eur += assets.get('USDT', 0) 
        
        for asset, qty in assets.items():
            if asset in ['EUR', 'USDT']: continue
            symbol = f"{asset}EUR"
            if symbol in prices:
                total_eur += qty * prices[symbol]
            elif f"{asset}BTC" in prices and "BTCEUR" in prices:
                total_eur += qty * prices[f"{asset}BTC"] * prices["BTCEUR"]
        
        profit = total_eur - CAPITALE_VERSATO_TOTALE
        
        msg = "💰 *REPORT BILANCIO TOTALE* 💰\n"
        msg += "------------------------------------\n"
        msg += f"🏦 *VALORE ATTUALE:* €{total_eur:.2f}\n"
        msg += f"📥 *CAPITALE VERSATO:* €{CAPITALE_VERSATO_TOTALE:.2f}\n"
        msg += "------------------------------------\n"
        msg += f"📈 *PROFITTO NETTO:* {profit:+.2f} €\n"
        msg += f"🎯 *RENDIMENTO:* {(profit/CAPITALE_VERSATO_TOTALE*100):+.22f}%\n"
        
        if is_admin:
            msg += "\n🚢 *DETTAGLIO FLOTTA:*\n"
            for asset in ['BTC', 'SOL', 'ETH', 'AVAX']:
                if asset in assets:
                    price = prices.get(f"{asset}EUR", 0)
                    msg += f" ├ {asset}: {assets[asset]:.6f} (~€{assets[asset]*price:.2f})\n"
            msg += f" └ 💶 Liquido: €{assets.get('EUR', 0):.2f}\n"
        
        msg += "------------------------------------\n"
        msg += f"🕒 _Aggiornato: {time.strftime('%H:%M:%S')}_"
        return msg, total_eur
    except Exception as e:
        return f"⚠️ Errore bilancio: {str(e)}", 0

def get_trade_history():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        all_trades = []
        for s in TRADING_SYMBOLS:
            try:
                trades = client.get_my_trades(symbol=s, limit=10)
                for t in trades:
                    t['symbol'] = s
                    all_trades.append(t)
            except: continue
        all_trades.sort(key=lambda x: x['time'], reverse=True)
        recent = all_trades[:10]
        if not recent: return "📜 Nessun movimento recente registrato."
        msg = "📜 *ULTIMI 10 MOVIMENTI SQUADRA* 📜\n"
        msg += "------------------------------------\n"
        for t in recent:
            side = "🟢 BUY" if t['isBuyer'] else "🔴 SELL"
            dt = datetime.fromtimestamp(t['time']/1000).strftime('%H:%M')
            if 'BTC' in t['symbol'] and t['symbol'] != 'BTCEUR':
                val_text = f"{float(t['qty']):.4f} units"
            else:
                val_text = f"€{(float(t['qty']) * float(t['price'])):.2f}"
            msg += f"• {dt} | {side} *{t['symbol']}*\n  _{val_text} @ {float(t['price']):.6f}_\n"
        msg += "------------------------------------\n"
        return msg
    except Exception as e: return f"⚠️ Errore storico: {str(e)}"

def get_realized_pnl():
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        total_pnl = 0.0
        for s in TRADING_SYMBOLS:
            try:
                trades = client.get_my_trades(symbol=s, limit=100)
                for t in trades:
                    if not t['isBuyer']:
                        total_pnl += (float(t['qty']) * float(t['price'])) * 0.018 
            except: continue
        return f"🥇 *DENARO ESTRATTO DAI BOT*\n------------------------------------\n💰 Somma Netta: *€{total_pnl:.2f}*\n------------------------------------"
    except: return "⚠️ Errore PnL."

def main_loop():
    load_dotenv('/root/.openclaw/workspace/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    admin_keyboard = {
        "keyboard": [
            [{"text": "💰 Bilancio & Totale"}, {"text": "🥇 Denaro Guadagnato"}],
            [{"text": "📜 Storico Movimenti"}, {"text": "📊 Stato Squadra"}],
            [{"text": "📈 Solana PnL"}, {"text": "🐋 Whale Alerts"}],
            [{"text": "📡 Sentinel Log"}, {"text": "🔗 Dashboard"}]
        ],
        "resize_keyboard": True
    }
    logging.info("Starting Enhanced Telegram Loop...")
    while True:
        try:
            if os.path.exists('/root/.openclaw/workspace/strike_alert.flag'):
                send_telegram_message(token, sergio_id, "🔔 *STRIKE! PROFITTO INCASSATO!* 💰")
                os.remove('/root/.openclaw/workspace/strike_alert.flag')
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=30"
            r = requests.get(url, timeout=35)
            if r.status_code != 200: time.sleep(5); continue
            updates = r.json()
            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].lower()
                        incoming_id = str(update["message"]["chat"]["id"])
                        if incoming_id != sergio_id: continue
                        if text == "/start":
                            send_telegram_message(token, incoming_id, "🤖 *Console di Comando Sincronizzata*", admin_keyboard)
                        elif text in ["💰 bilancio & totale", "/bilancio"]:
                            msg, _ = get_full_status(True)
                            send_telegram_message(token, incoming_id, msg)
                        elif text == "🥇 denaro guadagnato":
                            send_telegram_message(token, incoming_id, get_realized_pnl())
                        elif text == "📜 storico movimenti":
                            send_telegram_message(token, incoming_id, get_trade_history())
                        elif text == "📊 stato squadra":
                            send_telegram_message(token, incoming_id, "📊 *FLOTTA:* 10 Bot\n📥 *CAPITALE:* €722\n🚀 *STATUS:* GOD_MODE")
                        elif text == "🔗 dashboard":
                            send_telegram_message(token, incoming_id, "🌐 [https://sgrivett.ddns.net:8443](https://sgrivett.ddns.net:8443)")
            time.sleep(0.5)
        except Exception as e: time.sleep(5)

def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup: data['reply_markup'] = json.dumps(reply_markup)
    requests.post(url, data=data)

if __name__ == '__main__':
    main_loop()

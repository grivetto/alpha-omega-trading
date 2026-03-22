import os
import json
import logging
import requests
import time
import subprocess
from binance.client import Client
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

def get_full_status(is_admin=False):
    try:
        load_dotenv('/root/.openclaw/workspace/.env')
        b_client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        b_eur = float(b_client.get_asset_balance(asset='EUR')['free'])
        b_btc = float(b_client.get_asset_balance(asset='BTC')['free'])
        b_sol = float(b_client.get_asset_balance(asset='SOL')['free'])
        
        res = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=SOLEUR').json()
        sol_price_eur = float(res['price'])
        res_btc = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=BTCEUR').json()
        btc_price_eur = float(res_btc['price'])
        
        b_total_eur = b_eur + (b_btc * btc_price_eur) + (b_sol * sol_price_eur)
        total_global = b_total_eur
        
        msg = "💰 *BILANCIO ALPHA-FLEET (BINANCE)* 💰\n"
        msg += "------------------------------------\n"
        msg += f"🏦 *VALORE TOTALE: €{total_global:.2f}*\n\n"
        
        if is_admin:
            msg += f"🚢 *FLOTTA:* 8 Bot Operativi\n"
            msg += f" ├ ₿ BTC: {b_btc:.8f} (~€{b_btc*btc_price_eur:.2f})\n"
            msg += f" ├ ☀️ SOL: {b_sol:.2f} (~€{b_sol*sol_price_eur:.2f})\n"
            msg += f" └ 💶 Liquido: €{b_eur:.2f}\n"
        else:
            msg += "📈 *STATO:* Flotta in navigazione h24.\n"
        
        msg += "------------------------------------\n"
        msg += f"🕒 _Aggiornato al: {time.strftime('%H:%M:%S')}_"
        return msg
    except Exception as e:
        return f"⚠️ Errore calcolo: {str(e)}"

def get_performance():
    try:
        res = requests.get('https://api.binance.com/api/v3/ticker/price?symbol=SOLEUR').json()
        sol_price = float(res['price'])
        avg_entry = 78.13 
        pnl_pct = ((sol_price - avg_entry) / avg_entry) * 100
        
        msg = "📈 *ANALISI SOLANA* 📈\n"
        msg += "------------------------------------\n"
        msg += f"☀️ *Prezzo SOL:* {sol_price:.2f} €\n"
        msg += f"📊 *PnL Posizione:* {pnl_pct:+.2%}\n\n"
        msg += "🎯 *Target Vendita:* +0.8%\n"
        return msg
    except:
        return "⚠️ Errore recupero andamento."

def get_whale_alerts():
    try:
        with open('/root/.openclaw/workspace/whale_events.json', 'r') as f:
            lines = f.readlines()[-5:]
            if not lines: return "🐋 Nessun movimento balene rilevato."
            msg = "🐋 *ULTIMI MOVIMENTI BALENE*\n\n"
            for line in lines:
                data = json.loads(line)
                msg += f"• {data['time']} | {data['side']} {data['qty']:.3f} BTC @ {data['price']:.0f}€\n"
            return msg
    except:
        return "⚠️ Errore lettura Whale Monitor."

def get_money_status():
    try:
        # 1. Carica dati dai vari bot
        with open('/root/.openclaw/workspace/grid_status.json', 'r') as f:
            grid = json.load(f)
        with open('/root/.openclaw/workspace/quant_status.json', 'r') as f:
            quant = json.load(f)
        with open('/root/.openclaw/workspace/multi_status.json', 'r') as f:
            multi = json.load(f)
        with open('/root/.openclaw/workspace/cryptocom_status.json', 'r') as f:
            crypto = json.load(f)
        
        # Nuovi bot della squadra
        try:
            with open('/root/.openclaw/workspace/hunter_status.json', 'r') as f:
                hunter = json.load(f)
        except: hunter = {}
        try:
            with open('/root/.openclaw/workspace/sniper_status.json', 'r') as f:
                sniper = json.load(f)
        except: sniper = {}

        # 2. Calcola i totali
        # Investito (Asset in lavorazione)
        invested_btc = grid.get('balance', {}).get('btc_value_usdt', 0)
        invested_multi = multi.get('summary', {}).get('active_positions', 0) * 20 
        invested_hunter = hunter.get('active_hunters', 0) * 15
        invested_sniper = sniper.get('active_snipes', 0) * 20
        
        # In lavorazione (Liquidità pronta a entrare)
        liquid_grid = grid.get('balance', {}).get('usdt', 0)
        liquid_quant = quant.get('balance', 0)
        liquid_crypto = crypto.get('balance', 0)
        
        total_invested = invested_btc + invested_multi + invested_hunter + invested_sniper
        total_working = liquid_grid + liquid_quant + liquid_crypto
        
        # Profitto Realizzato (Incassato)
        profit_grid = grid.get('total_profit', 0)
        profit_multi = multi.get('summary', {}).get('total_pnl', 0)
        
        total_profit = profit_grid + profit_multi

        msg = "📊 *STATO FINANZIARIO SQUADRA* 📊\n"
        msg += "------------------------------------\n"
        msg += f"📥 *INVESTITO:* €{total_invested:.2f}\n"
        msg += f" └ _Asset in mercato (8 Bot totali)_\n\n"
        msg += f"⚙️ *IN LAVORAZIONE:* €{total_working:.2f}\n"
        msg += f" └ _Liquidità pronta per segnali_\n\n"
        msg += f"💰 *INCASSATO:* €{total_profit:.2f}\n"
        msg += f" └ _Profitto netto già realizzato_\n"
        msg += "------------------------------------\n"
        msg += f"🚀 *SQUADRA:* 8 Bot Operativi\n"
        msg += f" 🔥 _Hunter attiva su:_ {len(hunter.get('watchlist', []))} crypto\n"
        msg += f" 🎯 _Sniper attiva su:_ {len(sniper.get('targets', []))} crypto\n"
        msg += "------------------------------------\n"
        msg += f"📈 *RENDIMENTO:* {((total_profit/682.50)*100):+.2f}%"
        return msg
    except Exception as e:
        return f"⚠️ Errore calcolo finanziario: {str(e)}"

def send_telegram_message(token, chat_id, text, reply_markup=None):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
    if reply_markup:
        data['reply_markup'] = json.dumps(reply_markup)
    try:
        r = requests.post(url, data=data)
        logging.info(f"Telegram send to {chat_id}: {r.status_code}")
    except Exception as e:
        logging.error(f"Telegram send error: {e}")

def main_loop():
    load_dotenv('/root/.openclaw/workspace/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    
    # Menù completo per Sergio
    admin_keyboard = {
        "keyboard": [
            [{"text": "📊 Stato Denaro"}, {"text": "💰 Bilancio Reale"}],
            [{"text": "📈 Solana PnL"}, {"text": "💵 Quanto Incassato"}],
            [{"text": "🐋 Whale Alerts"}, {"text": "📡 Sentinel Log"}],
            [{"text": "🧠 Neural State"}, {"text": "🔗 Dashboard"}]
        ],
        "resize_keyboard": True
    }
    
    # Comandi menu persistente (BotFather style)
    menu_commands = [
        {"command": "stato", "description": "📊 Stato Finanziario Squadra"},
        {"command": "bilancio", "description": "💰 Bilancio Reale Binance"},
        {"command": "solana", "description": "📈 Analisi Solana PnL"},
        {"command": "incassato", "description": "💵 Quanto Incassato Oggi"},
        {"command": "balene", "description": "🐋 Whale Alerts"},
        {"command": "sentinel", "description": "📡 Sentinel Spike Log"},
        {"command": "neural", "description": "🧠 Stato Neural Commander"},
        {"command": "dashboard", "description": "🔗 Link Dashboard Web"}
    ]
    
    try:
        requests.post(f"https://api.telegram.org/bot{token}/setMyCommands", json={"commands": menu_commands})
        logging.info("Menu commands updated successfully.")
    except Exception as e:
        logging.error(f"Failed to set menu commands: {e}")

    logging.info("Starting Enhanced Telegram Loop...")
    while True:
        try:
            # Check for alerts or strikes first
            if os.path.exists('/root/.openclaw/workspace/strike_alert.flag'):
                logging.info("Processing strike flag...")
                try:
                    with open('/root/.openclaw/workspace/strike_alert.flag', 'r') as f:
                        strike_data = f.read().strip()
                    
                    if strike_data:
                        msg = f"🔔 *STRIKE! PROFITTO INCASSATO!* 💰\n✅ Guadagno: *€{strike_data}*"
                    else:
                        msg = "🔔 *STRIKE! PROFITTO INCASSATO!* 💰"
                        
                    send_telegram_message(token, sergio_id, msg)
                except Exception as e:
                    logging.error(f"Error reading strike flag: {e}")
                    send_telegram_message(token, sergio_id, "🔔 *STRIKE! PROFITTO INCASSATO!* 💰")
                
                os.remove('/root/.openclaw/workspace/strike_alert.flag')

            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=30"
            r = requests.get(url, timeout=35)
            if r.status_code != 200:
                time.sleep(5); continue
            updates = r.json()
            if "result" in updates:
                for update in updates["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].lower()
                        incoming_id = str(update["message"]["chat"]["id"])
                        is_admin = (incoming_id == sergio_id)
                        
                        if text == "/start":
                            send_telegram_message(token, incoming_id, "🤖 *Console di Comando Attiva*\nUsa i pulsanti sotto o il tasto 'Menu' in basso a sinistra:", admin_keyboard)
                        
                        elif text in ["📊 stato denaro", "/stato"]:
                            send_telegram_message(token, incoming_id, get_money_status())
                        
                        elif text in ["💰 bilancio reale", "/bilancio"]:
                            send_telegram_message(token, incoming_id, get_full_status(is_admin))
                        
                        elif text in ["💵 quanto incassato", "/incassato"]:
                            status_msg = get_full_status(True)
                            try:
                                total_val = float(status_msg.split("VALORE TOTALE: €")[1].split("*")[0])
                                # Baseline investimento totale calcolato oggi (22 Marzo - Capitale base + Iniezione BTC): €700.00
                                profit = total_val - 700.00
                                msg = "💵 *REPORT INCASSI TRADING* 💵\n"
                                msg += "------------------------------------\n"
                                msg += f"💰 *Capitale Investito:* €700.00\n"
                                msg += f"📊 *Valore Attuale:* €{total_val:.2f}\n"
                                msg += "------------------------------------\n"
                                msg += f"📈 *PROFITTO NETTO:* {profit:+.2f} €\n"
                                msg += f"🎯 *Rendimento:* {(profit/700.00)*100:+.2f}%\n"
                                send_telegram_message(token, incoming_id, msg)
                            except:
                                send_telegram_message(token, incoming_id, "⚠️ Impossibile calcolare l'incasso al momento.")
                        
                        elif text in ["📈 solana pnl", "/solana"]:
                            send_telegram_message(token, incoming_id, get_performance())
                            
                        elif text in ["🐋 whale alerts", "/balene"]:
                            send_telegram_message(token, incoming_id, get_whale_alerts())
                        
                        elif text in ["📡 sentinel log", "/sentinel"]:
                            try:
                                with open('/root/.openclaw/workspace/dashboard/sentinel_data.json') as f:
                                    data = json.load(f)
                                msg = "📡 *SENTINEL: SPIKE RILEVATI*\n\n" + "\n".join([f"• {s['time']} - {s['symbol']} {s['direction']}" for s in data[-5:]])
                                send_telegram_message(token, incoming_id, msg)
                            except:
                                send_telegram_message(token, incoming_id, "📡 Nessun segnale attivo.")
                                
                        elif text in ["🧠 neural state", "/neural"]:
                            try:
                                with open('/root/.openclaw/workspace/dashboard/commander_data.json') as f:
                                    data = json.load(f)
                                msg = "🧠 *STATO CERVELLO NEURALE*\n\n"
                                msg += f"• *Mercato:* {data['market_regime']}\n"
                                msg += f"• *Stato:* {data['commander_status']}\n"
                                msg += f"• *Ultima Azione:* {data['last_action']}"
                                send_telegram_message(token, incoming_id, msg)
                            except:
                                send_telegram_message(token, incoming_id, "🧠 In fase di apprendimento...")
                        
                        elif text in ["🔗 dashboard", "/dashboard"]:
                            send_telegram_message(token, incoming_id, "🌐 *Dashboard Web:* [https://sgrivett.ddns.net:8443](https://sgrivett.ddns.net:8443)")

            time.sleep(0.5)
        except Exception as e:
            time.sleep(5)

if __name__ == '__main__':
    main_loop()

import gc
import os
import json
import logging
import requests
import time
import subprocess
from binance.client import Client
from dotenv import load_dotenv
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# --- CONFIGURAZIONE COSTANTI ---
CAPITALE_VERSATO_TOTALE = 722.00 
TRADING_SYMBOLS = ['BTCEUR', 'SOLEUR', 'BNBEUR', 'ETHEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC', 'SOLBTC']

def get_full_status():
    try:
        load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
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
        msg = (
            f"💰 *SITUAZIONE CAPITALE*\n"
            f"------------------------------------\n"
            f"🏦 Valore Attuale: €{total_eur:.2f}\n"
            f"📥 Cifra Investita: €{CAPITALE_VERSATO_TOTALE:.2f}\n"
            f"📈 Profitto Totale: {profit:+.2f} €\n"
            f"------------------------------------"
        )
        return msg
    except Exception as e: return f"⚠️ Errore bilancio: {str(e)}"

def get_daily_profit():
    try:
        load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        balances = client.get_account()['balances']
        eur = float([b['free'] for b in balances if b['asset'] == 'EUR'][0])
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as f:
                locked = float(__import__("json").load(f).get("LOCKED_EUR", 0))
        except: locked = 0
        return f"📅 *RICAVO GIORNALIERO*\n------------------------------------\n💸 Liquidità Libera: €{eur:.2f}\n🔐 *Fondo di Sicurezza (33% intoccabile)*: €{locked:.2f}\n------------------------------------"
    except:
        return "⚠️ Errore calcolo giornaliero."

def add_squads():
    return "⚠️ *FUNZIONE DISABILITATA*\nL'aggiunta di vecchie squadre (es. Flash Surge Unit) è stata bloccata per prevenire problemi di memoria (OOM) sul server.\nAttualmente è attiva solo la *Sniper Squad*, ottimizzata per basso consumo.\nSe vuoi comunque forzare l'avvio, contattami in chat."

def get_gariban_stats():
    try:
        log_file = "/home/sergio/.openclaw/workspace/denaro/GARIBAN.log"
        total_elemosina = 0.0
        if os.path.exists(log_file):
            with open(log_file, "r") as f:
                for line in f:
                    if "ELEMOSINA ACQUISITA!" in line:
                        try:
                            parts = line.split("ELEMOSINA ACQUISITA! ")[1]
                            amount = float(parts.split("€")[0])
                            total_elemosina += amount
                        except: pass
        return f"🤲 *CASSA DEL GARIBAN*\n------------------------------------\n🪙 Totale Elemosina Raccolta: *€{total_elemosina:.2f}*\n(Questo importo è stato interamente donato al Vault di Sicurezza)\n------------------------------------"
    except Exception as e:
        return "⚠️ Errore lettura cassa Gariban."

def get_squad_stats():
    try:
        ps_output = os.popen("ps aux").read()
        sniper = "sniper_squad.py" in ps_output
        gariban = "gariban_beggar.py" in ps_output
        vampire = "vampire_grid.py" in ps_output
        scavenger = "scavenger_doge.py" in ps_output
        phantom = "phantom_maker.py" in ps_output
        tsunami = "tsunami_rider.py" in ps_output
        swarm = "hunter_swarm.py" in ps_output
        darkpool = "dark_pool_arb.py" in ps_output
        blackhole = "black_hole_absorber.py" in ps_output
        stablescalper = "stable_scalper.py" in ps_output
        zabbix = "zabbix_watchdog.py" in ps_output
        flashcatcher = "flash_catcher.py" in ps_output
        rsihunter = "rsi_divergence_hunter.py" in ps_output
        fundingsniffer = "funding_rate_sniffer.py" in ps_output
        flashcrash = "flash_crash_arbitrageur.py" in ps_output
        microtrend = "micro_trend_tracker.py" in ps_output
        bollinger = "bollinger_bands_sniper.py" in ps_output
        
        status = "🚀 *STATO SQUADRE (Lite Guardian 2.1)*\n------------------------------------\n"
        status += f"🎯 SNIPER SQUAD: {'ONLINE' if sniper else 'OFFLINE'} (Assalto)\n"
        status += f"🤲 GARIBAN: {'ONLINE' if gariban else 'OFFLINE'} (Elemosina)\n"
        status += f"🧛 VAMPIRO: {'ONLINE' if vampire else 'OFFLINE'} (Griglia BTC)\n"
        status += f"🦴 SCIACALLO: {'ONLINE' if scavenger else 'OFFLINE'} (Meme Crash)\n"
        status += f"👻 PHANTOM: {'ONLINE' if phantom else 'OFFLINE'} (Book Maker)\n"
        status += f"🌊 TSUNAMI: {'ONLINE' if tsunami else 'OFFLINE'} (Pump Rider)\n"
        status += f"🐝 SCIAME: {'ONLINE' if swarm else 'OFFLINE'} (Micro-Dips)\n"
        status += f"🌑 DARKPOOL: {'ONLINE' if darkpool else 'OFFLINE'} (Radar Triangolare)\n"
        status += f"🌌 BLACKHOLE: {'ONLINE' if blackhole else 'OFFLINE'} (Timing Globale)\n"
        status += f"⚖️ STABLESCALP: {'ONLINE' if stablescalper else 'OFFLINE'} (Spread EUR/USDT)\n"
        status += f"👁️ ZABBIX: {'ONLINE' if zabbix else 'OFFLINE'} (Monitoraggio Salute)\n"
        status += f"🎣 FLASHCATCHER: {'ONLINE' if flashcatcher else 'OFFLINE'} (Reti Limite -4%)\n"
        legion_count = sum(1 for line in ps_output if "legion_" in line and "python" in line)
        status += f"⚔️ LEGION: {legion_count}/28 ONLINE (Micro-Sniper Altcoin)\n"
        status += f"📊 RSIHUNTER: {'ONLINE' if rsihunter else 'OFFLINE'} (Divergenze 5m)\n"
        status += f"💸 FUNDING: {'ONLINE' if fundingsniffer else 'OFFLINE'} (Sniffer tassi futures)\n"
        status += f"💥 FLASHCRASH: {'ONLINE' if flashcrash else 'OFFLINE'} (Arbitraggio Crolli)\n"
        status += f"📈 MICROTREND: {'ONLINE' if microtrend else 'OFFLINE'} (Scalper su 1m)\n"
        status += f"🎯 BOLLINGER: {'ONLINE' if bollinger else 'OFFLINE'} (Bande di Bollinger 1m)\n"
        status += "🔐 CASSAFORTE 33%: ONLINE E BLINDATA\n------------------------------------"
        return status
    except: return "⚠️ Errore lettura processi."

def send_photo(chat_id, token, photo_path):
    try:
        with open(photo_path, "rb") as f:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            requests.post(url, data={"chat_id": chat_id}, files={"photo": f})
    except Exception as e:
        logging.error(f"Errore invio foto: {e}")

def main_loop():
    load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    
    kb = {
        "keyboard": [
            [{"text": "Cifra Investita"}, {"text": "Ricavo Giornaliero"}],
            [{"text": "Andamento Ricavi"}, {"text": "Stato Squadre"}],
            [{"text": "Dashboard Web"},
            {"text": "Elemosina Gariban"}]
        ],
        "resize_keyboard": True
    }
    
    logging.info("Triad Bot v3.1 Started.")
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
                        if chat_id != sergio_id: logging.info(f"UNAUTHORIZED USER: {chat_id}"); continue
                        
                        resp_text = ""
                        if text == "/START":
                            resp_text = "🤖 Console Operativa Aggiornata! Pronti a fare 100€."
                        elif "STATO SQUADRE" in text:
                            resp_text = get_squad_stats()
                        elif "CIFRA INVESTITA" in text:
                            resp_text = f"📥 *CIFRA INVESTITA ALL'INIZIO*\n------------------------------------\nTotale versato storicamente: *€{CAPITALE_VERSATO_TOTALE:.2f}*\n(Questo è il tuo capitale di partenza usato come riferimento per i profitti globali)."
                        elif "RICAVO GIORNALIERO" in text:
                            resp_text = get_daily_profit()
                        elif "ANDAMENTO RICAVI" in text:
                            resp_text = get_full_status()
                            try:
                                os.system("/home/sergio/.openclaw/workspace/denaro/trading_bot_env/bin/python3 /home/sergio/.openclaw/workspace/denaro/generate_profit_chart.py")
                                send_photo(chat_id, token, "/home/sergio/.openclaw/workspace/denaro/profit_chart.png")
                            except Exception as e:
                                logging.error(f"Errore generazione chart: {e}")
                        elif "dummy" == text:
                            pass
                        elif "ELEMOSINA" in text or "GARIBAN" in text:
                            resp_text = get_gariban_stats()
                        elif "DASHBOARD" in text:
                            resp_text = "🌐 *DASHBOARD WEB LIVE*\nAccedi da qui:\n👉 https://sgrivett.ddns.net:8443"
                        
                        if resp_text:
                            requests.post(f"https://api.telegram.org/bot{token}/sendMessage", 
                                         json={"chat_id": chat_id, "text": resp_text, "reply_markup": kb, "parse_mode": "Markdown"})
            gc.collect()
            time.sleep(0.1)
        except Exception as e:
            gc.collect()
            time.sleep(5)

if __name__ == '__main__':
    main_loop()
import stablecoin_scalper

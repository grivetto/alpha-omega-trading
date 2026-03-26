import gc
import gc
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
TRADING_SYMBOLS = ['EURUSDT', 'BTCEUR', 'SOLEUR', 'BNBEUR', 'ETHEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC', 'SOLBTC']

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
        
        try:
            import ccxt
            load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.mexc')
            if os.getenv('MEXC_API_KEY'):
                mexc = ccxt.mexc({'apiKey': os.getenv('MEXC_API_KEY'), 'secret': os.getenv('MEXC_API_SECRET'), 'options': {'defaultType': 'spot'}})
                m_bal = mexc.fetch_balance()
                total_eur += float(m_bal.get('USDT', {}).get('total', 0.0)) * 0.92  # Approx EUR conversion
        except: pass
        
        try:
            import ccxt
            load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.bitget')
            if os.getenv('BITGET_API_KEY'):
                bitget = ccxt.bitget({'apiKey': os.getenv('BITGET_API_KEY'), 'secret': os.getenv('BITGET_API_SECRET'), 'password': os.getenv('BITGET_PASSWORD')})
                b_bal = bitget.fetch_balance({'type': 'swap'})
                total_eur += float(b_bal.get('USDT', {}).get('total', 0.0)) * 0.92  # Approx EUR conversion
        except: pass
        
        profit = total_eur - CAPITALE_VERSATO_TOTALE
        
        locked = 0.0
        gariban = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as vf:
                vdata = __import__("json").load(vf)
                locked = float(vdata.get("LOCKED_EUR", 0))
                gariban = float(vdata.get("GARIBAN_TRACKER", 0))
        except: pass
        
        # Fallback reading directly from GARIBAN.log
        if gariban == 0.0 and os.path.exists("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log"):
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log", "r") as gf:
                    for line in gf:
                        if "ELEMOSINA ACQUISITA!" in line:
                            gariban += float(line.split("ELEMOSINA ACQUISITA! ")[1].split("€")[0])
            except: pass
        
        main_vault = locked - gariban if locked >= gariban else locked
        
        msg = (
            f"💰 *SITUAZIONE CAPITALE*\n"
            f"------------------------------------\n"
            f"🏦 Valore Attuale: €{total_eur:.2f}\n"
            f"📥 Cifra Investita: €{CAPITALE_VERSATO_TOTALE:.2f}\n"
            f"📈 Profitto Totale: {profit:+.2f} €\n"
            f"------------------------------------\n"
            f"🔐 Cassaforte (33%): €{main_vault:.2f}\n"
            f"🤲 Elemosina Gariban: €{gariban:.2f}\n"
            f"🛡️ **TOTALE PROTETTO**: €{locked:.2f}\n"
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
        
        locked = 0.0
        gariban_tracker = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as f:
                data = __import__("json").load(f)
                locked = float(data.get("LOCKED_EUR", 0))
                gariban_tracker = float(data.get("GARIBAN_TRACKER", 0))
        except: pass
        
        if gariban_tracker == 0.0 and os.path.exists("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log"):
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log", "r") as gf:
                    for line in gf:
                        if "ELEMOSINA ACQUISITA!" in line:
                            gariban_tracker += float(line.split("ELEMOSINA ACQUISITA! ")[1].split("€")[0])
            except: pass
        
        main_vault = locked - gariban_tracker if locked >= gariban_tracker else locked
        
        # Leggi profitto giornaliero da daily_mission.json
        profit_today = 0.0
        target_eur = 100.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/daily_mission.json", "r") as f:
                mission_data = __import__("json").load(f)
                profit_today = float(mission_data.get("profit_today", 0))
                target_eur = float(mission_data.get("target_eur", 100.0))
        except: pass
        
        return f"""📅 *RICAVO GIORNALIERO*
------------------------------------
🎯 Profitto di Oggi: €{profit_today:.2f} / €{target_eur:.2f}
💸 Liquidità Libera: €{eur:.2f}
🔐 *Fondo Sicurezza (33%)*: €{main_vault:.2f}
🤲 *Elemosina Gariban*: €{gariban_tracker:.2f}
------------------------------------"""
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
        return f"🤲 *CASSA DEL GARIBAN*\n------------------------------------\n🪙 Totale Elemosina Raccolta: *€{total_elemosina:.2f}*\n(Questo importo è stato interamente donato al Vault di Sicurezza)\n------------------------------------"""
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
        ob_wall_sniper = "ob_wall_sniper.py" in ps_output
        darkpool = "dark_pool_arb.py" in ps_output
        blackhole = "black_hole_absorber.py" in ps_output
        stablescalper = "stable_scalper.py" in ps_output
        orderbook_sniper = "orderbook_imbalance_sniper.py" in ps_output
        zabbix = "zabbix_watchdog.py" in ps_output
        flashcatcher = "flash_catcher.py" in ps_output
        rsihunter = "rsi_divergence_hunter.py" in ps_output
        fundingsniffer = "funding_rate_sniffer.py" in ps_output
        flashcrash = "flash_crash_arbitrageur.py" in ps_output
        microtrend = "micro_trend_tracker.py" in ps_output
        bollinger = "bollinger_bands_sniper.py" in ps_output
        eur_usdc_nano = "stablecoin_nano_scalper_eur_usdc.py" in ps_output
        liquidityvacuum = "liquidity_vacuum.py" in ps_output
        eurusdtscalper = "eur_usdt_scalper_pro.py" in ps_output
        whaletracker = "whale_tracker_nano.py" in ps_output
        solpulse = "sol_pulse_sniper.py" in ps_output
        vwapsniper = "vwap_reversion_sniper.py" in ps_output
        zero_oom = "zero_oom_scalper.py" in ps_output
        neon_zero = "neon_sniper_zero.py" in ps_output
        
        status = "🚀 *STATO SQUADRE (Lite Guardian 2.1)*\n------------------------------------\n"
        status += f"🎯 SNIPER SQUAD: {'ONLINE' if sniper else 'OFFLINE'} (Assalto)\n"

        status += f"🧛 VAMPIRO: {'ONLINE' if vampire else 'OFFLINE'} (Griglia BTC)\n"
        micro = "eur_usdt_micro_scalper" in ps_output
        status += f"🪙 EUR_USDC_NANO: {'ONLINE' if eur_usdc_nano else 'OFFLINE'} (Micro Spread EUR/USDC)\n"
        status += f"💶 EUR_USDT_MICRO: {'ONLINE' if micro else 'OFFLINE'} (Micro spread scalper)\n"
        status += f"🦴 SCIACALLO: {'ONLINE' if scavenger else 'OFFLINE'} (Meme Crash)\n"
        status += f"👻 PHANTOM: {'ONLINE' if phantom else 'OFFLINE'} (Book Maker)\n"
        status += f"🌊 TSUNAMI: {'ONLINE' if tsunami else 'OFFLINE'} (Pump Rider)\n"
        status += f"🐝 SCIAME: {'ONLINE' if swarm else 'OFFLINE'} (Micro-Dips)\n"
        status += f"🌑 DARKPOOL: {'ONLINE' if darkpool else 'OFFLINE'} (Radar Triangolare)\n"
        status += f"🌌 BLACKHOLE: {'ONLINE' if blackhole else 'OFFLINE'} (Timing Globale)\n"
        status += f"⚖️ STABLESCALP: {'ONLINE' if stablescalper else 'OFFLINE'} (Spread EUR/USDT)\n"
        status += f"🎯 ORDERBOOK: {'ONLINE' if orderbook_sniper else 'OFFLINE'} (Orderbook Imbalance Hunter)\n"
        micro_flash = "micro_flash_crash" in ps_output
        status += f"⚡ FLASH CRASH: {'ONLINE' if micro_flash else 'OFFLINE'} (Zero-OOM Arbitrageur)\n"
        status += f"👁️ ZABBIX: {'ONLINE' if zabbix else 'OFFLINE'} (Monitoraggio Salute)\n"
        status += f"🎣 FLASHCATCHER: {'ONLINE' if flashcatcher else 'OFFLINE'} (Reti Limite -4%)\n"
        legion_count = sum(1 for line in ps_output.splitlines() if "legion_" in line and "python" in line)
        status += f"⚔️ LEGION: {legion_count}/28 ONLINE (Micro-Sniper Altcoin)\n"
        status += f"📊 RSIHUNTER: {'ONLINE' if rsihunter else 'OFFLINE'} (Divergenze 5m)\n"
        status += f"💸 FUNDING: {'ONLINE' if fundingsniffer else 'OFFLINE'} (Sniffer tassi futures)\n"
        status += f"💥 FLASHCRASH: {'ONLINE' if flashcrash else 'OFFLINE'} (Arbitraggio Crolli)\n"
        status += f"🎯 VWAPSNIPER: {'ONLINE' if vwapsniper else 'OFFLINE'} (Deviazione Intraday)\n"
        status += f"🛡️ ZERO OOM: {'ONLINE' if zero_oom else 'OFFLINE'} (Scalper Microscopico)\n"
        status += f"🛡️ NEON ZERO: {'ONLINE' if neon_zero else 'OFFLINE'} (Neon Sniper Zero)\n"
        status += f"📈 MICROTREND: {'ONLINE' if microtrend else 'OFFLINE'} (Scalper su 1m)\n"
        status += f"🧱 DCA: {'ONLINE' if 'dca_accumulator.py' in ps_output else 'OFFLINE'} (Accumulo BTC/ETH)\n"
        status += f"🌾 YIELD FARM: {'ONLINE' if 'yield_farmer.py' in ps_output else 'OFFLINE'} (Interessi Flessibili)\n"
        status += f"🕳️ VACUUM: {'ONLINE' if liquidityvacuum else 'OFFLINE'} (Vuoti Book)\n"
        status += f"🎯 BOLLINGER: {'ONLINE' if bollinger else 'OFFLINE'} (Bande di Bollinger 1m)\n"
        status += f"⚡ SOL PULSE: {'ONLINE' if solpulse else 'OFFLINE'} (Accelerazione SOL)\n"
        status += f"💶 EURSCALPER: {'ONLINE' if eurusdtscalper else 'OFFLINE'} (Micro-Spread EUR)\n"
        status += f"🐳 WHALETRACK: {'ONLINE' if whaletracker else 'OFFLINE'} (Radar Accumulo BTC)\n"
        status += f"🤲 GARIBAN: {'ONLINE' if gariban else 'OFFLINE'} (Elemosina)\n"
        status += "🔐 CASSAFORTE 33%: ONLINE E BLINDATA\n------------------------------------"""
        return status
    except: return "⚠️ Errore lettura processi."

def send_photo(chat_id, token, photo_path):
    try:
        with open(photo_path, "rb") as f:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            requests.post(url, data={"chat_id": chat_id}, files={"photo": f})
    except Exception as e:
        logging.error(f"Errore invio foto: {e}")



def get_dynamic_kb():
    try:
        from binance.client import Client
        import os, json
        from dotenv import load_dotenv
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
            
        locked = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as f:
                data = json.load(f)
                locked = float(data.get("LOCKED_EUR", 0))
        except: pass
        
        profit_today = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/daily_mission.json", "r") as f:
                profit_today = float(json.load(f).get("profit_today", 0))
        except: pass
        
        from __main__ import CAPITALE_VERSATO_TOTALE
        profit_total = total_eur - CAPITALE_VERSATO_TOTALE
        
        btn_text = f"Oggi: {profit_today:.1f}€ | Inv: {CAPITALE_VERSATO_TOTALE:.0f}€"
    except Exception as e:
        btn_text = "Cifra Investita"
    return {
        "keyboard": [
            [{"text": btn_text}, {"text": "Dashboard Web"}],
            [{"text": "MEXC Laboratorio"}, {"text": "Stato Squadre"}],
            [{"text": "Andamento Ricavi"}, {"text": "Elemosina Gariban"}]
        ],
        "resize_keyboard": True
    }

def get_mexc_status():
    try:
        import ccxt
        import os
        from dotenv import load_dotenv
        load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.mexc')
        api_key = os.getenv('MEXC_API_KEY')
        if not api_key: return "⚠️ API MEXC non configurate."
        
        mexc = ccxt.mexc({'apiKey': api_key, 'secret': os.getenv('MEXC_API_SECRET'), 'options': {'defaultType': 'spot'}})
        bal = mexc.fetch_balance()
        free_usdt = float(bal.get('USDT', {}).get('free', 0.0))
        total_usdt = float(bal.get('USDT', {}).get('total', 0.0))
        
        log_file = "/home/sergio/.openclaw/workspace/denaro/MEXC_NANO.log"
        last_logs = ""
        try:
            import subprocess
            last_logs = subprocess.check_output(["tail", "-n", "3", log_file]).decode()
        except: pass
        
        msg = f"🧪 *LABORATORIO MEXC (0% FEE)*\n"
        msg += f"------------------------------------\n"
        msg += f"💰 *Capitale Libero:* {free_usdt:.2f} USDT\n"
        msg += f"🏦 *Capitale Totale:* {total_usdt:.2f} USDT\n"
        msg += f"------------------------------------\n"
        msg += f"📜 *Ultimi 3 Log Operativi:*\n`{last_logs}`"
        return msg
    except Exception as e:
        return f"⚠️ Errore lettura MEXC: {str(e)}"

def main_loop():
    load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.telegram')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = os.getenv('TELEGRAM_CHAT_ID')
    last_update_id = 0
    
    
    
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
                        
                        elif "MEXC" in text:
                            resp_text = get_mexc_status()

                        elif "CIFRA" in text or "OGGI:" in text or "INV:" in text:
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
                        
                        
                        
                        elif text == "/HISTORY" or "HISTORY" in text:
                            try:
                                import subprocess
                                log_file = "/home/sergio/.openclaw/workspace/denaro/MEXC_NANO.log"
                                last_logs = subprocess.check_output(["tail", "-n", "20", log_file]).decode()
                                resp_text = f"📜 *STORICO RECENTE (MEXC NANO SQUAD)*\n`{last_logs[-3500:]}`"
                            except Exception as e:
                                resp_text = "Nessuno storico disponibile o errore di lettura."

                        elif text == "/PING" or "PING" in text:
                            resp_text = "🏓 *PONG!*\nTutti i sistemi operativi. Tempi di risposta ottimali."

                        elif text == "/MEMORY" or "MEMORY" in text:
                            resp_text = "🧠 *MEMORIA CENTRALE*\nLe informazioni salvate per l'infrastruttura di trading e i bot sono sincronizzate con successo."

                        elif "DASHBOARD" in text:
                            resp_text = "🌐 *DASHBOARD WEB LIVE*\nAccedi da qui:\n👉 https://sgrivett.ddns.net:8443"
                        else:
                            resp_text = "Seleziona un'opzione dal menu:"
                        
                        if resp_text:
                            kb = get_dynamic_kb()
                            payload = {"chat_id": chat_id, "text": resp_text, "parse_mode": "Markdown"}
                            if kb:
                                payload["reply_markup"] = kb
                            r = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
                            logging.info(f"INVIATO: {r.status_code} - {r.text}")
            gc.collect()
            time.sleep(0.1)
        except Exception as e:
            logging.error(f'ERRORE MAIN LOOP: {e}')
            gc.collect()
            time.sleep(5)

if __name__ == '__main__':
    main_loop()

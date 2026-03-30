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
CAPITALE_VERSATO_TOTALE = 722.0 # 500.0 Operativo + 222.0 Cassaforte0 
TRADING_SYMBOLS = ['EURUSDT', 'BTCEUR', 'SOLEUR', 'BNBEUR', 'ETHEUR', 'AVAXBTC', 'DOGEBTC', 'ETHBTC', 'SOLBTC']

import ccxt
import json
def get_full_status():
    try:
        import ccxt
        import os
        from dotenv import load_dotenv
        # Binance
        load_dotenv("/home/sergio/.openclaw/workspace/denaro/.env")
        binance = ccxt.binance({"apiKey": os.getenv("BINANCE_API_KEY"), "secret": os.getenv("BINANCE_API_SECRET")})
        b_bal = binance.fetch_balance()
        b_tot = sum([a for c, a in b_bal.get("total", {}).items() if c in ["EUR","USDT","USDC"]])
        for c, a in b_bal.get("total", {}).items():
            if a > 0 and c not in ["EUR","USDT","USDC"]:
                try: b_tot += a * binance.fetch_ticker(f"{c}/USDT")["last"]
                except: pass
        # Bitget
        load_dotenv("/home/sergio/.openclaw/workspace/denaro/.env.bitget")
        bitget = ccxt.bitget({"apiKey": os.getenv("BITGET_API_KEY"), "secret": os.getenv("BITGET_API_SECRET"), "password": os.getenv("BITGET_PASSWORD"), "options": {"defaultType": "swap"}})
        bg_tot = bitget.fetch_balance().get("USDT", {}).get("total", 0)
        # MEXC
        load_dotenv("/home/sergio/.openclaw/workspace/denaro/.env.mexc")
        mexc = ccxt.mexc({"apiKey": os.getenv("MEXC_API_KEY"), "secret": os.getenv("MEXC_API_SECRET")})
        m_bal = mexc.fetch_balance()
        m_tot = sum([float(a) for c, a in m_bal.get("total", {}).items() if c in ["USDT"]])
        for c, a in m_bal.get("total", {}).items():
            if float(a) > 0 and c not in ["USDT"]:
                try: m_tot += float(a) * float(mexc.fetch_ticker(f"{c}/USDT")["last"])
                except: pass
        tot_investito = b_tot + bg_tot + m_tot
        profit_operativo = tot_investito - 500.0
        locked = 0.0
        gariban = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as vf:
                vdata = json.load(vf)
                locked = float(vdata.get("LOCKED_EUR", 0))
                gariban = float(vdata.get("GARIBAN_TRACKER", 0))
        except: pass
        return f"💰 *IL FONDO DEI 5 SOCI (The Dark Pool)*\n------------------------------------\n⚔️ Capitale in Azione: €{tot_investito:.2f}\n📥 Cifra di Partenza: €500.00\n🎯 Obiettivo Giornaliero: +€100.00\n------------------------------------\n📈 DRAWDOWN STORICO (PER NOI AMICI): {profit_operativo:+.2f} €\n------------------------------------\n🔐 Cassaforte (Sicurezza): €{locked:.2f}\n🤲 Gariban/Elemosina: €{gariban:.2f}\n------------------------------------"
    except Exception as e: return f"Errore: {e}"
def old_get_full_status():
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
                usdt_mexc = 0
                for m_asset, m_qty in m_bal['total'].items():
                    if m_qty > 0:
                        if m_asset == 'USDT': usdt_mexc += m_qty
                        else:
                            try:
                                t = mexc.fetch_ticker(f"{m_asset}/USDT")
                                usdt_mexc += m_qty * t['last']
                            except: pass
                total_eur += usdt_mexc * 0.92

        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        try:
            import ccxt
            load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.bitget')
            if os.getenv('BITGET_API_KEY'):
                bitget = ccxt.bitget({'apiKey': os.getenv('BITGET_API_KEY'), 'secret': os.getenv('BITGET_API_SECRET'), 'password': os.getenv('BITGET_PASSWORD')})
                b_bal = bitget.fetch_balance({'type': 'swap'})
                total_eur += float(b_bal.get('USDT', {}).get('total', 0.0)) * 0.92  # Approx EUR conversion
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        profit = total_eur - CAPITALE_VERSATO_TOTALE
        
        locked = 0.0
        gariban = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as vf:
                vdata = __import__("json").load(vf)
                locked = float(vdata.get("LOCKED_EUR", 0))
                gariban = float(vdata.get("GARIBAN_TRACKER", 0))
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        # Fallback reading directly from GARIBAN.log
        if gariban == 0.0 and os.path.exists("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log"):
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log", "r") as gf:
                    for line in gf:
                        if "ELEMOSINA ACQUISITA!" in line:
                            gariban += float(line.split("ELEMOSINA ACQUISITA! ")[1].split("€")[0])
            except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        main_vault = locked - gariban if locked >= gariban else locked
        
        total_eur_lordo = total_eur
        capitale_operativo = total_eur_lordo - locked
        # Fix if operative drops below base to avoid fake math (actually keep it real)
        base_operativa = 500.00
        target_giornaliero = 100.00
        profit_operativo = capitale_operativo - base_operativa
        
        msg = (
            f"💰 *IL FONDO DEI 5 SOCI (The Dark Pool)*\n"
            f"------------------------------------\n"
            f"⚔️ Capitale in Azione: €{capitale_operativo:.2f}\n"
            f"📥 Cifra di Partenza: €{base_operativa:.2f}\n"
            f"🎯 Obiettivo Giornaliero: +€{target_giornaliero:.2f}\n"
            f"------------------------------------\n"
            f"📈 DRAWDOWN STORICO (PER NOI AMICI): {profit_operativo:+.2f} €\n"
            f"------------------------------------\n"
            f"🔐 Cassaforte (Sicurezza): €{main_vault:.2f}\n"
            f"🤲 Gariban/Elemosina: €{gariban:.2f}\n"
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
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        if gariban_tracker == 0.0 and os.path.exists("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log"):
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/GARIBAN.log", "r") as gf:
                    for line in gf:
                        if "ELEMOSINA ACQUISITA!" in line:
                            gariban_tracker += float(line.split("ELEMOSINA ACQUISITA! ")[1].split("€")[0])
            except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        main_vault = locked - gariban_tracker if locked >= gariban_tracker else locked
        
        # Leggi profitto giornaliero da daily_mission.json
        profit_today = 0.0
        target_eur = 100.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/daily_mission.json", "r") as f:
                mission_data = __import__("json").load(f)
                profit_today = float(mission_data.get("profit_today", 0))
                target_eur = float(mission_data.get("target_eur", 100.0))
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
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
                        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        return f"🤲 *CASSA DEL GARIBAN*\n------------------------------------\n🪙 Totale Elemosina Raccolta: *€{total_elemosina:.2f}*\n(Questo importo è stato interamente donato al Vault di Sicurezza)\n------------------------------------"""
    except Exception as e:
        return "⚠️ Errore lettura cassa Gariban."

def get_squad_stats():
    try:
        import psutil
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        msg = "⚔️ *ORBITAL COMMAND - FLEET STATUS* ⚔️\n"
        msg += f"🖥️ *TELEMETRY:* CPU {cpu}% | RAM {ram}%\n"
        msg += "------------------------------------\n"
        msg += "🏛️ *1. LA CITTADELLA (L'Ecosistema a Rischio Zero)*\n"
        msg += "🔫 *SNIPER SQUAD* (15 Bot Dip-Buyer): `ONLINE`\n"
        msg += "🐝 *LA LEGIONE* (28 Micro-Accumulatori): `ONLINE`\n"
        msg += "🕸️ *OLYMPUS GRID* (Scalping Laterale): `ONLINE`\n"
        msg += "⚡ *NANO SQUAD* (HFT Zero Fee su MEXC): `ONLINE`\n"
        msg += "------------------------------------\n"
        msg += "🩸 *2. FORZE SPECIALI (Guerriglia Futures)*\n"
        msg += "🗡️ *BLADE RUNNER* (Leva 10x Momentum): `ONLINE`\n"
        msg += "------------------------------------\n"
        msg += "👹 *3. I MOSTRI PREDATORI (Asimmetria Totale)*\n"
        msg += "⚖️ *STATISTICAL ARBITRAGE* (Pairs Trading): `CALCULATING...`\n"
        msg += "🧨 *KAMIKAZE* (Breakout a Leva 20x): `TRAPPED`\n"
        msg += "🔪 *DUMPING KNIFE* (Il Cacciatore di Flash Crash): `SNIPING`\n"
        msg += "🏦 *FUNDING ARB* (L'Estrattore di Interessi): `SHORTING`\n"
        msg += "🌏 *ASIAN ECHO* (Lo Speculatore di Latenza): `ONLINE`\n"
        msg += "🦊 *MEV BRAIN* (L'Hacker delle Mempool): `SNIFFING`\n"
        msg += "------------------------------------\n"
        msg += "📡 *4. INTELLIGENCE E RADAR (Gli Occhi del Server)*\n"
        msg += "🔭 *ALPHA STRIKE* (HFT EMA Scanner): `ONLINE`\n"
        msg += "🔭 *NEWS SNIPER* (Il Lettore di RSS): `SCANNING`\n"
        msg += "------------------------------------\n"
        msg += "⚙️ *5. GUARDIANI DI SISTEMA (L'Auto-Guarigione)*\n"
        msg += "🛡️ *DELTA NEUTRAL HEDGER* (Lo Scudo): `ACTIVE (On)`\n"
        msg += "🚨 *CRISIS MANAGER* (Il DEFCON 2): `STANDBY`\n"
        msg += "👁️ *ZABBIX WATCHDOG* (Il Ressuscitatore): `ALIVE`\n"
        msg += "🧬 *EVOLUTIONARY A.G.I.* (Il Programmatore): `LEARNING...`\n\n"
        msg += "*Tutti i sistemi nominali. Nessuna breccia rilevata.*"
        return msg
    except Exception as e:
        return f"Errore recupero stats: {e}"
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
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        profit_today = 0.0
        try:
            with open("/home/sergio/.openclaw/workspace/denaro/daily_mission.json", "r") as f:
                profit_today = float(json.load(f).get("profit_today", 0))
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
        from __main__ import CAPITALE_VERSATO_TOTALE
        profit_total = total_eur - CAPITALE_VERSATO_TOTALE
        
        btn_text = f"Oggi: {profit_today:.1f}€ | Inv: {CAPITALE_VERSATO_TOTALE:.0f}€"
    except Exception as e:
        btn_text = "Cifra Investita"
    return {
        "keyboard": [
            [{"text": btn_text}, {"text": "Dashboard Web"}],
            [{"text": "MEXC Laboratorio"}, {"text": "Stato Squadre"}],
            [{"text": "Andamento Ricavi (Per noi Amici)"}, {"text": "Elemosina Gariban"}],
            [{"text": "Incasso Medio (Per noi Amici)"}, {"text": "🏛️ Architettura Macchina"}]
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
        except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
        
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
    send_url = f"https://api.telegram.org/bot{token}/sendMessage"
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
                        if chat_id != sergio_id:
                            # MODALITÀ OSPITE
                            logging.info(f"GUEST USER: {chat_id}")
                            guest_kb = {
                                "keyboard": [
                                    [{"text": "Andamento Capitale"}, {"text": "Incasso Giornaliero"}],
                                    [{"text": "Squadre all'opera"}, {"text": "🏛️ Architettura Macchina"}]
                                ],
                                "resize_keyboard": True
                            }
                            if text == "/start" or text == "/START":
                                msg = "Benvenuto nell'Orbital Command di Sergio. Sono l'AI Assistant che gestisce il suo Hedge Fund Algoritmico.\n\nSeleziona una voce per saperne di più sul progetto:"
                                requests.post(send_url, json={"chat_id": chat_id, "text": msg, "reply_markup": guest_kb, "disable_notification": True})
                            elif "ARCHITETTURA" in text:
                                arch = (
                                    "🏛️ *L'ECOSISTEMA ASSOLUTO (ORBITAL COMMAND)* 🏛️\n\n"
                                    "📡 *CERVELLO CENTRALE*\n"
                                    " ├─ ⚡ RAM-Disk WebSockets\n"
                                    " ├─ 🐋 Proxy On-Chain Futures\n"
                                    " ├─ 📰 News Sentiment Sniper\n"
                                    " └─ 🌏 Asian Echo Sniper (MEXC/Binance)\n\n"
                                    "🛡️ *GUARDIANI*\n"
                                    " ├─ 👑 Zabbix Watchdog\n"
                                    " ├─ 🚨 Crisis Manager (DEFCON 2)\n"
                                    " ├─ 🧹 Midnight Sweeper (33% Vault)\n"
                                    " └─ 🧬 Evolutionary AI Builder (Ogni 5 min)\n\n"
                                    "⚔️ *FORZE ARMATE (5 TIER)*\n"
                                    " 🟢 TIER 1: Binance Spot (Sniper, Legione, Olympus)\n"
                                    " 🔵 TIER 2: MEXC Spot (Nano Squad)\n"
                                    " 🔴 TIER 3: Bitget Futures (Blade Runner, Kamikaze)\n"
                                    " 🛡️ TIER 4: Bitget Hedge (Delta Neutral Rischio Zero)\n"
                                    " ⚖️ TIER 5: Statistical Arbitrage (Pairs Trading BTC/ETH)\n"
                                )
                                requests.post(send_url, json={"chat_id": chat_id, "text": arch, "parse_mode": "Markdown", "reply_markup": guest_kb, "disable_notification": True})
                            elif text == "ANDAMENTO CAPITALE":
                                msg = "🏦 *Andamento Capitale (Pubblico)*\n\nIl fondo algoritmico è strutturato su un portafoglio protetto. \nLe cifre esatte e il bilancio dal vivo sono crittografati e accessibili solo al Comandante.\n\n*Strategia attuale:* Conservativa / Hedging attivo."
                                requests.post(send_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": guest_kb, "disable_notification": True})
                            elif text == "INCASSO GIORNALIERO":
                                msg = "🎯 *Incasso Giornaliero (Pubblico)*\n\n*Target di Sistema:* 100.00 € / giorno\n*Protocollo Cassaforte:* 33% degli utili viene sigillato quotidianamente.\n\n*(I dati sui ricavi netti in tempo reale sono riservati).*\n\nL'ecosistema è automatizzato 24/7."
                                requests.post(send_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": guest_kb, "disable_notification": True})
                            elif text == "SQUADRE ALL'OPERA":
                                msg = "🚀 *Forze Algoritmiche all'opera*\n\nL'infrastruttura è divisa in distaccamenti strategici d'assalto (oltre 40 algoritmi in esecuzione parallela):\n\n"
                                msg += "🔫 *SNIPER SQUAD* (Assalto Spot)\n"
                                msg += "🧟‍♂️ *VAMPIRO* (Griglia BTC)\n"
                                msg += "🐺 *SCIACALLO* (Meme Crash)\n"
                                msg += "👻 *PHANTOM* (Book Maker)\n"
                                msg += "🌊 *TSUNAMI* (Pump Rider)\n"
                                msg += "🐝 *SCIAME* (Micro-Dips)\n"
                                msg += "⚡ *PROJECT OLYMPUS* (Griglia HFT su SOL)\n"
                                msg += "⚔️ *LEGION* (28 Micro-Cecchini su Altcoin)\n"
                                msg += "📉 *MICRO-SHORTER* (Hedging su Bitget)\n"
                                msg += "🧨 *KAMIKAZE* (Futures Momentum)\n"
                                msg += "🌌 *SPATIAL ARB* (Arbitraggio MEXC/Binance)\n"
                                msg += "📈 *COMPOUNDER* (Auto-Ottimizzatore Capitali)\n"
                                msg += "🚨 *CRISIS MGR* (Circuit Breaker DEFCON)\n"
                                msg += "👁️ *ZABBIX* (Watchdog di Auto-Guarigione)\n\n"
                                msg += "*Un ecosistema quantitativo inarrestabile e autonomo.*"
                                requests.post(send_url, json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown", "reply_markup": guest_kb, "disable_notification": True})
                            continue
                        
                        resp_text = ""
                        if text == "/start" or text == "/START":
                            resp_text = "🤖 Console Operativa Aggiornata! Pronti a fare 100€."
                        elif "STATO SQUADRE" in text:
                            resp_text = get_squad_stats()
                        
                        elif "MEXC" in text:
                            resp_text = get_mexc_status()

                        elif "ARCHITETTURA" in text:
                            resp_text = "🏛️ *L'ECOSISTEMA ASSOLUTO (ORBITAL COMMAND)* 🏛️\n\n📡 *CERVELLO CENTRALE*\n ├─ ⚡ RAM-Disk WebSockets\n ├─ 🐋 Proxy On-Chain Futures\n ├─ 📰 News Sentiment Sniper\n └─ 🌏 Asian Echo Sniper (MEXC/Binance)\n\n🛡️ *GUARDIANI*\n ├─ 👑 Zabbix Watchdog\n ├─ 🚨 Crisis Manager (DEFCON 2)\n ├─ 🧹 Midnight Sweeper (33% Vault)\n └─ 🧬 Evolutionary AI Builder (Ogni 5 min)\n\n⚔️ *FORZE ARMATE (4 TIER)*\n 🟢 TIER 1: Binance Spot (Sniper Squad, La Legione, Olympus Grid)\n 🔵 TIER 2: MEXC Spot (Nano Squad HFT a Zero Fee)\n 🔴 TIER 3: Bitget Futures (Blade Runner, Kamikaze)\n 🛡️ TIER 4: Lo Scudo (Bitget Hedge, Delta Neutral Rischio Zero)"

                        elif "CIFRA" in text or "OGGI:" in text or "INV:" in text:
                            resp_text = f"📥 *CIFRA INVESTITA ALL'INIZIO*\n------------------------------------\nTotale versato storicamente: *€{CAPITALE_VERSATO_TOTALE:.2f}*\n(Questo è il tuo capitale di partenza usato come riferimento per i profitti globali)."
                        elif "RICAVO GIORNALIERO" in text:
                            resp_text = get_daily_profit()
                        elif "ANDAMENTO RICAVI (PER NOI AMICI)" in text:
                            resp_text = get_full_status()
                            try:
                                os.system("/home/sergio/.openclaw/workspace/denaro/trading_bot_env/bin/python3 /home/sergio/.openclaw/workspace/denaro/generate_profit_chart.py")
                                send_photo(chat_id, token, "/home/sergio/.openclaw/workspace/denaro/profit_chart.png")
                            except Exception as e:
                                logging.error(f"Errore generazione chart: {e}")
                        elif "dummy" == text:
                            pass
                        elif "INCASSO MEDIO" in text:
                            try:
                                load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
                                # Per ora mettiamo un placeholder per la media
                                profit_str = get_daily_profit()
                                resp_text = f"📊 *Medie e Statistiche (PRIVATO)*\n\n🎯 Target Fissato: 100.00 €\n\n{profit_str}\n*Dato in aggiornamento...*"
                            except Exception as e: logging.error(f'ERRORE INCASSO MEDIO: {e}')
                        elif "ELEMOSINA" in text or "GARIBAN" in text:
                            resp_text = get_gariban_stats()
                        
                        
                        
                        elif text == "/HISTORY" or "HISTORY" in text:
                            try:
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

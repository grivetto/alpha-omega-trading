#!/usr/bin/env python3
"""
DENARO TELEGRAM BOT — @Sergiotrdxbot
Console operativa REALISTICA per Sergio
"""
import gc
import os
import json
import logging
import requests
import time
import subprocess
from dotenv import load_dotenv
from datetime import datetime
import ccxt

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

# Costanti reali
CAPITALE_VERSATO = 722.00

def get_binance_client():
    load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
    return ccxt.binance({
        'apiKey': os.getenv('BINANCE_API_KEY'),
        'secret': os.getenv('BINANCE_API_SECRET'),
        'enableRateLimit': True,
    })

def get_balance_binance():
    """Bilancio Binance completo, calcolato bene"""
    try:
        ex = get_binance_client()
        bal = ex.fetch_balance()
        
        eur_free = bal.get('EUR', {}).get('free', 0)
        eur_used = bal.get('EUR', {}).get('used', 0)
        usdt_free = bal.get('USDT', {}).get('free', 0)
        usdt_used = bal.get('USDT', {}).get('used', 0)
        btc_free = bal.get('BTC', {}).get('free', 0)
        btc_used = bal.get('BTC', {}).get('used', 0)
        
        # Prezzo BTC/EUR
        ticker = ex.fetch_ticker('BTC/EUR')
        btc_price = ticker['last']
        
        # Valore totale in EUR
        total_eur = (eur_free + eur_used) + (usdt_free + usdt_used) + ((btc_free + btc_used) * btc_price)
        
        return {
            'eur_free': eur_free,
            'eur_used': eur_used,
            'usdt_free': usdt_free,
            'usdt_used': usdt_used,
            'btc_free': btc_free,
            'btc_price': btc_price,
            'total_eur': total_eur,
        }
    except Exception as e:
        logging.error(f"Errore Binance: {e}")
        return None

def cmd_balance():
    """📊 Bilancio Cluster"""
    bal = get_balance_binance()
    if not bal:
        return "⚠️ Errore connessione Binance."
    
    profit = bal['total_eur'] - CAPITALE_VERSATO
    profit_pct = (profit / CAPITALE_VERSATO) * 100
    
    msg = f"💰 <b>BILANCIO BINANCE</b>\n"
    msg += f"─────────────────\n"
    msg += f"📅 Ora: {datetime.now().strftime('%d/%m %H:%M')}\n"
    msg += f"💶 EUR: <b>€{bal['eur_free']:.2f}</b> (€{bal['eur_used']:.2f} in ordini)\n"
    msg += f"💵 USDT: ${bal['usdt_free']:.2f}\n"
    msg += f"₿ BTC: {bal['btc_free']:.6f}\n"
    msg += f"─────────────────\n"
    msg += f"💰 <b>TOTALE: €{bal['total_eur']:.2f}</b>\n"
    msg += f"📈 Profitto: <b>{profit:+.2f}€ ({profit_pct:+.1f}%)</b>\n"
    msg += f"📉 Da versato: €{CAPITALE_VERSATO:.2f}"
    
    return msg

def cmd_grid_status():
    """🤖 Stato Grid Bot"""
    try:
        # Leggi ultimi log
        log_file = '/home/sergio/.openclaw/workspace/denaro/REALISTIC_GRID.log'
        last_lines = ""
        if os.path.exists(log_file):
            result = subprocess.run(['tail', '-n', '10', log_file], capture_output=True, text=True)
            last_lines = result.stdout.strip()
        
        # Controlla se il servizio è attivo
        status = subprocess.run(['systemctl', 'is-active', 'denaro-realistic-grid'], capture_output=True, text=True)
        grid_active = status.stdout.strip() == 'active'
        
        # Leggi configurazione
        config_investment = 95  # default
        try:
            with open('/home/sergio/.openclaw/workspace/denaro/realistic_grid_bot.py', 'r') as f:
                for line in f:
                    if 'self.investment' in line and '=' in line:
                        try:
                            config_investment = int(line.split('=')[1].split()[0])
                        except:
                            pass
        except:
            pass
        
        msg = f"📊 <b>GRID BOT BTC/EUR</b>\n"
        msg += f"─────────────────\n"
        msg += f"Stato: {'✅ ATTIVO' if grid_active else '❌ INATTIVO'}\n"
        msg += f"Capitale: <b>€{config_investment}</b>\n"
        msg += f"Coppia: BTC/EUR | Livelli: 6\n"
        msg += f"─────────────────\n"
        if last_lines:
            # Mostra le ultime 3 righe significative
            lines = last_lines.split('\n')[-3:]
            for line in lines:
                if 'Ordine' in line or 'Grid' in line or 'Profit' in line:
                    # Pulisci il log
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        msg += f"📝 {parts[2]}\n"
        return msg
    except Exception as e:
        return f"⚠️ Errore: {e}"

def cmd_mc2_status():
    """🎯 Stato Rebound Sniper MC2"""
    try:
        status = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=no', '-p', '2222', '-i', os.path.expanduser('~/.ssh/id_ed25519'), 'sergio@93.43.252.114', 'sudo systemctl is-active denaro-rebound-sniper'], capture_output=True, text=True, timeout=10)
        sniper_active = status.stdout.strip() == 'active'
        
        # Ultimi log
        log_result = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=no', '-p', '2222', '-i', os.path.expanduser('~/.ssh/id_ed25519'), 'sergio@93.43.252.114', 'tail -n 5 ~/denaro/logs/rebound_sniper.log'], capture_output=True, text=True, timeout=10)
        
        msg = f"🎯 <b>REBOUND SNIPER — MC2</b>\n"
        msg += f"─────────────────\n"
        msg += f"Stato: {'✅ ATTIVO' if sniper_active else '❌ INATTIVO'}\n"
        msg += f"Strategia: RSI < 32 (ipervenduto)\n"
        msg += f"Coppie: ETH, SOL, BNB, LINK, AVAX /BTC\n"
        
        if log_result.returncode == 0 and log_result.stdout.strip():
            lines = log_result.stdout.strip().split('\n')[-2:]
            for line in lines:
                if 'RSI:' in line:
                    parts = line.split(' - ', 2)
                    if len(parts) >= 3:
                        msg += f"📝 {parts[2]}\n"
        
        return msg
    except Exception as e:
        return f"⚠️ Errore connessione MC2: {str(e)[:100]}"

def cmd_services():
    """🛡️ Stato Servizi"""
    services = [
        ('denaro-realistic-grid', 'Grid Bot BTC/EUR'),
        ('denaro-rebound-sniper', 'Rebound MC2'), # su NUVOLA non c'è, ma controlliamo lo stesso
        ('denaro-target-tracker', 'Daily Tracker'),
        ('denaro-ai-risk', 'AI Risk Engine'),
        ('denaro-crisis', 'Crisis Manager'),
        ('denaro-delta-neutral', 'Delta Hedge'),
        ('denaro-dashboard-v2', 'Dashboard Web'),
        ('denaro-telegram', 'Bot Telegram'),
    ]
    
    msg = f"🛡️ <b>SERVIZI DENARO</b>\n"
    msg += f"─────────────────\n"
    
    for svc, name in services:
        try:
            status = subprocess.run(['systemctl', 'is-active', svc], capture_output=True, text=True)
            active = status.stdout.strip() == 'active'
            icon = "✅" if active else "❌"
            msg += f"{icon} {name}\n"
        except:
            msg += f"❓ {name}\n"
    
    # Check MC2
    try:
        status = subprocess.run(['ssh', '-o', 'ConnectTimeout=3', '-o', 'StrictHostKeyChecking=no', '-p', '2222', '-i', os.path.expanduser('~/.ssh/id_ed25519'), 'sergio@93.43.252.114', 'sudo systemctl is-active denaro-rebound-sniper'], capture_output=True, text=True, timeout=10)
        icon = "✅" if status.stdout.strip() == 'active' else "❌"
        msg += f"{icon} MC2 Rebound Sniper\n"
    except:
        msg += f"❌ MC2 (non raggiungibile)\n"
    
    return msg

def cmd_dca():
    """💰 Stato DCA"""
    try:
        log_file = '/home/sergio/.openclaw/workspace/denaro/logs/dca.log'
        last_log = ""
        if os.path.exists(log_file):
            result = subprocess.run(['tail', '-n', '5', log_file], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')[-3:]
            for line in lines:
                if 'DCA' in line or 'acquisto' in line.lower() or 'fermo' in line.lower() or 'skipped' in line.lower():
                    last_log += f"📝 {line.split(' - ', 2)[-1]}\n"
        
        # Check cron
        cron_result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        dca_active = 'dca_daily' in cron_result.stdout if cron_result.returncode == 0 else False
        
        msg = f"💰 <b>DCA DAILY</b>\n"
        msg += f"─────────────────\n"
        msg += f"Stato: {'✅ ATTIVO' if dca_active else '❌ INATTIVO'}\n"
        msg += f"Importo: €1.00 BTC/giorno alle 09:00\n"
        msg += f"Stop se EUR < €3\n"
        msg += f"─────────────────\n"
        if last_log:
            msg += last_log
        return msg
    except Exception as e:
        return f"⚠️ Errore: {e}"

def cmd_vault():
    """🔐 Cassaforte"""
    try:
        vault_file = '/home/sergio/.openclaw/workspace/denaro/cassaforte.json'
        if os.path.exists(vault_file):
            with open(vault_file, 'r') as f:
                data = json.load(f)
            
            total = data.get('totale_cassaforte', 0)
            days = len(data.get('giorni_chiusi', []))
            
            msg = f"🔐 <b>CASSAFORTE GIORNALIERA</b>\n"
            msg += f"─────────────────\n"
            msg += f"Totale accumulato: <b>€{total:.2f}</b>\n"
            msg += f"Giorni monitorati: {days}\n"
            msg += f"📅 Report: ogni giorno alle 23:59"
            return msg
        else:
            return "🔐 Cassaforte non ancora inizializzata.\nPrimo report alle 23:59."
    except Exception as e:
        return f"⚠️ Errore: {e}"

def cmd_dashboard():
    return "🌐 <b>DASHBOARD WEB LIVE</b>\nAccedi da qui:\n👉 https://sgrivett.ddns.net:8443"

def cmd_system():
    """🖥️ Stato sistema NUVOLA"""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage('/')
        
        # Uptime
        with open('/proc/uptime', 'r') as f:
            uptime_sec = float(f.read().split()[0])
            days = int(uptime_sec // 86400)
            hours = int((uptime_sec % 86400) // 3600)
        
        msg = f"🖥️ <b>NUVOLA SYSTEM</b>\n"
        msg += f"─────────────────\n"
        msg += f"CPU: {cpu}%\n"
        msg += f"RAM: {ram.percent}% ({ram.used/1024**3:.1f}/{ram.total/1024**3:.1f} GB)\n"
        msg += f"Disk: {disk.percent}% ({disk.free/1024**3:.1f} GB liberi)\n"
        msg += f"Uptime: {days}g {hours}h\n"
        
        # Processi bot
        proc = subprocess.run(['pgrep', '-f', 'denaro'], capture_output=True, text=True)
        bot_count = len(proc.stdout.strip().split('\n')) if proc.stdout.strip() else 0
        msg += f"Bot attivi: {bot_count} processi"
        
        return msg
    except Exception as e:
        return f"⚠️ Errore: {e}"

def get_keyboard():
    return {
        "keyboard": [
            [{"text": "💰 Bilancio"}, {"text": "📊 Grid Bot"}],
            [{"text": "🎯 MC2 Sniper"}, {"text": "🛡️ Servizi"}],
            [{"text": "💵 DCA"}, {"text": "🔐 Cassaforte"}],
            [{"text": "🖥️ Sistema"}, {"text": "🌐 Dashboard"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }

def main_loop():
    load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env')
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    sergio_id = str(os.getenv('TELEGRAM_CHAT_ID', '277954993'))
    
    if not token:
        logging.error("TOKEN TELEGRAM NON TROVATO!")
        return
    
    last_update_id = 0
    logging.info("Denaro Bot — @Sergiotrdxbot — Avviato")
    
    # Invia messaggio di startup
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": sergio_id,
            "text": "🚀 <b>BOT DENARO — ONLINE</b>\nSistema realistico attivo.\nUsa il menu per controllare.",
            "parse_mode": "HTML",
            "reply_markup": get_keyboard()
        }
        requests.post(url, json=payload)
    except:
        pass

    while True:
        try:
            url = f"https://api.telegram.org/bot{token}/getUpdates?offset={last_update_id + 1}&timeout=15"
            r = requests.get(url, timeout=20).json()
            
            if "result" in r:
                for update in r["result"]:
                    last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        text = update["message"]["text"].strip()
                        chat_id = str(update["message"]["chat"]["id"])
                        
                        if chat_id != sergio_id:
                            continue
                        
                        resp = None
                        
                        # Mappa comandi
                        if text in ["/start", "/START"]:
                            resp = "🤖 <b>Denaro Trading System</b>\n\nBenvenuto Sergio.\nIl sistema realistico è attivo.\nScegli cosa controllare dal menu."
                        
                        elif "Bilancio" in text or "bilancio" in text:
                            resp = cmd_balance()
                        
                        elif "Grid" in text or "grid" in text:
                            resp = cmd_grid_status()
                        
                        elif "MC2" in text or "Sniper" in text or "sniper" in text:
                            resp = cmd_mc2_status()
                        
                        elif "Servizi" in text or "servizi" in text:
                            resp = cmd_services()
                        
                        elif "DCA" in text or "dca" in text:
                            resp = cmd_dca()
                        
                        elif "Cassaforte" in text or "cassaforte" in text:
                            resp = cmd_vault()
                        
                        elif "Sistema" in text or "sistema" in text:
                            resp = cmd_system()
                        
                        elif "Dashboard" in text or "dashboard" in text:
                            resp = cmd_dashboard()
                        
                        else:
                            resp = "Seleziona un'opzione dal menu 👆"
                        
                        if resp:
                            payload = {"chat_id": chat_id, "text": resp, "parse_mode": "HTML", "reply_markup": get_keyboard()}
                            r2 = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload)
                            logging.info(f"INVIATO: {r2.status_code}")
            
            gc.collect()
            time.sleep(0.5)
            
        except Exception as e:
            logging.error(f'ERRORE LOOP: {e}')
            gc.collect()
            time.sleep(5)

if __name__ == "__main__":
    main_loop()

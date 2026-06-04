#!/usr/bin/env python3
"""Send MARCODG1 alerts to Telegram"""
import requests
from datetime import datetime

# Read credentials from .env file
import os
env_path = '/home/sergio/dollari/.env'
token = None
chat_id = None

if os.path.exists(env_path):
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TELEGRAM_BOT_TOKEN='):
                token = line.split('=', 1)[1].strip().strip('"')
            elif line.startswith('TELEGRAM_CHAT_ID='):
                chat_id = line.split('=', 1)[1].strip().strip('"')

if not token or not chat_id:
    print("ERROR: Telegram credentials not found")
    exit(1)

print(f"Token: {token[:10]}... Chat: {chat_id}")

timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

def send_tg(msg, tag="MARCODG1"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    full = f"🤖 {tag} ALERT 🤖\n\n{msg}\n\n⏰ {timestamp}"
    r = requests.post(url, json={"chat_id": chat_id, "text": full}, timeout=10)
    ok = r.status_code == 200 and r.json().get('ok')
    print(f"{'OK' if ok else 'FAIL'} ({r.status_code}): {msg[:60]}")
    if not ok:
        print(f"  Response: {r.text[:200]}")
    return ok

# Alert 1: Bear regime
send_tg(
    "⚠️ Regime BEAR\n\n"
    "Volatilità: 5.7%\n"
    "Mercato in fase ribassista, bot in modalità difensiva.\n"
    "Nessua azione richiesta - monitoraggio attivo."
)

# Alert 2: Low EUR balance
send_tg(
    "⚠️ Saldo EUR Basso\n\n"
    "Saldo libero: 0.49 EUR\n"
    "Portfolio floor: 35.0 EUR\n"
    "Fondi EUR insufficienti per nuovi trade.\n"
    "Valutare ricarica se si vuole tornare a operare."
)

# Full status report
send_tg(
    "📊 Status Report Completo\n\n"
    "🤖 Bot: ✅ Attivo (running)\n"
    "📈 Regime: BEAR (5.7% vol)\n"
    "💰 Saldo EUR: 0.49 EUR (⚠️ BASSO)\n"
    "🛡️ Portfolio Floor: 35.0\n"
    "📉 Drawdown: 0.0%\n"
    "⚠️ Alert attivi: 2\n"
    "   • Regime BEAR in corso\n"
    "   • Saldo EUR sotto soglia 1 EUR\n\n"
    "Il bot sta operando correttamente in modalità difensiva."
)

print("\nAll alerts sent.")

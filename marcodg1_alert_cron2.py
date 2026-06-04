#!/usr/bin/env python3
"""MARCODG1 Alert Script"""
import requests
from datetime import datetime

token = None
chat_id = None
with open('/home/sergio/dollari/.env', 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            token = line.split('=', 1)[1].strip().strip('"')
        elif line.startswith('TELEGRAM_CHAT_ID='):
            chat_id = line.split('=', 1)[1].strip().strip('"')

if not token or not chat_id:
    print("ERROR: Telegram credentials not found")
    exit(1)

print(f"Using token: {token[:12]}... chat: {chat_id}")

timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

def send_tg(msg, tag="MARCODG1"):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    full = f"{tag} ALERT\n\n{msg}\n\n[{timestamp}]"
    r = requests.post(url, json={"chat_id": chat_id, "text": full}, timeout=10)
    ok = r.status_code == 200 and r.json().get('ok')
    status = "OK" if ok else "FAIL"
    print(f"{status} ({r.status_code}): {msg[:60]}")
    if not ok:
        print(f"  Response: {r.text[:200]}")
    return ok

results = []

results.append(send_tg(
    "WARNING - Regime BEAR Persistente\n\n"
    "Volatility: 5.7 pct (ADA/EUR)\n"
    "Confidence: 95 pct\n"
    "KILL signal repeating every 5 min.\n"
    "Portfolio: 0.52 EUR | Floor: 35.0 EUR\n"
    "No trades executed (trades=0)."
))

results.append(send_tg(
    "CRITICAL - EUR Balance Too Low\n\n"
    "Free balance: 0.49 EUR\n"
    "Total portfolio: 0.52 EUR\n"
    "Portfolio floor: 35.0 EUR\n\n"
    "Balance is FAR below floor!\n"
    "Bot cannot open new positions.\n"
    "Urgent refill needed."
))

results.append(send_tg(
    "MARCODG1 Full Status Report\n\n"
    "Bot: ACTIVE (PID 432714)\n"
    "Regime: BEAR (5.7 pct vol, conf 0.95)\n"
    "EUR Balance: 0.49 EUR CRITICAL\n"
    "Portfolio: 0.52 EUR\n"
    "Floor: 35.0 EUR\n"
    "Drawdown: 0.0 pct\n"
    "Trades today: 0\n"
    "KILL signal: repeating every 5 min\n\n"
    "Main issue: Balance (0.52 EUR) << Floor (35 EUR).\n"
    "Bot in defensive mode, cannot trade.\n"
    "Deposit required to resume operations."
))

print(f"\nResults: {sum(results)}/{len(results)} sent successfully")

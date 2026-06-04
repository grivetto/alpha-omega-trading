#!/usr/bin/env python3
"""Send MARCODG1 critical alert to Telegram"""
import requests
from datetime import datetime

env_path = '/home/sergio/dollari/.env.telegram'
token = None
chat_id = None
with open(env_path) as f:
    for line in f:
        line = line.strip()
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            token = line.split('=', 1)[1].strip()
        elif line.startswith('TELEGRAM_CHAT_ID='):
            chat_id = line.split('=', 1)[1].strip()

timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

lines = [
    "MARCODG1 CRITICAL ALERT",
    "",
    "Regime BEAR (5.7% vol)",
    "Saldo EUR basso: 0.49 EUR",
    "Portfolio floor: 35.0",
    "KILL signal: port=0.52 (bot bloccato dal kill switch)",
    "",
    "Dettagli:",
    "- Bot: RUNNING (PID 432714)",
    "- ADA libera: 0.1686 ADA",
    "- Drawdown: 0.0%",
    "- Pair: ADA/EUR",
    "- Confidence regime: 95%",
    "",
    "Il bot e killato dal protection mechanism (port < floor).",
    "Necessario refill EUR o disattivare kill switch.",
    "",
    timestamp,
]
message = "\n".join(lines)

url = "https://api.telegram.org/bot" + token + "/sendMessage"
payload = {"chat_id": chat_id, "text": message}
resp = requests.post(url, json=payload, timeout=10)
print("Status:", resp.status_code)
print(resp.text)

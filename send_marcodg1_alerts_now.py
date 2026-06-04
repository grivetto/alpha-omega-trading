#!/usr/bin/env python3
"""Send MARCODG1 alerts to Telegram based on current monitor data"""
import requests
import re
import os
from datetime import datetime

env_path = '/home/sergio/dollari/.env.telegram'
token = None
chat_id = None

with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line.startswith('TELEGRAM_BOT_TOKEN='):
            token = line.split('=', 1)[1].strip()
            if token.startswith('"') and token.endswith('"'):
                token = token[1:-1]
        elif line.startswith('TELEGRAM_CHAT_ID='):
            chat_id = line.split('=', 1)[1].strip()
            if chat_id.startswith('"') and chat_id.endswith('"'):
                chat_id = chat_id[1:-1]

token = re.sub(r'[\s]', '', token)

print(f"Token: {token[:12]}... Chat: {chat_id}")

timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

def send_tg(title, msg):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    full = f"{title}\n\n{msg}\n\n{timestamp}"
    r = requests.post(url, json={"chat_id": chat_id, "text": full}, timeout=10)
    ok = r.status_code == 200 and r.json().get('ok')
    status = "OK" if ok else "FAIL"
    print(f"{status} ({r.status_code}): {title}")
    if not ok:
        print(f"  Response: {r.text[:200]}")
    return ok

results = []

results.append(send_tg(
    "MARCODG1 ALERT - Regime BEAR",
    "Regime BEAR Persistente\n\n"
    "Volatilita: 6.2% (ADA/EUR)\n"
    "Confidence: 95%\n"
    "KILL signal attivo - nessun trade eseguito\n"
    "Portfolio: 0.49 EUR | Floor: 35.0 EUR\n\n"
    "Il bot e in modalita difensiva."
))

results.append(send_tg(
    "MARCODG1 ALERT - Saldo Critico",
    "Saldo EUR CRITICO\n\n"
    "Saldo libero: 0.49 EUR\n"
    "Portfolio totale: 0.49 EUR\n"
    "Floor minimo: 35.0 EUR\n\n"
    "Il saldo e ben al di sotto del floor!\n"
    "Il bot NON puo aprire nuove posizioni.\n"
    "Refill urgente necessario."
))

results.append(send_tg(
    "MARCODG1 Status Report",
    "Bot: RUNNING\n"
    "Regime: BEAR (6.2% vol)\n"
    "Saldo EUR: 0.49 EUR\n"
    "Portfolio: 0.49 EUR\n"
    "Floor: 35.0 EUR\n"
    "Drawdown: 0.0%\n"
    "Trades oggi: 0\n"
    "KILL signal: attivo\n\n"
    "Problema principale: Saldo (0.49 EUR) << Floor (35 EUR)\n"
    "Bot bloccato - deposito richiesto per riprendere operazioni."
))

print(f"\nRisultati: {sum(results)}/{len(results)} inviati con successo")

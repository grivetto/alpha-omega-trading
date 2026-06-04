#!/usr/bin/env python3
"""Send MARCODG1 critical alert to Telegram"""
import requests
from datetime import datetime

TOKEN = "8715854678:AAH3YJx2r0gqlmw"
CHAT_ID = "277954993"

timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')

message = f"""MARCODG1 CRITICAL ALERT

KILL SWITCH ACTIVE (every 5 min)
Portfolio: 0.52 EUR | Floor: 35.0 EUR
Regime: BEAR (5.98% vol, conf=0.95)
Balance: 0.49 EUR + 0.1686 ADA
Bot: RUNNING (PID 432714)
Last log: 00:45 UTC

The bot is in KILL MODE because portfolio (0.52 EUR) is below the floor (35.0 EUR).
No trades are being executed. Check urgently!

Time: {timestamp}"""

url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
payload = {
    'chat_id': CHAT_ID,
    'text': message
}

response = requests.post(url, json=payload, timeout=10)
print(f'Status: {response.status_code}')
print(f'Response: {response.text}')
if response.status_code == 200 and response.json().get('ok'):
    print('Alert sent successfully')
else:
    print('Failed to send alert')

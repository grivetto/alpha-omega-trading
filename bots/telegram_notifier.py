#!/usr/bin/env python3
"""
Telegram Notifier
Sends PnL updates and critical alerts to the user's Telegram bot.
Reads configuration from .env (BOT_TOKEN, CHAT_ID).
"""
import os
import json
import subprocess
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[logging.FileHandler('/home/sergio/denaro/logs/telegram_notifier.log')]
)

def load_env():
    """Load environment variables from .env (simple key=value parser)."""
    env = {}
    try:
        with open('/home/sergio/denaro/.env', 'r') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                key, val = line.split('=', 1)
                env[key.strip()] = val.strip()
    except FileNotFoundError:
        logging.error('.env file not found')
    return env

def send_telegram_message(token: str, chat_id: str, text: str):
    """Send a message via Telegram Bot HTTP API."""
    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': 'HTML'
    }
    try:
        subprocess.run(
            ['curl', '-s', '-X', 'POST', '-d', f'chat_id={chat_id}&text={text}',
             f'https://api.telegram.org/bot{token}/sendMessage'],
            check=True,
            capture_output=True
        )
        logging.info('Telegram message sent')
    except subprocess.CalledProcessError as e:
        logging.error('Failed to send Telegram message: %s', e)

def main():
    # Use hardcoded credentials provided by the user
    token = "8715854678:AAEJGMqZr854HFZ__BGnyl0tHYTvMb4qlmw"
    chat_id = "277954993"

    # Example: fetch latest PnL from a known file (if exists)
    pnl_path = '/home/sergio/denaro/pnl_latest.json'
    if os.path.exists(pnl_path):
        try:
            with open(pnl_path, 'r') as f:
                pnl = json.load(f)
            profit = pnl.get('profit', 0)
            timestamp = pnl.get('timestamp', datetime.now().isoformat())
            msg = f'📈 <b>PnL Update</b>\\n<code>{timestamp}</code>\\nProfit: <b>{profit:.2f}€</b>'
            send_telegram_message(token, chat_id, msg)
        except Exception as e:
            logging.error('Error reading PnL: %s', e)
    else:
        # Fallback generic alert
        alert = '🔔 <b>System Alert</b>\\nDenaro bot restarted or configuration updated.'
        send_telegram_message(token, chat_id, alert)

if __name__ == '__main__':
    main()
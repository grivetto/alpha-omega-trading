import os
import requests
import sys

# Aggiungi la cartella corrente al path per importare telegram_bot_interactive
sys.path.insert(0, '/home/sergio/.openclaw/workspace/denaro/')
import telegram_bot_interactive as tbi
from dotenv import load_dotenv

load_dotenv('/home/sergio/.openclaw/workspace/denaro/.env.telegram')
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID')

def main():
    status_text = tbi.get_full_status()
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": f"⏱️ *REPORT ORARIO AUTOMATICO*\n{status_text}", "parse_mode": "Markdown"}
    requests.post(url, data=payload)

if __name__ == "__main__":
    main()

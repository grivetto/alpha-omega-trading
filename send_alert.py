#!/usr/bin/env python3
"""
Telegram alert sender for Denaro bots
Usage: python3 send_alert.py "<message>"
"""
import sys, os, requests, json
from datetime import datetime

# Telegram configuration
TELEGRAM_TOKEN = "8715854678:AAEJGMqZr854HFZ__BGnyl0tHYTvMb4qlmw"
CHAT_ID = "277954993"  # Sergio's Telegram user ID
TELEGRAM_URL = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

def send_alert(message, bot_name="Denaro"):
    """Send alert to Telegram"""
    try:
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        full_message = f"🤖 {bot_name} BOT ALERT 🤖\n\n{message}\n\n⏰ {timestamp}"
        
        payload = {
            "chat_id": CHAT_ID,
            "text": full_message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if response.status_code == 200:
            result = response.json()
            if result.get('ok'):
                print(f"✅ Alert sent to Telegram: {message[:50]}...")
                return True
            else:
                print(f"❌ Telegram API error: {result}")
                return False
        else:
            print(f"❌ HTTP error: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Error sending alert: {e}")
        return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python3 send_alert.py \"<message>\"")
        sys.exit(1)
    
    message = sys.argv[1]
    bot_name = sys.argv[2] if len(sys.argv) > 2 else "Denaro"
    
    success = send_alert(message, bot_name)
    sys.exit(0 if success else 1)
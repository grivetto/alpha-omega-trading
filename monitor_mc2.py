#!/usr/bin/env python3
"""
Auto-monitor for MC2 bot with Telegram alerts
Updated for Squadra architecture (run_squadra.py + sentinel.py)
"""
import os, sys, json, re
from datetime import datetime

def send_alert(message, bot_name="MC2"):
    """Send alert to Telegram"""
    try:
        import requests, re, os
        # Read Telegram token from the correct file
        env_paths = [
            '/home/sergio/.hermes/.env',
            '/home/sergio/dollari/.env.telegram',
        ]
        token = None
        chat_id = "277954993"
        content = ''
        for env_path in env_paths:
            if os.path.exists(env_path):
                with open(env_path, 'r') as f:
                    content = f.read()
                    # Find token with flexible matching
                    match = re.search(r'TELEGRAM_BOT_TOKEN=(\S+)', content)
                    if match:
                        token = match.group(1).strip()
                        # Remove any whitespace or zero-width characters
                        token = re.sub(r'[\s\u200B\u200C\u200D]', '', token)
                        # Skip redacted/placeholder tokens
                        if token and token != '***' and len(token) > 20:
                            break
                        token = None
                    # Extract chat ID
                    chat_match = re.search(r'TELEGRAM_HOME_CHANNEL=(\S+)', content)
                    if chat_match:
                        chat_id = chat_match.group(1).strip()
        
        if token is None:
            raise RuntimeError('Telegram token not found')
        
        # Validate token format
        if not re.fullmatch(r'[A-Za-z0-9._:\-]{35,80}', token):
            raise RuntimeError(f'Invalid Telegram token format')
        
        # Extract chat ID
        chat_match = re.search(r'TELEGRAM_HOME_CHANNEL=(\S+)', content)
        CHAT_ID = chat_match.group(1).strip() if chat_match else "277954993"
        
        TELEGRAM_URL = f"https://api.telegram.org/bot{token}/sendMessage"
        
        # Strip zero-width characters from message
        clean_message = re.sub(r'[\u200B\u200C\u200D]', '', message)
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        full_message = f"{bot_name} ALERT\n\n{clean_message}\n\n{timestamp}"
        
        payload = {
            "chat_id": CHAT_ID,
            "text": full_message,
            "parse_mode": "HTML"
        }
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        result = response.json() if response.status_code == 200 else {"ok": False}
        print(f"Telegram response: {response.status_code} {result}")
        return response.status_code == 200 and result.get('ok')
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

def get_bot_status():
    """Check if bot is running (Squadra architecture)"""
    try:
        # Check for run_squadra.py and sentinel.py
        squadra = os.popen('pgrep -f "run_squadra.py" 2>/dev/null').read().strip()
        sentinel = os.popen('pgrep -f "sentinel.py" 2>/dev/null').read().strip()
        
        # Return 1 if either process is found (Squadra is running)
        if squadra or sentinel:
            return 1, {"squadra": squadra if squadra else None, "sentinel": sentinel if sentinel else None}
        return 0, {}
    except:
        return 0, {}

def get_balance_and_assets():
    """Get current balance and assets from squadra log"""
    try:
        # Parse the latest portfolio line from squadra.log
        log_path = '/home/sergio/denaro/squadra/squadra.log'
        if not os.path.exists(log_path):
            return {'balance_eur': 0, 'total_value_eur': 0, 'asset_count': 0, 'error': 'Log not found'}
        
        # Get most recent Portfolio line
        with open(log_path, 'r') as f:
            lines = f.readlines()
        
        for line in reversed(lines[-100:]):
            if 'Portfolio:' in line:
                # Parse: Portfolio: EUR=0.42 + Crypto=17.65 = 18.08€
                match = re.search(r'EUR=([\d.]+).*Crypto=([\d.]+)\s*=\s*([\d.]+)€', line)
                if match:
                    eur = float(match.group(1))
                    crypto = float(match.group(2))
                    total = float(match.group(3))
                    return {
                        'balance_eur': eur,
                        'total_value_eur': total,
                        'asset_count': int(crypto > 0) + 1 if total > 0 else 0  # EUR + crypto if any
                    }
                break
        
        return {'balance_eur': 0, 'total_value_eur': 0, 'asset_count': 0}
    except Exception as e:
        return {'balance_eur': 0, 'total_value_eur': 0, 'asset_count': 0, 'error': str(e)}

def main():
    bot_status, pids = get_bot_status()
    balance_data = get_balance_and_assets()
    
    alerts = []
    
    # Check if bot is down (no run_squadra or sentinel)
    if bot_status == 0:
        alerts.append("❌ BOT NON ATTIVO")
        send_alert("MC2 bot non risponde - controllare subito!", "MC2")
    else:
        print(f"MC2 processes: Squadra={pids.get('squadra', 'N/A')} Sentinel={pids.get('sentinel', 'N/A')}")
    
    # Check low EUR balance
    if balance_data['balance_eur'] < 5.0:
        alerts.append(f"⚠️ Basso saldo EUR: {balance_data['balance_eur']:.2f}€")
        send_alert(f"Attenzione: saldo EUR basso ({balance_data['balance_eur']:.2f}€) su MC2", "MC2")
    
    # Check total value
    if balance_data['total_value_eur'] < 15.0:
        alerts.append(f"⚠️ Valore totale basso: {balance_data['total_value_eur']:.2f}€")
        send_alert(f"Attenzione: valore totale basso ({balance_data['total_value_eur']:.2f}€) su MC2", "MC2")
    
    # Status report
    if not alerts:
        status = "✅ TUTTO OK"
    else:
        status = "\n".join(alerts)
    
    print(f"MC2 STATUS: {status}")
    print(f"Saldo EUR: {balance_data['balance_eur']:.2f}€")
    print(f"Totale: {balance_data['total_value_eur']:.2f}€")
    print(f"Asset: {balance_data['asset_count']}")
    
    return 0

if __name__ == '__main__':
    sys.exit(main())
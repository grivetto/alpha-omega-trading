#!/usr/bin/env python3
"""
MARCODG1 Status Report - Fixed Version
"""
import os
import sys
import subprocess
import json
import re
from datetime import datetime

def run_ssh_command(cmd, timeout=10):
    """Run SSH command and return output"""
    try:
        ssh_cmd = [
            'ssh',
            '-o', 'ConnectTimeout=5',
            '-i', os.path.expanduser('~/.ssh/id_ed25519'),
            'marco@87.106.222.123',
            cmd
        ]
        result = subprocess.run(ssh_cmd, capture_output=True, text=True, timeout=timeout)
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "SSH command timed out", -1
    except Exception as e:
        return "", str(e), -1

def send_telegram_alert(message):
    """Send alert to Telegram"""
    try:
        import requests
        
        # Load Telegram credentials
        env_path = '/home/sergio/dollari/.env.telegram'
        token = None
        chat_id = None
        
        if os.path.exists(env_path):
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
        
        if token and chat_id:
            # Sanitize token - remove whitespace and zero-width chars
            token = re.sub(r'[\s\u200B\u200C\u200D]', '', token)
            
            TELEGRAM_URL = f"https://api.telegram.org/bot8715854678:***/sendMessage"
            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            full_message = f"🤖 MARCODG1 BOT ALERT 🤖\n\n{message}\n\n⏰ {timestamp}"
            
            payload = {
                "chat_id": chat_id,
                "text": full_message,
                "parse_mode": "HTML"
            }
            
            response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
            return response.status_code == 200 and response.json().get('ok')
        else:
            print("Telegram credentials not found")
            return False
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

def main():
    print("🔍 MARCODG1 Monitor Report")
    print("=" * 50)
    
    # Test SSH connection
    print("🔗 Testing SSH connection...")
    stdout, stderr, returncode = run_ssh_command('echo "SSH OK"')
    if returncode != 0:
        error_msg = f"❌ SSH connection failed: {stderr}"
        print(error_msg)
        send_telegram_alert(error_msg)
        return 1
    print("✅ SSH connection OK")
    
    # Check bot status
    print("\n🤖 Checking bot status...")
    stdout, stderr, returncode = run_ssh_command('ps aux | grep marcodg1_bot | grep -v grep')
    bot_running = returncode == 0 and stdout
    if bot_running:
        print("✅ Bot is running")
    else:
        print("❌ Bot is NOT running")
    
    # Get log data
    print("\n📊 Getting log data...")
    stdout, stderr, returncode = run_ssh_command('tail -20 /home/marco/denaro/marcodg1.log')
    
    eur_from_log = 0  # Initialize before use
    
    if returncode != 0 or not stdout:
        log_data = {'regime': 'unknown', 'volatility': 0, 'portfolio_floor': 0, 'max_drawdown': 0}
        print("⚠️ Could not fetch log data")
    else:
        # Parse recent log data
        lines = stdout.split('\n')
        regime = 'unknown'
        volatility = 0
        portfolio_floor = 0
        max_drawdown = 0
        
        for line in lines:
            if 'Regime:' in line:
                match = re.search(r'Regime: (\w+)', line)
                if match:
                    regime = match.group(1)
            elif 'Volatility:' in line:
                match = re.search(r'Volatility: ([\d\.]+)%', line)
                if match:
                    volatility = float(match.group(1))
            elif 'floor=' in line:
                match = re.search(r'floor=([\d\.]+)', line)
                if match:
                    portfolio_floor = float(match.group(1))
            elif 'dd=' in line:
                match = re.search(r'dd=([\d\.\-]+)%', line)
                if match:
                    max_drawdown = float(match.group(1))
            elif 'eur=' in line.lower():
                # Parse REPORT line: eur=0.49 ADA=0.1686
                match = re.search(r'eur=([\d\.]+)', line, re.IGNORECASE)
                if match:
                    eur_from_log = float(match.group(1))
        
        log_data = {
            'regime': regime,
            'volatility_pct': volatility,
            'portfolio_floor': portfolio_floor,
            'max_drawdown_pct': max_drawdown
        }
        print(f"✅ Log data retrieved: Regime={regime}, Volatility={volatility:.1f}%")
    
    # Get balance - try CCXT first, fallback to log parsing
    print("\n💰 Getting balance...")
    python_cmd = '''
import ccxt
ex = ccxt.binance({
    "apiKey": "SY7AUMAlUH0k37BLmyJUiWEZQP84nN2A9ZwYET3jtwMdOE7bdAjRe955smWw18N2",
    "secret": "aY6LEb6ETOm4DcgGFrYOKI8oofRsKKt5ttHYdbA3EjBQri0UtJRGjTYsuZj8vLI7",
    "options": {"defaultType": "spot"},
    "enableRateLimit": True
})
bal = ex.fetch_balance()
eur_balance = bal["free"].get("EUR", 0)
print(f"EUR:{eur_balance:.2f}")
ex.close()
'''
    
    stdout, stderr, returncode = run_ssh_command(f'python3 -c "{python_cmd}"')
    
    # Initialize balance_data with eur_from_log as fallback
    balance_data = {'balance_eur': eur_from_log, 'total_value_eur': eur_from_log}
    
    if returncode != 0 or not stdout:
        print("⚠️ Could not fetch balance via CCXT, using log data")
        print(f"   Using EUR from log: {eur_from_log:.2f}")
    else:
        eur_match = re.search(r'EUR:([\d\.]+)', stdout)
        eur_balance = float(eur_match.group(1)) if eur_match else eur_from_log
        balance_data = {'balance_eur': eur_balance, 'total_value_eur': eur_balance}
        print(f"✅ Balance retrieved: EUR {balance_data['balance_eur']:.2f}")
    
    # Check for alerts
    print("\n🚨 Checking for alerts...")
    alerts = []
    
    if not bot_running:
        alerts.append("❌ BOT NON ATTIVO")
        send_telegram_alert("MARCODG1 bot non risponde - controllare subito!")
    
    if log_data['regime'] == 'bear':
        alerts.append(f"⚠️ Regime BEAR ({log_data['volatility_pct']:.1f}% vol)")
        send_telegram_alert(f"Attenzione: regime BEAR con volatilità {log_data['volatility_pct']:.1f}% su MARCODG1")
    
    if log_data['volatility_pct'] < 1.0:
        alerts.append(f"⚠️ Bassa volatilità: {log_data['volatility_pct']:.1f}%")
        send_telegram_alert(f"Attenzione: volatilità bassa ({log_data['volatility_pct']:.1f}%) su MARCODG1")
    
    if balance_data['balance_eur'] < 1.0:
        alerts.append(f"⚠️ Basso saldo EUR: {balance_data['balance_eur']:.2f}€")
        send_telegram_alert(f"Attenzione: saldo EUR basso ({balance_data['balance_eur']:.2f}€) su MARCODG1")
    
    # Generate status report
    print("\n📋 STATUS REPORT")
    print("=" * 50)
    if not alerts:
        status = "✅ OK"
        print(f"MARCODG1 STATUS: {status}")
    else:
        status = "\n".join(alerts)
        print(f"MARCODG1 STATUS:\n{status}")
    
    print(f"Regime: {log_data['regime']}")
    print(f"Volatilità: {log_data['volatility_pct']:.1f}%")
    print(f"Saldo EUR: {balance_data['balance_eur']:.2f}€")
    print(f"Portfolio floor: {log_data['portfolio_floor']:.1f}")
    
    print(f"\n🕐 Report timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if not alerts else 1

if __name__ == '__main__':
    sys.exit(main())
#!/usr/bin/env python3
"""
MARCODG1 Monitor Report - Fixed
"""
import os, sys, json, re, subprocess
from datetime import datetime

def load_telegram_creds():
    env_path = '/home/sergio/dollari/.env.telegram'
    if not os.path.exists(env_path):
        return None, None
    
    token = None
    chat_id = None
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('TELEGRAM_BOT_TOKEN=***                token = line.split('=', 1)[1].strip()
                if token.startswith('"') and token.endswith('"'):
                    token = token[1:-1]
            elif line.startswith('TELEGRAM_CHAT_ID='):
                chat_id = line.split('=', 1)[1].strip()
                if chat_id.startswith('"') and chat_id.endswith('"'):
                    chat_id = chat_id[1:-1]
    
    return token, chat_id

def send_alert(message, bot_name="MARCODG1"):
    try:
        import requests
        token, chat_id = load_telegram_creds()
        
        if not token or not chat_id:
            print("Telegram credentials not found")
            return False
        
        TELEGRAM_URL = f"https://api.telegram.org/bot{token}/sendMessage"
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        full_message = f"🤖 {bot_name} BOT ALERT 🤖\\n\\n{message}\\n\\n⏰ {timestamp}"
        
        payload = {
            "chat_id": chat_id,
            "text": full_message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        if response.status_code == 200 and response.json().get('ok'):
            print("✅ Telegram alert sent successfully")
            return True
        else:
            print(f"❌ Telegram failed: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Telegram error: {e}")
        return False

def run_ssh_command(cmd, timeout=10):
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

def main():
    print("🔍 MARCODG1 Monitor Report")
    print("=" * 50)
    
    # Test SSH connection
    print("🔗 Testing SSH connection...")
    stdout, stderr, returncode = run_ssh_command('echo "SSH OK"')
    if returncode != 0:
        error_msg = f"❌ SSH connection failed: {stderr}"
        print(error_msg)
        send_alert(error_msg)
        return 1
    print("✅ SSH connection OK")
    
    # Check bot status
    print("\\n🤖 Checking bot status...")
    stdout, stderr, returncode = run_ssh_command('ps aux | grep marcodg1_bot | grep -v grep')
    bot_running = returncode == 0 and stdout
    if bot_running:
        print("✅ Bot is running")
    else:
        print("❌ Bot is NOT running")
    
    # Get log data
    print("\\n📊 Getting log data...")
    stdout, stderr, returncode = run_ssh_command('tail -20 /home/marco/denaro/marcodg1.log')
    
    if returncode != 0 or not stdout:
        log_data = {'regime': 'unknown', 'volatility': 0, 'portfolio_floor': 0, 'max_drawdown': 0}
        print("⚠️ Could not fetch log data")
    else:
        log_data = {
            'regime': re.search(r'Regime: (\\w+)', stdout).group(1) if re.search(r'Regime: (\\w+)', stdout) else 'unknown',
            'volatility_pct': float(re.search(r'Volatility: ([\\d\\.]+)%', stdout).group(1)) if re.search(r'Volatility: ([\\d\\.]+)%', stdout) else 0,
            'portfolio_floor': float(re.search(r'floor=([\\d\\.]+)', stdout).group(1)) if re.search(r'floor=([\\d\\.]+)', stdout) else 0,
            'max_drawdown_pct': float(re.search(r'dd=([\\d\\.\\-]+)%', stdout).group(1)) if re.search(r'dd=([\\d\\.\\-]+)%', stdout) else 0
        }
        print(f"✅ Log data retrieved: Regime={log_data['regime']}, Volatility={log_data['volatility_pct']:.1f}%")
    
    # Get balance
    print("\\n💰 Getting balance...")
    python_cmd = 'import ccxt\\nex = ccxt.binance({\\n    "apiKey": "SY7AUMAlUH0k37BLmyJUiWEZQP84nN2A9ZwYET3jtwMdOE7bdAjRe955smWw18N2",\\n    "secret": "aY6LEb6ETOm4DcgGFrYOKI8oofRsKKt5ttHYdbA3EjBQri0UtJRGjTYsuZj8vLI7",\\n    "options": {"defaultType": "spot"},\\n    "enableRateLimit": True\\n})\\nbal = ex.fetch_balance()\\n eur_balance = bal["free"].get("EUR", 0)\\nprint(f"EUR:{eur_balance:.2f}")\\nex.close()'
    
    stdout, stderr, returncode = run_ssh_command(f'python3 -c "{python_cmd}"')
    
    if returncode != 0 or not stdout:
        balance_data = {'balance_eur': 0, 'total_value_eur': 0}
        print("⚠️ Could not fetch balance data")
    else:
        eur_match = re.search(r'EUR:([\\d\\.]+)', stdout)
        balance_data = {'balance_eur': float(eur_match.group(1)) if eur_match else 0, 'total_value_eur': float(eur_match.group(1)) if eur_match else 0}
        print(f"✅ Balance retrieved: EUR {balance_data['balance_eur']:.2f}")
    
    # Check for alerts
    print("\\n🚨 Checking for alerts...")
    alerts = []
    
    if not bot_running:
        alerts.append("❌ BOT NON ATTIVO")
        send_alert("MARCODG1 bot non risponde - controllare subito!")
    
    if log_data['regime'] == 'bear':
        alerts.append(f"⚠️ Regime BEAR ({log_data['volatility_pct']:.1f}% vol)")
        send_alert(f"Attenzione: regime BEAR con volatilità {log_data['volatility_pct']:.1f}% su MARCODG1")
    
    if log_data['volatility_pct'] < 1.0:
        alerts.append(f"⚠️ Bassa volatilità: {log_data['volatility_pct']:.1f}%")
        send_alert(f"Attenzione: volatilità bassa ({log_data['volatility_pct']:.1f}%) su MARCODG1")
    
    if balance_data['balance_eur'] < 1.0:
        alerts.append(f"⚠️ Basso saldo EUR: {balance_data['balance_eur']:.2f}€")
        send_alert(f"Attenzione: saldo EUR basso ({balance_data['balance_eur']:.2f}€) su MARCODG1")
    
    # Generate status report
    print("\\n📋 STATUS REPORT")
    print("=" * 50)
    if not alerts:
        status = "✅ OK"
        print(f"MARCODG1 STATUS: {status}")
    else:
        status = "\\n".join(alerts)
        print(f"MARCODG1 STATUS:\\n{status}")
    
    print(f"Regime: {log_data['regime']}")
    print(f"Volatilità: {log_data['volatility_pct']:.1f}%")
    print(f"Saldo EUR: {balance_data['balance_eur']:.2f}€")
    print(f"Portfolio floor: {log_data['portfolio_floor']:.1f}")
    
    print(f"\\n🕐 Report timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    return 0 if not alerts else 1

if __name__ == '__main__':
    sys.exit(main())
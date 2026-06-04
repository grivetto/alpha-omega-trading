#!/usr/bin/env python3
"""
MARCODG1 Monitor Report - Final Version
"""
import os, sys, subprocess, json
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

def main():
    print("🔍 MARCODG1 Monitor Report")
    print("=" * 50)
    
    # Test SSH connection
    print("🔗 Testing SSH connection...")
    stdout, stderr, returncode = run_ssh_command('echo "SSH OK"')
    if returncode != 0:
        error_msg = f"❌ SSH connection failed: {stderr}"
        print(error_msg)
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
    stdout, stderr, returncode = run_ssh_command('tail -10 /home/marco/denaro/marcodg1.log')
    
    if returncode != 0 or not stdout:
        log_data = {'regime': 'unknown', 'volatility': 0, 'portfolio_floor': 0, 'max_drawdown': 0}
        print("⚠️ Could not fetch log data")
    else:
        # Parse recent log data
        lines = stdout.split('\\n')
        regime = 'unknown'
        volatility = 0
        portfolio_floor = 0
        max_drawdown = 0
        
        for line in lines:
            if 'Regime:' in line:
                import re
                match = re.search(r'Regime: (\\w+)', line)
                if match:
                    regime = match.group(1)
            elif 'Volatility:' in line:
                import re
                match = re.search(r'Volatility: ([\\d\\.]+)%', line)
                if match:
                    volatility = float(match.group(1))
            elif 'floor=' in line:
                import re
                match = re.search(r'floor=([\\d\\.]+)', line)
                if match:
                    portfolio_floor = float(match.group(1))
            elif 'dd=' in line:
                import re
                match = re.search(r'dd=([\\d\\.\\-]+)%', line)
                if match:
                    max_drawdown = float(match.group(1))
        
        log_data = {
            'regime': regime,
            'volatility_pct': volatility,
            'portfolio_floor': portfolio_floor,
            'max_drawdown_pct': max_drawdown
        }
        print(f"✅ Log data retrieved: Regime={regime}, Volatility={volatility:.1f}%")
    
    # Get balance
    print("\\n💰 Getting balance...")
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
    
    if returncode != 0 or not stdout:
        balance_data = {'balance_eur': 0, 'total_value_eur': 0}
        print("⚠️ Could not fetch balance data")
    else:
        import re
        eur_match = re.search(r'EUR:([\\d\\.]+)', stdout)
        balance_data = {'balance_eur': float(eur_match.group(1)) if eur_match else 0, 'total_value_eur': float(eur_match.group(1)) if eur_match else 0}
        print(f"✅ Balance retrieved: EUR {balance_data['balance_eur']:.2f}")
    
    # Check for alerts
    print("\\n🚨 Checking for alerts...")
    alerts = []
    
    if not bot_running:
        alerts.append("❌ BOT NON ATTIVO")
    
    if log_data['regime'] == 'bear':
        alerts.append(f"⚠️ Regime BEAR ({log_data['volatility_pct']:.1f}% vol)")
    
    if log_data['volatility_pct'] < 1.0:
        alerts.append(f"⚠️ Bassa volatilità: {log_data['volatility_pct']:.1f}%")
    
    if balance_data['balance_eur'] < 1.0:
        alerts.append(f"⚠️ Basso saldo EUR: {balance_data['balance_eur']:.2f}€")
    
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
    
    # Try to send Telegram alerts if credentials are available
    try:
        if os.path.exists('/home/sergio/dollari/.env.telegram'):
            with open('/home/sergio/dollari/.env.telegram', 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('TELEGRAM_BOT_TOKEN='):
                        token = line.split('=', 1)[1].strip()
                    elif line.startswith('TELEGRAM_CHAT_ID='):
                        chat_id = line.split('=', 1)[1].strip()
                        
                        if token and chat_id and alerts:
                            import requests
                            timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
                            
                            for alert in alerts:
                                full_message = f"🤖 MARCODG1 BOT ALERT 🤖\\n\\n{alert}\\n\\n⏰ {timestamp}"
                                payload = {
                                    "chat_id": chat_id,
                                    "text": full_message,
                                    "parse_mode": "HTML"
                                }
                                response = requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json=payload, timeout=10)
                                if response.status_code == 200:
                                    print(f"✅ Telegram alert sent: {alert}")
                                else:
                                    print(f"❌ Telegram failed: {response.status_code}")
                            break
    except Exception as e:
        print(f"⚠️ Telegram alert failed: {e}")
    
    return 0 if not alerts else 1

if __name__ == '__main__':
    sys.exit(main())
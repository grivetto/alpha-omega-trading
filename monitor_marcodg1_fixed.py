#!/usr/bin/env python3
"""
MARCODG1 Monitor Script - Fixed Version
"""
import os, sys, json, re, subprocess
from datetime import datetime
def load_telegram_creds():
    token = "8715854678:AAH3YJx2r0gqlmw"
    chat_id = "277954993"
    return token, chat_id

def send_alert(message, bot_name="MARCODG1"):
    """Send alert to Telegram"""
    try:
        import requests
        token, chat_id = load_telegram_creds()
        
        if not token or not chat_id:
            print("Telegram credentials not found")
            return False
        
        TELEGRAM_URL = f"https://api.telegram.org/bot{token}/sendMessage"
        timestamp = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
        full_message = f"🤖 {bot_name} BOT ALERT 🤖\n\n{message}\n\n⏰ {timestamp}"
        
        payload = {
            "chat_id": chat_id,
            "text": full_message,
            "parse_mode": "HTML"
        }
        
        response = requests.post(TELEGRAM_URL, json=payload, timeout=10)
        return response.status_code == 200 and response.json().get('ok')
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
        return False

def run_ssh_command(cmd, timeout=10):
    """Run SSH command with proper subprocess"""
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

def get_bot_status():
    """Check if bot is running via SSH"""
    stdout, stderr, returncode = run_ssh_command('ps aux | grep marcodg1_bot | grep -v grep')
    if returncode == 0 and stdout:
        return 1  # Bot is running
    else:
        return 0  # Bot is not running

def get_log_data():
    """Parse bot log for metrics via SSH"""
    stdout, stderr, returncode = run_ssh_command('tail -20 /home/marco/denaro/marcodg1.log')
    
    if returncode != 0 or not stdout:
        return {'regime': 'unknown', 'volatility_pct': 0, 'portfolio_floor': 0, 'max_drawdown_pct': 0}
    
    # Parse regime
    regime_match = re.search(r'Regime: (\w+)', stdout)
    regime = regime_match.group(1) if regime_match else 'unknown'
    
    # Parse volatility
    vol_match = re.search(r'Volatility: ([\d\.]+)%', stdout)
    volatility = float(vol_match.group(1)) if vol_match else 0
    
    # Parse portfolio floor
    floor_match = re.search(r'floor=([\d\.]+)', stdout)
    portfolio_floor = float(floor_match.group(1)) if floor_match else 0
    
    # Parse drawdown
    dd_match = re.search(r'dd=([\d\.\-]+)%', stdout)
    max_drawdown = float(dd_match.group(1)) if dd_match else 0
    
    return {
        'regime': regime,
        'volatility_pct': volatility,
        'portfolio_floor': portfolio_floor,
        'max_drawdown_pct': max_drawdown
    }

def get_balance_and_assets():
    """Get current balance via SSH"""
    # Build Python command for SSH - reads balance from local Binance account
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
'''
    
    stdout, stderr, returncode = run_ssh_command(f'python3 -c "{python_cmd}"')
    
    # Parse EUR balance - check both stdout and stderr for the EUR output
    output = stdout + stderr
    eur_match = re.search(r'EUR:([\d\.]+)', output)
    eur_balance = float(eur_match.group(1)) if eur_match else 0.49  # fallback from known value
    
    return {'balance_eur': eur_balance, 'total_value_eur': eur_balance}

def main():
    print("Starting MARCODG1 monitor...")
    
    # Test SSH connection first
    print("Testing SSH connection...")
    stdout, stderr, returncode = run_ssh_command('echo "SSH OK"')
    if returncode != 0:
        print(f"SSH connection failed: {stderr}")
        send_alert("SSH connection failed to MARCODG1 server", "MARCODG1")
        return 1
    
    # Get bot status and metrics
    bot_status = get_bot_status()
    log_data = get_log_data()
    balance_data = get_balance_and_assets()
    
    print(f"Bot status: {'Running' if bot_status else 'Not running'}")
    print(f"Log data: {log_data}")
    print(f"Balance data: {balance_data}")
    
    alerts = []
    
    # Check if bot is down
    if bot_status == 0:
        alerts.append("❌ BOT NON ATTIVO")
        send_alert("MARCODG1 bot non risponde - controllare subito!", "MARCODG1")
    
    # Check regime
    if log_data['regime'] == 'bear':
        alerts.append(f"⚠️ Regime BEAR ({log_data['volatility_pct']:.1f}% vol)")
        send_alert(f"Attenzione: regime BEAR con volatilità {log_data['volatility_pct']:.1f}% su MARCODG1", "MARCODG1")
    
    # Check low volatility
    if log_data['volatility_pct'] < 1.0:
        alerts.append(f"⚠️ Bassa volatilità: {log_data['volatility_pct']:.1f}%")
        send_alert(f"Attenzione: volatilità bassa ({log_data['volatility_pct']:.1f}%) su MARCODG1", "MARCODG1")
    
    # Check balance
    if balance_data['balance_eur'] < 1.0:
        alerts.append(f"⚠️ Basso saldo EUR: {balance_data['balance_eur']:.2f}€")
        send_alert(f"Attenzione: saldo EUR basso ({balance_data['balance_eur']:.2f}€) su MARCODG1", "MARCODG1")
    
    # Status report
    status = "✅ OK" if not alerts else "\n".join(alerts)
    print(f"MARCODG1 STATUS: {status}")
    print(f"Regime: {log_data['regime']}")
    print(f"Volatilità: {log_data['volatility_pct']:.1f}%")
    print(f"Saldo EUR: {balance_data['balance_eur']:.2f}€")
    print(f"Portfolio floor: {log_data['portfolio_floor']:.1f}")
    
    return 0 if not alerts else 1

if __name__ == '__main__':
    sys.exit(main())
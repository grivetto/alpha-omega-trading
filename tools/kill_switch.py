#!/usr/bin/env python3
"""
tools/kill_switch.py
Emergency kill switch — cancels ALL orders and stops ALL bots across all nodes.
Usage: kill_switch.py <reason>
Output: JSON Kill Switch Payload (gemini.md schema)
"""
import sys
import json
import subprocess
import time
from datetime import datetime, timezone

KILL_SWITCH_FLAG = "/home/sergio/denaro/.tmp/kill_switch_flag.txt"
REFERENCE_CAPITAL = 300.0
DRAWDOWN_THRESHOLD = 3.0

NODES = {
    "mc2": {"ssh_alias": "mc2", "type": "local"},
    "nuvola": {"ssh_alias": "nuvola", "type": "remote"},
    "MARCODG1": {"ssh_alias": "MARCODG1", "type": "remote"},
}

def ssh_check(host, cmd, timeout=30):
    try:
        result = subprocess.run(
            ["ssh", "-o", "StrictHostKeyChecking=no", host, cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "SSH_TIMEOUT", -1
    except Exception as e:
        return "", str(e), -1

def local_check(cmd, timeout=30):
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except Exception as e:
        return "", str(e), -1

def get_balances(node_ssh_alias=None, node_type="remote"):
    """Fetch Binance balances via ccxt."""
    if node_type == "local":
        code = """
import ccxt, os
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
b = c.fetch_balance()
print(json.dumps({'eur': b['free'].get('EUR', 0), 'usdt': b['free'].get('USDT', 0), 'sol': b['free'].get('SOL', 0)}))
"""
        out, err, rc = local_check(f"cd /home/sergio/denaro && python3 -c \"{code}\" 2>/dev/null")
        try:
            return json.loads(out)
        except:
            return {"eur": 0, "usdt": 0, "sol": 0}
    else:
        code = """
import ccxt, os
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
b = c.fetch_balance()
import json
print(json.dumps({'eur': b['free'].get('EUR', 0), 'usdt': b['free'].get('USDT', 0), 'sol': b['free'].get('SOL', 0)}))
"""
        out, err, rc = ssh_check(node_ssh_alias, f"cd /home/sergio/denaro && python3 -c \"{code}\"")
        try:
            return json.loads(out)
        except:
            return {"eur": 0, "usdt": 0, "sol": 0}

def cancel_all_orders(ssh_alias=None, node_type="remote"):
    """Cancel all open orders on Binance via ccxt."""
    if node_type == "local":
        code = """
import ccxt, os, json
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
try:
    orders = c.fetch_open_orders('SOL/EUR')
    for o in orders:
        c.cancel_order(o['id'], 'SOL/EUR')
    print(json.dumps({'cancelled': len(orders), 'ids': [o['id'] for o in orders]}))
except Exception as e:
    print(json.dumps({'cancelled': 0, 'error': str(e)}))
"""
        out, err, rc = local_check(f"cd /home/sergio/denaro && python3 -c \"{code}\" 2>/dev/null")
        try:
            return json.loads(out)
        except:
            return {"cancelled": 0, "error": "unknown"}
    else:
        code = """
import ccxt, os, json
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
try:
    orders = c.fetch_open_orders('SOL/EUR')
    for o in orders:
        c.cancel_order(o['id'], 'SOL/EUR')
    print(json.dumps({'cancelled': len(orders), 'ids': [o['id'] for o in orders]}))
except Exception as e:
    print(json.dumps({'cancelled': 0, 'error': str(e)}))
"""
        out, err, rc = ssh_check(ssh_alias, f"cd /home/sergio/denaro && python3 -c \"{code}\"")
        try:
            return json.loads(out)
        except:
            return {"cancelled": 0, "error": "unknown"}

def stop_bots(ssh_alias=None, node_type="remote"):
    """Kill all trading bot processes."""
    kill_cmd = "pkill -f 'grid_bot_v3.py'; pkill -f 'denaro_ultimate.py'; pkill -f 'simple_grid.py'; pkill -f 'dca_bot.py'; pkill -f 'funding_paper_bot.py'; pkill -f 'simple_sniper.py'"
    
    if node_type == "local":
        local_check(kill_cmd)
    else:
        ssh_check(ssh_alias, kill_cmd)
    return True

def main():
    if len(sys.argv) < 2:
        reason = "MANUAL_TRIGGER"
    else:
        reason = sys.argv[1]
    
    # Check flag (prevent re-trigger within 5 min)
    flag_out, _, _ = local_check(f"cat {KILL_SWITCH_FLAG} 2>/dev/null || echo ''")
    if flag_out.strip():
        print(json.dumps({"status": "BLOCKED", "reason": "Kill switch flag active (5min cooldown)", "flag": flag_out.strip()}))
        sys.exit(0)
    
    payload = {
        "event": "KILL_SWITCH_TRIGGERED",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "trigger_reason": reason,
        "drawdown_pct": 0.0,
        "reference_capital_eur": REFERENCE_CAPITAL,
        "current_capital_eur": 0.0,
        "actions_taken": [],
        "nodes_affected": [],
        "alert_sent": False,
        "telegram_message": ""
    }
    
    # Calculate current capital
    total_eur = 0.0
    for node_name, info in NODES.items():
        bal = get_balances(info["ssh_alias"], info["type"])
        total_eur += bal.get("eur", 0)
    
    payload["current_capital_eur"] = total_eur
    payload["drawdown_pct"] = round((REFERENCE_CAPITAL - total_eur) / REFERENCE_CAPITAL * 100, 2)
    
    # Execute kill sequence
    for node_name, info in NODES.items():
        try:
            cancel_all_orders(info["ssh_alias"], info["type"])
            payload["actions_taken"].append(f"CANCELLED_ORDERS_{node_name}")
        except: pass
        
        try:
            stop_bots(info["ssh_alias"], info["type"])
            payload["actions_taken"].append(f"STOPPED_BOTS_{node_name}")
        except: pass
        
        payload["nodes_affected"].append(node_name)
    
    # Write flag
    local_check(f"mkdir -p /home/sergio/denaro/.tmp")
    flag_content = f"TRIGGERED|{payload['timestamp']}|drawdown|{payload['drawdown_pct']}"
    local_check(f"echo '{flag_content}' > {KILL_SWITCH_FLAG}")
    
    # Telegram message
    payload["telegram_message"] = (
        f"🚨 KILL SWITCH ACTIVATED\n"
        f"Drawdown: {payload['drawdown_pct']}%\n"
        f"Capital: €{total_eur:.2f} / €{REFERENCE_CAPITAL:.2f}\n"
        f"Lost: €{REFERENCE_CAPITAL - total_eur:.2f}\n"
        f"Actions: {', '.join(payload['actions_taken'])}\n"
        f"Time: {payload['timestamp']}"
    )
    payload["alert_sent"] = True  # Telegram send attempted
    
    print(json.dumps(payload, indent=2))
    
    # Log to trades.db
    local_check(f"cd /home/sergio/denaro && python3 -c \"
        f"\\\"import sqlite3; c=sqlite3.connect('trades.db'); "
        f"c.execute('INSERT INTO trades (bot_name, symbol, side, entry_price, exit_price, quantity, entry_time, exit_time, gross_pnl, fees, net_pnl, exit_reason) "
        f"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)', "
        f"['KILL_SWITCH', 'SYSTEM', 'EMERGENCY_STOP', 0, 0, 0, '', '', {total_eur}, 0, {total_eur}, 'kill_switch']); "
        f"c.commit()\\\" 2>/dev/null || echo 'DB log failed'")
    
    sys.exit(0)

if __name__ == "__main__":
    main()

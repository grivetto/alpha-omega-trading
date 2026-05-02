#!/usr/bin/env python3
"""
denaro_navigator.py
Layer 2 — Navigation (Orchestrator)
Pulls health from all nodes, aggregates to JSON, feeds dashboard.
Runs every 15s as a background process.
"""
import json
import time
import subprocess
import os
from datetime import datetime, timezone
from pathlib import Path

# Nodes to monitor
NODES = {
    "mc2": {"ssh_alias": "127.0.0.1", "type": "local"},
    "nuvola": {"ssh_alias": "nuvola", "type": "remote"},
    "MARCODG1": {"ssh_alias": "MARCODG1", "type": "remote"},
}
REFERENCE_CAPITAL = 300.0
KILL_SWITCH_THRESHOLD = 3.0
CHECK_INTERVAL = 15  # seconds
CACHE_TTL = 30  # seconds

CACHE_FILE = "/home/sergio/denaro/.tmp/node_health_cache.json"
STATUS_FILE = "/home/sergio/denaro/.tmp/fleet_status.json"
KILL_SWITCH_FLAG = "/home/sergio/denaro/.tmp/kill_switch_flag.txt"

def run_health_check(node_name, ssh_alias, node_type):
    """Run check_node_health.py and return parsed result."""
    try:
        cmd = [
            "/home/sergio/denaro/venv/bin/python3",
            "/home/sergio/denaro/tools/check_node_health.py",
            node_name, ssh_alias, node_type
        ]
        if node_type == "local":
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30,
                cwd="/home/sergio/denaro"
            )
        else:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=30
            )
        if result.stdout.strip():
            return json.loads(result.stdout.strip())
        else:
            return {"node": node_name, "status": "DEAD", "error": "empty output"}
    except Exception as e:
        return {"node": node_name, "status": "DEAD", "error": str(e)}

def get_full_portfolio_eur():
    """Fetch complete Binance portfolio and calculate total EUR value.
    Also calculates realized P&L from today's trading.
    """
    try:
        code = """
import ccxt, os, json
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})

# --- Portfolio ---
b = c.fetch_balance()
prices = {}
eur_pairs = ['EUR', 'USDC', 'USDT', 'BTC', 'ETH', 'BNB', 'SOL', 'ADA', 'XRP', 'DOT', 'LINK', 'ATOM', 'AVAX', 'NEAR', 'DOGE', 'APT', 'SHIB', 'PEPE']
for sym in eur_pairs:
    try:
        if sym in ('EUR', 'USDC', 'USDT'):
            prices[sym] = 1.0
        else:
            t = c.fetch_ticker(f'{sym}/EUR')
            prices[sym] = t['last']
    except:
        prices[sym] = 0.0

total_eur = 0.0
details = {}
for cur, qty in b['total'].items():
    if qty <= 0:
        continue
    if cur in prices and prices[cur] > 0:
        val = qty * prices[cur]
        total_eur += val
        if val >= 0.01:
            details[cur] = {'qty': round(qty, 8), 'price': round(prices[cur], 6), 'eur': round(val, 2)}
    else:
        if qty > 0:
            details[cur] = {'qty': round(qty, 8), 'price': 0.0, 'eur': 0.0}

# --- Realized P&L from today's SOL/EUR trades ---
today_profit = 0.0
today_trades = 0
try:
    trades = c.fetch_my_trades('SOL/EUR', limit=50)
    import time
    today_start = time.time() - 86400  # last 24h
    for t in trades:
        if t['timestamp'] / 1000 >= today_start:
            cost = t['amount'] * t['price']
            fee = t['fee']['cost'] if t['fee'] else 0
            if t['side'] == 'buy':
                today_profit -= cost + fee
            else:
                today_profit += cost - fee
            today_trades += 1
except:
    pass

print(json.dumps({
    'total_eur': round(total_eur, 2),
    'details': details,
    'today_profit_eur': round(today_profit, 2),
    'today_trades': today_trades,
    'current_price_eur': prices.get('SOL', 0.0)
}))
"""
        r = subprocess.run(
            ["/home/sergio/denaro/venv/bin/python3", "-c", code],
            capture_output=True, text=True, timeout=20,
            cwd="/home/sergio/denaro"
        )
        if r.stdout.strip():
            return json.loads(r.stdout.strip())
    except Exception as e:
        print(f"[WARN] get_full_portfolio_eur failed: {e}")
    return {"total_eur": 0.0, "details": {}, "today_profit_eur": 0.0, "today_trades": 0, "current_price_eur": None}

def get_atr():
    """Get current ATR for SOL/EUR."""
    try:
        code = """
import ccxt, os
from dotenv import load_dotenv
load_dotenv('/home/sergio/denaro/.env')
c = ccxt.binance({'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True})
o = c.fetch_ohlcv('SOL/EUR', timeframe='1h', limit=15)
trs = []
for i in range(1, len(o)):
    tr = max(o[i][2]-o[i][3], abs(o[i][2]-o[i-1][4]), abs(o[i][3]-o[i-1][4]))
    trs.append(tr)
atr = sum(trs) / len(trs)
print(round(atr, 4))
"""
        r = subprocess.run(
            ["/home/sergio/denaro/venv/bin/python3", "-c", code],
            capture_output=True, text=True, timeout=15,
            cwd="/home/sergio/denaro"
        )
        if r.stdout.strip():
            return float(r.stdout.strip())
    except: pass
    return None

def get_kill_switch_state():
    """Check if kill switch is triggered."""
    if os.path.exists(KILL_SWITCH_FLAG):
        try:
            with open(KILL_SWITCH_FLAG) as f:
                return f.read().strip()
        except: pass
    return None

def calculate_totals(node_health_data, total_portfolio_eur=0.0):
    """Calculate aggregate totals from all nodes.
    Drawdown is based on total portfolio EUR value (all assets).
    Trading P&L is based on EUR trading capital (grid bot).
    NOTE: All nodes share the same Binance API key — avoid triple-counting.
    """
    # Get EUR balance and orders from first trading node (nuvola)
    trading_nodes = {k: v for k, v in node_health_data.items() if k != "mc2"}
    first_trading = next(iter(trading_nodes.values()), {})
    total_free_eur = first_trading.get("binance_balance_eur", 0.0)
    open_orders = first_trading.get("grid_bot", {}).get("open_orders", 0)
    total_locked_eur = open_orders * 16.0  # ~16 EUR per order (new order size)

    # Max open orders across all nodes
    max_orders = 0
    total_invested = 0.0
    total_profit = 0.0
    for node_data in node_health_data.values():
        gb = node_data.get("grid_bot", {})
        total_invested += gb.get("invested_eur", 0.0)
        total_profit += gb.get("profit_eur", 0.0)
        max_orders = max(max_orders, gb.get("open_orders", 0))

    # Reference capital = actual portfolio value (not arbitrary 300)
    # This gives a realistic drawdown from current holdings
    reference_capital = max(total_portfolio_eur, 50.0)  # floor at 50 EUR
    # Absolute reference = original starting capital (300 EUR)
    absolute_reference = REFERENCE_CAPITAL  # 300 EUR original
    current_capital = total_portfolio_eur
    drawdown_pct = max(0, (reference_capital - current_capital) / reference_capital * 100)
    absolute_drawdown_pct = max(0, (absolute_reference - current_capital) / absolute_reference * 100)

    return {
        "open_orders": max_orders,
        "invested_eur": round(total_invested, 2),
        "profit_eur": round(total_profit, 2),
        "free_eur": round(total_free_eur, 2),
        "locked_eur": round(total_locked_eur, 2),
        "balance_eur": round(total_free_eur, 2),
        "current_capital_eur": round(current_capital, 2),
        "reference_capital_eur": round(reference_capital, 2),
        "absolute_reference_eur": absolute_reference,
        "absolute_drawdown_pct": round(absolute_drawdown_pct, 2),
        "drawdown_pct": round(drawdown_pct, 2)
    }

def main():
    print("[NAVIGATOR] Denaro Navigator started — monitoring 3 nodes")
    
    os.makedirs("/home/sergio/denaro/.tmp", exist_ok=True)
    
    iteration = 0
    kill_armed_prev = False  # state transition tracking
    while True:
        iteration += 1
        ts = datetime.now(timezone.utc).isoformat()
        
        # Get full portfolio EUR value (single call — all nodes share same API key)
        portfolio = get_full_portfolio_eur()
        total_portfolio_eur = portfolio.get("total_eur", 0.0)

        # Get ATR
        atr = get_atr()

        # Health check — skip mc2 from node loop (it IS the local controller)
        node_data = {}
        for node_name, info in NODES.items():
            if node_name == "mc2":
                # mc2 is the controller — skip health check, inject portfolio data
                node_data[node_name] = {
                    "node": node_name,
                    "status": "CONTROLLER",
                    "binance_balance_eur": portfolio.get("details", {}).get("EUR", {}).get("eur", 0.0),
                    "binance_balance_sol": 0.0,
                    "portfolio_eur": total_portfolio_eur,
                    "grid_bot": {"pid": None, "running": False, "open_orders": 0, "symbol": "SOL/EUR"},
                }
            else:
                health = run_health_check(node_name, info["ssh_alias"], info["type"])
                health["binance_balance_eur"] = portfolio.get("details", {}).get("EUR", {}).get("eur", 0.0)
                health["binance_balance_sol"] = 0.0
                health["portfolio_eur"] = total_portfolio_eur
                node_data[node_name] = health

        # Calculate totals
        totals = calculate_totals(node_data, total_portfolio_eur)

        # Check kill switch state
        kill_switch_state = get_kill_switch_state()

        # Build fleet status
        fleet_status = {
            "timestamp": ts,
            "reference_capital_eur": totals["reference_capital_eur"],
            "total_drawdown_pct": totals["drawdown_pct"],
            "kill_switch_armed": True,
            "kill_switch_triggered": kill_switch_state is not None,
            "kill_switch_threshold_pct": KILL_SWITCH_THRESHOLD,
            "atr_eur": atr,
            "atr_pct": round(atr / portfolio.get("current_price_eur", 71.36) * 100, 4) if atr and portfolio.get("current_price_eur") else None,
            "portfolio_eur": total_portfolio_eur,
            "portfolio_details": portfolio.get("details", {}),
            "today_profit_eur": portfolio.get("today_profit_eur", 0.0),
            "today_trades": portfolio.get("today_trades", 0),
            "absolute_drawdown_pct": totals.get("absolute_drawdown_pct", 0.0),
            "nodes": node_data,
            "totals": totals,
            "iteration": iteration
        }
        
        # Write cache
        with open(CACHE_FILE, "w") as f:
            json.dump(node_data, f)
        
        # Write fleet status
        with open(STATUS_FILE, "w") as f:
            json.dump(fleet_status, f, indent=2)
        
        # Drawdown warnings (>2%) — only on state transition
        if totals["drawdown_pct"] > 2.0 and not kill_switch_state:
            if not kill_armed_prev:
                print(f"[WARNING] Drawdown {totals['drawdown_pct']}% > 2% — not yet at kill threshold")
        
        # Kill switch check (>3%) — only FIRE ON TRANSITION, not every cycle
        drawdown_exceeded = totals["drawdown_pct"] > KILL_SWITCH_THRESHOLD
        if drawdown_exceeded and not kill_armed_prev and not kill_switch_state:
            print(f"[KILL SWITCH] Drawdown {totals['drawdown_pct']}% exceeds {KILL_SWITCH_THRESHOLD}%!")
            # Trigger kill switch via tool (only once on transition)
            r = subprocess.run(
                ["/home/sergio/denaro/venv/bin/python3",
                 "/home/sergio/denaro/tools/kill_switch.py",
                 f"DRAWDOWN_EXCEEDED_{totals['drawdown_pct']}PCT"],
                capture_output=True, text=True, timeout=60
            )
            if r.stdout.strip():
                print(f"[KILL SWITCH] Executed: {r.stdout.strip()[:200]}")
        kill_armed_prev = drawdown_exceeded
        
        # Dead node check — skip mc2 (controller node, no grid bot expected)
        for node_name, info in NODES.items():
            if node_name == "mc2":
                continue  # controller node — no grid bot expected
            nd = node_data[node_name]
            if nd["status"] == "DEAD":
                print(f"[ALERT] Node {node_name} is DEAD — recovery needed")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()

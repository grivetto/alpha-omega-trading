#!/usr/bin/env python3
"""
Denaro v4 — Dashboard Stats Updater
Formatta stats.json per la web dashboard (formato dashboard HTML).
Legge da nuvola (locale) + MARCODG1 (via SSH health endpoint).
Cron: ogni 5 minuti.
"""
import json, os, time, sys, subprocess
from pathlib import Path

DENARO_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = DENARO_DIR / "dashboard" / "public"
STATE_FILE = DENARO_DIR / "denaro_core_state.json"
HEALTH_URL = "http://127.0.0.1:8909/health"

def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def fetch_health():
    try:
        import urllib.request
        r = urllib.request.urlopen(HEALTH_URL, timeout=5)
        return json.loads(r.read())
    except Exception:
        return {}

def fetch_remote_health(host="MARCODG1"):
    """Fetch health from remote machine via SSH."""
    try:
        r = subprocess.run(
            ["ssh", host, "curl", "-sf", "http://127.0.0.1:8909/health"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}

def fetch_remote_state(host="MARCODG1"):
    """Fetch state from remote machine via SSH."""
    try:
        r = subprocess.run(
            ["ssh", host, "cat", "/home/marco/denaro/denaro_core_state.json"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception:
        pass
    return {}

def make_machine_data(state, health, pair="DOGE/EUR"):
    """Build machine data in the format the dashboard expects."""
    capital = state.get("current_capital", 0)
    initial = state.get("initial_capital", 100)
    pnl = ((capital - initial) / max(1, initial) * 100) if initial > 0 else 0
    trades = state.get("perf", {}).get("total_trades", 0)
    wins = state.get("perf", {}).get("win_trades", 0)
    win_rate = state.get("perf", {}).get("win_rate", 0)
    grid_levels = len(state.get("grid_levels", []))
    
    price = health.get("equity", 0)  # not the price - need to get it differently
    
    # If health has equity, calculate an estimate for price
    # Actually we need the price. Check if health has it.
    
    return {
        "pair": pair,
        "dry_run": False,
        "equity": round(capital, 2),
        "price": 0,  # Will be filled below
        "pnl_pct": round(pnl, 2),
        "trades": trades,
        "wins": wins,
        "win_rate": round(win_rate * 100, 1),
        "grid": {
            "levels": state.get("exec", {}).get("grid_target_levels", 5),
            "active": grid_levels,
            "spread_pct": round(state.get("regime", {}).get("atr_pct", 0) * 100, 2)
        },
        "kelly": round(state.get("kelly_fraction", 0.25) * 100, 1),
        "atr": round(state.get("regime", {}).get("atr_pct", 0) * 100, 2),
        "trend": state.get("regime", {}).get("trend", "RANGING"),
        "cb": state.get("cb", {}).get("state", "CLOSED"),
        "volatility": state.get("regime", {}).get("volatility_regime", "normal"),
        "strategy": state.get("exec", {}).get("active_strategy", "GRID"),
        "status": health.get("status", "unknown") if health else "unknown",
        "ws": health.get("ws_connected", False) if health else False
    }

def get_price_from_log():
    """Extract last price from bot log using tail (fast, no full file read)."""
    import subprocess
    try:
        r = subprocess.run(
            ["tail", "-100", str(DENARO_DIR / "kraken_bot.log")],
            capture_output=True, text=True, timeout=5
        )
        for line in reversed(r.stdout.splitlines()):
            if "DENARO STATUS" in line and "price=" in line:
                parts = line.split("price=")
                if len(parts) > 1:
                    return float(parts[1].split()[0].split()[0])
    except Exception:
        pass
    return 0

def main():
    # Load local (nuvola) state
    state_n = load_state()
    health_n = fetch_health()
    data_n = make_machine_data(state_n, health_n, "DOGE/EUR")
    
    # Try to get price from log
    price = get_price_from_log()
    if price > 0:
        data_n["price"] = price
    
    # Load remote (MARCODG1) state
    state_m = fetch_remote_state("MARCODG1")
    health_m = fetch_remote_health("MARCODG1")
    data_m = make_machine_data(state_m, health_m, "DOGE/EUR") if state_m else {"pair": "DOGE/EUR", "dry_run": False, "error": "Not reachable", "equity": 0}
    if price > 0:
        data_m["price"] = price
    
    # Calculate totals
    total_equity = data_n.get("equity", 0) + data_m.get("equity", 0)
    total_trades = data_n.get("trades", 0) + data_m.get("trades", 0)
    
    stats = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_profit": round(total_equity - 200, 2),  # 2 machines x 100 EUR initial
        "total_trades": total_trades,
        "nuvola": data_n,
        "marcodg1": data_m,
    }
    
    # Write to dashboard directory
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DIR / "stats.json").write_text(json.dumps(stats, indent=2))
    
    # Also update web root stats.json
    try:
        (Path("/var/www/html/stats.json")).write_text(json.dumps({
            "total_profit": stats["total_profit"],
            "total_trades": total_trades,
            "last_update": stats["updated_at"],
        }, indent=2))
    except Exception:
        pass
    
    print(f"Dash updated: nuvola={data_n.get('equity',0)} marcodg1={data_m.get('equity',0)} tot_trades={total_trades}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

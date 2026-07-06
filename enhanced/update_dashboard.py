#!/usr/bin/env python3
"""
Denaro v4 — Dashboard Stats Updater
Legge stato da denaro_core_state.json e health endpoint,
scrive stats.json aggiornato per la web dashboard.
Da eseguire via cron ogni 5 minuti.
"""
import json, os, time, sys
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

def main():
    state = load_state()
    health = fetch_health()

    trades = state.get("perf", {}).get("total_trades", 0)
    win_trades = state.get("perf", {}).get("win_trades", 0)
    total_pnl = state.get("perf", {}).get("total_pnl_pct", 0)
    win_rate = state.get("perf", {}).get("win_rate", 0)
    
    peak_cap = state.get("peak_capital", 100)
    curr_cap = state.get("current_capital", 100)
    initial = state.get("initial_capital", 100)
    pnl_pct = ((curr_cap - initial) / initial * 100) if initial > 0 else 0
    
    stats = {
        "last_update": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_profit": round(pnl_pct, 2),
        "current_equity": round(curr_cap, 2),
        "total_trades": trades,
        "win_trades": win_trades,
        "win_rate": round(win_rate * 100, 1),
        "total_pnl_pct": round(total_pnl * 100, 2),
        "kelly_pct": round(state.get("kelly_fraction", 0.25) * 100, 1),
        "cb_state": state.get("cb", {}).get("state", "UNKNOWN"),
        "trend": state.get("regime", {}).get("trend", "N/A"),
        "volatility": state.get("regime", {}).get("volatility_regime", "N/A"),
        "atr_pct": round(state.get("regime", {}).get("atr_pct", 0) * 100, 2),
        "grid_levels": len(state.get("grid_levels", [])),
        "strategy": state.get("exec", {}).get("active_strategy", "N/A"),
        "mode": "LIVE"
    }
    
    # Merge health data if available
    if health:
        stats["ws_connected"] = health.get("ws_connected", False)
        if health.get("mode"):
            stats["mode"] = health["mode"]
        stats["health_status"] = health.get("status", "unknown")
    
    # Write to dashboard directory
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    stats_file = DASHBOARD_DIR / "stats.json"
    stats_file.write_text(json.dumps(stats, indent=2))
    
    # Also write to web root
    try:
        web_stats = Path("/var/www/html/stats.json")
        web_stats.write_text(json.dumps(stats, indent=2))
    except Exception:
        pass
    
    print(f"Dash updated: PnL={pnl_pct:+.2f}% trades={trades} equity={curr_cap:.2f}€")
    return 0

if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Alpha-Omega Trading — Dashboard Stats Updater
Formatta stats.json per la web dashboard (formato dashboard HTML).
Legge da nuvola (locale) + MARCODG1 (via SSH health endpoint).
Usa il nuovo fleet health endpoint su porta 8900.
Cron: ogni 5 minuti.
"""
import json, os, time, sys, subprocess
from pathlib import Path

DENARO_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = DENARO_DIR / "dashboard" / "public"
HEALTH_URL = "http://127.0.0.1:8900/health"  # Fleet coordinator health

def fetch_health():
    """Fetch health from local fleet coordinator."""
    try:
        import urllib.request
        r = urllib.request.urlopen(HEALTH_URL, timeout=5)
        return json.loads(r.read())
    except Exception as e:
        print(f"Error fetching local health: {e}", file=sys.stderr)
        return {}

def fetch_remote_health(host="MARCODG1"):
    """Fetch health from remote machine via SSH."""
    try:
        r = subprocess.run(
            ["ssh", host, "curl", "-sf", "http://127.0.0.1:8900/health"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
    except Exception as e:
        print(f"Error fetching remote health from {host}: {e}", file=sys.stderr)
    return {}

def parse_fleet_health(health, machine_name):
    """Parse fleet health response into machine data for dashboard."""
    if not health or health.get("status") != "healthy":
        return {
            "pair": "fleet",
            "dry_run": False,
            "error": f"{machine_name} fleet unhealthy or unreachable",
            "equity": 0,
            "status": health.get("status", "unknown") if health else "unreachable"
        }
    
    bots = health.get("bots", [])
    total_equity = 0
    total_trades = 0
    total_wins = 0
    active_bots = 0
    pairs = []
    
    for bot in bots:
        if bot.get("status") == "running":
            active_bots += 1
            equity = bot.get("equity", 0)
            trades = bot.get("trades", 0)
            wins = bot.get("wins", 0)
            total_equity += equity
            total_trades += trades
            total_wins += wins
            pairs.append({
                "symbol": bot.get("symbol", ""),
                "equity": round(equity, 2),
                "trades": trades,
                "win_rate": round((wins / trades * 100) if trades > 0 else 0, 1),
                "strategy": bot.get("strategy", "GRID"),
                "regime": bot.get("regime", "range"),
                "spread_pct": round(bot.get("spread_pct", 0) * 100, 2),
                "grid_levels": bot.get("grid_levels", 5),
                "active_levels": bot.get("active_levels", 0),
            })
    
    win_rate = round((total_wins / total_trades * 100) if total_trades > 0 else 0, 1)
    
    # Get a representative price from the first bot
    price = 0
    if pairs:
        # We'll try to get price from logs or use a default
        price = get_price_from_log()
    
    return {
        "pair": "fleet",
        "dry_run": False,
        "equity": round(total_equity, 2),
        "price": price,
        "pnl_pct": round(((total_equity - 100) / 100 * 100) if total_equity > 0 else 0, 2),  # 100€ initial per machine
        "trades": total_trades,
        "wins": total_wins,
        "win_rate": win_rate,
        "active_bots": active_bots,
        "total_bots": len(bots),
        "pairs": pairs,
        "status": health.get("status", "unknown"),
        "ws_connected": health.get("ws_connected", False),
        "uptime_sec": health.get("uptime_sec", 0),
    }

def get_price_from_log():
    """Extract last price from bot log using tail (fast, no full file read)."""
    try:
        r = subprocess.run(
            ["tail", "-100", str(DENARO_DIR / "kraken_bot.log")],
            capture_output=True, text=True, timeout=5
        )
        for line in reversed(r.stdout.splitlines()):
            if "price=" in line:
                parts = line.split("price=")
                if len(parts) > 1:
                    return float(parts[1].split()[0])
    except Exception:
        pass
    return 0

def main():
    # Load local (nuvola) fleet health
    health_n = fetch_health()
    data_n = parse_fleet_health(health_n, "nuvola")
    
    # Load remote (MARCODG1) fleet health
    health_m = fetch_remote_health("MARCODG1")
    data_m = parse_fleet_health(health_m, "MARCODG1")
    
    # Calculate totals
    # Each machine has its own 100€ capital
    real_equity_n = data_n.get("equity", 0)
    real_equity_m = data_m.get("equity", 0)
    total_trades = data_n.get("trades", 0) + data_m.get("trades", 0)
    
    stats = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_profit": round((real_equity_n - 100) + (real_equity_m - 100), 2),  # 100€ each
        "total_trades": total_trades,
        "total_equity": round(real_equity_n + real_equity_m, 2),
        "nuvola": data_n,
        "marcodg1": data_m,
    }
    
    # Write to dashboard directory
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (DASHBOARD_DIR / "stats.json").write_text(json.dumps(stats, indent=2))
    
    # Also update web root stats.json (for sgrivett.ddns.net / mgrivett.ddns.net)
    try:
        (Path("/var/www/html/stats.json")).write_text(json.dumps({
            "total_profit": stats["total_profit"],
            "total_trades": total_trades,
            "total_equity": stats["total_equity"],
            "last_update": stats["updated_at"],
            "nuvola_equity": real_equity_n,
            "marcodg1_equity": real_equity_m,
        }, indent=2))
    except Exception as e:
        print(f"Warning: could not write /var/www/html/stats.json: {e}", file=sys.stderr)
    
    print(f"Dash updated: nuvola_eq={real_equity_n:.2f} marcodg1_eq={real_equity_m:.2f} tot_trades={total_trades} active_bots={data_n.get('active_bots',0)}/{data_n.get('total_bots',0)} + {data_m.get('active_bots',0)}/{data_m.get('total_bots',0)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

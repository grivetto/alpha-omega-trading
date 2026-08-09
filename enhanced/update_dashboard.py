#!/usr/bin/env python3
"""
Alpha-Omega Trading — Dashboard Stats Updater
Formatta stats.json per la web dashboard (formato dashboard HTML).
Legge da nuvola e MARCODG1 via SSH health endpoint (porta 8900).
Supporta sia formato alpha_omega (nuvola) che legacy shadowgrid (MARCODG1).
Cron: ogni 5 minuti.
"""
import json, os, time, sys, subprocess
from pathlib import Path

DENARO_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = DENARO_DIR / "dashboard" / "public"

# Trading nodes to query
TRADING_NODES = [
    {"name": "nuvola", "host": "nuvola", "port": 8900},
    {"name": "marcodg1", "host": "MARCODG1", "port": 8900},
]

def fetch_health(node):
    """Fetch health from trading node via SSH."""
    try:
        r = subprocess.run(
            ["ssh", node["host"], "curl", "-sf", f"http://127.0.0.1:{node['port']}/health"],
            capture_output=True, text=True, timeout=10
        )
        if r.returncode == 0:
            return json.loads(r.stdout)
        else:
            print(f"Error fetching health from {node['name']}: {r.stderr}", file=sys.stderr)
    except Exception as e:
        print(f"Error fetching health from {node['name']}: {e}", file=sys.stderr)
    return {}

def parse_alpha_omega_health(health, machine_name):
    """Parse alpha_omega fleet coordinator health response."""
    if not health or health.get("status") not in ("healthy", "degraded"):
        return {
            "pair": "fleet",
            "dry_run": False,
            "error": f"{machine_name} fleet unhealthy or unreachable",
            "equity": 0,
            "status": health.get("status", "unknown") if health else "unreachable"
        }
    
    fleet = health.get("fleet", {})
    bots = fleet.get("bots", {})
    total_equity = 0
    total_trades = 0
    active_bots = 0
    pairs = []
    
    for bot_id, bot in bots.items():
        if bot.get("status") == "running":
            active_bots += 1
            equity = bot.get("equity", 0)
            trades = bot.get("trades", 0)
            total_equity += equity
            total_trades += trades
            pairs.append({
                "symbol": bot_id,
                "equity": round(equity, 2),
                "trades": trades,
                "win_rate": 0,
                "strategy": "GRID",
                "regime": "range",
                "spread_pct": 0,
                "grid_levels": 5,
                "active_levels": bot.get("open_orders", 0),
            })
    
    price = 0
    if pairs:
        price = get_price_from_log()
    
    return {
        "pair": "fleet",
        "dry_run": False,
        "equity": round(total_equity, 2),
        "price": price,
        "pnl_pct": round(((total_equity - 100) / 100 * 100) if total_equity > 0 else 0, 2),
        "trades": total_trades,
        "wins": 0,
        "win_rate": 0,
        "active_bots": active_bots,
        "total_bots": len(bots),
        "pairs": pairs,
        "status": health.get("status", "unknown"),
        "ws_connected": False,
        "uptime_sec": 0,
    }

def parse_legacy_shadowgrid_health(health, machine_name):
    """Parse legacy shadowgrid_fleet.py health response."""
    if not health:
        return {
            "pair": "fleet",
            "dry_run": False,
            "error": f"{machine_name} fleet unreachable",
            "equity": 0,
            "status": "unreachable"
        }
    
    bots = health.get("bots", {})
    total_equity = 0
    total_trades = 0
    active_bots = 0
    pairs = []
    
    for bot_id, bot in bots.items():
        if bot.get("state") == "running" or bot.get("status") == "running":
            active_bots += 1
            # Legacy format has capital but not equity - use capital as proxy
            equity = bot.get("capital", 0)
            trades = 0  # Not available in legacy format
            total_equity += equity
            total_trades += trades
            pairs.append({
                "symbol": bot.get("symbol", bot_id),
                "equity": round(equity, 2),
                "trades": trades,
                "win_rate": 0,
                "strategy": "GRID",
                "regime": "range",
                "spread_pct": 0,
                "grid_levels": 5,
                "active_levels": 0,
            })
    
    price = 0
    if pairs:
        price = get_price_from_log()
    
    # Use total_capital from risk if available
    if total_equity == 0:
        risk = health.get("risk", {})
        total_equity = risk.get("current_equity", risk.get("total_capital", 0))
    
    return {
        "pair": "fleet",
        "dry_run": False,
        "equity": round(total_equity, 2),
        "price": price,
        "pnl_pct": round(((total_equity - 100) / 100 * 100) if total_equity > 0 else 0, 2),
        "trades": total_trades,
        "wins": 0,
        "win_rate": 0,
        "active_bots": active_bots,
        "total_bots": len(bots),
        "pairs": pairs,
        "status": health.get("status", "healthy"),
        "ws_connected": False,
        "uptime_sec": 0,
    }

def parse_fleet_health(health, machine_name):
    """Parse fleet health response - auto-detect format."""
    # Alpha-omega format has 'fleet' key with 'bots' inside
    if "fleet" in health:
        return parse_alpha_omega_health(health, machine_name)
    # Legacy format has 'bots' at top level
    elif "bots" in health:
        return parse_legacy_shadowgrid_health(health, machine_name)
    else:
        return {
            "pair": "fleet",
            "dry_run": False,
            "error": f"{machine_name} unknown health format",
            "equity": 0,
            "status": "unknown"
        }

def get_price_from_log():
    """Extract last price from bot log using tail."""
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
    machine_data = {}
    
    for node in TRADING_NODES:
        health = fetch_health(node)
        data = parse_fleet_health(health, node["name"])
        machine_data[node["name"]] = data
    
    # Calculate totals
    real_equity_n = machine_data.get("nuvola", {}).get("equity", 0)
    real_equity_m = machine_data.get("marcodg1", {}).get("equity", 0)
    total_trades = machine_data.get("nuvola", {}).get("trades", 0) + machine_data.get("marcodg1", {}).get("trades", 0)
    
    stats = {
        "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_profit": round((real_equity_n - 100) + (real_equity_m - 100), 2),
        "total_trades": total_trades,
        "total_equity": round(real_equity_n + real_equity_m, 2),
        "nuvola": machine_data.get("nuvola", {}),
        "marcodg1": machine_data.get("marcodg1", {}),
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
    except PermissionError:
        pass
    except Exception as e:
        print(f"Warning: could not write /var/www/html/stats.json: {e}", file=sys.stderr)
    
    print(f"Dash updated: nuvola_eq={real_equity_n:.2f} marcodg1_eq={real_equity_m:.2f} tot_trades={total_trades} active_bots={machine_data.get('nuvola',{}).get('active_bots',0)}/{machine_data.get('nuvola',{}).get('total_bots',0)} + {machine_data.get('marcodg1',{}).get('active_bots',0)}/{machine_data.get('marcodg1',{}).get('total_bots',0)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

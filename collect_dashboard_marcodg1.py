#!/usr/bin/env python3
"""DENARO Dashboard Data Collector - MARCODG1 (v2 con Grid Bot)"""
import json, os, sys, time, subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/marco/denaro")
DASHBOARD_DIR = BASE_DIR / "dashboard" / "public"

def get_binance_balances():
    try:
        from dotenv import load_dotenv
        import hmac, hashlib, urllib.parse, requests
        load_dotenv(BASE_DIR / ".env")
        key = os.getenv("BINANCE_API_KEY", "")
        sec = os.getenv("BINANCE_API_SECRET", "")
        if not key or not sec:
            return {}
        ts = int(time.time() * 1000)
        q = urllib.parse.urlencode({"timestamp": ts})
        sig = hmac.new(sec.encode(), q.encode(), hashlib.sha256).hexdigest()
        r = requests.get("https://api1.binance.com/api/v3/account",
            params={"timestamp": ts, "signature": sig}, headers={"X-MBX-APIKEY": key}, timeout=10)
        if r.status_code != 200:
            return {}
        balances = {}
        for b in r.json().get("balances", []):
            free, locked = float(b["free"]), float(b["locked"])
            total = free + locked
            if total > 0:
                balances[b["asset"]] = {"free": free, "locked": locked, "total": total}
        return balances
    except:
        return {}

def get_eur_prices():
    try:
        import requests
        r = requests.get("https://api1.binance.com/api/v3/ticker/price", timeout=10)
        if r.status_code != 200:
            return {}
        prices = {}
        for t in r.json():
            sym = t["symbol"]
            if sym.endswith("EUR"):
                prices[sym.replace("EUR","")] = float(t["price"])
        try:
            r2 = requests.get("https://api1.binance.com/api/v3/ticker/price?symbol=EURUSDT", timeout=10)
            prices["EURUSDT"] = float(r2.json()["price"])
        except:
            prices["EURUSDT"] = 1.0
        return prices
    except:
        return {}

def compute_portfolio(balances, prices):
    total_eur = 0
    total_usdt = 0
    for asset, bal in balances.items():
        eur_rate = prices.get("EURUSDT", 1)
        if asset == "EUR":
            total_eur += bal["total"]
        elif asset == "USDT":
            total_usdt += bal["total"]
        elif asset in prices:
            total_eur += bal["total"] * prices[asset]
        elif f"{asset}/USDT" in prices:
            total_usdt += bal["total"] * prices[f"{asset}/USDT"]
    
    total = total_eur + (total_usdt / prices.get("EURUSDT", 1))
    return {
        "total": round(total, 2),
        "eur_free": round(balances.get("EUR", {}).get("free", 0), 2),
        "eur_locked": round(balances.get("EUR", {}).get("locked", 0), 2),
        "ada_free": round(balances.get("ADA", {}).get("free", 0), 4),
        "ada_locked": round(balances.get("ADA", {}).get("locked", 0), 4),
    }

def get_grid_state():
    """Read grid bot state from state file"""
    state_file = BASE_DIR / "grid_state.json"
    try:
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)
            # Check freshness
            age = int(time.time()) - state.get("file_mtime", int(state_file.stat().st_mtime))
            running = age < 600  # 10 min threshold
            return {
                "running": running,
                "price": state.get("price", 0),
                "orders": state.get("orders", 0),
                "age_sec": age
            }
    except:
        pass
    return {"running": False, "price": 0, "orders": 0, "age_sec": -1}

def get_system_info():
    info = {"hostname": "marcodg1", "uptime": "---", "load": "---", "memory": "---"}
    try:
        r = subprocess.run(["uptime", "-p"], capture_output=True, text=True, timeout=5)
        info["uptime"] = r.stdout.strip()
    except: pass
    try:
        with open("/proc/loadavg") as f:
            l = f.read().split()
            info["load"] = f"{l[0]} {l[1]} {l[2]}"
    except: pass
    try:
        r = subprocess.run(["free", "-h"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.split("\n"):
            if line.startswith("Mem:"):
                info["memory"] = line.split()[2] + " / " + line.split()[1]
    except: pass
    return info

def get_grid_active_orders():
    """Fetch actual active orders from Binance for grid reporting"""
    try:
        from dotenv import load_dotenv
        import hmac, hashlib, urllib.parse, requests
        load_dotenv(BASE_DIR / ".env")
        key = os.getenv("BINANCE_API_KEY", "")
        sec = os.getenv("BINANCE_API_SECRET", "")
        if not key or not sec:
            return []
        ts = int(time.time() * 1000)
        params = {"symbol": "ADAEUR", "timestamp": ts}
        qs = urllib.parse.urlencode(sorted(params.items()))
        sig = hmac.new(sec.encode(), qs.encode(), hashlib.sha256).hexdigest()
        r = requests.get(f"https://api1.binance.com/api/v3/openOrders?{qs}&signature={sig}",
            headers={"X-MBX-APIKEY": key}, timeout=10)
        if r.status_code != 200:
            return []
        orders = []
        for o in r.json():
            if o["status"] == "NEW":
                orders.append({
                    "side": o["side"],
                    "qty": float(o["origQty"]),
                    "price": float(o["price"]),
                    "value": round(float(o["price"]) * float(o["origQty"]), 2)
                })
        return orders
    except:
        return []

def collect_all():
    now = datetime.utcnow()
    ts = now.strftime("%H:%M")
    balances = get_binance_balances()
    prices = get_eur_prices()
    portfolio = compute_portfolio(balances, prices)
    sys_info = get_system_info()
    grid = get_grid_state()
    grid_orders = get_grid_active_orders()
    
    live_prices = {}
    for sym in ["XRP", "SOL", "ADA", "DOGE", "ETH", "BNB"]:
        if sym in prices:
            live_prices[sym] = prices[sym]
    
    # Check if screen is running
    screen_active = False
    try:
        r = subprocess.run(["screen", "-list"], capture_output=True, text=True, timeout=5)
        screen_active = "marcobots" in r.stdout
    except:
        pass
    
    return {
        "ts": ts,
        "portfolio": portfolio,
        "system": sys_info,
        "live_prices": live_prices,
        "server": "marcodg1",
        "spr": portfolio.get("total", 0),
        "grid": {
            "symbol": "ADAEUR",
            "running": screen_active and grid["running"],
            "price": grid["price"],
            "orders": len(grid_orders) if grid_orders else grid["orders"],
            "order_details": grid_orders,
            "age_sec": grid["age_sec"]
        }
    }

if __name__ == "__main__":
    data = collect_all()
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(DASHBOARD_DIR / "marcodg1.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    cap = data.get("spr", 0)
    grid_status = "🟢" if data.get("grid", {}).get("running") else "🔴"
    grid_orders = data.get("grid", {}).get("orders", 0)
    print(f"MARCODG1 dashboard data written | Capital: {cap}€ | Grid: {grid_status} ({grid_orders} ordini)")

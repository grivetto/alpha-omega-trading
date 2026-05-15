#!/usr/bin/env python3
"""DENARO Dashboard Data Collector - NUVOLA"""
import json, os, re, subprocess
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = BASE_DIR / "dashboard" / "public"

def parse_grid_log():
    log_file = BASE_DIR / "grid.log"
    result = {"running": False, "price": 0, "invested": 0, "profit": 0,
              "buy_orders": 0, "sell_orders": 0, "last_update": None}
    if not os.path.exists(log_file):
        try:
            r = subprocess.run(["systemctl", "is-active", "denaro-grid.service"],
                capture_output=True, text=True, timeout=5)
            result["running"] = r.stdout.strip() == "active"
        except: pass
        return result
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        lines = lines[-5000:]
        result["running"] = True
        for line in lines:
            line = line.strip()
            m = re.search(r"Price:\s+([\d.]+)€\s+\|\s+Invested:\s+([\d.]+)€\s+\|\s+Profit:\s+([-\d.]+)€", line)
            if m:
                result["price"] = float(m.group(1))
                result["invested"] = float(m.group(2))
                result["profit"] = float(m.group(3))
                tm = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
                if tm: result["last_update"] = tm.group(1)
            m = re.search(r"Sync complete:\s+(\d+)\s+buy\s+/\s+(\d+)\s+sell", line)
            if m:
                result["buy_orders"] = int(m.group(1))
                result["sell_orders"] = int(m.group(2))
    except: pass
    return result

def get_system_info():
    info = {"hostname": "nuvola", "uptime": "---", "load": "---", "memory": "---"}
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

if __name__ == "__main__":
    now = datetime.utcnow()
    ts = now.strftime("%H:%M")
    grid = parse_grid_log()
    sys_info = get_system_info()
    data = {"ts": ts, "grid": grid, "system": sys_info, "portfolio": None}
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(DASHBOARD_DIR / "nuvola.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"NUVOLA dashboard data written to {DASHBOARD_DIR / 'nuvola.json'}")

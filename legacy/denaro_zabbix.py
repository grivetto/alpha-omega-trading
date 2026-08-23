#!/usr/bin/env python3
"""
Zabbix UserParameter provider per Denaro v4.
Legge da denaro_core_state.json + health endpoint.
Non ha dipendenze extra (solo stdlib).
"""
import json, os, sys, time
from pathlib import Path

STATE = Path(__file__).resolve().parent / "denaro_core_state.json"

def load():
    try:
        return json.loads(STATE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

s = load()
cmd = sys.argv[1] if len(sys.argv) > 1 else "status"

if cmd == "running":
    try:
        import subprocess
        r = subprocess.run(["pidof", "python3"], capture_output=True, text=True, timeout=5)
        count = 0
        for pid in r.stdout.strip().split():
            try:
                cmdline = Path(f"/proc/{pid}/cmdline").read_text()
                if "denaro" in cmdline and "main" in cmdline:
                    count += 1
            except:
                pass
        print(count)
    except:
        print(0)

elif cmd == "health":
    try:
        import urllib.request
        r = urllib.request.urlopen("http://127.0.0.1:8909/health", timeout=3)
        print(json.loads(r.read()).get("status", "down"))
    except:
        print("down")

elif cmd == "status":
    pnl = ((s.get("current_capital", 100) - s.get("initial_capital", 100)) 
           / max(1, s.get("initial_capital", 100)) * 100)
    trades = s.get("perf", {}).get("total_trades", 0)
    grid = len(s.get("grid_levels", []))
    cb = s.get("cb", {}).get("state", "UNKNOWN")
    trend = s.get("regime", {}).get("trend", "N/A")
    strat = s.get("exec", {}).get("active_strategy", "N/A")
    print(f"PnL={pnl:+.2f}% trades={trades} grid={grid} CB={cb} {trend} {strat}")

elif cmd == "grid":
    print(len(s.get("grid_levels", [])))

elif cmd == "trades":
    print(s.get("perf", {}).get("total_trades", 0))

elif cmd == "pnl":
    pnl = ((s.get("current_capital", 100) - s.get("initial_capital", 100))
           / max(1, s.get("initial_capital", 100)) * 100)
    print(f"{pnl:+.4f}")

elif cmd == "equity":
    print(f"{s.get('current_capital', 100):.2f}")

elif cmd == "kelly":
    k = s.get("kelly_fraction", 0.25)
    sm = s.get("sizing_multiplier", 1.0)
    print(f"{k * sm * 100:.1f}")

elif cmd == "atr":
    print(f"{s.get('regime', {}).get('atr_pct', 0) * 100:.2f}")

elif cmd == "trend":
    print(s.get("regime", {}).get("trend", "RANGING"))

elif cmd == "cb":
    print(s.get("cb", {}).get("state", "CLOSED"))

elif cmd == "load":
    try:
        l1, l5, l15 = os.getloadavg()
        print(f"{l1:.2f}")
    except:
        print(0)

elif cmd == "mem":
    try:
        with open("/proc/meminfo") as f:
            total = avail = 1
            for line in f:
                if line.startswith("MemTotal:"): total = int(line.split()[1])
                elif line.startswith("MemAvailable:"): avail = int(line.split()[1])
        print(f"{(total-avail)/total*100:.1f}")
    except:
        print(0)

elif cmd == "disk":
    try:
        st = os.statvfs("/")
        print(f"{(1-st.f_bavail/st.f_blocks)*100:.1f}")
    except:
        print(0)

else:
    print(f"unknown: {cmd}")

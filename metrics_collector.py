#!/usr/bin/env python3
"""Denaro metrics collector - writes JSON for dashboard, runs every 30s"""
import json, subprocess, os, time
BASE = "/home/sergio/denaro/dashboard/public"
os.makedirs(BASE, exist_ok=True)

def ssh(host, cmd, timeout=10):
    try:
        if host in ("nuvola", "127.0.0.1", "localhost"):
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip()
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=5", host, cmd], capture_output=True, text=True, timeout=timeout)
        return r.stdout.strip()
    except: return ""

def gval(out, marker, default="0"):
    for line in out.split("\n"):
        if marker in line:
            return line.split(marker)[1].strip().split()[0] if marker in line else default
    return default

# NUVOLA
n = ssh("nuvola", "echo BOT=$(pgrep -c -f grid_bot_v3.py 2>/dev/null); echo WDG=$(pgrep -c -f watchdog.sh 2>/dev/null); echo INV=$(grep -oP 'Invested: \\K[0-9.]+' /home/sergio/denaro/grid.log 2>/dev/null | tail -1); echo PRF=$(grep -oP 'Profit: \\K[0-9.]+' /home/sergio/denaro/grid.log 2>/dev/null | tail -1); echo PRI=$(grep -oP 'Price: \\K[0-9.]+' /home/sergio/denaro/grid.log 2>/dev/null | tail -1); echo TREND=$(grep -oP 'Trend: \\K[A-Z_]+' /home/sergio/denaro/grid.log 2>/dev/null | tail -1); echo RSI=$(grep -oP 'RSI: \\K[0-9.]+' /home/sergio/denaro/grid.log 2>/dev/null | tail -1); echo TRADES=$(grep -c 'SELL filled' /home/sergio/denaro/grid.log 2>/dev/null); echo ACTIVE=$(zabbix_agentd -t denaro.service.active 2>/dev/null | grep -o 'active\\|inactive'); echo DISK=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%'); echo MEM=$(free -m | grep Mem | awk '{printf \"%.0f\", $3/$2*100}')")

nuvola = {
    "ts": time.strftime("%H:%M"), "b": int(gval(n,"BOT=","0")), "w": int(gval(n,"WDG=","0")),
    "i": float(gval(n,"INV=","0")), "p": float(gval(n,"PRF=","0")),
    "pr": float(gval(n,"PRI=","0")), "t": gval(n,"TREND=","?"),
    "r": float(gval(n,"RSI=","0")), "tr": int(gval(n,"TRADES=","0")),
    "a": gval(n,"ACTIVE=","?"), "d": int(gval(n,"DISK=","0") or "0"),
    "m": int(gval(n,"MEM=","0") or "0"), "v4": 1
}
json.dump(nuvola, open(f"{BASE}/nuvola.json","w"))

# MARCODG1
m = ssh("MARCODG1", "echo BOT=$(pgrep -c -f grid_bot_v3.py 2>/dev/null); echo WDG=$(pgrep -c -f watchdog.sh 2>/dev/null); echo INV=$(grep -oP 'Invested: \\K[0-9.]+' /home/marco/denaro/grid.log 2>/dev/null | tail -1); echo PRF=$(grep -oP 'Profit: \\K[0-9.]+' /home/marco/denaro/grid.log 2>/dev/null | tail -1); echo PRI=$(grep -oP 'Price: \\K[0-9.]+' /home/marco/denaro/grid.log 2>/dev/null | tail -1); echo TREND=$(grep -oP 'Trend: \\K[A-Z_]+' /home/marco/denaro/grid.log 2>/dev/null | tail -1); echo TRADES=$(grep -c 'SELL filled' /home/marco/denaro/grid.log 2>/dev/null); echo ACTIVE=$(zabbix_agentd -t denaro.service.active 2>/dev/null | grep -o 'active\\|inactive'); echo DISK=$(df -h / | tail -1 | awk '{print $5}' | tr -d '%'); echo MEM=$(free -m | grep Mem | awk '{printf \"%.0f\", $3/$2*100}')")

marcodg1 = {
    "ts": time.strftime("%H:%M"), "b": int(gval(m,"BOT=","0")), "w": int(gval(m,"WDG=","0")),
    "i": float(gval(m,"INV=","0")), "p": float(gval(m,"PRF=","0")),
    "pr": float(gval(m,"PRI=","0")), "t": gval(m,"TREND=","?"),
    "tr": int(gval(m,"TRADES=","0")), "a": gval(m,"ACTIVE=","?"),
    "d": int(gval(m,"DISK=","0") or "0"), "m": int(gval(m,"MEM=","0") or "0"), "v4": 1
}
json.dump(marcodg1, open(f"{BASE}/marcodg1.json","w"))

# MC2 + Scalper
log = "/home/sergio/denaro/scalper.log"
scp = 0; spp = 0; sppr = 0; sr = 0; sb = 0; se = 0; sdisk = 0; smem = 0
if os.path.exists(log):
    scp = int(subprocess.run(["pgrep","-c","-f","scalper_v2.py"], capture_output=True,text=True).stdout.strip() or "0")
    txt = open(log).read()
    for l in txt.split("\n")[-50:]:
        if "PnL:" in l:
            try: spp = float(l.split("PnL:")[1].strip().split("€")[0])
            except: pass
        if "ETH/EUR @" in l:
            try: sppr = float(l.split("@")[1].strip().split("€")[0])
            except: pass
        if "RSI=" in l:
            try: sr = float(l.split("RSI=")[1].split("|")[0].strip())
            except: pass
    sdisk = 0  # MC2 data not available from remote
    smem = 0
else:
    sdisk = int(subprocess.run(["df","-h","/"], capture_output=True,text=True).stdout.split("\n")[1].split()[4].strip("%"))
    smem = round(float(subprocess.run(["free","-m"], capture_output=True,text=True).stdout.split("\n")[1].split()[2]) / float(subprocess.run(["free","-m"], capture_output=True,text=True).stdout.split("\n")[1].split()[1]) * 100)

# Read cumulative profit from trade_db or profit optimizer trades
total_profit = 0.0
try:
    from trade_db import TradeDB
    db = TradeDB()
    total_profit = db.get_daily_pnl()  # or get_total_pnl if we add it
except Exception as e:
    # Fallback to profit optimizer trades file
    profit_file = "/home/sergio/denaro/.tmp/profit_optimizer_trades.json"
    if os.path.exists(profit_file):
        try:
            with open(profit_file, "r") as f:
                trades = json.load(f)
            total_profit = sum(t["profit"] for t in trades)
        except:
            pass

mc2 = {
    "ts": time.strftime("%H:%M"), "sc": scp, "sp": round(spp,2),
    "spr": sppr, "sr": round(sr,1), "sb": int(subprocess.run(["grep","-c","BUY|SELL",log], capture_output=True,text=True).stdout.strip() or "0") if os.path.exists(log) else 0,
    "se": float(subprocess.run(["grep","-oP","EUR=\\K[0-9.]+",log], capture_output=True,text=True).stdout.strip().split("\n")[-1] or "0") if os.path.exists(log) else 0,
    "d": sdisk, "m": smem, "z": 1 if scp > 0 else 0,
    "profit": round(total_profit, 2)  # Cumulative profit instead of last PnL
}
json.dump(mc2, open(f"{BASE}/mc2.json","w"))

print(f"OK {nuvola['ts']} N={nuvola['i']}€ M={marcodg1['i']}€ S={mc2['sp']}€")

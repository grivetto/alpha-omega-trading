#!/usr/bin/env python3
"""DENARO Dashboard Data Collector - NUVOLA (v4: screen + log fallback)"""
import json, os, re, subprocess, time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = BASE_DIR / "dashboard" / "public"
LOG_FILE = BASE_DIR / "grid_bot_v3.log"

def parse_price_line(line):
    """Parse a price line: Price: X | Risk: Y | Invested: Z | Profit: W | Trend: T"""
    m = re.search(r"Price:\s+([\d.]+).*?Invested:\s+([\d.]+).*?Profit:\s+([-\d.]+)", line)
    if not m:
        return None
    result = {
        "price": round(float(m.group(1)), 2),
        "invested": round(float(m.group(2)), 2),
        "profit": round(float(m.group(3)), 2),
    }
    tm = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
    if tm:
        result["last_update"] = tm.group(1)
    m2 = re.search(r"Trend:\s+(STRONG_UP|UP|NEUTRAL|DOWN|STRONG_DOWN)", line)
    if m2:
        result["trend"] = m2.group(1)
    return result

def parse_sync_line(line):
    """Parse sync line: Sync complete: X buy, Y sell"""
    m = re.search(r"Sync complete:\s+(\d+)\s+buy.*?(\d+)\s+sell", line)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None

def get_grid_from_log():
    """Parse grid_bot_v3.log for recent data"""
    result = {}
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        # Check freshness
        mtime = LOG_FILE.stat().st_mtime
        age = time.time() - mtime
        result["log_age_min"] = round(age / 60, 1)
        
        for line in reversed(lines):
            line = line.strip()
            p = parse_price_line(line)
            if p and "price" not in result:
                result.update(p)
            s = parse_sync_line(line)
            if s:
                result["buy_orders"] = s[0]
                result["sell_orders"] = s[1]
            if "price" in result and "trend" in result:
                break
    except:
        pass
    return result

def get_grid_from_screen():
    """Extract grid state from screen hardcopy (real-time, handles encoding issues)"""
    result = {"running": False}
    try:
        subprocess.run(["screen", "-S", "grid_bot", "-X", "hardcopy", "/tmp/sc_grid.txt"],
            capture_output=True, timeout=5)
        time.sleep(0.15)
        hp = Path("/tmp/sc_grid.txt")
        if not (hp.exists() and hp.stat().st_size > 50):
            return result
        
        # Read as binary, decode with replace
        with open(hp, "rb") as f:
            raw = f.read()
        text = raw.decode("utf-8", errors="replace")
        result["running"] = True
        
        # Join wrapped lines
        raw_lines = text.split("\n")
        lines = []
        buf = ""
        for ln in raw_lines:
            if ln and not re.match(r"^\d{4}-\d{2}-\d{2}", ln):
                buf += ln.strip()
            else:
                if buf:
                    lines.append(buf)
                buf = ln
        if buf:
            lines.append(buf)
        
        # Parse newest first
        for line in reversed(lines):
            line = line.strip()
            p = parse_price_line(line)
            if p and "price" not in result:
                result.update(p)
            s = parse_sync_line(line)
            if s:
                result["buy_orders"] = s[0]
                result["sell_orders"] = s[1]
            if "price" in result and "trend" in result:
                break
    except:
        pass
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
                parts = line.split()
                info["memory"] = f"{parts[2]} / {parts[1]}"
    except: pass
    return info

if __name__ == "__main__":
    now = datetime.now(timezone.utc)
    ts = now.strftime("%H:%M")
    
    # Try screen first (real-time), fall back to log
    grid = get_grid_from_screen()
    if grid.get("price", 0) == 0:
        log_data = get_grid_from_log()
        if log_data:
            grid.update(log_data)
            if "log_age_min" in log_data:
                grid["data_source"] = f"log ({log_data['log_age_min']}m old)"
        else:
            grid["data_source"] = "no data"
    else:
        grid["data_source"] = "screen (live)"
    
    sys_info = get_system_info()
    data = {"ts": ts, "grid": grid, "system": sys_info, "portfolio": None}
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(DASHBOARD_DIR / "nuvola.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    
    gs = "🟢" if grid.get("running") else "🔴"
    print(f"NUVOLA data | Grid:{gs} Price:{grid.get('price',0)} Inv:{grid.get('invested',0)} "
          f"Trend:{grid.get('trend','?')} Source:{grid.get('data_source','?')}")

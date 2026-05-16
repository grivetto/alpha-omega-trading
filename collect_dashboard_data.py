#!/usr/bin/env python3
"""DENARO Dashboard Data Collector - MC2"""
import json, os, sys, time, re, subprocess, glob
from datetime import datetime
from pathlib import Path

BASE_DIR = Path("/home/sergio/denaro")
DASHBOARD_DIR = BASE_DIR / "dashboard" / "public"

SQUADRA_LOG = BASE_DIR / "squadra" / "squadra.log"

def parse_squadra_log():
    """Parse squadra log for bot states"""
    bots = {"Ares": {"symbol":"ETH/EUR","in_position":False,"signal":"HOLD"},
            "Hermes": {"symbol":"SOL/EUR","in_position":False,"signal":"HOLD"},
            "Apollo": {"symbol":"ETH/BTC","in_position":False,"ratio":0,"history":0}}
    if not SQUADRA_LOG.exists():
        return bots
    try:
        with open(SQUADRA_LOG) as f:
            lines = f.readlines()
        lines = lines[-200:]
        for line in reversed(lines):
            line = line.strip()
            m = re.search(r"Ares \| (\S+) @ ([\d.]+) \| Signal: (\S+) \| Pos: (\S+)", line)
            if m:
                bots["Ares"] = {"symbol":m.group(1),"price":float(m.group(2)),
                                "signal":m.group(3),"in_position":m.group(4)=="True"}
            m = re.search(r"Hermes \| (\S+) @ ([\d.]+).*?Signal: (\S+) \| Pos: (\S+)", line)
            if m:
                bots["Hermes"] = {"symbol":m.group(1),"price":float(m.group(2)),
                                  "signal":m.group(3),"in_position":m.group(4)=="True"}
            m = re.search(r"Apollo \| Ratio: ([\d.]+) \| Building history \((\d+)/", line)
            if m:
                bots["Apollo"]["ratio"] = float(m.group(1))
                bots["Apollo"]["history"] = int(m.group(2))
    except:
        pass
    return bots

def get_squadra_status():
    """Extract Squadra Opportunistica status from SQLite + log"""
    result = {"running":False,"bots":{},"positions":0,"exposure":0.0,"profit":0.0,
              "uptime":"---","last_trade":None,"win_rate":0,"budget":80}
    # Parse log for bot states
    result["bots"] = parse_squadra_log()
    # Count positions
    for b in result["bots"].values():
        if b.get("in_position"):
            result["positions"] += 1
    # Trades DB (shared with squadra)
    db_path = BASE_DIR / "trades.db"
    if db_path.exists():
        try:
            import sqlite3
            conn = sqlite3.connect(str(db_path))
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(net_pnl),0) as pnl FROM trades")
            row = c.fetchone()
            result["profit"] = round(row["pnl"], 2)
            c.execute("""SELECT COALESCE(SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END),0) as wins,
                COUNT(*) as total FROM trades""")
            row = c.fetchone()
            result["win_rate"] = round(row["wins"]/max(row["total"],1)*100, 1)
            c.execute("""SELECT entry_price, exit_price,
                ROUND((exit_price-entry_price)/entry_price*100,2) as pnl_pct, net_pnl
                FROM trades ORDER BY exit_time DESC LIMIT 1""")
            row = c.fetchone()
            if row and row["exit_price"]:
                result["last_trade"] = {"exit_price":row["exit_price"],
                    "pnl_pct":row["pnl_pct"],"net_eur":round(row["net_pnl"],2)}
            c.execute("""SELECT COALESCE(SUM(quantity*entry_price),0) as expo
                FROM bot_state WHERE is_in_position=1""")
            result["exposure"] = round(c.fetchone()["expo"], 2)
            c.execute("SELECT MAX(last_heartbeat) as hb FROM bot_state")
            row = c.fetchone()
            if row and row["hb"]:
                result["running"] = (time.time()-float(row["hb"])) < 300
            c.execute("""SELECT MIN(entry_time) as fe FROM bot_state WHERE entry_time>0""")
            row = c.fetchone()
            if row and row["fe"]:
                secs = time.time()-float(row["fe"])
                result["uptime"] = f"{int(secs//3600)}:{int((secs%3600)//60):02d}"
            conn.close()
        except: pass
    return result

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
            elif sym.endswith("USDT"):
                prices[f"{sym.replace('USDT','')}/USDT"] = float(t["price"])
        try:
            r2 = requests.get("https://api1.binance.com/api/v3/ticker/price?symbol=EURUSDT", timeout=10)
            if r2.status_code == 200:
                prices["EUR/USDT"] = float(r2.json()["price"])
        except:
            prices["EUR/USDT"] = 1.0
        return prices
    except:
        return {}

def compute_portfolio(balances, prices):
    eur_usdt = prices.get("EUR/USDT", 1.0)
    total_eur = 0.0
    assets = []
    for asset, bal in balances.items():
        qty = bal["total"]
        if asset == "EUR":
            price_eur = 1.0
        elif asset in prices:
            price_eur = prices[asset]
        elif f"{asset}/USDT" in prices:
            price_eur = prices[f"{asset}/USDT"] / eur_usdt
        else:
            price_eur = 0
        value_eur = qty * price_eur
        total_eur += value_eur
        if value_eur > 0.01:
            assets.append({"asset": asset, "qty": round(qty, 6), "value_eur": round(value_eur, 2)})
    assets.sort(key=lambda x: x["value_eur"], reverse=True)
    return {"total": round(total_eur, 2), "assets": assets}

def parse_scalper_log(log_file, symbol):
    result = {"symbol": symbol, "running": False, "last_signal": None, "last_signal_time": None,
              "last_trade": None, "last_trade_time": None, "last_trade_side": None,
              "last_trade_price": None, "last_trade_qty": None, "trades": 0, "signals": 0,
              "pnl_total": 0.0, "wins": 0, "losses": 0, "open_pos": None}
    if not os.path.exists(log_file):
        return result
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        lines = lines[-5000:]
        result["running"] = True
        for line in lines:
            line = line.strip()
            m = re.search(r"(BUY|SELL|Soft SELL|Soft BUY).*?([\d.]+)€.*?([\d.]+)\s*(\w+)", line)
            if m:
                result["trades"] += 1
                result["last_trade"] = m.group(1)
                result["last_trade_side"] = m.group(1)
                result["last_trade_price"] = float(m.group(2))
                result["last_trade_qty"] = m.group(3) + " " + m.group(4)
                tm = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
                if tm:
                    result["last_trade_time"] = tm.group(1)
            m = re.search(r"PnL[:\s]+([-\d.]+)€", line)
            if m:
                result["pnl_total"] += float(m.group(1))
            m = re.search(r"(WIN|LOSS|PROFIT|LOSS)", line)
            if m:
                if m.group(1) in ("WIN", "PROFIT"):
                    result["wins"] += 1
                else:
                    result["losses"] += 1
            m = re.search(r"(LONG|SHORT|SELL|BUY)\s+signal", line, re.IGNORECASE)
            if m:
                result["signals"] += 1
                result["last_signal"] = m.group(1)
                tm = re.search(r"(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})", line)
                if tm:
                    result["last_signal_time"] = tm.group(1)
        result["pnl_total"] = round(result["pnl_total"], 2)
    except:
        pass
    return result

def parse_orchestrator_log():
    log_file = BASE_DIR / "orchestrator.log"
    result = {"capital": 0, "eur_free": 0, "sol_value": 0, "sol_qty": 0, "max_trade": 0}
    if not os.path.exists(log_file):
        return result
    try:
        with open(log_file, "r") as f:
            lines = f.readlines()
        lines = lines[-5000:]
        for line in lines:
            line = line.strip()
            m = re.search(r"Capital:\s+([\d.]+)€", line)
            if m: result["capital"] = float(m.group(1))
            m = re.search(r"Pool:\s+([\d.]+)€\s+EUR free", line)
            if m: result["eur_free"] = float(m.group(1))
            m = re.search(r"SOL=([\d.]+)€\s+\(([\d.]+)\s+SOL\)", line)
            if m:
                result["sol_value"] = float(m.group(1))
                result["sol_qty"] = float(m.group(2))
            m = re.search(r"max_trade=([\d.]+)€", line)
            if m: result["max_trade"] = float(m.group(1))
    except:
        pass
    return result

def get_system_info():
    info = {"hostname": "mc2", "uptime": "---", "load": "---", "memory": "---"}
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

def get_legacy_bots_status():
    bots = []
    now = time.time()
    for log_file in glob.glob(str(BASE_DIR / "*.log")):
        mtime = os.path.getmtime(log_file)
        size = os.path.getsize(log_file)
        name = os.path.basename(log_file).replace(".log", "")
        last_line = "empty"
        try:
            with open(log_file, "r") as f:
                f.seek(max(0, size - 2000))
                last_lines = f.read()
            last_line = last_lines.strip().split("\n")[-1][:200] if last_lines else "empty"
        except: pass
        bots.append({"name": name, "last_line": last_line,
                     "age_min": round((now - mtime) / 60, 1),
                     "size_kb": round(size / 1024, 1),
                     "active": (now - mtime) < 300})
    bots.sort(key=lambda x: x["size_kb"], reverse=True)
    return bots

def get_legion_status():
    """Extract Legion Manager PROD status from SQLite only"""
    result = {"running": False, "positions": 0, "max_positions": 12, "exposure": 0.0,
              "win_rate": 0.0, "profit": 0.0, "blocked": 0, "boost": 1.0,
              "uptime": "---", "last_trade": None, "trades_total": 0, "symbols_active": 0}
    db_path = BASE_DIR / "trades.db"
    if not db_path.exists():
        return result
    try:
        import sqlite3
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        c = conn.cursor()

        # Total trades & P&L
        c.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(net_pnl),0) as pnl FROM trades")
        row = c.fetchone()
        result["trades_total"] = row["cnt"]
        result["profit"] = round(row["pnl"], 2)

        # Win rate
        c.execute("""SELECT 
            COALESCE(SUM(CASE WHEN net_pnl > 0 THEN 1 ELSE 0 END),0) as wins,
            COUNT(*) as total
            FROM trades""")
        row = c.fetchone()
        wins, total_trades = row["wins"], row["total"]
        result["win_rate"] = round(wins / max(total_trades, 1) * 100, 1)

        # Last trade
        c.execute("""SELECT exit_price, 
            ROUND((exit_price - entry_price) / entry_price * 100, 2) as pnl_pct,
            net_pnl
            FROM trades ORDER BY exit_time DESC LIMIT 1""")
        row = c.fetchone()
        if row and row["exit_price"]:
            result["last_trade"] = {
                "exit_price": row["exit_price"],
                "pnl_pct": row["pnl_pct"],
                "net_eur": round(row["net_pnl"], 2)
            }

        # Open positions from bot_state
        c.execute("""SELECT COUNT(*) as cnt,
            COALESCE(SUM(quantity * entry_price), 0) as total_exposure
            FROM bot_state WHERE is_in_position=1""")
        row = c.fetchone()
        result["positions"] = row["cnt"]
        result["symbols_active"] = row["cnt"]
        result["exposure"] = round(row["total_exposure"], 2)

        # Running check: any bot with heartbeat < 5 min
        c.execute("""SELECT MAX(last_heartbeat) as hb FROM bot_state""")
        row = c.fetchone()
        if row and row["hb"]:
            try:
                hb_time = float(row["hb"])
                result["running"] = (time.time() - hb_time) < 300  # 5 min
            except:
                pass

        # Uptime: from oldest entry_time of any bot
        c.execute("""SELECT MIN(entry_time) as first_entry FROM bot_state WHERE entry_time > 0""")
        row = c.fetchone()
        if row and row["first_entry"]:
            try:
                fe = float(row["first_entry"])
                uptime_secs = time.time() - fe
                hours = int(uptime_secs // 3600)
                mins = int((uptime_secs % 3600) // 60)
                result["uptime"] = f"{hours}:{mins:02d}"
            except:
                pass

        # Blocked symbols (auto_disabled table)
        try:
            c.execute("SELECT COUNT(*) as cnt FROM auto_disabled")
            result["blocked"] = c.fetchone()["cnt"]
        except:
            pass

        conn.close()
    except Exception as e:
        print(f"Legion status error: {e}", file=sys.stderr)
    return result

def collect_all():
    now = datetime.utcnow()
    ts = now.strftime("%H:%M")
    balances = get_binance_balances()
    prices = get_eur_prices()
    portfolio = compute_portfolio(balances, prices)
    sys_info = get_system_info()
    squadra = get_squadra_status()
    live_prices = {}
    for sym in ["XRP", "SOL", "ADA", "DOGE", "ETH", "BNB", "BTC"]:
        if sym in prices:
            live_prices[sym] = prices[sym]
    return {
        "ts": ts,
        "spr": portfolio.get("total", 0),
        "portfolio": portfolio,
        "system": sys_info,
        "squadra": squadra,
        "live_prices": live_prices,
    }

if __name__ == "__main__":
    data = collect_all()
    os.makedirs(DASHBOARD_DIR, exist_ok=True)
    with open(DASHBOARD_DIR / "mc2.json", "w") as f:
        json.dump(data, f, ensure_ascii=False)
    print(f"Dashboard data written to {DASHBOARD_DIR / 'mc2.json'}")
    sq = data.get('squadra', {})
    print(f"Capital: {data.get('spr', 0)}€ | Squadra: {sq.get('positions',0)} pos | "
          f"Profit: {sq.get('profit',0)}€ | Running: {sq.get('running',False)}")

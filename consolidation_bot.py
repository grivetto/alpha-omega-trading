#!/usr/bin/env python3
"""DENARO CONSOLIDATION BOT v2 — SOL/USDC, REST engine, KillSwitch."""

import json, os, sys, time, sqlite3, hashlib, hmac, requests
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
ENV_PATH = BASE / '.env'

def load_env():
    env = {}
    if ENV_PATH.exists():
        with open(ENV_PATH) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    env[k.strip()] = v.strip()
    return env

# === ENGINE (REST, no ccxt sapi issues) ===
class Engine:
    def __init__(self, key, secret, symbol="SOL/USDC"):
        self.key, self.secret = key, secret
        self.symbol, self.sym = symbol, symbol.replace("/", "")
        self.base, self.quote = symbol.split("/")

    def _sign(self, qs):
        return hmac.new(self.secret.encode(), qs.encode(), hashlib.sha256).hexdigest()

    def _get(self, path, params=""):
        ts = int(time.time() * 1000)
        q = f"timestamp={ts}&recvWindow=30000"
        if params: q += "&" + params
        sig = self._sign(q)
        r = requests.get(f"https://api.binance.com{path}?{q}&signature={sig}",
                         headers={"X-MBX-APIKEY": self.key}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:200]}

    def _post(self, path, params=""):
        ts = int(time.time() * 1000)
        q = f"timestamp={ts}&recvWindow=30000"
        if params: q += "&" + params
        sig = self._sign(q)
        r = requests.post(f"https://api.binance.com{path}?{q}&signature={sig}",
                          headers={"X-MBX-APIKEY": self.key}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:200]}

    def price(self):
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={self.sym}", timeout=10)
        return float(r.json()["price"]) if r.status_code == 200 else 0

    def balance(self):
        b = self._get("/api/v3/account")
        if "balances" in b:
            return {x["asset"]: float(x["free"]) for x in b["balances"] if float(x["free"]) > 0}
        return {}

    def equity(self):
        b = self.balance()
        usdc = b.get(self.quote, 0)
        sol = b.get(self.base, 0)
        return usdc + sol * self.price() if sol else usdc

    def open_orders(self):
        o = self._get("/api/v3/openOrders", f"symbol={self.sym}")
        return o if isinstance(o, list) else []

    def cancel_all(self):
        for o in self.open_orders():
            self._post("/api/v3/order", f"symbol={self.sym}&orderId={o['orderId']}")

    def limit_buy(self, amount, price):
        return self._post("/api/v3/order",
            f"symbol={self.sym}&side=BUY&type=LIMIT&timeInForce=GTC&quantity={amount:.4f}&price={price:.2f}")

    def limit_sell(self, amount, price):
        return self._post("/api/v3/order",
            f"symbol={self.sym}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={amount:.4f}&price={price:.2f}")

    def ohlcv(self, interval="5m", limit=24):
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={self.sym}&interval={interval}&limit={limit}", timeout=10)
        return r.json() if r.status_code == 200 else []

# === DUCKDB (migrated from SQLite) ===
try:
    import duckdb
    DB_BACKEND = "duckdb"
    db_path = str(BASE / '.tmp' / 'denaro.duckdb')
    os.makedirs(BASE / '.tmp', exist_ok=True)
    conn = duckdb.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER, symbol TEXT, side TEXT, price REAL, amount REAL, value_usdc REAL, fee_usdc REAL, net_pnl REAL, strategy TEXT, regime TEXT, filled_at TIMESTAMP)")
    conn.execute("CREATE TABLE IF NOT EXISTS daily_pnl (day DATE PRIMARY KEY, pnl REAL DEFAULT 0, trades INTEGER DEFAULT 0, fees REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT, updated_at TIMESTAMP)")
except ImportError:
    DB_BACKEND = "sqlite"
    db_path = str(BASE / '.tmp' / 'denaro.db')
    os.makedirs(BASE / '.tmp' / 'denaro.db'.replace('/',''), exist_ok=True)
    os.makedirs(BASE / '.tmp', exist_ok=True)
    conn = sqlite3.connect(str(BASE / '.tmp' / 'denaro.db'), timeout=10, check_same_thread=False)
    conn.execute("CREATE TABLE IF NOT EXISTS trades (id INTEGER PRIMARY KEY AUTOINCREMENT, symbol TEXT, side TEXT, price REAL, amount REAL, value_usdc REAL, fee_usdc REAL, net_pnl REAL, strategy TEXT, regime TEXT, filled_at TEXT DEFAULT (datetime('now')))")
    conn.execute("CREATE TABLE IF NOT EXISTS daily_pnl (day TEXT PRIMARY KEY, pnl REAL DEFAULT 0, trades INTEGER DEFAULT 0, fees REAL DEFAULT 0)")
    conn.execute("CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT, updated_at REAL)")

def save_trade(side, price, amount, value_usdc, fee_usdc, net_pnl, strategy, regime=""):
    now = datetime.utcnow().isoformat()
    if DB_BACKEND == "duckdb":
        conn.execute("INSERT INTO trades VALUES (nextval('seq_trade_id'),?,?,?,?,?,?,?,?,?,?)",
                     ("SOL/USDC", side, price, amount, value_usdc, fee_usdc, net_pnl, strategy, regime, now))
    else:
        conn.execute("INSERT INTO trades (symbol,side,price,amount,value_usdc,fee_usdc,net_pnl,strategy,regime) VALUES (?,?,?,?,?,?,?,?,?)",
                     ("SOL/USDC", side, price, amount, value_usdc, fee_usdc, net_pnl, strategy, regime))
        conn.commit()

def update_daily(pnl, trades=1, fees=0):
    today = datetime.now().strftime('%Y-%m-%d')
    c = conn.execute if DB_BACKEND == "duckdb" else conn.execute
    if DB_BACKEND == "duckdb":
        conn.execute("INSERT OR REPLACE INTO daily_pnl VALUES (?, COALESCE((SELECT pnl FROM daily_pnl WHERE day=?),0)+?, COALESCE((SELECT trades FROM daily_pnl WHERE day=?),0)+?, COALESCE((SELECT fees FROM daily_pnl WHERE day=?),0)+?)",
                     (today, today, pnl, today, trades, today, fees))
    else:
        c("INSERT OR REPLACE INTO daily_pnl (day,pnl,trades,fees) VALUES (?,COALESCE((SELECT pnl FROM daily_pnl WHERE day=?),0)+?,COALESCE((SELECT trades FROM daily_pnl WHERE day=?),0)+?,COALESCE((SELECT fees FROM daily_pnl WHERE day=?),0)+?)",
          (today, today, pnl, today, trades, today, fees))
        conn.commit()

def get_daily():
    today = datetime.now().strftime('%Y-%m-%d')
    r = conn.execute(f"SELECT COALESCE(pnl,0), COALESCE(trades,0), COALESCE(fees,0) FROM daily_pnl WHERE day='{today}'" if DB_BACKEND == "duckdb" else "SELECT pnl, trades, fees FROM daily_pnl WHERE day=?", (today,) if DB_BACKEND != "duckdb" else None)
    if DB_BACKEND == "duckdb":
        row = r.fetchone()
    else:
        row = r.fetchone()
    return (0, 0, 0) if row is None else (row[0], row[1], row[2])

# === KILL-SWITCH ===
class KillSwitch:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.day_start_equity = 0.0
        self.halted = False

    def update(self, trade_pnl):
        self.daily_pnl += trade_pnl
        if trade_pnl < 0:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def reset_day(self, equity):
        self.day_start_equity = equity
        self.consecutive_losses = 0
        self.daily_pnl = 0
        self.halted = False

    def can_open(self, equity):
        if self.halted:
            return False
        loss_pct = abs(self.daily_pnl) / max(self.day_start_equity, 1) * 100
        if self.consecutive_losses >= 3:
            print(f"  🔴 KILL-SWITCH L1: {self.consecutive_losses} perdite consecutive")
            return False
        if loss_pct > 3.0:
            print(f"  🔴 KILL-SWITCH L2: daily loss {loss_pct:.1f}% > 3%")
            return False
        if loss_pct > 5.0:
            print(f"  🔴 KILL-SWITCH L3: daily loss {loss_pct:.1f}% > 5% LIQUIDATE")
            self.halted = True
            return False
        return True

# === MAIN LOOP ===
def main():
    env = load_env()
    key = env.get("BINANCE_API_KEY", "")
    sec = env.get("BINANCE_API_SECRET", "")
    if not key:
        print("❌ API key missing")
        sys.exit(1)

    eng = Engine(key, sec, "SOL/USDC")
    ks = KillSwitch()
    capital = float(env.get("TOTAL_CAPITAL_USDC", 50))
    spacing = float(env.get("GRID_SPACING_PCT", 0.012))
    levels = int(env.get("GRID_LEVELS", 4))
    min_order = float(env.get("MIN_ORDER_USDC", 5.1))

    print("=" * 56)
    print("DENARO CONSOLIDATION BOT v2 — SOL/USDC")
    print(f"  Capital: ${capital:.0f}  Grid: {levels} livelli  Spacing: {spacing*100:.1f}%")
    print(f"  DB: {DB_BACKEND}  Kill-Switch: 4 livelli")
    print("=" * 56)

    ks.reset_day(eng.equity())
    placed_grid = False

    while True:
        try:
            p = eng.price()
            if p <= 0:
                time.sleep(5)
                continue

            orders = eng.open_orders()
            eq = eng.equity()

            if not ks.can_open(eq):
                time.sleep(60)
                continue

            # === REGIME DETECTION ===
            klines = eng.ohlcv("5m", 48)
            regime = "ranging"
            if len(klines) >= 12:
                closes = [float(k[4]) for k in klines]
                highs = [float(k[2]) for k in klines]
                lows = [float(k[3]) for k in klines]
                vols = [float(k[5]) for k in klines]
                trs = [max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1])) for i in range(1, len(klines))]
                atr = sum(trs[-12:]) / 12
                vol_pct = atr / p * 100 if p else 0
                recent_vol = sum(vols[-6:]) / 6
                avg_vol = sum(vols[:-6]) / max(len(vols)-6, 1)
                if vol_pct > 2.5:
                    regime = "volatile"
                elif vol_pct < 0.3:
                    regime = "quiet"
                elif recent_vol > avg_vol * 2:
                    regime = "volatile"

            # === ADAPT GRID SPACING ===
            cfg_levels = {"volatile": min(levels-1, 3), "quiet": min(levels+1, 6), "ranging": levels}
            n = cfg_levels.get(regime, levels)
            cap_per_level = (capital * 0.85) / n
            if cap_per_level < min_order:
                n = max(1, int((capital * 0.85) / min_order))
                cap_per_level = (capital * 0.85) / n

            if len(orders) == 0 and not placed_grid:
                # Build grid
                print(f"\n  📊 Building grid: {n} levels, regime={regime}, price=${p:.2f}")
                for i in range(1, n + 1):
                    bp = round(p * (1 - spacing * i / n), 2)
                    sp = round(bp * (1 + spacing * 1.5), 2)
                    amt = round(cap_per_level / bp, 4)
                    if amt * bp < min_order:
                        continue
                    eng.limit_buy(amt, bp)
                    time.sleep(0.3)
                    eng.limit_sell(amt * 0.998, sp)
                    time.sleep(0.3)
                    print(f"  BUY {amt} @ ${bp} → SELL @ ${sp}")
                placed_grid = True

            elif len(orders) == 0 and placed_grid:
                # Grid completed (all filled and settled) — recycle
                print(f"  ✅ Grid cycle complete. Recycling...")
                placed_grid = False
                ks.reset_day(eng.equity())

            # Status (every 10 loops)
            if int(time.time()) % 60 < 10:  # FIXED
                sol = eng.balance().get("SOL", 0)
                usdc = eng.balance().get("USDC", 0)
                ord_str = f"{len(orders)} orders" if orders else "idle"
                print(f"  {datetime.now().strftime('%H:%M:%S')}  SOL=${p:.2f}  eq=${eq:.2f}  reg={regime}  {ord_str}  L{ks.consecutive_losses}")

        except Exception as e:
            print(f"  ❌ {str(e)[:80]}")

        time.sleep(30)

if __name__ == "__main__":
    main()

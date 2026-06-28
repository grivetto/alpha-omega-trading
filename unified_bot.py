#!/usr/bin/env python3
"""DENARO UNIFIED BOT — One process, all strategies, State Engine brain.
Architecture: State Engine decides → Grid (always) + Opportunistic (state-driven).
All €229 on one machine. No fragmentation. Brutal simplicity."""
import os, sys, time, json, hashlib, hmac, requests
from datetime import datetime

# ============================================================
# ENGINE (direct REST, no ccxt)
# ============================================================
class Engine:
    def __init__(self):
        self.key = os.getenv("BINANCE_API_KEY", "").strip()
        self.sec = os.getenv("BINANCE_API_SECRET", "").strip()
        if not self.key:
            # Try loading from .env
            for p in [os.path.expanduser("~/denaro/.env"), ".env", "../.env"]:
                if os.path.exists(p):
                    for line in open(p):
                        if line.strip() and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == "BINANCE_API_KEY": self.key = v.strip()
                            if k.strip() == "BINANCE_API_SECRET": self.sec = v.strip()
        if not self.key:
            print("❌ API keys not found"); sys.exit(1)

    def _sign(self, qs): return hmac.new(self.sec.encode(), qs.encode(), hashlib.sha256).hexdigest() if self.sec else ""

    def _call(self, method, path, extra=""):
        ts = int(time.time() * 1000)
        q = f"timestamp={ts}&recvWindow=30000"
        if extra: q += "&" + extra
        sig = self._sign(q)
        url = f"https://api.binance.com{path}?{q}&signature={sig}"
        r = requests.request(method, url, headers={"X-MBX-APIKEY": self.key}, timeout=15)
        return r.json() if r.status_code == 200 else {"error": r.text[:100]}

    def price(self, sym="SOLUSDC"):
        r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={sym}", timeout=5)
        return float(r.json()["price"]) if r.status_code == 200 else 0.0

    def balance(self, asset=None):
        b = self._call("GET", "/api/v3/account")
        if "balances" not in b: return 0.0 if asset else {}
        if asset:
            return float(next((x["free"] for x in b["balances"] if x["asset"] == asset), 0))
        return {x["asset"]: {"free": float(x["free"]), "locked": float(x["locked"])}
                for x in b["balances"] if float(x["free"]) > 0 or float(x["locked"]) > 0}

    def equity(self):
        b = self.balance()
        sol_data = b.get("SOL", {})
        sol = sol_data.get("free", 0) + sol_data.get("locked", 0) if isinstance(sol_data, dict) else 0
        usdc_data = b.get("USDC", {})
        usdc = usdc_data.get("free", 0) + usdc_data.get("locked", 0) if isinstance(usdc_data, dict) else 0
        sol_price = self.price()
        return usdc + sol * sol_price

    def open_orders(self, sym="SOLUSDC"):
        return self._call("GET", "/api/v3/openOrders", f"symbol={sym}")

    def cancel_all(self, sym="SOLUSDC"):
        for o in self.open_orders(sym):
            self._call("DELETE", "/api/v3/order", f"symbol={sym}&orderId={o['orderId']}")

    def market_buy(self, quote_amount, sym="SOLUSDC"):
        return self._call("POST", "/api/v3/order", f"symbol={sym}&side=BUY&type=MARKET&quoteOrderQty={quote_amount:.2f}")

    def market_sell(self, qty, sym="SOLUSDC"):
        return self._call("POST", "/api/v3/order", f"symbol={sym}&side=SELL&type=MARKET&quantity={qty:.4f}")

    def limit_sell(self, qty, price, sym="SOLUSDC"):
        return self._call("POST", "/api/v3/order", f"symbol={sym}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={qty:.4f}&price={price:.2f}")

    def ohlcv(self, sym="SOLUSDC", interval="1d", limit=25):
        r = requests.get(f"https://api.binance.com/api/v3/klines?symbol={sym}&interval={interval}&limit={limit}", timeout=10)
        return r.json() if r.status_code == 200 else []

    def atr(self, sym="SOLUSDC", period=14):
        k = self.ohlcv(sym, "5m", limit=period+1)
        if len(k) < period+1: return 0.0
        trs = [max(float(k[i][2])-float(k[i][3]), abs(float(k[i][2])-float(k[i-1][4])), abs(float(k[i][3])-float(k[i-1][4]))) for i in range(1,len(k))]
        return sum(trs)/len(trs)

    def imbalance(self, sym="SOLUSDC"):
        r = requests.get(f"https://api.binance.com/api/v3/depth?symbol={sym}&limit=20", timeout=5)
        d = r.json() if r.status_code == 200 else {}
        bids = sum(float(b[1]) for b in d.get("bids", []))
        asks = sum(float(a[1]) for a in d.get("asks", []))
        return bids/asks if asks > 0 else 1.0


# ============================================================
# STATE ENGINE (20-day lookback, 5% threshold)
# ============================================================
class StateEngine:
    BULL, BEAR, SIDEWAYS = "BULL", "BEAR", "SIDEWAYS"
    
    def __init__(self):
        self.state = self.SIDEWAYS
        self.transitions = {}
        self.last_check = ""
        self._prev_state = self.SIDEWAYS
    
    def update(self, eng):
        today = datetime.now().strftime("%Y-%m-%d")
        if today == self.last_check: return
        self.last_check = today
        
        ohlcv = eng.ohlcv("SOLUSDC", "1d", 25)
        if len(ohlcv) < 5: return
        
        price_old = float(ohlcv[0][4])
        price_now = eng.price()
        change = (price_now - price_old) / price_old
        
        if change > 0.05: new_state = self.BULL
        elif change < -0.05: new_state = self.BEAR
        else: new_state = self.SIDEWAYS
        
        if new_state != self.state:
            key = f"{self.state}->{new_state}"
            self.transitions[key] = self.transitions.get(key, 0) + 1
        
        self._prev_state = self.state
        self.state = new_state
    
    def signal(self):
        """Return strategy configuration for current state."""
        if self.state == self.BULL:
            return {"grid": True, "grid_size": 0.5, "momentum": True, "scalp": True, "whale": True}
        elif self.state == self.BEAR:
            return {"grid": False, "grid_size": 0, "momentum": False, "scalp": True, "whale": False}
        else:  # SIDEWAYS
            return {"grid": True, "grid_size": 1.0, "momentum": False, "scalp": True, "whale": True}


# ============================================================
# GRID STRATEGY (always-on base layer)
# ============================================================
class GridStrategy:
    def __init__(self, eng, capital=150, levels=6, spacing=0.015):
        self.eng = eng; self.cap = capital; self.levels = levels
        self.spacing = spacing; self.trades = 0; self.pnl = 0.0
        self._placed = False
    
    def run(self, signal):
        if not signal.get("grid"): return
        
        orders = self.eng.open_orders()
        if isinstance(orders, list) and len(orders) > 0:
            return  # Grid already placed
        
        if self._placed and len(orders) == 0:
            # Grid completed a cycle — profit!
            new_eq = self.eng.equity()
            self.pnl += new_eq - self.cap
            self.cap = new_eq
            self._placed = False
        
        # Place grid
        p = self.eng.price()
        if p <= 0: return
        
        active_levels = max(2, int(self.levels * signal.get("grid_size", 1.0)))
        cap_per_level = min(self.cap * 0.8 / active_levels, 30)
        if cap_per_level < 5: return
        
        print(f"  📊 Grid: {active_levels} levels, spacing={self.spacing*100:.1f}%, state={self.eng._state.state}")
        
        for i in range(1, active_levels + 1):
            buy_p = round(p * (1 - self.spacing * i / active_levels), 2)
            sell_p = round(buy_p * (1 + self.spacing * 1.5), 2)
            qty = round(cap_per_level / buy_p, 4)
            if qty * buy_p >= 5:
                self.eng._call("POST", "/api/v3/order", f"symbol=SOLUSDC&side=BUY&type=LIMIT&timeInForce=GTC&quantity={qty:.4f}&price={buy_p:.2f}")
                time.sleep(0.3)
                self.eng.limit_sell(qty * 0.998, sell_p)
                time.sleep(0.3)
        self._placed = True
        self.trades += 1


# ============================================================
# SCALPER (opportunistic, only when state allows)
# ============================================================
class Scalper:
    def __init__(self, eng, capital=30):
        self.eng = eng; self.cap = capital; self.trades = 0; self.pnl = 0.0
        self.high = 0.0; self.entry = 0.0; self.in_position = False
    
    def run(self, signal):
        if not signal.get("scalp"): return
        
        p = self.eng.price()
        if p <= 0: return
        self.high = max(self.high, p)
        
        orders = self.eng.open_orders()
        if isinstance(orders, list) and any(o.get("side") == "SELL" for o in orders):
            return  # Already in position
        
        drop = (self.high - p) / self.high if self.high else 0
        usdc = self.eng.balance("USDC")
        
        if drop >= 0.008 and usdc >= 5 and not self.in_position:
            amt = min(self.cap * 0.5, 15)
            r = self.eng.market_buy(amt)
            if "executedQty" in r:
                qty = float(r["executedQty"]); cost = float(r["cummulativeQuoteQty"])
                self.entry = cost / qty; self.in_position = True
                self.eng.limit_sell(qty * 0.998, self.entry * 1.004)
                self.trades += 1


# ============================================================
# MAIN ORCHESTRATOR
# ============================================================
def main():
    print("=" * 55)
    print("  ⚔️ DENARO UNIFIED — State-Driven War Machine")
    print("=" * 55)
    
    eng = Engine()
    state = StateEngine()
    eng._state = state  # Attach for grid access
    
    total = eng.equity()
    print(f"  Equity: ${total:.0f} | State: {state.state}")
    
    # Capital allocation
    grid = GridStrategy(eng, capital=total * 0.65, levels=6, spacing=0.015)
    scalper = Scalper(eng, capital=total * 0.20)
    
    cycle = 0
    while True:
        try:
            cycle += 1
            
            # Daily state update
            state.update(eng)
            sig = state.signal()
            
            # Run strategies
            grid.run(sig)
            scalper.run(sig)
            
            # Status every 2 minutes
            if cycle % 24 == 0:
                eq = eng.equity()
                color = "\033[92m" if eq > total else "\033[91m"
                print(f"  {datetime.now().strftime('%H:%M:%S')} State:{state.state} "
                      f"Eq:{color}${eq:.0f}\033[0m G:{grid.trades} S:{scalper.trades}")
            
            time.sleep(5)
            
        except KeyboardInterrupt:
            print("\n  Shutting down...")
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}")
            time.sleep(10)

if __name__ == "__main__":
    main()

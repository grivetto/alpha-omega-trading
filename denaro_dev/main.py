"""
Denaro Dev — Grid+ATR Strategy
Dynamic grid levels based on ATR, with exchange filter compliance.
Tests on MARCODG1 with $10 capital.
"""
import json, os, sys, time, math, hmac, hashlib
from datetime import datetime
from urllib.parse import urlencode
from typing import List, Optional, Dict

import requests


# ═══════════════════════════════
# ENGINE
# ═══════════════════════════════

class Engine:
    def __init__(self):
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip())
        self.key = os.environ.get("BINANCE_API_KEY", "")
        self.secret = os.environ.get("BINANCE_API_SECRET", "").encode()
        self.base = "https://api.binance.com"
        self.ses = requests.Session()
        self.ses.headers.update({"X-MBX-APIKEY": self.key})
        self._timeout = (5, 10)

    def _sign(self, p):
        p["timestamp"] = int(time.time() * 1000)
        p["signature"] = hmac.new(self.secret, urlencode(p).encode(), hashlib.sha256).hexdigest()
        return p

    def _get(self, ep, params=None, signed=False):
        p = params or {}
        if signed: p = self._sign(p)
        r = self.ses.get(f"{self.base}{ep}", params=p, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, ep, params):
        p = self._sign(params)
        r = self.ses.post(f"{self.base}{ep}", data=p, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _delete(self, ep, params):
        p = self._sign(params)
        r = self.ses.delete(f"{self.base}{ep}", params=p, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def price(self, sym): return float(self._get("/api/v3/ticker/price", {"symbol": sym})["price"])
    def balance(self, asset):
        d = self._get("/api/v3/account", signed=True)
        for b in d["balances"]:
            if b["asset"] == asset: return float(b["free"])
        return 0.0
    def ohlcv(self, sym, interval="5m", limit=50):
        return self._get("/api/v3/klines", {"symbol": sym, "interval": interval, "limit": limit})
    def depth(self, sym, limit=20):
        return self._get("/api/v3/depth", {"symbol": sym, "limit": limit})
    def market_buy(self, sym, qty):
        return self._post("/api/v3/order", {"symbol": sym, "side": "BUY", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def market_sell(self, sym, qty):
        return self._post("/api/v3/order", {"symbol": sym, "side": "SELL", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def limit_buy(self, sym, qty, price):
        return self._post("/api/v3/order", {"symbol": sym, "side": "BUY", "type": "LIMIT", "timeInForce": "GTC",
                                              "quantity": f"{qty:.{self._qprec}f}", "price": f"{price:.{self._pprec}f}"})
    def limit_sell(self, sym, qty, price):
        return self._post("/api/v3/order", {"symbol": sym, "side": "SELL", "type": "LIMIT", "timeInForce": "GTC",
                                               "quantity": f"{qty:.{self._qprec}f}", "price": f"{price:.{self._pprec}f}"})
    def cancel_order(self, sym, oid):
        return self._delete("/api/v3/order", {"symbol": sym, "orderId": oid})
    def open_orders(self, sym):
        return self._get("/api/v3/openOrders", {"symbol": sym}, signed=True)

    def load_filters(self, sym):
        """Load LOT_SIZE + PRICE_FILTER for symbol."""
        r = self._get("/api/v3/exchangeInfo", {"symbol": sym})
        f = {x["filterType"]: x for x in r["symbols"][0]["filters"]}
        ls = f["LOT_SIZE"]
        pf = f["PRICE_FILTER"]
        self._lot_step = float(ls["stepSize"])
        self._lot_min = float(ls["minQty"])
        self._tick = float(pf["tickSize"])
        self._qprec = len(str(self._lot_step).split(".")[1]) if "." in str(self._lot_step) else 0
        self._pprec = len(str(self._tick).split(".")[1]) if "." in str(self._tick) else 0
        print(f"  📐 Filters: lot_step={self._lot_step} tick={self._tick} qprec={self._qprec} pprec={self._pprec}")

    def round_qty(self, qty):
        if self._lot_step >= 1: return math.floor(qty)
        return math.floor(qty / self._lot_step) * self._lot_step

    def round_price(self, price):
        return round(round(price / self._tick) * self._tick, self._pprec)


# ═══════════════════════════════
# ATR CALC
# ═══════════════════════════════

def calc_atr(klines, period=14):
    if len(klines) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(klines)):
        high = float(klines[i][2])
        low = float(klines[i][3])
        prev_close = float(klines[i - 1][4])
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period if len(trs) >= period else 0.0


# ═══════════════════════════════
# GRID+ATR STRATEGY
# ═══════════════════════════════

class GridATR:
    def __init__(self, engine, symbol: str, capital: float, config: dict):
        self.eng = engine
        self.sym = symbol
        self.base = symbol.replace("USDC", "")
        self.capital = capital
        self.cfg = config

        self.grid_levels = config.get("grid_levels", 3)
        self.grid_spread_atr = config.get("grid_spread_atr", 0.8)
        self.tp_atr = config.get("tp_atr", 1.5)
        self.atr_period = config.get("atr_period", 14)
        self.max_pos_pct = config.get("max_position_pct", 0.8)
        self.rebal_interval = config.get("rebalance_interval_s", 300)

        self.trades = 0
        self.pnl = 0.0
        self.wins = 0
        self.losses = 0
        self._orders: Dict[str, dict] = {}
        self._last_rebalance = 0.0
        self._atr = 0.0
        self._price = 0.0
        self._bal_base = 0.0
        self._bal_quote = 0.0
        self.history: List[dict] = []

    def refresh_balances(self):
        self._bal_base = self.eng.balance(self.base)
        self._bal_quote = self.eng.balance("USDC")

    def update_market(self):
        try:
            kl = self.eng.ohlcv(self.sym, "5m", limit=30)
            self._atr = calc_atr(kl, self.atr_period)
            self._price = self.eng.price(self.sym)
            return True
        except Exception as e:
            print(f"  ⚠️ market: {e}")
            return False

    def cancel_all(self):
        for o in self.eng.open_orders(self.sym):
            try:
                self.eng.cancel_order(self.sym, o["orderId"])
            except:
                pass
        self._orders.clear()

    def place_grid(self):
        if self._atr <= 0 or self._price <= 0:
            return
        self.cancel_all()
        time.sleep(0.5)
        self.refresh_balances()
        self._last_rebalance = time.time()

        # Use most of available USDC for a single order
        order_usdc = self._bal_quote * 1.0
        raw_spread = max(self._atr * self.grid_spread_atr, self.eng._tick * 2)

        # BUY orders below price (we have USDC, no ADA to sell initially)
        for i in range(1, self.grid_levels + 1):
            px = self.eng.round_price(self._price - raw_spread * i)
            px = max(px, self.eng._tick)
            qty = self.eng.round_qty(order_usdc / px)
            if qty >= self.eng._lot_min and qty * px >= 5.0:
                try:
                    r = self.eng.limit_buy(self.sym, qty, px)
                    if "orderId" in r:
                        self._orders[r["orderId"]] = {
                            "side": "BUY", "price": px, "qty": qty,
                            "tp": self.eng.round_price(self._price + raw_spread * i * 1.5),
                            "ts": time.time()
                        }
                except Exception as e:
                    print(f"  \u26a0\ufe0f BUY fail: {str(e)[:60]}")
                    pass

        # SELL only if we have quote asset to sell
        if self._bal_base >= self.eng._lot_min * 2:
            for i in range(1, self.grid_levels + 1):
                px = self.eng.round_price(self._price + raw_spread * i)
                qty = self.eng.round_qty(self._bal_base * 0.8)
                if qty >= self.eng._lot_min and qty * px >= 5.0:
                    try:
                        r = self.eng.limit_sell(self.sym, qty, px)
                        if "orderId" in r:
                            self._orders[r["orderId"]] = {
                                "side": "SELL", "price": px, "qty": qty,
                                "tp": self.eng.round_price(self._price - raw_spread * i * 0.5),
                                "ts": time.time()
                            }
                    except Exception as e:
                        pass

        print(f"  📋 Grid: {len(self._orders)} ordini, spread={raw_spread:.4f}, ATR={self._atr:.4f}")

    def check_fills(self):
        current = {o["orderId"]: o for o in self.eng.open_orders(self.sym)}
        current_ids = set(current.keys())

        filled = []
        for oid, info in list(self._orders.items()):
            if oid not in current_ids:
                filled.append(info)
                del self._orders[oid]

        for fill in filled:
            side = fill["side"]
            px = fill["price"]
            qty = fill["qty"]
            self.trades += 1

            tp_px = fill["tp"]
            rq = self.eng.round_qty(qty)
            if rq < self.eng._lot_min:
                continue

            try:
                if side == "BUY":
                    r = self.eng.limit_sell(self.sym, rq, tp_px)
                    if "orderId" in r:
                        self._orders[r["orderId"]] = {"side": "SELL", "price": tp_px, "qty": rq, "parent": "TP", "ts": time.time()}
                else:
                    r = self.eng.limit_buy(self.sym, rq, tp_px)
                    if "orderId" in r:
                        self._orders[r["orderId"]] = {"side": "BUY", "price": tp_px, "qty": rq, "parent": "TP", "ts": time.time()}
            except:
                pass

            est_pnl = (tp_px - px) * qty if side == "BUY" else (px - tp_px) * qty
            if side == "SELL":
                if est_pnl >= 0: self.wins += 1
                else: self.losses += 1
                self.pnl += est_pnl
                self.history.append({
                    "ts": datetime.now().isoformat(),
                    "side": side, "price": px, "qty": qty, "pnl": round(est_pnl, 4),
                    "cum_pnl": round(self.pnl, 2)
                })

    def run_cycle(self) -> dict:
        self.update_market()
        now = time.time()
        if now - self._last_rebalance > self.rebal_interval:
            self._last_rebalance = now
            self.place_grid()
        self.check_fills()
        return {"price": self._price, "atr": self._atr, "orders": len(self._orders),
                "trades": self.trades, "pnl": self.pnl}

    def stats(self) -> dict:
        total = self.wins + self.losses
        return {
            "trades": self.trades, "pnl": round(self.pnl, 2),
            "winrate": f"{self.wins/total*100:.1f}%" if total > 0 else "N/A",
            "wins": self.wins, "losses": self.losses,
            "open_orders": len(self._orders),
            "bal_usdc": round(self._bal_quote, 2)
        }


# ═══════════════════════════════
# MAIN
# ═══════════════════════════════

if __name__ == "__main__":
    cfg = {
        "grid_levels": 1,
        "grid_spread_atr": 1.5,
        "tp_atr": 1.5,
        "atr_period": 14,
        "max_position_pct": 0.8,
        "rebalance_interval_s": 300
    }

    SYMBOL = "ADAUSDC"
    eng = Engine()
    eng.load_filters(SYMBOL)

    print(f"  USDC: ${eng.balance('USDC'):.2f}  ADA: {eng.balance('ADA'):.4f}")
    print(f"  Prezzo {SYMBOL}: ${eng.price(SYMBOL):.4f}")

    strat = GridATR(eng, SYMBOL, capital=10.0, config=cfg)
    strat.update_market()

    cycle = 0
    while True:
        try:
            cycle += 1
            status = strat.run_cycle()
            if cycle % 12 == 0:
                s = strat.stats()
                elapsed = int(time.time() - strat._last_rebalance + strat.rebal_interval)
                print(f"  ⚡ C{cycle} | T:{s['trades']} PnL:${s['pnl']} WR:{s['winrate']} "
                      f"Ord:{s['open_orders']} USDC:{s['bal_usdc']}")
            time.sleep(5)
        except KeyboardInterrupt:
            print("\n  ⚔️ Stop")
            strat.cancel_all()
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}")
            time.sleep(10)

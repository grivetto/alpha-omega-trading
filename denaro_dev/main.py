"""
Denaro Dev — Grid+ATR Strategy
Dynamic grid levels based on ATR, with auto-tuning.
Tests on MARCODG1 with $10 capital.
"""
import json, os, sys, time, math, hmac, hashlib
from datetime import datetime
from urllib.parse import urlencode
from typing import List, Optional, Dict

import requests


# ═══════════════════════════════
# ENGINE (same pattern as v6)
# ═══════════════════════════════

class Engine:
    def __init__(self):
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
                                              "quantity": f"{qty:.6f}", "price": f"{price:.4f}"})
    def limit_sell(self, sym, qty, price):
        return self._post("/api/v3/order", {"symbol": sym, "side": "SELL", "type": "LIMIT", "timeInForce": "GTC",
                                               "quantity": f"{qty:.6f}", "price": f"{price:.4f}"})
    def cancel_order(self, sym, oid):
        return self._delete("/api/v3/order", {"symbol": sym, "orderId": oid})
    def open_orders(self, sym):
        return self._get("/api/v3/openOrders", {"symbol": sym}, signed=True)


# ═══════════════════════════════
# ATR CALC
# ═══════════════════════════════

def calc_atr(klines, period=14):
    """Calculate ATR from klines."""
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
    """
    Dynamic grid with ATR-based spacing.
    Places N buy/sell limit orders around current price.
    When a limit fills, places the opposite order at TP level.
    """
    def __init__(self, engine, symbol: str, capital: float, config: dict):
        self.eng = engine
        self.sym = symbol
        self.base = symbol.replace("USDC", "")
        self.capital = capital
        self.cfg = config

        # Configurable params
        self.grid_levels = config.get("grid_levels", 3)        # buy + sell sides
        self.grid_spread_atr = config.get("grid_spread_atr", 0.5)  # spacing as fraction of ATR
        self.tp_atr = config.get("tp_atr", 1.5)                 # TP as multiple of ATR
        self.sl_atr = config.get("sl_atr", 3.0)                 # SL as multiple of ATR
        self.atr_period = config.get("atr_period", 14)
        self.max_position_pct = config.get("max_position_pct", 0.8)
        self.rebalance_interval = config.get("rebalance_interval_s", 300)  # 5min

        # State
        self.trades = 0
        self.pnl = 0.0
        self.wins = 0
        self.losses = 0
        self._orders: Dict[str, dict] = {}  # orderId -> info
        self._last_rebalance = 0.0
        self._current_atr = 0.0
        self._current_price = 0.0
        self._position_qty = 0.0
        self._position_avg = 0.0
        self._bal_base = 0.0
        self._bal_quote = 0.0

        # History
        self.history: List[dict] = []

    def refresh_balances(self):
        """Update balance snapshot."""
        self._bal_base = self.eng.balance(self.base)
        self._bal_quote = self.eng.balance("USDC")

    def update_market(self):
        """Fetch ATR, price, depth."""
        try:
            kl = self.eng.ohlcv(self.sym, "5m", limit=30)
            self._current_atr = calc_atr(kl, self.atr_period)
            self._current_price = self.eng.price(self.sym)
            return True
        except Exception as e:
            print(f"  ⚠️ market update: {e}")
            return False

    def cancel_all(self):
        """Cancel all open orders for symbol."""
        for o in self.eng.open_orders(self.sym):
            try:
                self.eng.cancel_order(self.sym, o["orderId"])
            except:
                pass
        self._orders.clear()

    def place_grid(self):
        """Place grid of limit orders around current price."""
        if self._current_atr <= 0 or self._current_price <= 0:
            return

        self.cancel_all()
        time.sleep(0.5)
        self.refresh_balances()

        # Available capital per side
        per_side = self._bal_quote * 0.3 / self.grid_levels  # 30% of USDC per side, divided by levels

        spread = self._current_atr * self.grid_spread_atr

        # BUY orders below price
        for i in range(1, self.grid_levels + 1):
            px = self._current_price - spread * i
            qty = per_side / px
            qty = self._round_qty(qty)
            if qty > 0:
                try:
                    r = self.eng.limit_buy(self.sym, qty, px)
                    if "orderId" in r:
                        self._orders[r["orderId"]] = {
                            "side": "BUY", "price": px, "qty": qty,
                            "tp": self._current_price + spread * (i * 0.5),  # TP above entry
                            "ts": time.time()
                        }
                except Exception as e:
                    print(f"  ⚠️ buy order fail: {e}")

        # SELL orders above price
        for i in range(1, self.grid_levels + 1):
            px = self._current_price + spread * i
            qty = per_side / px
            qty = self._round_qty(qty)
            if qty > 0:
                try:
                    r = self.eng.limit_sell(self.sym, qty, px)
                    if "orderId" in r:
                        self._orders[r["orderId"]] = {
                            "side": "SELL", "price": px, "qty": qty,
                            "tp": self._current_price - spread * (i * 0.5),
                            "ts": time.time()
                        }
                except Exception as e:
                    print(f"  ⚠️ sell order fail: {e}")

        print(f"  📋 Grid: {len(self._orders)} orders @ ±{spread:.4f} ATR={self._current_atr:.4f} px={self._current_price:.4f}")

    def check_fills(self):
        """Check if any orders filled, place opposite TP order."""
        filled = []
        current_orders = {o["orderId"]: o for o in self.eng.open_orders(self.sym)}
        current_ids = set(current_orders.keys())

        for oid, info in list(self._orders.items()):
            if oid not in current_ids:
                # Order was filled (or cancelled externally)
                filled.append(info)
                del self._orders[oid]

        for fill in filled:
            side = fill["side"]
            px = fill["price"]
            qty = fill["qty"]
            self.trades += 1

            # Place opposite TP order
            if side == "BUY":
                # Sold too cheap? no - bought low, now sell high at TP
                tp_px = fill["tp"]
                rq = self._round_qty(qty * 0.95)  # sell slightly less to avoid rounding issues
                if rq > 0:
                    try:
                        r = self.eng.limit_sell(self.sym, rq, tp_px)
                        self._orders[r["orderId"]] = {
                            "side": "SELL", "price": tp_px, "qty": rq,
                            "parent": "TP", "ts": time.time()
                        }
                        print(f"  📈 BUY filled @ {px} → SELL TP @ {tp_px:.4f}")
                    except Exception as e:
                        print(f"  ⚠️ TP sell fail: {e}")
            else:
                # Sold high, now buy back at TP
                tp_px = fill["tp"]
                rq = self._round_qty(qty * 0.95)
                if rq > 0:
                    try:
                        r = self.eng.limit_buy(self.sym, rq, tp_px)
                        self._orders[r["orderId"]] = {
                            "side": "BUY", "price": tp_px, "qty": rq,
                            "parent": "TP", "ts": time.time()
                        }
                        print(f"  📉 SELL filled @ {px} → BUY TP @ {tp_px:.4f}")
                    except Exception as e:
                        print(f"  ⚠️ TP buy fail: {e}")

            # Record trade (estimate PnL)
            if side == "SELL":
                est_pnl = (px - fill.get("avg_entry", px)) * qty
                if est_pnl >= 0:
                    self.wins += 1
                else:
                    self.losses += 1
                self.pnl += est_pnl
                self.history.append({
                    "ts": datetime.now().isoformat(),
                    "side": side, "price": px, "qty": qty, "pnl": round(est_pnl, 4),
                    "cum_pnl": round(self.pnl, 2)
                })

    def run_cycle(self) -> dict:
        """Single cycle: update market, rebalance grid, check fills."""
        self.update_market()

        now = time.time()
        if now - self._last_rebalance > self.rebalance_interval:
            self._last_rebalance = now
            self.place_grid()

        self.check_fills()

        return {
            "price": self._current_price,
            "atr": self._current_atr,
            "orders": len(self._orders),
            "trades": self.trades,
            "pnl": self.pnl,
            "wins": self.wins,
            "losses": self.losses,
            "bal_usdc": self._bal_quote,
            "bal_base": self._bal_base
        }

    def _round_qty(self, qty):
        if qty > 100: return math.floor(qty)
        elif qty > 1: return round(qty, 2)
        elif qty > 0.01: return round(qty, 4)
        else: return round(qty, 6)

    def stats(self) -> dict:
        total = self.wins + self.losses
        return {
            "trades": self.trades,
            "pnl": round(self.pnl, 2),
            "winrate": f"{self.wins/total*100:.1f}%" if total > 0 else "N/A",
            "wins": self.wins,
            "losses": self.losses,
            "open_orders": len(self._orders),
            "bal_usdc": round(self._bal_quote, 2),
            "bal_base": round(self._bal_base, 6)
        }


# ═══════════════════════════════
# TEST HARNESS
# ═══════════════════════════════

def run_test(strategy, symbol: str, duration_minutes: int = 60, save_results: bool = True):
    """Run a strategy and collect metrics."""
    print(f"\n{'='*60}")
    print(f"  TEST HARNESS | {strategy.__class__.__name__} | {symbol}")
    print(f"  Duration: {duration_minutes}min | Start: {datetime.now().isoformat()}")
    print(f"{'='*60}\n")

    start = time.time()
    end = start + duration_minutes * 60
    cycles = 0
    errors = 0

    result_file = f"results/{strategy.__class__.__name__}_{symbol}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"

    while time.time() < end:
        try:
            status = strategy.run_cycle()
            cycles += 1

            if cycles % 60 == 0:
                s = strategy.stats()
                elapsed = int(time.time() - start)
                print(f"  [{elapsed}s] T:{s['trades']} PnL:${s['pnl']} WR:{s['winrate']} "
                      f"Ord:{s['open_orders']} USDC:{s['bal_usdc']}")

            time.sleep(5)  # 5s per cycle

        except KeyboardInterrupt:
            print("\n  ⚔️ Stopped by user")
            break
        except Exception as e:
            errors += 1
            print(f"  ❌ Cycle {cycles}: {str(e)[:80]}")
            time.sleep(10)

    elapsed = int(time.time() - start)
    s = strategy.stats()

    print(f"\n{'='*60}")
    print(f"  TEST COMPLETE | {elapsed}s | {cycles} cycles | {errors} errors")
    print(f"  {json.dumps(s, indent=2)}")
    print(f"{'='*60}\n")

    if save_results:
        with open(result_file, "w") as f:
            json.dump({
                "strategy": strategy.__class__.__name__,
                "symbol": symbol,
                "duration_s": elapsed,
                "cycles": cycles,
                "errors": errors,
                "stats": s,
                "history": strategy.history[-100:]  # last 100 trades
            }, f, indent=2)
        print(f"  Results saved to {result_file}")

    return s


# ═══════════════════════════════
# MAIN
# ═══════════════════════════════

if __name__ == "__main__":
    # Load config
    cfg = {
        "grid_levels": 3,
        "grid_spread_atr": 0.5,
        "tp_atr": 1.5,
        "sl_atr": 3.0,
        "atr_period": 14,
        "max_position_pct": 0.8,
        "rebalance_interval_s": 300
    }

    SYMBOL = "ADAUSDC"
    eng = Engine()

    print(f"  Balance USDC: ${eng.balance('USDC'):.2f}")
    print(f"  Balance ADA: {eng.balance('ADA'):.6f}")
    print(f"  Price {SYMBOL}: ${eng.price(SYMBOL):.4f}")

    strat = GridATR(eng, SYMBOL, capital=10.0, config=cfg)

    # First: update market + place initial grid
    strat.update_market()
    strat.place_grid()

    # Run test
    run_test(strat, SYMBOL, duration_minutes=60, save_results=False)

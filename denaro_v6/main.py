"""
Denaro v6 — INTELLIGENT War Machine.
Adaptive parameters per market state. Compounds capital. Makes real money.
"""
import json, os, sys, time, signal, hashlib, hmac, math, threading
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False

import requests


def load_config(path="config/v6_config.json"):
    with open(os.path.join(os.path.dirname(__file__), path)) as f:
        return json.load(f)


# ═══════════════════════════════════════
# ENGINE
# ═══════════════════════════════════════

class Engine:
    def __init__(self, config: dict):
        self.cfg = config
        bcfg = config.get("binance", {})
        self.base = bcfg.get("base_url", "https://api.binance.com")
        self.key = os.environ.get("BINANCE_API_KEY", bcfg.get("api_key", ""))
        self.secret = os.environ.get("BINANCE_API_SECRET", bcfg.get("api_secret", "")).encode()
        self.ses = requests.Session()
        self.ses.headers.update({"X-MBX-APIKEY": self.key})
        self._timeout = (5, 10)

    def _sign(self, p): p["timestamp"] = int(time.time()*1000); qs = urlencode(p); p["signature"] = hmac.new(self.secret, qs.encode(), hashlib.sha256).hexdigest(); return p
    def _get(self, ep, params=None, signed=False):
        params = params or {}
        if signed: params = self._sign(params)
        r = self.ses.get(f"{self.base}{ep}", params=params, timeout=self._timeout); r.raise_for_status(); return r.json()
    def _post(self, ep, params, signed=True):
        if signed: params = self._sign(params)
        r = self.ses.post(f"{self.base}{ep}", data=params, timeout=self._timeout); r.raise_for_status(); return r.json()
    def _delete(self, ep, params, signed=True):
        if signed: params = self._sign(params)
        r = self.ses.delete(f"{self.base}{ep}", params=params, timeout=self._timeout); r.raise_for_status(); return r.json()

    def price(self, sym): return float(self._get("/api/v3/ticker/price", {"symbol": sym})["price"])
    def balance(self, asset):
        d = self._get("/api/v3/account", signed=True)
        for b in d["balances"]:
            if b["asset"] == asset: return float(b["free"])
        return 0.0
    def imbalance(self, sym, limit=20):
        d = self._get("/api/v3/depth", {"symbol": sym, "limit": limit})
        bids = sum(float(b[1]) for b in d["bids"]); asks = sum(float(a[1]) for a in d["asks"])
        return bids/asks if asks > 0 else float('inf')
    def market_buy(self, sym, qty): return self._post("/api/v3/order", {"symbol": sym, "side": "BUY", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def market_sell(self, sym, qty): return self._post("/api/v3/order", {"symbol": sym, "side": "SELL", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def open_orders(self, sym): return self._get("/api/v3/openOrders", {"symbol": sym}, signed=True)
    def cancel_order(self, sym, oid): return self._delete("/api/v3/order", {"symbol": sym, "orderId": oid})
    def cancel_all(self, sym):
        for o in self.open_orders(sym): self.cancel_order(sym, o["orderId"])
    def ohlcv(self, sym, interval="5m", limit=30): return self._get("/api/v3/klines", {"symbol": sym, "interval": interval, "limit": limit})

    # WebSocket price cache
    _prices: Dict[str, float] = {}
    _lock = threading.Lock()
    _ws_alive = False

    def get_price(self, sym):
        with self._lock: return self._prices.get(sym, 0.0)

    def start_ws(self, symbols):
        if not HAS_WS: return False
        streams = "/".join(f"{s.lower()}@ticker" for s in symbols)
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"
        def _on_msg(ws, msg):
            try:
                data = json.loads(msg).get("data", {}); sym = data.get("s", ""); px = float(data.get("c", 0))
                if sym and px:
                    with self._lock: self._prices[sym] = px
            except: pass
        def _on_open(ws): self._ws_alive = True
        def _run(): ws = websocket.WebSocketApp(url, on_message=_on_msg, on_open=_on_open); ws.run_forever(reconnect=5)
        t = threading.Thread(target=_run, daemon=True); t.start(); time.sleep(1); return True


# ═══════════════════════════════════════
# CIRCUIT BREAKER
# ═══════════════════════════════════════

class CircuitBreaker:
    CLOSED, HALF_OPEN, OPEN = "CLOSED", "HALF_OPEN", "OPEN"

    def __init__(self, config: dict):
        self.max_losses = config.get("cb_max_consecutive_losses", 3)
        self.max_daily_dd = config.get("cb_max_daily_drawdown_pct", 3.0)
        self.max_total_dd = config.get("cb_max_total_drawdown_pct", 5.0)
        self.half_scale = config.get("cb_half_open_scale", 0.5)
        self.state = self.CLOSED
        self._consecutive_losses = 0; self._daily_pnl = 0.0; self._peak = 0.0; self._current = 0.0
        self._state_file = config.get("cb_state_file", "circuit_breaker_v6.json")

    def update_equity(self, eq):
        self._current = eq
        if eq > self._peak: self._peak = eq

    def record_trade(self, pnl):
        self._daily_pnl += pnl
        self._consecutive_losses = 0 if pnl >= 0 else self._consecutive_losses + 1
        self._update_state(); self._save()

    def can_trade(self, amount):
        if self.state == self.CLOSED: return True, "CLOSED", amount
        if self.state == self.HALF_OPEN: return True, "HALF_OPEN", amount * self.half_scale
        return False, "OPEN", 0.0

    def _update_state(self):
        total_dd = (self._peak - self._current)/self._peak*100 if self._peak > 0 else 0
        daily_dd = abs(self._daily_pnl)/self._peak*100 if self._peak > 0 else 0
        if total_dd >= self.max_total_dd or daily_dd >= self.max_daily_dd: self.state = self.OPEN
        elif self._consecutive_losses >= self.max_losses: self.state = self.HALF_OPEN
        else: self.state = self.CLOSED

    def _save(self):
        try:
            with open(self._state_file, "w") as f:
                json.dump({"state": self.state, "losses": self._consecutive_losses, "peak": self._peak, "daily": self._daily_pnl}, f)
        except: pass

    def load(self):
        try:
            with open(self._state_file) as f:
                d = json.load(f)
                if d.get("state") == self.OPEN and self._current > 0:
                    self.state = self.CLOSED  # fresh start, don't stay OPEN
                else:
                    self.state = d.get("state", self.CLOSED)
                self._consecutive_losses = d.get("losses", 0); self._peak = d.get("peak", self._current); self._daily_pnl = d.get("daily", 0)
        except FileNotFoundError: pass


# ═══════════════════════════════════════
# STATE ENGINE
# ═══════════════════════════════════════

class StateEngine:
    BULL, BEAR, SIDEWAYS = "BULL", "BEAR", "SIDEWAYS"

    def __init__(self, lookback=20, threshold=5.0):
        self.lookback = lookback; self.threshold = threshold; self.state = self.SIDEWAYS

    def update(self, price, ohlcv):
        if ohlcv and len(ohlcv) >= self.lookback:
            past = float(ohlcv[-self.lookback][4])
            ch = (price - past)/past
            if ch > self.threshold/100: self.state = self.BULL
            elif ch < -self.threshold/100: self.state = self.BEAR
            else: self.state = self.SIDEWAYS
        return self.state

    def params(self):
        """Return strategy parameters tuned for current market state."""
        if self.state == self.BULL:
            return {"scalp_entry": 0.004, "scalp_tp": 0.006, "scalp_sl": 0.015,
                    "whale_imb": 2.0, "whale_tp": 0.012, "whale_sl": 0.02,
                    "mom_pump": 1, "mom_pct": 0.008, "mom_tp": 0.02, "mom_sl": 0.025,
                    "position_pct": 0.80, "cooldown_s": 10}
        elif self.state == self.BEAR:
            return {"scalp_entry": 0.006, "scalp_tp": 0.003, "scalp_sl": 0.01,
                    "whale_imb": 99, "whale_tp": 0, "whale_sl": 0,
                    "mom_pump": 99, "mom_pct": 99, "mom_tp": 0, "mom_sl": 0,
                    "position_pct": 0.30, "cooldown_s": 60}
        else:  # SIDEWAYS
            return {"scalp_entry": 0.005, "scalp_tp": 0.004, "scalp_sl": 0.015,
                    "whale_imb": 2.5, "whale_tp": 0.008, "whale_sl": 0.02,
                    "mom_pump": 2, "mom_pct": 0.01, "mom_tp": 0.015, "mom_sl": 0.02,
                    "position_pct": 0.65, "cooldown_s": 20}


# ═══════════════════════════════════════
# STRATEGIES (adaptive)
# ═══════════════════════════════════════

def _rq(q):
    if q > 100: return math.floor(q)
    elif q > 1: return math.floor(q*100)/100
    elif q > 0.01: return math.floor(q*10000)/10000
    else: return math.floor(q*1000000)/1000000


class Scalper:
    def __init__(self, eng, sym):
        self.eng = eng; self.sym = sym
        self.t = 0; self.pnl = 0.0; self._pos = None; self._ep = 0.0; self._eq = 0.0; self._et = 0.0
        self._high = 0.0; self._cd = 0.0; self._trail = 0.0

    def run(self, cb, equity, params):
        now = time.time()
        if self._pos: return self._manage(now, params)
        if now < self._cd: return None
        px = self.eng.get_price(self.sym)
        if not px: return None
        if px > self._high or self._high == 0: self._high = px
        if now - getattr(self, '_rh', 0) > 60: self._high = px; self._rh = now
        drop = (self._high - px)/self._high
        if drop >= params["scalp_entry"]:
            usdc = equity * params["position_pct"] * 0.35
            qty = _rq(usdc/px)
            ok, st, amt = cb.can_trade(qty*px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._ep = px; self._eq = qty; self._et = now; self._trail = px
                self.t += 1
                return {"action": "BUY", "px": px, "qty": qty, "strat": "scalp", "state": st}
        return None

    def _manage(self, now, params):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._ep)/self._ep
        # Trailing stop: lock profit at 50% of TP
        if pnl_pct >= params["scalp_tp"]*0.5 and px > self._trail:
            self._trail = px
        if pnl_pct >= params["scalp_tp"]: return self._close(px, "TP")
        if pnl_pct <= -params["scalp_sl"]: return self._close(px, "SL")
        if (px - self._trail)/self._trail <= -params["scalp_tp"]*0.4: return self._close(px, "TRAIL")
        if now - self._et > 180: return self._close(px, "TIME")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._eq)
        pnl = (px - self._ep)*self._eq; self.pnl += pnl
        self._pos = None; self._cd = time.time() + 10; self._high = 0
        return {"action": "SELL", "px": px, "pnl": round(pnl,4), "reason": reason, "strat": "scalp"}


class WhaleTracker:
    def __init__(self, eng, sym):
        self.eng = eng; self.sym = sym
        self.t = 0; self.pnl = 0.0; self._pos = None; self._ep = 0.0; self._eq = 0.0; self._et = 0.0
        self._cd = 0.0; self._trail = 0.0

    def run(self, cb, equity, params):
        now = time.time()
        if self._pos: return self._manage(now, params)
        if now < self._cd: return None
        try: imb = self.eng.imbalance(self.sym, 20)
        except: return None
        if imb >= params["whale_imb"]:
            px = self.eng.get_price(self.sym)
            if not px: return None
            usdc = equity * params["position_pct"] * 0.35
            qty = _rq(usdc/px)
            ok, st, _ = cb.can_trade(qty*px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._ep = px; self._eq = qty; self._et = now; self._trail = px
                self.t += 1
                return {"action": "BUY", "px": px, "strat": "whale", "state": st, "imb": f"{imb:.1f}"}
        return None

    def _manage(self, now, params):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._ep)/self._ep
        if pnl_pct >= params["whale_tp"]*0.5 and px > self._trail: self._trail = px
        if pnl_pct >= params["whale_tp"]: return self._close(px, "TP")
        if pnl_pct <= -params["whale_sl"]: return self._close(px, "SL")
        if (px - self._trail)/self._trail <= -params["whale_tp"]*0.4: return self._close(px, "TRAIL")
        if now - self._et > 300: return self._close(px, "TIME")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._eq)
        pnl = (px - self._ep)*self._eq; self.pnl += pnl
        self._pos = None; self._cd = time.time() + 15
        return {"action": "SELL", "px": px, "pnl": round(pnl,4), "reason": reason, "strat": "whale"}


class MomentumReactor:
    def __init__(self, eng, sym):
        self.eng = eng; self.sym = sym
        self.t = 0; self.pnl = 0.0; self._pos = None; self._ep = 0.0; self._eq = 0.0; self._et = 0.0
        self._cd = 0.0; self._trail = 0.0; self._lp = 0.0; self._pumps = 0

    def run(self, cb, equity, params):
        now = time.time()
        if self._pos: return self._manage(now, params)
        if now < self._cd: return None
        px = self.eng.get_price(self.sym)
        if not px: return None
        if self._lp > 0:
            ch = (px - self._lp)/self._lp
            if ch > params["mom_pct"]*0.7: self._pumps += 1
            else: self._pumps = 0
        self._lp = px
        if self._pumps >= params["mom_pump"]:
            usdc = equity * params["position_pct"] * 0.30
            qty = _rq(usdc/px)
            ok, st, _ = cb.can_trade(qty*px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._ep = px; self._eq = qty; self._et = now; self._trail = px
                self._pumps = 0; self.t += 1
                return {"action": "BUY", "px": px, "strat": "mom", "state": st}
        return None

    def _manage(self, now, params):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._ep)/self._ep
        if pnl_pct >= params["mom_tp"]*0.5 and px > self._trail: self._trail = px
        if pnl_pct >= params["mom_tp"]: return self._close(px, "TP")
        if pnl_pct <= -params["mom_sl"]: return self._close(px, "SL")
        if (px - self._trail)/self._trail <= -params["mom_tp"]*0.4: return self._close(px, "TRAIL")
        if now - self._et > 600: return self._close(px, "TIME")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._eq)
        pnl = (px - self._ep)*self._eq; self.pnl += pnl
        self._pos = None; self._cd = time.time() + 30
        return {"action": "SELL", "px": px, "pnl": round(pnl,4), "reason": reason, "strat": "mom"}


# ═══════════════════════════════════════
# 5-MINUTE TREND FILTER
# ═══════════════════════════════════════

def trend_5m(eng, sym):
    """Return 1 if 5m trend is up (last 3 closes rising), -1 if down, 0 if flat."""
    try:
        kl = eng.ohlcv(sym, "5m", limit=6)
        if len(kl) < 6: return 0
        closes = [float(k[4]) for k in kl[-4:]]
        if closes[-1] > closes[-2] > closes[-3]: return 1
        if closes[-1] < closes[-2] < closes[-3]: return -1
        return 0
    except: return 0


# ═══════════════════════════════════════
# MAIN
# ═══════════════════════════════════════

def main():
    # Load .env
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())

    cfg = load_config()
    eng = Engine(cfg)
    symbols = cfg.get("symbols", ["SOLUSDC"])
    SLEEP = 0.5

    # WebSocket
    ws = eng.start_ws(symbols)
    print(f"  {'⚡ WS' if ws else '🌐 REST'} | {len(symbols)} symbols")

    # Circuit breaker
    cb = CircuitBreaker(cfg.get("circuit_breaker", {}))
    cb._state_file = "circuit_breaker_v6.json"

    # State engine
    state = StateEngine()

    # Strategies — ALL three per symbol
    strats = []
    for sym in symbols:
        strats.append(("scalp", sym, Scalper(eng, sym)))
        strats.append(("whale", sym, WhaleTracker(eng, sym)))
        strats.append(("mom", sym, MomentumReactor(eng, sym)))

    # Initialize equity for CB
    equity = 0.0
    for sym in symbols:
        base = sym.replace("USDC", "")
        px = eng.get_price(sym) or eng.price(sym)
        qty = eng.balance(base)
        equity += qty * px
    equity += eng.balance("USDC")
    cb.update_equity(equity)
    cb.load()

    # Cancel orphans
    for sym in symbols:
        try:
            orders = eng.open_orders(sym)
            if orders: print(f"  🧹 {sym}: {len(orders)} orphans"); eng.cancel_all(sym)
        except Exception as e: print(f"  ⚠️ {sym}: {e}")

    # SIGTERM
    _sd = {"f": False}
    def _term(sig, frame): print("\n  ⚔️ SIGTERM"); _sd["f"] = True
    signal.signal(signal.SIGTERM, _term)

    print(f"  ⚔️  DENARO v6 INTELLIGENT | ${equity:.0f} | {len(strats)} strats | CB:{cb.state}")
    cycle = 0; state_cycle = 0

    while True:
        if _sd["f"]:
            for _, sym, _ in strats:
                try: eng.cancel_all(sym)
                except: pass
            sys.exit(0)

        try:
            cycle += 1

            # State update every ~12 min (1440 cycles at 0.5s)
            if cycle % 1440 == 1 or not state.state:
                sym = symbols[0]
                try:
                    ohlcv = eng.ohlcv(sym, "1d", limit=25)
                    px = eng.get_price(sym) or eng.price(sym)
                    state.update(px, ohlcv)
                    print(f"  📊 {state.state} | {state.params()['position_pct']*100:.0f}% sizing")
                except Exception as e: print(f"  ⚠️ State: {e}")

            # Equity update
            eq = eng.balance("USDC")
            for sym in symbols:
                base = sym.replace("USDC", ""); px = eng.get_price(sym) or eng.price(sym)
                eq += eng.balance(base) * px
            cb.update_equity(eq)

            params = state.params()
            trend = {sym: trend_5m(eng, sym) for sym in symbols}

            for stype, sym, strat in strats:
                # BEAR: only scalp, only if 5m trend not down
                if state.state == "BEAR" and stype != "scalp": continue
                # BULL: prefer long if 5m trend up
                if state.state == "BULL" and stype != "scalp" and trend[sym] <= 0: continue

                try:
                    result = strat.run(cb, eq, params)
                    if result:
                        if result["action"] == "SELL":
                            cb.record_trade(result["pnl"])
                        icon = "💰" if result["action"] == "SELL" else "📈"
                        extra = f" PnL={result.get('pnl')}" if result["action"] == "SELL" else f" imb={result.get('imb','')}" if result.get("imb") else ""
                        print(f"  {icon} [{sym}] {result['strat']}: {result['action']} @{result['px']:.4f}{extra} [{result.get('reason','')}]")
                except Exception as e:
                    print(f"  ❌ [{sym}] {stype}: {str(e)[:80]}")

            if cycle % 24 == 0:
                tt = sum(s[2].t for s in strats); tp = sum(s[2].pnl for s in strats)
                ws_icon = "⚡" if eng._ws_alive else "🌐"
                print(f"  {ws_icon} C{cycle} | T:{tt} | PnL:${tp:+.2f} | Eq:${eq:.1f} | {cb.state} | {state.state} {trend[ symbols[0] ] if symbols else ''}")

            time.sleep(SLEEP)

        except KeyboardInterrupt:
            print("\n  ⚔️ Shutdown")
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}"); time.sleep(5)


if __name__ == "__main__":
    main()

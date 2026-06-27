"""
Denaro v6 — Unified War Machine.
Best of v3 (CircuitBreaker) + v5 (WSEngine, StateEngine, Strategies).
Single file, sync, zero-frills. Makes money or dies trying.
"""
import json, os, sys, time, signal, hashlib, hmac, math, threading
from datetime import datetime
from typing import Dict, Optional, Tuple
from urllib.parse import urlencode

# ── Optional WebSocket (pip install websocket-client) ──
try:
    import websocket
    HAS_WS = True
except ImportError:
    HAS_WS = False

import requests


# ═══════════════════════════════════════════════════════════════
# CONFIG
# ═══════════════════════════════════════════════════════════════

def load_config(path="config/v6_config.json"):
    with open(os.path.join(os.path.dirname(__file__), path)) as f:
        return json.load(f)


# ═══════════════════════════════════════════════════════════════
# BINANCE ENGINE (sync REST)
# ═══════════════════════════════════════════════════════════════

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

    def _sign(self, p: dict) -> dict:
        p["timestamp"] = int(time.time() * 1000)
        qs = urlencode(p)
        p["signature"] = hmac.new(self.secret, qs.encode(), hashlib.sha256).hexdigest()
        return p

    def _get(self, ep, params=None, signed=False):
        params = params or {}
        if signed: params = self._sign(params)
        r = self.ses.get(f"{self.base}{ep}", params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _post(self, ep, params, signed=True):
        if signed: params = self._sign(params)
        r = self.ses.post(f"{self.base}{ep}", data=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def _delete(self, ep, params, signed=True):
        if signed: params = self._sign(params)
        r = self.ses.delete(f"{self.base}{ep}", params=params, timeout=self._timeout)
        r.raise_for_status()
        return r.json()

    def price(self, sym): return float(self._get("/api/v3/ticker/price", {"symbol": sym})["price"])
    def balance(self, asset):
        d = self._get("/api/v3/account", signed=True)
        for b in d["balances"]:
            if b["asset"] == asset: return float(b["free"])
        return 0.0
    def imbalance(self, sym, limit=20):
        d = self._get("/api/v3/depth", {"symbol": sym, "limit": limit})
        bids = sum(float(b[1]) for b in d["bids"])
        asks = sum(float(a[1]) for a in d["asks"])
        return bids / asks if asks > 0 else float('inf')
    def market_buy(self, sym, qty):
        return self._post("/api/v3/order", {"symbol": sym, "side": "BUY", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def market_sell(self, sym, qty):
        return self._post("/api/v3/order", {"symbol": sym, "side": "SELL", "type": "MARKET", "quantity": f"{qty:.6f}"})
    def open_orders(self, sym):
        return self._get("/api/v3/openOrders", {"symbol": sym}, signed=True)
    def cancel_order(self, sym, oid):
        return self._delete("/api/v3/order", {"symbol": sym, "orderId": oid})
    def cancel_all(self, sym):
        for o in self.open_orders(sym):
            self.cancel_order(sym, o["orderId"])
    def ohlcv(self, sym, interval="5m", limit=30):
        return self._get("/api/v3/klines", {"symbol": sym, "interval": interval, "limit": limit})

    # Price cache (filled by WS or REST)
    _prices: Dict[str, float] = {}
    _lock = threading.Lock()
    _ws_alive = False

    def get_price(self, sym):
        with self._lock:
            return self._prices.get(sym, 0.0)

    def start_ws(self, symbols):
        if not HAS_WS: return False
        streams = "/".join(f"{s.lower()}@ticker" for s in symbols)
        url = f"wss://stream.binance.com:9443/stream?streams={streams}"

        def _on_msg(ws, msg):
            try:
                data = json.loads(msg).get("data", {})
                sym = data.get("s", "")
                px = float(data.get("c", 0))
                if sym and px:
                    with self._lock:
                        self._prices[sym] = px
            except Exception:
                pass

        def _on_open(ws):
            self._ws_alive = True

        def _run():
            ws = websocket.WebSocketApp(url, on_message=_on_msg, on_open=_on_open)
            ws.run_forever(reconnect=5)

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        time.sleep(1)
        return True


# ═══════════════════════════════════════════════════════════════
# CIRCUIT BREAKER (from v3)
# ═══════════════════════════════════════════════════════════════

class CircuitBreaker:
    CLOSED, HALF_OPEN, OPEN = "CLOSED", "HALF_OPEN", "OPEN"

    def __init__(self, config: dict):
        self.max_consecutive_losses = config.get("cb_max_consecutive_losses", 3)
        self.max_daily_drawdown_pct = config.get("cb_max_daily_drawdown_pct", 3.0)
        self.max_total_drawdown_pct = config.get("cb_max_total_drawdown_pct", 5.0)
        self.half_open_scale = config.get("cb_half_open_scale", 0.5)
        self.state = self.CLOSED
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._peak_equity = 0.0
        self._current_equity = 0.0
        self._trades: list = []
        self._state_file = config.get("cb_state_file", "circuit_breaker.json")

    def update_equity(self, equity: float):
        self._current_equity = equity
        if equity > self._peak_equity:
            self._peak_equity = equity

    def record_trade(self, pnl: float):
        self._trades.append({"pnl": pnl, "ts": time.time()})
        self._daily_pnl += pnl
        if pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0
        self._update_state()
        self._save()

    def can_trade(self, amount: float) -> Tuple[bool, str, float]:
        if self.state == self.CLOSED:
            return True, "CLOSED", amount
        elif self.state == self.HALF_OPEN:
            return True, "HALF_OPEN", amount * self.half_open_scale
        return False, "OPEN", 0.0

    def _update_state(self):
        total_drawdown = (self._peak_equity - self._current_equity) / self._peak_equity * 100 if self._peak_equity > 0 else 0
        daily_drawdown = abs(self._daily_pnl) / self._peak_equity * 100 if self._peak_equity > 0 else 0

        if total_drawdown >= self.max_total_drawdown_pct or daily_drawdown >= self.max_daily_drawdown_pct:
            self.state = self.OPEN
        elif self._consecutive_losses >= self.max_consecutive_losses:
            self.state = self.HALF_OPEN
        else:
            self.state = self.CLOSED

    def _save(self):
        try:
            with open(self._state_file, "w") as f:
                json.dump({"state": self.state, "consecutive_losses": self._consecutive_losses,
                           "daily_pnl": self._daily_pnl, "peak_equity": self._peak_equity,
                           "current_equity": self._current_equity}, f)
        except Exception:
            pass

    def load(self):
        try:
            with open(self._state_file) as f:
                d = json.load(f)
                self.state = d.get("state", self.CLOSED)
                self._consecutive_losses = d.get("consecutive_losses", 0)
                self._peak_equity = d.get("peak_equity", 0)
                self._daily_pnl = d.get("daily_pnl", 0)
        except FileNotFoundError:
            pass


# ═══════════════════════════════════════════════════════════════
# STATE ENGINE (from v5)
# ═══════════════════════════════════════════════════════════════

class StateEngine:
    BULL, BEAR, SIDEWAYS = "BULL", "BEAR", "SIDEWAYS"

    def __init__(self, lookback_days=20, threshold_pct=5.0):
        self.lookback = lookback_days
        self.threshold = threshold_pct
        self.state = ""
        self._history = []

    def update(self, current_price: float, ohlcv: list) -> dict:
        if ohlcv and len(ohlcv) >= self.lookback:
            past_price = float(ohlcv[-self.lookback][4])
            change = (current_price - past_price) / past_price
            if change > self.threshold / 100:
                self.state = self.BULL
            elif change < -self.threshold / 100:
                self.state = self.BEAR
            else:
                self.state = self.SIDEWAYS
        return {"state": self.state, "change_pct": round((current_price / float(ohlcv[-1][4]) - 1) * 100, 2) if ohlcv else 0}

    def strategy_signal(self) -> dict:
        if self.state == self.BEAR:
            return {"primary": "defensive", "scalper": True, "whale": False, "momentum": False, "grid": False}
        elif self.state == self.BULL:
            return {"primary": "aggressive", "scalper": True, "whale": True, "momentum": True, "grid": False}
        return {"primary": "grid", "scalper": True, "whale": True, "momentum": True, "grid": True}


# ═══════════════════════════════════════════════════════════════
# STRATEGIES
# ═══════════════════════════════════════════════════════════════

def _round_qty(qty: float) -> float:
    if qty > 100:    return math.floor(qty)
    elif qty > 1:    return math.floor(qty * 100) / 100
    elif qty > 0.01: return math.floor(qty * 10000) / 10000
    else:            return math.floor(qty * 1000000) / 1000000


class Scalper:
    def __init__(self, eng: Engine, sym: str, capital: float):
        self.eng = eng; self.sym = sym; self.capital = capital
        self.t = 0; self.pnl = 0.0
        self._pos = None; self._entry_price = 0.0; self._entry_qty = 0.0; self._entry_time = 0.0
        self._high = 0.0; self._cooldown = 0.0

    def run(self, cb: CircuitBreaker) -> Optional[dict]:
        now = time.time()
        if self._pos: return self._manage(now)
        if now < self._cooldown: return None
        px = self.eng.get_price(self.sym) or (self.eng.price(self.sym) if not self.eng._ws_alive else 0)
        if not px: return None
        if px > self._high or self._high == 0: self._high = px
        if now - getattr(self, '_reset_high', 0) > 60:
            self._high = px; self._reset_high = now
        drop = (self._high - px) / self._high
        if drop >= 0.008:
            qty = _round_qty(self.capital * 0.5 / px)
            ok, _, amt = cb.can_trade(qty * px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._entry_price = px; self._entry_qty = qty; self._entry_time = now
                self.t += 1
                return {"action": "BUY", "price": px, "qty": qty, "strategy": "scalper"}
        return None

    def _manage(self, now):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._entry_price) / self._entry_price
        if pnl_pct >= 0.004: return self._close(px, "TP")
        if pnl_pct <= -0.02: return self._close(px, "SL")
        if now - self._entry_time > 120: return self._close(px, "TIMEOUT")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._entry_qty)
        pnl = (px - self._entry_price) * self._entry_qty
        self.pnl += pnl; self._pos = None; self._cooldown = time.time() + 30; self._high = 0
        return {"action": "SELL", "price": px, "pnl": round(pnl, 4), "reason": reason, "strategy": "scalper"}


class WhaleTracker:
    def __init__(self, eng: Engine, sym: str, capital: float):
        self.eng = eng; self.sym = sym; self.capital = capital
        self.t = 0; self.pnl = 0.0
        self._pos = None; self._entry_price = 0.0; self._entry_qty = 0.0; self._entry_time = 0.0
        self._cooldown = 0.0

    def run(self, cb: CircuitBreaker) -> Optional[dict]:
        now = time.time()
        if self._pos: return self._manage(now)
        if now < self._cooldown: return None
        try:
            imb = self.eng.imbalance(self.sym, 20)
        except Exception:
            return None
        if imb >= 3.0:
            px = self.eng.get_price(self.sym) or self.eng.price(self.sym)
            if not px: return None
            qty = _round_qty(self.capital * 0.3 / px)
            ok, _, _ = cb.can_trade(qty * px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._entry_price = px; self._entry_qty = qty; self._entry_time = now
                self.t += 1
                return {"action": "BUY", "price": px, "reason": f"imb={imb:.1f}", "strategy": "whale"}
        return None

    def _manage(self, now):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._entry_price) / self._entry_price
        if pnl_pct >= 0.008: return self._close(px, "TP")
        if pnl_pct <= -0.015: return self._close(px, "SL")
        if now - self._entry_time > 180: return self._close(px, "TIMEOUT")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._entry_qty)
        pnl = (px - self._entry_price) * self._entry_qty
        self.pnl += pnl; self._pos = None; self._cooldown = time.time() + 20
        return {"action": "SELL", "price": px, "pnl": round(pnl, 4), "reason": reason, "strategy": "whale"}


class MomentumReactor:
    def __init__(self, eng: Engine, sym: str, capital: float):
        self.eng = eng; self.sym = sym; self.capital = capital
        self.t = 0; self.pnl = 0.0
        self._pos = None; self._entry_price = 0.0; self._entry_qty = 0.0; self._entry_time = 0.0
        self._cooldown = 0.0; self._last_px = 0.0; self._pumps = 0

    def run(self, cb: CircuitBreaker) -> Optional[dict]:
        now = time.time()
        if self._pos: return self._manage(now)
        if now < self._cooldown: return None
        px = self.eng.get_price(self.sym) or self.eng.price(self.sym)
        if not px: return None
        if self._last_px > 0:
            change = (px - self._last_px) / self._last_px
            if change > 0.01: self._pumps += 1
            else: self._pumps = 0
        self._last_px = px
        if self._pumps >= 2:
            qty = _round_qty(self.capital * 0.25 / px)
            ok, _, _ = cb.can_trade(qty * px)
            if not ok or qty == 0: return None
            r = self.eng.market_buy(self.sym, qty)
            if r and "orderId" in r:
                self._pos = "LONG"; self._entry_price = px; self._entry_qty = qty; self._entry_time = now
                self._pumps = 0; self.t += 1
                return {"action": "BUY", "price": px, "reason": "momentum_pump", "strategy": "momentum"}
        return None

    def _manage(self, now):
        px = self.eng.get_price(self.sym)
        if not px: return None
        pnl_pct = (px - self._entry_price) / self._entry_price
        if pnl_pct >= 0.015: return self._close(px, "TP")
        if pnl_pct <= -0.02: return self._close(px, "SL")
        if now - self._entry_time > 600: return self._close(px, "TIMEOUT")
        return None

    def _close(self, px, reason):
        self.eng.market_sell(self.sym, self._entry_qty)
        pnl = (px - self._entry_price) * self._entry_qty
        self.pnl += pnl; self._pos = None; self._cooldown = time.time() + 300
        return {"action": "SELL", "price": px, "pnl": round(pnl, 4), "reason": reason, "strategy": "momentum"}


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # Load .env into os.environ (systemd doesn't source it)
    _env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(_env_path):
        with open(_env_path) as _f:
            for _line in _f:
                _line = _line.strip()
                if _line and not _line.startswith("#") and "=" in _line:
                    _k, _v = _line.split("=", 1)
                    os.environ.setdefault(_k.strip(), _v.strip())

    cfg = load_config()
    eng = Engine(cfg)
    total = float(cfg.get("total_capital", 70))
    symbols = cfg.get("symbols", ["SOLUSDC"])
    SLEEP = 0.5

    # WebSocket price feed
    ws_started = eng.start_ws(symbols)
    if ws_started:
        print("  ⚡ WebSocket active")
    else:
        print("  🌐 REST-only mode")

    # Circuit breaker
    cb_cfg = cfg.get("circuit_breaker", {})
    cb_cfg["cb_state_file"] = "circuit_breaker_v6.json"
    cb = CircuitBreaker(cb_cfg)
    cb.load()

    # State engine
    state = StateEngine()

    # Strategies
    strats = []
    for sym in symbols:
        pool = total / len(symbols) / 3
        strats.append(("scalper", sym, Scalper(eng, sym, cfg.get("scalper_capital", pool * 0.40))))
        strats.append(("whale", sym, WhaleTracker(eng, sym, cfg.get("whale_capital", pool * 0.30))))
        strats.append(("momentum", sym, MomentumReactor(eng, sym, cfg.get("momentum_capital", pool * 0.30))))

    # Cancel orphans
    for sym in symbols:
        try:
            orders = eng.open_orders(sym)
            if orders:
                print(f"  🧹 Cancelling {len(orders)} orphaned orders for {sym}")
                eng.cancel_all(sym)
        except Exception as e:
            print(f"  ⚠️  Orphan cleanup {sym}: {e}")

    # SIGTERM handler
    _shutdown = {"flag": False}
    def _on_term(sig, frame):
        print("\n  ⚔️  SIGTERM — shutting down...")
        _shutdown["flag"] = True
    signal.signal(signal.SIGTERM, _on_term)

    print("=" * 50)
    print(f"  ⚔️  DENARO v6 — UNIFIED WAR MACHINE")
    print(f"  Capital: ${total:.0f} | {len(symbols)} symbols | {len(strats)} strategies")
    print(f"  CB: {cb.state} | State Engine: {state.lookback}d")
    print("=" * 50)

    cycle = 0
    while True:
        if _shutdown["flag"]:
            for _, sym, _ in strats:
                try: eng.cancel_all(sym)
                except: pass
            sys.exit(0)

        try:
            cycle += 1

            # State update (every ~12 min)
            if cycle % (1440 if SLEEP == 0.5 else 240) == 1 or not state.state:
                sym = symbols[0]
                try:
                    ohlcv = eng.ohlcv(sym, "1d", limit=25)
                    px = eng.get_price(sym) or eng.price(sym)
                    info = state.update(px, ohlcv)
                    sig = state.strategy_signal()
                    print(f"  📊 State: {state.state} | Signal: {sig['primary']} | "
                          f"Scalp={sig['scalper']} Whale={sig['whale']} Mom={sig['momentum']}")
                except Exception as e:
                    print(f"  ⚠️  State update: {e}")

            # Equity update (every cycle with WS prices)
            quote_balance = eng.balance("USDC")
            equity = quote_balance
            for sym in symbols:
                base = sym.replace("USDC", "")
                base_qty = eng.balance(base)
                px = eng.get_price(sym) or eng.price(sym)
                equity += base_qty * px
            cb.update_equity(equity)

            # Run strategies
            sig = state.strategy_signal()
            for stype, sym, strat in strats:
                if stype == "scalper" and not sig.get("scalper", True): continue
                if stype == "whale" and not sig.get("whale", True): continue
                if stype == "momentum" and not sig.get("momentum", True): continue

                try:
                    result = strat.run(cb)
                    if result:
                        if "SELL" in str(result.get("action", "")):
                            pnl_val = result.get("pnl", 0)
                            cb.record_trade(pnl_val)
                        tag = "💰" if result.get("action") == "SELL" else "📈"
                        print(f"  {tag} [{sym}] {result['strategy']}: {result['action']} "
                              f"@{result.get('price', 0):.4f} "
                              f"{result.get('reason', '')} "
                              f"{'PnL=' + str(result.get('pnl', '')) if result.get('action') == 'SELL' else ''}")
                except Exception as e:
                    print(f"  ❌ [{sym}] {stype}: {str(e)[:80]}")

            # Status line
            if cycle % 24 == 0:
                tt = sum(s[2].t for s in strats)
                tp = sum(s[2].pnl for s in strats)
                ws_icon = "⚡" if eng._ws_alive else "🌐"
                print(f"  {ws_icon} C{cycle} | Trades:{tt} | PnL:${tp:+.2f} | "
                      f"Eq:${equity:.1f} | CB:{cb.state} | {state.state}")

            time.sleep(SLEEP)

        except KeyboardInterrupt:
            print("\n  ⚔️  Shutting down...")
            break
        except Exception as e:
            print(f"  ! {str(e)[:80]}")
            time.sleep(5)


if __name__ == "__main__":
    main()

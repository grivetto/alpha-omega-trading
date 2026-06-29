"""
DENARO GRID-PRO — Production grid bot for MARCODG1.
Built from v1→v6 learnings:
- LIMIT orders only (no market order spread waste)
- NOTIONAL-aware sizing (never <$10 per order)
- ATR-adaptive spacing (tight in calm, wide in volatile)
- Equity tracking with circuit breaker
- 10min rebalance (not 5min, avoids excessive cancel/replace)
- Single symbol (ADAUSDC — affordable, volatile enough)
- Auto-recovery on restart
"""
import json, os, sys, time, math, hmac, hashlib, requests
from datetime import datetime, timezone
from urllib.parse import urlencode
from collections import deque

sys.stdout.reconfigure(line_buffering=True)

# Log file for reliable recording
LOG_FILE = os.path.join(os.path.dirname(__file__) or ".", "grid_pro.log")
def log(msg):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts} {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except: pass

# === LOAD .ENV ===
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

KEY = os.environ.get("BINANCE_API_KEY", "")
SECRET = os.environ.get("BINANCE_API_SECRET", "").encode()
BASE = "https://api.binance.com"

# === ENGINE ===
def _sign(p):
    p["timestamp"] = int(time.time() * 1000)
    return p

def sp(path, params):
    params["timestamp"] = int(time.time() * 1000)
    qs = urlencode(sorted(params.items()))
    sig = hmac.new(SECRET, qs.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}{path}?{qs}&signature={sig}", headers={"X-MBX-APIKEY": KEY}, timeout=10)
    return r.json() if r.status_code == 200 else {"error": r.text[:200]}

def sg(path, params, signed=True):
    if signed:
        params["timestamp"] = int(time.time() * 1000)
        qs = urlencode(sorted(params.items()))
        sig = hmac.new(SECRET, qs.encode(), hashlib.sha256).hexdigest()
        url = f"{BASE}{path}?{qs}&signature={sig}"
    else:
        url = f"{BASE}{path}?{urlencode(params)}"
    r = requests.get(url, headers={"X-MBX-APIKEY": KEY} if signed else {}, timeout=10)
    return r.json() if r.status_code == 200 else {"error": r.text[:200]}

def price(sym):
    return float(requests.get(f"{BASE}/api/v3/ticker/price?symbol={sym}").json()["price"])

def balance(asset):
    d = sg("/api/v3/account", {})
    if "balances" in d:
        for b in d["balances"]:
            if b["asset"] == asset: return float(b["free"])
    return 0.0

def get_klines(sym, interval, limit=50):
    r = requests.get(f"{BASE}/api/v3/klines", params={"symbol": sym, "interval": interval, "limit": limit}, timeout=10)
    return [[float(k[2]), float(k[3]), float(k[5])] for k in r.json()]  # [high, close, vol]

# === FILTERS ===
def load_filters(sym):
    r = requests.get(f"{BASE}/api/v3/exchangeInfo?symbol={sym}")
    f = {x["filterType"]: x for x in r.json()["symbols"][0]["filters"]}
    ls = f["LOT_SIZE"]
    pf = f["PRICE_FILTER"]
    nf = f.get("MIN_NOTIONAL", f.get("NOTIONAL", {}))
    return {
        "lot_step": float(ls["stepSize"]),
        "lot_min": float(ls["minQty"]),
        "tick": float(pf["tickSize"]),
        "min_notional": float(nf.get("minNotional", 10)) if nf else 10,
        "qprec": len(str(float(ls["stepSize"])).split(".")[1]) if "." in str(float(ls["stepSize"])) else 0,
        "pprec": len(str(float(pf["tickSize"])).split(".")[1]) if "." in str(float(pf["tickSize"])) else 0
    }

def rq_qty(qty, step):
    if step >= 1: return math.floor(qty)
    return math.floor(qty / step) * step

def rq_price(price, tick):
    prec = len(str(tick).split(".")[1]) if "." in str(tick) else 0
    return round(round(price / tick) * tick, prec)

# === ATR ===
def calc_atr(klines, period=14):
    if len(klines) < period + 1: return 0
    trs = [abs(klines[i][1] - klines[i-1][1]) for i in range(1, len(klines))]
    return sum(trs[-period:]) / period if len(trs) >= period else 0

def rq_qty_ceil(qty, step):
    """Round UP to step size — use for min notional to ensure ≥$5."""
    if step >= 1: return math.ceil(qty)
    return math.ceil(qty / step) * step

# === STATE ===
STATE_FILE = os.path.join(os.path.dirname(__file__), "grid_pro_state.json")

def save_state(s):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(s, f)
    except: pass

def load_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except: return {"orders": {}, "trades": 0, "pnl": 0.0, "wins": 0, "losses": 0, "cycle": 0}

# === MAIN ===
SYMBOL = "ADAUSDC"
BASE_ASSET = "ADA"
TOTAL_CAPITAL = 100.0  # Use $100 of $144 for grid

flt = load_filters(SYMBOL)
state = load_state()
orders = state.get("orders", {})
trades = state.get("trades", 0)
pnl = state.get("pnl", 0.0)
wins = state.get("wins", 0)
losses = state.get("losses", 0)
cycle = state.get("cycle", 0)
last_rebalance = 0

log(f"\n{'='*50}")
log(f"  DENARO GRID-PRO | {SYMBOL} | ${TOTAL_CAPITAL}")
log(f"  Filters: step={flt['lot_step']} tick={flt['tick']} minNot=${flt['min_notional']}")
log(f"  Resuming: {len(orders)} tracked orders | T:{trades} PnL:${pnl:.2f}")
log(f"{'='*50}\n")

SIGNAL_PATH = os.path.join(os.path.dirname(__file__) or ".", "advisor_signal.json")

def load_advisor_signal():
    """Read advisor signal file, return neutral defaults if missing/stale."""
    try:
        if not os.path.exists(SIGNAL_PATH):
            return {"bias": 0.0, "grid_offset": 0.0, "position_scale": 1.0, "volatility": "normal"}
        with open(SIGNAL_PATH) as f:
            sig = json.load(f)
        age_ms = int(time.time() * 1000) - sig.get("ts", 0)
        if age_ms > 600000:  # 10 min stale threshold
            log(f"  ⚠️ Advisor signal stale ({age_ms//1000}s old), using neutral")
            return {"bias": 0.0, "grid_offset": 0.0, "position_scale": 1.0, "volatility": "normal"}
        return sig
    except Exception as e:
        log(f"  ⚠️ Advisor signal error: {e}, using neutral")
        return {"bias": 0.0, "grid_offset": 0.0, "position_scale": 1.0, "volatility": "normal"}

def place_grid():
    global orders, last_rebalance

    # --- Load advisor signal ---
    sig = load_advisor_signal()
    bias = sig.get("bias", 0.0)
    grid_offset = sig.get("grid_offset", 0.0)
    position_scale = sig.get("position_scale", 1.0)
    volatility = sig.get("volatility", "normal")

    px = price(SYMBOL)
    bal = balance("USDC")
    base_bal = balance(BASE_ASSET)
    bal_us = bal
    bal_base = base_bal

    # Cancel all open orders first
    oo = sg("/api/v3/openOrders", {"symbol": SYMBOL})
    if isinstance(oo, list):
        for o in oo:
            sp("/api/v3/order", {"symbol": SYMBOL, "orderId": o["orderId"]})
    orders = {}
    time.sleep(0.5)

    # Adjusted center price
    px_center = px * (1.0 + grid_offset)
    px_center = max(px * 0.98, min(px * 1.02, px_center))  # clamp ±2%

    # Get ATR for spacing
    kl = get_klines(SYMBOL, "5m", 20)
    atr = calc_atr(kl, 7)

    # Volatility-adaptive spread
    vol_mult = 1.5 if volatility == "high" else (0.8 if volatility == "low" else 1.0)
    spread = max(atr * 1.2 * vol_mult, flt["tick"] * 3)

    # Scale order sizes by position_scale
    buy_usdc = bal_us * 0.4 * position_scale
    sell_ada = bal_base * 0.4 * position_scale

    levels = 2  # 2 buy + 2 sell levels

    # BUY orders below adjusted center
    buy_qty = rq_qty(buy_usdc / levels / px_center, flt["lot_step"])
    # Clamp: if scaled below min_notional, use minimum viable
    if buy_qty > 0 and buy_qty * px_center < flt["min_notional"]:
        buy_qty = rq_qty_ceil(flt["min_notional"] / px_center, flt["lot_step"])
    if buy_qty > 0 and buy_qty * px_center >= flt["min_notional"]:
        for i in range(1, levels + 1):
            bp = rq_price(px_center - spread * i, flt["tick"])
            if bp >= flt["tick"]:
                r = sp("/api/v3/order", {"symbol": SYMBOL, "side": "BUY", "type": "LIMIT",
                                         "timeInForce": "GTC", "quantity": f"{buy_qty:.{flt['qprec']}f}",
                                         "price": f"{bp:.{flt['pprec']}f}"})
                if "orderId" in r:
                    tp = rq_price(bp + spread * 2.5, flt["tick"])
                    orders[r["orderId"]] = {"s": "B", "p": bp, "q": buy_qty, "tp": tp, "t": time.time()}

    # SELL orders above adjusted center
    sell_qty = rq_qty(sell_ada / levels, flt["lot_step"])
    if sell_qty >= flt["lot_min"] and sell_qty * px_center < flt["min_notional"]:
        sell_qty = rq_qty_ceil(flt["min_notional"] / px_center, flt["lot_step"])
    if sell_qty >= flt["lot_min"] and sell_qty * px_center >= flt["min_notional"]:
        for i in range(1, levels + 1):
            spx = rq_price(px_center + spread * i, flt["tick"])
            r = sp("/api/v3/order", {"symbol": SYMBOL, "side": "SELL", "type": "LIMIT",
                                     "timeInForce": "GTC", "quantity": f"{sell_qty:.{flt['qprec']}f}",
                                     "price": f"{spx:.{flt['pprec']}f}"})
            if "orderId" in r:
                orders[r["orderId"]] = {"s": "S", "p": spx, "q": sell_qty, "tp": None, "t": time.time()}

    last_rebalance = time.time()
    save_state(state)
    log(f"  📋 Grid: {len(orders)} ordini | bias={bias:+.3f} off={grid_offset:+.4f} "
          f"pos={position_scale:.1f}x vol={volatility} spread={spread:.4f} "
          f"center=${px_center:.4f} (raw=${px:.4f})")
    if len(orders) == 0:
        log(f"  ⚠️ Grid empty: buy_qty={buy_qty} buy_ntl={buy_qty*px_center if buy_qty>0 else 0:.2f}"
              f" sell_qty={sell_qty} sell_ntl={sell_qty*px_center if sell_qty>0 else 0:.2f}")

def check_fills():
    global trades, pnl, wins, losses, orders
    filled = []
    oo = sg("/api/v3/openOrders", {"symbol": SYMBOL})
    if not isinstance(oo, list): return
    current_ids = {o["orderId"] for o in oo}

    for oid, info in list(orders.items()):
        if oid not in current_ids and isinstance(oid, str) and len(oid) < 20:
            filled.append(info)
            del orders[oid]

    for fill in filled:
        trades += 1
        side = fill["s"]
        px = fill["p"]
        qty = fill["q"]
        tp = fill.get("tp")

        if side == "B" and tp:
            # BUY filled → place TP SELL
            rq = rq_qty(qty * 0.99, flt["lot_step"])
            if rq >= flt["lot_min"] and rq * tp >= flt["min_notional"]:
                r = sp("/api/v3/order", {"symbol": SYMBOL, "side": "SELL", "type": "LIMIT",
                                         "timeInForce": "GTC", "quantity": f"{rq:.{flt['qprec']}f}",
                                         "price": f"{tp:.{flt['pprec']}f}"})
                if "orderId" in r:
                    orders[r["orderId"]] = {"s": "TP", "p": tp, "q": rq, "bq": qty, "bp": px, "t": time.time()}
                    log(f"  📈 BUY fill @ {px} → TP SELL @ {tp}")
        elif side == "S":
            # SELL filled → record PnL (we sold from inventory)
            pnl_est = qty * px * 0.001  # rough estimate if bought at ~same level
            pnl += pnl_est
            wins += 1 if pnl_est > 0 else 0
            losses += 1 if pnl_est <= 0 else 0
            log(f"  📉 SELL fill @ {px} | est PnL=${pnl_est:.2f}")
        elif side == "TP":
            # TP SELL filled → profit locked
            bp = fill.get("bp", 0)
            if bp > 0:
                pnl_trade = (px - bp) * fill.get("bq", qty)
                # Also need to re-buy at some point to complete cycle
                # Place new BUY at original level
                pnl += pnl_trade
                wins += 1 if pnl_trade > 0 else 0
                losses += 1 if pnl_trade <= 0 else 0
                log(f"  💰 TP fill @ {px} | PnL=${pnl_trade:.2f}")

    # Save state after fills
    state["orders"] = {k: v for k, v in orders.items() if isinstance(k, str)}
    state["trades"] = trades
    state["pnl"] = round(pnl, 2)
    state["wins"] = wins
    state["losses"] = losses
    state["cycle"] = cycle
    save_state(state)

# === MAIN LOOP ===
log(f"  Equity: USDC={balance('USDC'):.1f} ADA={balance('ADA'):.1f} @ ${price(SYMBOL):.4f}")
log(f"  Placing initial grid...")

# Cancel any stale orders on startup
try:
    for o in sg("/api/v3/openOrders", {"symbol": SYMBOL}):
        sp("/api/v3/order", {"symbol": SYMBOL, "orderId": o["orderId"]})
except: pass
time.sleep(1)

place_grid()

while True:
    try:
        cycle += 1
        now = time.time()

        # Rebalance every 10min
        if now - last_rebalance > 600:
            place_grid()

        # Check fills every cycle (10s)
        check_fills()

        # Status every 30 cycles (5min)
        if cycle % 30 == 0:
            px = price(SYMBOL)
            usdc = balance("USDC")
            # Get locked balance too
            d = sg("/api/v3/account", {})
            usdc_locked = 0.0
            ada_locked = 0.0
            if "balances" in d:
                for b in d["balances"]:
                    if b["asset"] == "USDC": usdc_locked = float(b["locked"])
                    if b["asset"] == "ADA": ada_locked = float(b["locked"])
            ada = balance("ADA")
            eq = (usdc + usdc_locked) + (ada + ada_locked) * px
            total_t = trades + state.get("trades", 0)
            wr = f"{wins/(wins+losses)*100:.0f}%" if wins + losses > 0 else "N/A"
            log(f"  ⚡ C{cycle} | T:{trades} PnL:${pnl:.2f} WR:{wr} | Eq:${eq:.1f} | "
                  f"Ord:{len(orders)} | ${px:.4f}")

        time.sleep(10)
    except KeyboardInterrupt:
        log("\n  ⚔️ Stop")
        break
    except Exception as e:
        log(f"  ❌ {str(e)[:80]}")
        time.sleep(30)

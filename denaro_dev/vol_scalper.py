"""
VOL-SCALPER: Volatility scalper for Nuvola dev.
Enters when 1min ATR > 1.5x rolling avg, exploits volatility expansion.
Goal: catch the move when volatility spikes, not predict direction.
"""
import json, os, sys, time, math, hmac, hashlib, requests
from datetime import datetime, timezone
from urllib.parse import urlencode
from collections import deque

# === ENGINE ===
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

def sp(path, params):
    params["timestamp"] = str(int(time.time() * 1000))
    q = urlencode(sorted(params.items()))
    sig = hmac.new(SECRET, q.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}{path}?{q}&signature={sig}",
                     headers={"X-MBX-APIKEY": KEY}, timeout=10)
    return r.json() if r.status_code == 200 else {"error": r.text[:200]}

def sg(path, params, signed=False):
    if signed:
        params["timestamp"] = str(int(time.time() * 1000))
        q = urlencode(sorted(params.items()))
        sig = hmac.new(SECRET, q.encode(), hashlib.sha256).hexdigest()
        url = f"{BASE}{path}?{q}&signature={sig}"
    else:
        url = f"{BASE}{path}?{urlencode(params)}"
    r = requests.get(url, headers={"X-MBX-APIKEY": KEY} if signed else {}, timeout=10)
    return r.json() if r.status_code == 200 else {"error": r.text[:200]}

def get_klines(sym, interval, limit=100):
    r = requests.get(f"{BASE}/api/v3/klines", params={"symbol": sym, "interval": interval, "limit": limit}, timeout=10)
    return [[float(k[2]), float(k[3]), int(k[0])] for k in r.json()]  # [high, close, time]

def load_filters(sym):
    r = requests.get(f"{BASE}/api/v3/exchangeInfo?symbol={sym}")
    f = {x["filterType"]: x for x in r.json()["symbols"][0]["filters"]}
    ls = f["LOT_SIZE"]
    pf = f["PRICE_FILTER"]
    notional = float(f.get("MIN_NOTIONAL", f.get("NOTIONAL", {})).get("minNotional", 5))
    return {
        "lot_step": float(ls["stepSize"]), "lot_min": float(ls["minQty"]),
        "tick": float(pf["tickSize"]), "min_notional": notional
    }

def rq(qty, step):
    if step >= 1: return math.floor(qty)
    return math.floor(qty / step) * step

def rp(price, tick):
    prec = len(str(tick).split(".")[1]) if "." in str(tick) else 0
    return round(round(price / tick) * tick, prec)

# === VOLATILITY SCALPER ===
SYMBOL = "DOGEUSDC"  # DOGE is cheaper, easier to get >$5 notional
CAPITAL = 5.0  # Test with $5

flt = load_filters(SYMBOL)
print(f"  Filters: lot_step={flt['lot_step']} min_notional=${flt['min_notional']} tick={flt['tick']}")

# Rolling ATR buffers
atr_1m = deque(maxlen=20)  # last 20 ATRs of 1min candles
pos = None  # {"qty":, "entry":, "time":, "sl":, "tp":}
trades = 0
pnl = 0.0
daily_trades = 0
last_hour = 0
cooldown_until = 0

def calc_atr(klines, period=14):
    if len(klines) < period + 1: return 0
    trs = []
    for i in range(1, len(klines)):
        tr = abs(klines[i][1] - klines[i-1][1])  # |close - prev_close|
        trs.append(tr)
    return sum(trs[-period:]) / period

def log(msg, fpath=None):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")
    if fpath:
        with open(fpath, "a") as f:
            f.write(json.dumps({"ts": ts, "msg": msg}) + "\n")

print(f"\n{'='*50}")
print(f"  VOL-SCALPER | {SYMBOL} | ${CAPITAL} test")
print(f"{'='*50}\n")

while True:
    try:
        now = time.time()
        hour = int(now / 3600)

        # Reset daily trade counter
        if hour % 24 == 0 and hour != last_hour:
            daily_trades = 0

        # === PHASE 1: Calculate volatility ===
        k1m = get_klines(SYMBOL, "1m", limit=15)
        k5m = get_klines(SYMBOL, "5m", limit=10)
        price = k1m[-1][1]
        atr_1m_val = calc_atr(k1m, 7)
        atr_5m_val = calc_atr(k5m, 7)
        atr_1m.append(atr_1m_val)
        avg_atr = sum(atr_1m) / len(atr_1m) if atr_1m else atr_1m_val

        # Volatility expansion ratio
        vol_ratio = atr_1m_val / avg_atr if avg_atr > 0 else 1

        # === PHASE 2: Entry logic ===
        if pos is None and now > cooldown_until and daily_trades < 5:
            # Entry condition: volatility expanding AND we're in a direction
            if vol_ratio > 1.5 and atr_1m_val > atr_5m_val * 0.5:
                # Check which direction: compare last 3 closes
                closes = [k[1] for k in k1m[-4:]]
                direction = 1 if closes[-1] > closes[0] else -1

                # Calculate min viable quantity (meet NOTIONAL)
                min_qty = rq(flt["min_notional"] / price, flt["lot_step"])
                qty = rq(min(CAPITAL / price * 0.8, CAPITAL / price), flt["lot_step"])
                qty = max(qty, min_qty)

                if qty > 0 and qty * price >= flt["min_notional"]:
                    spread = max(atr_1m_val * 1.5, price * 0.005)  # at least 0.5%
                    tp = rp(price + spread, flt["tick"])
                    sl = rp(price - spread * 0.6, flt["tick"])

                    r = sp("/api/v3/order", {
                        "symbol": SYMBOL, "side": "BUY", "type": "MARKET",
                        "quantity": f"{qty:.{8}f}"
                    })
                    if "orderId" in r:
                        pos = {"qty": qty, "entry": price, "time": now, "sl": sl, "tp": tp}
                        trades += 1; daily_trades += 1
                        log(f"📈 BUY {qty:.{8}f} @ ${price:.6f} | vol={vol_ratio:.1f}x TP=${tp:.6f} SL=${sl:.6f}")
                    else:
                        log(f"⚠️ BUY fail: {r.get('error', str(r)[:80])}")

        # === PHASE 3: Manage position ===
        if pos is not None:
            price = get_klines(SYMBOL, "1m", limit=1)[0][1]
            pnl_pct = (price - pos["entry"]) / pos["entry"]

            reason = None
            if price <= pos["sl"]:
                reason = "SL"
            elif price >= pos["tp"]:
                reason = "TP"
            elif now - pos["time"] > 600:  # 10min max
                reason = "TIME"
            # Trailing: if in profit >0.5%, trail SL up
            elif pnl_pct > 0.005:
                new_sl = max(pos["sl"], price * 0.995)
                if new_sl > pos["sl"]:
                    pos["sl"] = new_sl

            if reason:
                r = sp("/api/v3/order", {
                    "symbol": SYMBOL, "side": "SELL", "type": "MARKET",
                    "quantity": f"{pos['qty']:.{8}f}"
                })
                if "orderId" in r:
                    pnl_trade = (price - pos["entry"]) * pos["qty"]
                    pnl += pnl_trade
                    log(f"📉 SELL @ ${price:.6f} | PnL=${pnl_trade:.4f} | {reason}")
                    pos = None
                    cooldown_until = now + 120  # 2min cooldown

        # === PHASE 4: Status ===
        if int(now) % 300 < 10:  # every 5min
            pos_str = f"POS @ ${pos['entry']:.6f} SL=${pos['sl']:.6f} TP=${pos['tp']:.6f}" if pos else "NO POS"
            log(f"[STATUS] ${price:.6f} | vol_ratio={vol_ratio:.1f}x | T:{trades} PnL:${pnl:.2f} | {pos_str}")

    except Exception as e:
        log(f"❌ {str(e)[:80]}")

    time.sleep(30)

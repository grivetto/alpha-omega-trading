"""
MR-SOL: Mean Reversion strategy.
Buys SOL when RSI(1h) < 25, sells at +5% or RSI > 70.
Stop loss at -3%.
"""
import json, os, sys, time, math, hmac, hashlib, requests
from datetime import datetime, timezone
from urllib.parse import urlencode

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

def sg(path, params):
    params["timestamp"] = str(int(time.time() * 1000))
    q = urlencode(sorted(params.items()))
    sig = hmac.new(SECRET, q.encode(), hashlib.sha256).hexdigest()
    r = requests.get(f"{BASE}{path}?{q}&signature={sig}",
                     headers={"X-MBX-APIKEY": KEY}, timeout=10)
    return r.json()


# === UTILITIES ===
def calc_rsi(closes, period=14):
    if len(closes) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(-period, 0):
        ch = closes[i] - closes[i-1]
        gains.append(max(ch, 0))
        losses.append(max(-ch, 0))
    avg_g = sum(gains) / period
    avg_l = sum(losses) / period
    if avg_l == 0:
        return 100
    rs = avg_g / avg_l
    return 100 - (100 / (1 + rs))


def get_klines(sym, interval, limit=100):
    r = requests.get(f"{BASE}/api/v3/klines", params={"symbol": sym, "interval": interval, "limit": limit}, timeout=10)
    return [[float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[0])] for k in r.json()]


def signed_post(path, params):
    params["timestamp"] = str(int(time.time() * 1000))
    q = urlencode(sorted(params.items()))
    sig = hmac.new(SECRET, q.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}{path}?{q}&signature={sig}",
                      headers={"X-MBX-APIKEY": KEY}, timeout=10)
    return r.json()


def round_qty(qty):
    return math.floor(qty / 0.001) * 0.001  # SOL step size


# === MAIN LOOP ===
SYMBOL = "SOLUSDC"
CAPITAL = 50.0  # Use $50 of the $149 capital
POSITION = None  # None or {"qty": float, "entry": float, "time": float}
TRADES = 0
PNL = 0.0
LOG = []

def log(msg):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")
    LOG.append({"ts": ts, "msg": msg})
    with open(f"results/mr_sol_{datetime.now().strftime('%Y%m%d')}.json", "a") as f:
        f.write(json.dumps({"ts": ts, "msg": msg}) + "\n")


print(f"\n{'='*50}")
print(f"  MR-SOL Starting | {SYMBOL} | ${CAPITAL}")
print(f"{'='*50}\n")

while True:
    try:
        klines = get_klines(SYMBOL, "1h", limit=30)
        closes = [k[3] for k in klines]
        price = closes[-1]
        rsi = calc_rsi(closes, 14)
        high_14 = max(k[2] for k in klines[-14:])
        low_14 = min(k[1] for k in klines[-14:])

        now = time.time()

        if POSITION is None:
            # Check entry condition
            if rsi < 25 and price < low_14 * 1.02:
                qty = round_qty(CAPITAL / price)
                if qty > 0:
                    r = signed_post("/api/v3/order", {
                        "symbol": SYMBOL, "side": "BUY", "type": "MARKET",
                        "quantity": f"{qty:.3f}"
                    })
                    if "orderId" in r:
                        POSITION = {"qty": qty, "entry": price, "time": now, "stop": price * 0.97, "tp": price * 1.05}
                        TRADES += 1
                        log(f"📈 BUY {qty:.3f} SOL @ ${price:.2f} | RSI={rsi:.1f}")
                    else:
                        log(f"⚠️ BUY fail: {r.get('msg', str(r)[:80])}")
            elif rsi > 70:
                log(f"RSI={rsi:.1f} but no position (oversold entry at <25)")
        else:
            # Manage position
            pnl_pct = (price - POSITION["entry"]) / POSITION["entry"]

            # Update trailing stop
            if price > POSITION["entry"] * 1.02:
                new_stop = price * 0.98
                if new_stop > POSITION["stop"]:
                    POSITION["stop"] = new_stop

            # Exit conditions
            reason = None
            if price <= POSITION["stop"]:
                reason = "SL"
            elif price >= POSITION["tp"]:
                reason = "TP"
            elif now - POSITION["time"] > 86400:  # 24h max hold
                reason = "TIME"

            if reason:
                r = signed_post("/api/v3/order", {
                    "symbol": SYMBOL, "side": "SELL", "type": "MARKET",
                    "quantity": f"{POSITION['qty']:.3f}"
                })
                if "orderId" in r:
                    pnl = (price - POSITION["entry"]) * POSITION["qty"]
                    PNL += pnl
                    log(f"📉 SELL @ ${price:.2f} | PnL=${pnl:.2f} | {reason}")
                    POSITION = None
                else:
                    log(f"⚠️ SELL fail: {r.get('msg', str(r)[:80])}")

        # Status every 30min
        if int(now) % 1800 < 10:
            pos_str = f"POS: {POSITION['qty']:.3f} @ ${POSITION['entry']:.2f}" if POSITION else "NO POS"
            log(f"[STATUS] RSI={rsi:.1f} | ${price:.2f} | {pos_str} | T:{TRADES} PnL:${PNL:.2f}")

    except Exception as e:
        log(f"❌ {str(e)[:80]}")

    time.sleep(60)  # Check every 60s

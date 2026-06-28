"""
ML-PREDICTOR: Lightweight ML classifier for SOL direction.
Trains on last 500 1h candles, predicts if next close > current close.
If confidence > 55%, executes trade.
Runs every 1h.
"""
import json, os, sys, time, math, hmac, hashlib, requests
from datetime import datetime, timezone
from urllib.parse import urlencode

# --- Try to load sklearn ---
try:
    import numpy as np
    from sklearn.ensemble import RandomForestClassifier
    HAS_SKLEARN = True
except ImportError:
    HAS_SKLEARN = False

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

def signed_post(path, params):
    params["timestamp"] = str(int(time.time() * 1000))
    q = urlencode(sorted(params.items()))
    sig = hmac.new(SECRET, q.encode(), hashlib.sha256).hexdigest()
    r = requests.post(f"{BASE}{path}?{q}&signature={sig}",
                      headers={"X-MBX-APIKEY": KEY}, timeout=10)
    return r.json()

def get_klines(sym, interval, limit=500):
    r = requests.get(f"{BASE}/api/v3/klines", params={"symbol": sym, "interval": interval, "limit": limit}, timeout=15)
    return [[float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[0])] for k in r.json()]

def round_qty(qty):
    return math.floor(qty / 0.001) * 0.001

# === FEATURE ENGINEERING ===
def build_features(klines):
    """Build feature vector from klines."""
    closes = np.array([k[3] for k in klines])
    highs = np.array([k[2] for k in klines])
    lows = np.array([k[1] for k in klines])
    vols = np.array([k[4] for k in klines])

    features = []
    targets = []

    for i in range(20, len(closes) - 1):
        # Returns over different periods
        ret1 = (closes[i] - closes[i-1]) / closes[i-1]
        ret3 = (closes[i] - closes[i-3]) / closes[i-3]
        ret6 = (closes[i] - closes[i-6]) / closes[i-6]
        ret12 = (closes[i] - closes[i-12]) / closes[i-12]

        # Volatility
        hi_lo_12 = np.max(highs[i-12:i]) - np.min(lows[i-12:i])
        volatility = hi_lo_12 / closes[i]

        # Volume ratio
        vol_ratio = vols[i] / np.mean(vols[i-12:i]) if np.mean(vols[i-12:i]) > 0 else 1

        # RSI-like
        gains = np.mean([max(closes[j] - closes[j-1], 0) for j in range(i-13, i)])
        losses = np.mean([max(closes[j-1] - closes[j], 0) for j in range(i-13, i)])
        rsi = 50 if losses == 0 else 100 - (100 / (1 + gains/losses))

        # Price relative to range
        rng = np.max(highs[i-20:i]) - np.min(lows[i-20:i])
        pos_in_range = (closes[i] - np.min(lows[i-20:i])) / rng if rng > 0 else 0.5

        f = [ret1, ret3, ret6, ret12, volatility, vol_ratio, rsi / 100, pos_in_range]
        features.append(f)

        # Target: 1 if next close >= current close, else 0
        target = 1 if closes[i+1] >= closes[i] else 0
        targets.append(target)

    return np.array(features), np.array(targets)


# === MAIN ===
SYMBOL = "SOLUSDC"
CAPITAL = 50.0
POSITION = None
TRADES = 0
PNL = 0.0
CONFIDENCE_CACHE = None
LAST_HOUR_CHECK = 0

def log(msg, fpath=None):
    ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
    print(f"  [{ts}] {msg}")
    if fpath:
        with open(fpath, "a") as f:
            f.write(json.dumps({"ts": ts, "msg": msg}) + "\n")


print(f"\n{'='*50}")
print(f"  ML-PREDICTOR Starting | {SYMBOL} | sklearn={HAS_SKLEARN}")
print(f"{'='*50}\n")

if not HAS_SKLEARN:
    print("  ⚠️ sklearn not installed. Run: pip install scikit-learn numpy")
    sys.exit(1)

model = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
trained = False

while True:
    try:
        now = time.time()
        hour_start = int(now / 3600) * 3600

        # Retrain every 6 hours
        if not trained or hour_start % 21600 < 60:
            klines = get_klines(SYMBOL, "1h", limit=500)
            X, y = build_features(klines)

            if len(X) > 100:
                split = int(len(X) * 0.8)
                X_train, X_test = X[:split], X[split:]
                y_train, y_test = y[:split], y[split:]

                model.fit(X_train, y_train)
                train_acc = model.score(X_train, y_train)
                test_acc = model.score(X_test, y_test)

                # Feature importance
                importances = [f"{v:.2f}" for v in model.feature_importances_]
                feat_names = ["ret1", "ret3", "ret6", "ret12", "volatility", "vol_ratio", "rsi", "pos_range"]

                trained = True
                log(f"🧠 Model trained | Train={train_acc:.1%} Test={test_acc:.1%} | Features: {dict(zip(feat_names, importances))}",
                    f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")

        # Predict every hour
        if hour_start != LAST_HOUR_CHECK:
            LAST_HOUR_CHECK = hour_start

            klines = get_klines(SYMBOL, "1h", limit=50)
            closes = [k[3] for k in klines]
            price = closes[-1]

            X_last, _ = build_features(klines)
            if len(X_last) > 0:
                latest_features = X_last[-1:]

                proba = model.predict_proba(latest_features)[0]
                pred = model.predict(latest_features)[0]
                confidence = max(proba)

                # If model predicts UP with >55% confidence
                if pred == 1 and confidence > 0.55:
                    if POSITION is None:
                        qty = round_qty(CAPITAL / price)
                        if qty > 0:
                            r = signed_post("/api/v3/order", {
                                "symbol": SYMBOL, "side": "BUY", "type": "MARKET",
                                "quantity": f"{qty:.3f}"
                            })
                            if "orderId" in r:
                                POSITION = {"qty": qty, "entry": price, "time": now, "stop": price * 0.97, "tp": price * 1.04}
                                TRADES += 1
                                log(f"📈 ML BUY {qty:.3f} SOL @ ${price:.2f} | conf={confidence:.1%}",
                                    f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")
                elif pred == 0 and confidence > 0.55 and POSITION is not None:
                    # Model predicts down, close position
                    qty = POSITION["qty"]
                    r = signed_post("/api/v3/order", {
                        "symbol": SYMBOL, "side": "SELL", "type": "MARKET",
                        "quantity": f"{qty:.3f}"
                    })
                    if "orderId" in r:
                        pnl = (price - POSITION["entry"]) * qty
                        PNL += pnl
                        log(f"📉 ML SELL @ ${price:.2f} | PnL=${pnl:.2f} | conf={confidence:.1%}",
                            f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")
                        POSITION = None

                log(f"🧠 Pred={pred} conf={confidence:.1%} price=${price:.2f} pos={POSITION is not None}",
                    f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")

        # Manage open position (TP/SL check)
        if POSITION is not None:
            klines = get_klines(SYMBOL, "1h", limit=5)
            price = klines[-1][3]

            pnl_pct = (price - POSITION["entry"]) / POSITION["entry"]
            reason = None
            if price <= POSITION["stop"]:
                reason = "SL"
            elif price >= POSITION["tp"]:
                reason = "TP"
            elif now - POSITION["time"] > 86400:
                reason = "TIME"

            if reason:
                r = signed_post("/api/v3/order", {
                    "symbol": SYMBOL, "side": "SELL", "type": "MARKET",
                    "quantity": f"{POSITION['qty']:.3f}"
                })
                if "orderId" in r:
                    pnl = (price - POSITION["entry"]) * POSITION["qty"]
                    PNL += pnl
                    log(f"📉 ML {reason} @ ${price:.2f} | PnL=${pnl:.2f}",
                        f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")
                    POSITION = None

        # Global status
        if int(now) % 3600 < 10:
            log(f"[STATUS] T:{TRADES} PnL:${PNL:.2f} | pred={CONFIDENCE_CACHE} | "
                f"{'POS:' + str(round(POSITION.get('qty',0),3)) + '@$' + str(round(POSITION.get('entry',0),2)) if POSITION else 'NO POS'}",
                f"results/ml_sol_{datetime.now().strftime('%Y%m%d')}.json")

    except Exception as e:
        log(f"❌ {str(e)[:80]}")

    time.sleep(60)

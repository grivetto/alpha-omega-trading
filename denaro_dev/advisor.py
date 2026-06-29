"""
ADVISOR — Trend signal generator for Denaro GRID-PRO.
Runs every 5 minutes. Calculates EMA crossover + RSI + ATR regime.
Writes advisor_signal.json for GRID-PRO to consume.
Independent from GRID-PRO — if it dies, grid keeps working with neutral bias.
"""
import json, os, sys, time, requests
from datetime import datetime, timezone
from collections import deque

sys.stdout.reconfigure(line_buffering=True)

SYMBOL = os.environ.get("ADVISOR_SYMBOL", "ADAUSDC")
BASE = "https://api.binance.com"
SIGNAL_FILE = os.path.join(os.path.dirname(__file__) or ".", "advisor_signal.json")

def fetch_klines(symbol, interval, limit=100):
    r = requests.get(f"{BASE}/api/v3/klines",
                     params={"symbol": symbol, "interval": interval, "limit": limit},
                     timeout=10)
    return r.json() if r.status_code == 200 else []

def ema(values, period):
    if len(values) < period:
        return values[-1] if values else 0
    k = 2 / (period + 1)
    result = sum(values[:period]) / period
    for v in values[period:]:
        result = k * v + (1 - k) * result
    return result

def rsi(values, period=14):
    if len(values) < period + 1:
        return 50
    gains, losses = [], []
    for i in range(1, len(values)):
        diff = values[i] - values[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100
    return 100 - (100 / (1 + avg_gain / avg_loss))

def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i-1]),
                 abs(lows[i] - closes[i-1]))
        trs.append(tr)
    return sum(trs[-period:]) / period

print(f"  ADVISOR starting for {SYMBOL}...")

while True:
    try:
        # Fetch 1h candles (50 + padding for EMA)
        raw = fetch_klines(SYMBOL, "1h", 70)
        if len(raw) < 50:
            print(f"  ⚠️ Got only {len(raw)} candles, skipping cycle")
            time.sleep(300)
            continue

        closes = [float(k[4]) for k in raw]  # index 4 = close
        highs = [float(k[2]) for k in raw]
        lows = [float(k[3]) for k in raw]
        price = closes[-1]

        # --- Indicators ---
        ema20 = ema(closes[-30:], 20)
        ema50 = ema(closes, 50)
        rsi_val = rsi(closes, 14)
        atr_val = atr(highs, lows, closes, 14)

        # --- Trend Bias ---
        # EMA crossover baseline
        ema_diff_pct = (ema20 - ema50) / ema50 * 100

        # RSI adjustment
        rsi_bias = 0
        if rsi_val > 70: rsi_bias = -0.3  # overbought → bearish
        elif rsi_val < 30: rsi_bias = 0.3  # oversold → bullish
        elif rsi_val > 50: rsi_bias = 0.1
        else: rsi_bias = -0.1

        # Combined bias (-1 to +1)
        raw_bias = (ema_diff_pct / 3) + rsi_bias  # normalize EMA diff
        bias = max(-1.0, min(1.0, raw_bias))

        # --- Volatility Regime ---
        vol_ratio = atr_val / price * 100  # ATR as % of price
        if vol_ratio < 0.5:
            volatility = "low"
        elif vol_ratio < 1.5:
            volatility = "normal"
        else:
            volatility = "high"

        # --- Trend Strength ---
        strength = abs(bias)
        if strength > 0.5:
            trend = "strong"
        elif strength > 0.2:
            trend = "weak"
        else:
            trend = "neutral"

        # --- Grid parameters ---
        # grid_offset: shift grid center toward trend direction
        grid_offset = bias * 0.005  # max ±0.5% shift

        # position_scale: more aggressive in strong trends
        if volatility == "high":
            position_scale = 0.5  # reduce exposure
        elif trend == "strong":
            position_scale = 1.3
        elif trend == "weak":
            position_scale = 1.0
        else:
            position_scale = 0.7  # neutral/range → be cautious

        # --- Write signal ---
        signal = {
            "symbol": SYMBOL,
            "price": round(price, 6),
            "bias": round(bias, 4),
            "trend": trend,
            "strength": round(strength, 4),
            "volatility": volatility,
            "grid_offset": round(grid_offset, 6),
            "position_scale": round(position_scale, 2),
            "indicators": {
                "ema20": round(ema20, 6),
                "ema50": round(ema50, 6),
                "rsi": round(rsi_val, 1),
                "atr_pct": round(atr_val / price * 100, 4),
            },
            "ts": int(time.time() * 1000),
            "dt": datetime.now(timezone.utc).isoformat()
        }

        # Atomic write: temp file → rename
        tmp = SIGNAL_FILE + ".tmp"
        with open(tmp, "w") as f:
            json.dump(signal, f)
        os.replace(tmp, SIGNAL_FILE)

        # Compact log
        arrow = "▲" if bias > 0.2 else ("▼" if bias < -0.2 else "◆")
        print(f"  {arrow} bias={bias:+.3f} {trend:7s} vol={volatility:6s} "
              f"grid_off={grid_offset:+.4f} pos_scale={position_scale:.1f}x | "
              f"EMA20={ema20:.4f} EMA50={ema50:.4f} RSI={rsi_val:.0f}")

    except Exception as e:
        print(f"  ❌ Advisor error: {str(e)[:100]}")

    time.sleep(300)  # 5 minuti

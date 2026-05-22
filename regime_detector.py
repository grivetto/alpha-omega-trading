#!/usr/bin/env python3
"""
Regime Detector — Analyzes market conditions every 5 minutes
Classifies: trending, ranging, volatile, quiet
Outputs to Denaro Memory DB. Also writes a JSON for fast consumption.
"""
import json, os, sys, time, math
from pathlib import Path
from datetime import datetime, timezone
import urllib.request
import numpy as np

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
from denaro_memory import DenaroMemory

BINANCE = "https://api.binance.com"
SYMBOLS = ["ADAUSDT", "BTCUSDT", "ETHUSDT", "SOLUSDT"]
LOOKBACK_HOURS = 4   # 48 candles x 5min
VOLATILITY_WINDOW = 12  # 1 hour
TREND_WINDOW = 24       # 2 hours


def fetch_klines(symbol, interval="5m", limit=48):
    url = f"{BINANCE}/api/v3/klines?symbol={symbol}&interval={interval}&limit={limit}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
        return [{
            "time": k[0],
            "open": float(k[1]),
            "high": float(k[2]),
            "low": float(k[3]),
            "close": float(k[4]),
            "volume": float(k[5]),
        } for k in data]
    except Exception as e:
        print(f"[REGIME] Error fetching {symbol}: {e}")
        return []


def compute_volatility(candles):
    """ATR-like volatility as % of price"""
    if len(candles) < 2:
        return 0
    ranges = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        ranges.append(tr)
    avg_tr = sum(ranges) / len(ranges)
    avg_price = sum(c["close"] for c in candles) / len(candles)
    return avg_tr / avg_price * 100  # percent


def compute_trend_strength(candles):
    """Linear regression slope normalized -1..1"""
    if len(candles) < 4:
        return 0
    closes = [c["close"] for c in candles]
    x = list(range(len(closes)))
    n = len(closes)
    # Linear regression
    sx = sum(x)
    sy = sum(closes)
    sxy = sum(xi * yi for xi, yi in zip(x, closes))
    sxx = sum(xi * xi for xi in x)
    slope = (n * sxy - sx * sy) / (n * sxx - sx * sx) if (n * sxx - sx * sx) != 0 else 0
    # Normalize by price
    avg_price = sy / n
    if avg_price == 0:
        return 0
    return slope / avg_price * 100  # % change per candle


def compute_volume_ratio(candles, recent_n=6):
    """Recent avg volume vs longer avg volume"""
    if len(candles) < recent_n + 1:
        return 1.0
    recent = sum(c["volume"] for c in candles[-recent_n:]) / recent_n
    prior = sum(c["volume"] for c in candles[:-recent_n]) / (len(candles) - recent_n)
    if prior == 0:
        return 1.0
    return recent / prior


def classify_regime(volatility, trend, volume_ratio):
    """Classify market regime using heuristic thresholds"""
    if volatility > 2.5:
        return "volatile"
    if abs(trend) > 0.15 and volatility < 1.5:
        return "trending"
    if volatility < 0.5 and abs(trend) < 0.05:
        return "quiet"
    return "ranging"


def detect():
    memory = DenaroMemory()
    
    all_volatilities = []
    all_trends = []
    all_volume_ratios = []
    details = {}

    for symbol in SYMBOLS:
        candles = fetch_klines(symbol)
        if len(candles) < 6:
            print(f"[REGIME] Skipping {symbol} — insufficient data ({len(candles)})")
            continue
        vol = compute_volatility(candles)
        trend = compute_trend_strength(candles)
        vol_ratio = compute_volume_ratio(candles)
        all_volatilities.append(vol)
        all_trends.append(trend)
        all_volume_ratios.append(vol_ratio)
        details[symbol] = {"volatility": round(vol, 3), "trend": round(trend, 5), "volume_ratio": round(vol_ratio, 3)}
        print(f"[REGIME] {symbol}: vol={vol:.3f}% trend={trend:.5f} vol_ratio={vol_ratio:.3f}")

    if not all_volatilities:
        print("[REGIME] No data — skipping")
        return

    avg_volatility = sum(all_volatilities) / len(all_volatilities)
    avg_trend = sum(all_trends) / len(all_trends)
    avg_volume = sum(all_volume_ratios) / len(all_volume_ratios)
    regime = classify_regime(avg_volatility, avg_trend, avg_volume)
    
    memory.save_regime(regime, avg_volatility, avg_trend, avg_volume, {"per_symbol": details})
    
    # Also write a fast JSON for bots
    path = BASE / "regime.json"
    with open(path, "w") as f:
        json.dump({
            "regime": regime,
            "volatility": round(avg_volatility, 3),
            "trend_strength": round(avg_trend, 5),
            "volume_ratio": round(avg_volume, 3),
            "details": details,
            "detected_at": datetime.now(timezone.utc).isoformat(),
        }, f, indent=2)

    print(f"[REGIME] → {regime} (vol={avg_volatility:.3f}%, trend={avg_trend:.5f}, vol_ratio={avg_volume:.3f})")


if __name__ == "__main__":
    detect()

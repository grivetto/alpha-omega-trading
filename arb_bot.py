#!/usr/bin/env python3
"""Triangular Arbitrage Bot — SOL/BTC/USDC"""
import ccxt, time, os

API = os.environ.get("ARB_API_KEY", "")
SEC = os.environ.get("ARB_API_SECRET", "")

if not API or not SEC:
    print("ERR: ARB_API_KEY and ARB_API_SECRET must be set in environment", flush=True)
    exit(1)

ex = ccxt.binance({"apiKey":API,"secret":SEC,"enableRateLimit":True,"options":{"defaultType":"spot"}})
MIN_PCT = 0.003  # 0.3%
CAP = 50.0

def prices():
    return {
        "su": ex.fetch_ticker("SOL/USDC")["last"],   # SOL in USDC
        "bu": ex.fetch_ticker("BTC/USDC")["last"],   # BTC in USDC
        "sb": ex.fetch_ticker("SOL/BTC")["last"],   # SOL in BTC
    }

print("=== TRIANGULAR ARB BOT ===")
print("CAP=$%.0f MIN=%.2f%%" % (CAP, MIN_PCT*100))

while True:
    try:
        p = prices()
        # Path 1: USDC -> SOL -> BTC -> USDC
        # 50 USDC -> buy 50/su SOL -> sell for 50/su * sb BTC -> sell for 50/su * sb * bu USDC
        usdc_v1 = CAP / p["su"] * p["sb"] * p["bu"]
        pct1 = (usdc_v1 - CAP) / CAP * 100

        # Path 2: USDC -> BTC -> SOL -> USDC
        # 50 USDC -> buy 50/bu BTC -> buy 50/bu / sb SOL -> sell for 50/bu / sb * su USDC
        usdc_v2 = CAP / p["bu"] / p["sb"] * p["su"]
        pct2 = (usdc_v2 - CAP) / CAP * 100

        ts = time.strftime("%H:%M:%S")
        best = max(pct1, pct2)
        path = "P1" if pct1 > pct2 else "P2"
        print("%s %s %+.4f%% | SOL=%.2f BTC=%.0f SB=%.6f" % (
            ts, path, best, p["su"], p["bu"], p["sb"]), flush=True)

        if best > MIN_PCT * 100:
            print(">>> ARB %s @ %+.4f%% <<<" % (path, best), flush=True)

    except Exception as e:
        print("ERR: %s" % str(e)[:100], flush=True)
    time.sleep(2)

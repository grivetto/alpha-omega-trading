#!/usr/bin/env python3
"""MC2 Grid Bot - SOL/USDC (direct REST balance)"""
import ccxt, time, hashlib, hmac, requests, os

API = os.environ.get("BINANCE_API_KEY", "")
SEC = os.environ.get("BINANCE_API_SECRET", "")

if not API or not SEC:
    print("ERR: BINANCE_API_KEY and BINANCE_API_SECRET must be set", flush=True)
    exit(1)

ex = ccxt.binance({"apiKey":API,"secret":SEC,"enableRateLimit":True,"options":{"defaultType":"spot"}})
SYM = "SOL/USDC"
MIN = 5.0
SPACING = 0.04
TAKE = 0.01

def bal():
    st = int(time.time() * 1000)
    q = "timestamp=%d&recvWindow=10000" % st
    sig = hmac.new(SEC.encode(), q.encode(), hashlib.sha256).hexdigest()
    r = requests.get("https://api.binance.com/api/v3/account?" + q + "&signature=" + sig, headers={"X-MBX-APIKEY": API})
    b = {}
    if r.status_code == 200:
        for a in r.json()["balances"]:
            f, l = float(a["free"]), float(a["locked"])
            if f > 0 or l > 0: b[a["asset"]] = {"f": f, "l": l}
    return b

print("MC2 Grid SOL/USDC | min=%.1f spacing=%.1f%%" % (MIN, SPACING*100))
for o in ex.fetch_open_orders(SYM):
    ex.cancel_order(o["id"], SYM)
while True:
    try:
        p = ex.fetch_ticker(SYM)["last"]
        b = bal()
        usdc = b.get("USDC", {}).get("f", 0)
        sol = b.get("SOL", {}).get("f", 0)
        orders = ex.fetch_open_orders(SYM)
        ts = time.strftime("%H:%M:%S")
        if len(orders) == 0:
            if usdc >= MIN:
                bp = round(p * (1 - SPACING * 0.5), 2)
                a = round(usdc / bp, 2)
                if a * bp >= MIN:
                    ex.create_limit_buy_order(SYM, a, bp)
                    print("%s BUY @ %.2f x %.2f = $%.2f" % (ts, bp, a, a*bp))
            if sol >= 0.1:
                sp = round(p * (1 + SPACING * 0.5), 2)
                a2 = round(sol * 0.999, 4)  # 0.1% for fees
                if a2 * sp >= MIN:
                    ex.create_limit_sell_order(SYM, a2, sp)
                    print("%s SELL @ %.2f x %.2f = $%.2f" % (ts, sp, a2, a2*sp))
        print("%s USDC=%.2f SOL=%.4f orders=%d" % (ts, usdc, sol, len(orders)))
    except Exception as e:
        print("%s ERR: %s" % (ts, str(e)[:80]))
    time.sleep(60)

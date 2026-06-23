#!/usr/bin/env python3
"""Gariban Beggar v2 — Micro-scalper con Kill-Switch integrato."""
import requests, time, hashlib, hmac, json, os
from datetime import datetime, timezone

K = "G73HP5WHS5bQNwJTFAoVMbdamgVU3JkG79yDJ2Pt199abLpDV4LjOrEAmQoC9vew"
S = "nIV5sWI11K9StdPPopESTU2OzAjRBVlAhj5Zi9B2SxDrcuCjgZJZDJJ759D6je7b"
SYM = "SOLUSDC"

ENTRY_DROP = 0.008
TAKE_PROFIT = 0.004
STOP_LOSS = 0.02
MIN_NOTIONAL = 5.0
MAX_CAPITAL = 20.0
CHECK_INTERVAL = 5

# === KILL-SWITCH ===
class KillSwitch:
    def __init__(self):
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.day_start_equity = 0.0
        self.halted = False
        self.day = ""

    def update(self, pnl):
        self.daily_pnl += pnl
        if pnl < -0.01:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0

    def check(self, equity):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if today != self.day:
            self.day_start_equity = equity
            self.daily_pnl = 0
            self.consecutive_losses = 0
            self.halted = False
            self.day = today
        loss_pct = abs(self.daily_pnl) / max(self.day_start_equity, 1) * 100
        if self.consecutive_losses >= 3:
            print(f"  🔴 KS L1: {self.consecutive_losses} consecutive losses — stop nuovi entry")
            return False
        if loss_pct > 5.0:
            print(f"  🔴 KS L3: daily loss {loss_pct:.1f}% > 5% — LIQUIDATE + HALT")
            self.halted = True
            return False
        if loss_pct > 3.0:
            print(f"  🟡 KS L2: daily loss {loss_pct:.1f}% > 3% — stop nuovi entry")
            return False
        return True

# === ENGINE ===
def req(method, params):
    ts = int(time.time() * 1000)
    q = f"timestamp={ts}&recvWindow=30000&{params}"
    sig = hmac.new(S.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"https://api.binance.com{method}?{q}&signature={sig}"
    r = requests.request("POST" if "order" in method else "GET", url, headers={"X-MBX-APIKEY": K})
    return r.json() if r.status_code == 200 else {"error": r.text[:200]}

def price():
    r = requests.get(f"https://api.binance.com/api/v3/ticker/price?symbol={SYM}", timeout=10)
    return float(r.json()["price"]) if r.status_code == 200 else 0

def balance():
    b = req("/api/v3/account", "")
    if "balances" in b:
        return {x["asset"]: float(x["free"]) for x in b["balances"] if float(x["free"]) > 0}
    return {}

def equity():
    b = balance()
    usdc = b.get("USDC", 0)
    sol = b.get("SOL", 0)
    p = price()
    return usdc + sol * p if sol else usdc

# === MAIN ===
ks = KillSwitch()
trade_count = 0
pnl_total = 0.0
posizione = False
buy_price = 0.0
sell_price = 0.0
high_price = 0.0

print("🧿 Gariban Beggar v2 — Kill-Switch integrato")
print(f"   Entry: -{ENTRY_DROP*100:.1f}%  TP: +{TAKE_PROFIT*100:.1f}%  SL: -{STOP_LOSS*100:.0f}%")

while True:
    try:
        # Check kill-switch
        eq = equity()
        if not ks.check(eq):
            if ks.halted:
                print("  ⛔ BOT HALTED — kill-switch L3")
                break
            time.sleep(60)
            continue

        p = price()
        if p <= 0:
            time.sleep(CHECK_INTERVAL)
            continue

        if not posizione:
            b = balance()
            usdc = b.get("USDC", 0)
            orders = req("/api/v3/openOrders", f"symbol={SYM}")
            if isinstance(orders, list) and any(o.get("side") == "SELL" for o in orders):
                time.sleep(CHECK_INTERVAL)
                continue

            high_price = max(high_price, p)
            drop = (high_price - p) / high_price if high_price else 0

            if drop >= ENTRY_DROP and usdc >= MIN_NOTIONAL:
                buy_amt = min(usdc, MAX_CAPITAL)
                r = req("/api/v3/order", f"symbol={SYM}&side=BUY&type=MARKET&quoteOrderQty={buy_amt:.2f}")
                if "executedQty" in r:
                    qty = float(r["executedQty"])
                    cost = float(r["cummulativeQuoteQty"])
                    buy_price = cost / qty
                    sell_price = buy_price * (1 + TAKE_PROFIT)
                    posizione = True
                    trade_count += 1
                    high_price = p
                    print(f"\n  ✅ BUY {qty:.4f} SOL @ ${buy_price:.2f} = ${cost:.2f}")
                    ls = req("/api/v3/order", f"symbol={SYM}&side=SELL&type=LIMIT&timeInForce=GTC&quantity={qty:.4f}&price={sell_price:.2f}")
                    if "error" in ls:
                        print(f"  ❌ SELL error: {ls['error'][:60]}")
                elif "error" in r:
                    print(f"  ❌ {r['error'][:60]}")

        else:
            orders = req("/api/v3/openOrders", f"symbol={SYM}")
            if isinstance(orders, list) and not any(o.get("side") == "SELL" for o in orders):
                usdc = balance().get("USDC", 0)
                profit = usdc - buy_price
                pnl_total += profit
                ks.update(profit)
                print(f"\n  💰 SELL FILLED! Profit: ${profit:.2f} | Tot: ${pnl_total:.2f}")
                posizione = False
                buy_price = 0
                high_price = 0
                continue

            if p < buy_price * (1 - STOP_LOSS):
                sol = balance().get("SOL", 0)
                if sol >= 0.01:
                    for o in (orders if isinstance(orders, list) else []):
                        req("/api/v3/order", f"symbol={SYM}&orderId={o['orderId']}&cancelRestrictedOnly=false")
                    ms = req("/api/v3/order", f"symbol={SYM}&side=SELL&type=MARKET&quantity={sol:.4f}")
                    profit = float(ms.get("cummulativeQuoteQty", 0)) - buy_price * sol
                    ks.update(profit)
                    print(f"  🛑 STOP LOSS @ ${p:.2f} | Loss: ${profit:.2f}")
                posizione = False
                buy_price = 0
                high_price = 0

        if trade_count % 10 == 0 and not posizione:
            state = f"L{ks.consecutive_losses} PnL=${pnl_total:.2f}"
            print(f"  {datetime.now().strftime('%H:%M:%S')} SOL=${p:.2f}  {state}", end="\r")

    except Exception as e:
        print(f"  ! {str(e)[:80]}")

    time.sleep(CHECK_INTERVAL)

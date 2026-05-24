#!/usr/bin/env python3
"""
Denaro — mc2 (Momentum Multi-Pair Scalper)
Trades 28 USDT pairs on Binance spot.
Entry: RSI < 30 + volume spike + price > EMA50 + ATR confirmation
Exit: TP=ATR*1.5, SL=ATR*2.0 (limit orders)
Max 3 concurrent positions.
Uses BNB for fee discount.
"""
import asyncio, json, time, os, traceback
from pathlib import Path
from datetime import datetime, timezone
import ccxt.async_support as ccxt
import pandas as pd

BASE_DIR = Path(__file__).parent
import sys
sys.path.insert(0, str(BASE_DIR))
from denaro_shared import setup_logger, send_telegram, BotState
from dotenv import load_dotenv

load_dotenv(BASE_DIR / ".env")
logger = setup_logger("Mc2Scalper", "mc2.log")

SYMBOLS = [
    "MATIC/USDT", "MKR/USDT", "UNI/USDT", "ALGO/USDT", "CHZ/USDT", "FTM/USDT",
    "GALA/USDT", "BCH/USDT", "ADA/USDT", "LINK/USDT", "ETC/USDT", "AVAX/USDT",
    "NEAR/USDT", "XTZ/USDT", "VET/USDT", "AAVE/USDT", "DOT/USDT", "SAND/USDT",
    "MANA/USDT", "FIL/USDT", "XLM/USDT", "ENJ/USDT", "ZIL/USDT", "BAT/USDT",
    "EOS/USDT", "LTC/USDT", "AXS/USDT", "ATOM/USDT",
]

WS_SYMBOLS = [s.lower().replace("/", "").replace("usdt", "usdt@ticker") for s in SYMBOLS]

FEE_RATE = 0.001
TRADE_CAPITAL = 500.0
RISK_PER_TRADE = 0.01
MAX_EXPOSURE = 33.0
MAX_CONCURRENT = 3
ATL = {}

class MomentumBot:
    def __init__(self, exchange, symbol):
        self.exchange = exchange
        self.symbol = symbol
        self.base = symbol.split("/")[0]
        self.position = False
        self.buy_price = 0.0
        self.qty = 0.0
        self.tp = 0.0
        self.sl = 0.0
        self.price_history = []
        self.vol_history = []
        self.latest_price = None
        self.load_state()

    def load_state(self):
        sp = BASE_DIR / ".tmp" / f"mc2_{self.base}.json"
        if sp.exists():
            try:
                with open(sp) as f:
                    d = json.load(f)
                    self.position = d.get("pos", False)
                    self.buy_price = d.get("bp", 0)
                    self.qty = d.get("qty", 0)
                    self.tp = d.get("tp", 0)
                    self.sl = d.get("sl", 0)
            except Exception:
                pass

    def save_state(self):
        sp = BASE_DIR / ".tmp" / f"mc2_{self.base}.json"
        with open(sp, "w") as f:
            json.dump({"pos": self.position, "bp": self.buy_price, "qty": self.qty, "tp": self.tp, "sl": self.sl}, f)

    def remove_state(self):
        sp = BASE_DIR / ".tmp" / f"mc2_{self.base}.json"
        if sp.exists():
            sp.unlink()

    def update(self, price, vol):
        self.latest_price = price
        self.price_history.append(price)
        self.vol_history.append(vol)
        if len(self.price_history) > 100:
            self.price_history.pop(0)
            self.vol_history.pop(0)

    async def evaluate_entry(self):
        if self.position or len(self.price_history) < 20:
            return None
        price = self.latest_price
        if price is None:
            return None
        df = pd.DataFrame({"close": self.price_history, "volume": self.vol_history})
        rsi = self._rsi(df["close"], 14)
        if rsi is None or rsi >= 30:
            return None
        ema50 = df["close"].ewm(span=50).mean().iloc[-1] if len(df) >= 50 else price
        if price <= ema50:
            return None
        if len(self.vol_history) >= 20:
            avg_vol = sum(self.vol_history[-20:]) / 20
            if self.vol_history[-1] < avg_vol * 1.5:
                return None
        atr = self._atr()
        if atr is None or atr <= 0:
            return None
        risk_d = (atr * 2.0) / price
        size = (TRADE_CAPITAL * RISK_PER_TRADE) / risk_d if risk_d > 0 else 11.0
        size = max(5.0, min(MAX_EXPOSURE, size))
        return {"size": size, "atr": atr, "price": price}

    async def open_position(self, signal):
        try:
            size = signal["size"]
            price = signal["price"]
            atr = signal["atr"]
            order = await self.exchange.create_market_buy_order(
                self.symbol, size, {"quoteOrderQty": size}
            )
            filled = float(order.get("filled", 0))
            if filled <= 0:
                filled = size / price
            self.qty = filled
            self.buy_price = float(order.get("price", price))
            self.tp = self.buy_price + (atr * 1.5)
            self.sl = self.buy_price - (atr * 2.0)
            self.position = True
            self.save_state()
            logger.info(f" ⚔️ OPEN {self.symbol} @ {self.buy_price:.4f} | size={size:.2f} | TP={self.tp:.4f} SL={self.sl:.4f}")
            await send_telegram(logger, f"⚔️ OPEN {self.symbol} @ {self.buy_price:.4f} | {size:.1f}USDT")
            return True
        except Exception as e:
            logger.error(f"Buy fail {self.symbol}: {e}")
            return False

    async def check_exit(self):
        if not self.position or self.latest_price is None:
            return None
        price = self.latest_price
        if price >= self.tp:
            return "TP"
        if price <= self.sl:
            return "SL"
        return None

    async def close_position(self, reason):
        try:
            order = await self.exchange.create_market_sell_order(self.symbol, round(self.qty, 6))
            sell_price = float(order.get("price", self.latest_price or self.buy_price))
            profit = self.qty * (sell_price - self.buy_price) - (self.qty * (sell_price + self.buy_price) * FEE_RATE)
            logger.info(f" CLOSE {self.symbol} | {reason} | exit={sell_price:.4f} | PnL={profit:.2f}USDT")
            if profit > 0:
                await send_telegram(logger, f"💰 CLOSE {self.symbol} | {reason} | +{profit:.2f}USDT")
            else:
                await send_telegram(logger, f"❌ CLOSE {self.symbol} | {reason} | {profit:.2f}USDT")
            self.position = False
            self.qty = 0
            self.buy_price = 0
            self.remove_state()
            return profit
        except Exception as e:
            logger.error(f"Sell fail {self.symbol}: {e}")
            return 0

    def _rsi(self, series, length=14):
        if len(series) < length + 1:
            return None
        delta = series.diff()
        gain = delta.where(delta > 0, 0).rolling(length).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(length).mean()
        rs = gain / loss.replace(0, 0.001)
        rsi = 100 - (100 / (1 + rs.iloc[-1]))
        return rsi

    def _atr(self):
        if len(self.price_history) < 14:
            return None
        closes = self.price_history
        highs = [max(closes[max(0, i-1):i+1]) for i in range(1, len(closes))]
        lows = [min(closes[max(0, i-1):i+1]) for i in range(1, len(closes))]
        tr = max(highs[-1] - lows[-1], abs(highs[-1] - closes[-2]), abs(lows[-1] - closes[-2])) if len(closes) >= 2 else 0
        return tr

async def main():
    exchange = ccxt.binance({
        "apiKey": os.getenv("BINANCE_API_KEY"),
        "secret": os.getenv("BINANCE_API_SECRET"),
        "enableRateLimit": True,
        "options": {"defaultType": "spot", "defaultFeeCurrency": "BNB"},
    })
    state = BotState("mc2_scalper")
    bots = {s: MomentumBot(exchange, s) for s in SYMBOLS}
    feed_active = True

    async def price_feed():
        nonlocal feed_active
        url = "wss://stream.binance.com:9443/ws/!ticker@arr"
        while feed_active:
            try:
                import websockets
                async with websockets.connect(url, ping_interval=30) as ws:
                    logger.info("WS connected to !ticker@arr")
                    while feed_active:
                        msg = await ws.recv()
                        tickers = json.loads(msg)
                        for t in tickers:
                            s = t["s"].lower()
                            sym = next((x for x in SYMBOLS if x.lower().replace("/", "") == s), None)
                            if sym and sym in bots:
                                bots[sym].update(float(t["c"]), float(t["v"]))
            except Exception as e:
                logger.error(f"WS error: {e}")
                await asyncio.sleep(5)

    logger.info(f"Mc2 Scalper starting | {len(SYMBOLS)} pairs | max_concurrent={MAX_CONCURRENT}")
    await send_telegram(logger, f"✅ Mc2 Scalper started | {len(SYMBOLS)} pairs")

    feed_task = asyncio.create_task(price_feed())
    await asyncio.sleep(5)

    try:
        while True:
            active = sum(1 for b in bots.values() if b.position)
            for sym, bot in bots.items():
                if not bot.position and active < MAX_CONCURRENT:
                    signal = await bot.evaluate_entry()
                    if signal:
                        ok = await bot.open_position(signal)
                        if ok:
                            active += 1
                            await asyncio.sleep(2)
            for sym, bot in bots.items():
                if bot.position:
                    reason = await bot.check_exit()
                    if reason:
                        profit = await bot.close_position(reason)
                        state.set("pnl", state.get("pnl", 0) + (profit or 0))
                        state.set("trades", state.get("trades", 0) + 1)
                        state.save()
                        await asyncio.sleep(1)
            await asyncio.sleep(3)
    except KeyboardInterrupt:
        pass
    finally:
        feed_active = False
        await feed_task
        await exchange.close()

if __name__ == "__main__":
    asyncio.run(main())

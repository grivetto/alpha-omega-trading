#!/usr/bin/env python3
"""
MarcoSOL — SOL/EUR opportunistic reversal bot for MARCODG1
Strategy: Sell SOL at +0.5% premium, buy back at -0.4% discount.
Cycles: sell → buy → sell → buy → ...
Uses existing SOL inventory + small EUR reserve.
Minimal overlap with Stellatron (ADA grid on nuvola, same account).
"""
import asyncio, ccxt.async_support as ccxt, logging, os, sys, time, json, urllib.request
from pathlib import Path

BASE = Path(__file__).parent
LOG_FILE = BASE / "marco_sol.log"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(str(LOG_FILE))], force=True)
logger = logging.getLogger("MarcoSOL")

MIN_NOTIONAL = 5.0
FEE = 0.00075  # 0.075% per side
OPTIMIZER_API = "http://192.168.1.99:8899/api/params/marco_sol"
PARAMS_FILE = BASE / "params_marco_sol.json"

class MarcoSOL:
    def __init__(self):
        self.exchange = None
        self.symbol = "SOL/EUR"
        self.asset = "SOL"
        self.sell_target = None
        self.buy_target = None
        self.sell_oid = None
        self.buy_oid = None
        self.cycle = 0
        self.profit = 0.0
        self.fills = 0
        self.active = True
        self.last_trade = 0
        self.sell_raise = 0.005  # default +0.5%
        self.buy_drop = 0.996    # default -0.4% (multiplier form)
        self._last_params_fetch = 0
        self._load_state()
        self._load_optimized_params()

    def _load_optimized_params(self):
        """Fetch optimized spread params from Denaro optimizer"""
        params = None
        try:
            with urllib.request.urlopen(OPTIMIZER_API, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                params = data.get("params", {})
                if params:
                    logger.info(f"Loaded params from API: {json.dumps(params)}")
        except Exception as e:
            logger.debug(f"Optimizer API fail: {e}")
        if not params and PARAMS_FILE.exists():
            try:
                params = json.loads(PARAMS_FILE.read_text())
                logger.info(f"Loaded params from {PARAMS_FILE}")
            except Exception: pass
        if not params:
            return
        sr = params.get("sell_raise")
        bd = params.get("buy_drop")
        if sr:
            self.sell_raise = 1.0 + abs(sr) if abs(sr) < 1 else sr
            logger.info(f"Spread: sell_raise -> {self.sell_raise:.4f}")
        if bd:
            self.buy_drop = 1.0 - abs(bd) if abs(bd) < 1 else bd
            logger.info(f"Spread: buy_drop -> {self.buy_drop:.4f}")

    def _refresh_params(self):
        if time.time() - self._last_params_fetch > 1800:
            self._last_params_fetch = time.time()
            self._load_optimized_params()

    def _load_state(self):
        sf = BASE / ".tmp" / "marco_sol_state.json"
        if sf.exists():
            try:
                d = json.loads(sf.read_text())
                self.sell_target = d.get("sell_target")
                self.buy_target = d.get("buy_target")
                self.cycle = d.get("cycle", 0)
                self.profit = d.get("profit", 0.0)
                self.fills = d.get("fills", 0)
                logger.info(f"State: cycle={self.cycle} PnL={self.profit:.4f}")
            except Exception as e:
                logger.warning(f"State load error: {e}")

    def _save_state(self):
        sf = BASE / ".tmp" / "marco_sol_state.json"
        sf.parent.mkdir(exist_ok=True)
        json.dump({"sell_target": self.sell_target, "buy_target": self.buy_target,
                    "cycle": self.cycle, "profit": self.profit, "fills": self.fills}, open(sf, "w"))

    async def connect(self):
        key, secret = "", ""
        for env_path in [BASE / ".env", Path("/home/sergio/denaro/.env")]:
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    line = line.strip()
                    if line.startswith("BINANCE_API_KEY="): key = line.split("=", 1)[1].strip()
                    elif line.startswith("BINANCE_API_SECRET="): secret = line.split("=", 1)[1].strip()
                if key: break
        if not key:
            key = os.environ.get("BINANCE_API_KEY", "")
            secret = os.environ.get("BINANCE_API_SECRET", "")
        if not key:
            logger.error("No API keys"); sys.exit(1)
        self.exchange = ccxt.binance({"apiKey": key, "secret": secret, "enableRateLimit": True,
                                       "options": {"defaultType": "spot"}})
        await self.exchange.load_markets()
        logger.info(f"Connected | key={key[:8]}...")

    async def close(self):
        if self.exchange: await self.exchange.close()

    async def bal(self):
        b = await self.exchange.fetch_balance()
        return {
            "EUR": float(b["free"].get("EUR", 0) or 0),
            "EUR_u": float(b["used"].get("EUR", 0) or 0),
            "SOL": float(b["free"].get("SOL", 0) or 0),
            "SOL_u": float(b["used"].get("SOL", 0) or 0),
        }

    async def price(self):
        return float((await self.exchange.fetch_ticker(self.symbol))["last"])

    async def cancel(self, oid=None):
        try:
            for o in await self.exchange.fetch_open_orders(self.symbol):
                if oid is None or o["id"] == oid:
                    await self.exchange.cancel_order(o["id"], self.symbol)
        except: pass

    async def place_sell(self, price):
        b = await self.bal()
        sol_free = b["SOL"]
        if sol_free < 0.01: return None
        sell_amt = round(min(sol_free, 0.15), 3)
        if sell_amt * price < MIN_NOTIONAL: return None
        try:
            o = await self.exchange.create_limit_sell_order(self.symbol, sell_amt, price)
            self.sell_oid = o["id"]
            self.sell_target = price
            logger.info(f"SELL {sell_amt} SOL @ {price} | id={o['id'][:12]}")
            return o
        except Exception as e:
            logger.error(f"Sell error: {e}")
            return None

    async def place_buy(self, price):
        b = await self.bal()
        eur_free = b["EUR"]
        if eur_free < MIN_NOTIONAL: return None
        buy_eur = min(6.0, eur_free * 0.6)
        buy_amt = round(buy_eur / price, 3)
        if buy_amt * price < MIN_NOTIONAL or buy_amt < 0.01: return None
        try:
            o = await self.exchange.create_limit_buy_order(self.symbol, buy_amt, price)
            self.buy_oid = o["id"]
            self.buy_target = price
            logger.info(f"BUY {buy_amt} SOL @ {price} | {buy_eur:.2f}€ | id={o['id'][:12]}")
            return o
        except Exception as e:
            logger.error(f"Buy error: {e}")
            return None

    async def check_fills(self):
        try:
            open_ids = {o["id"] for o in await self.exchange.fetch_open_orders(self.symbol)}
        except: open_ids = set()
        try:
            trades = await self.exchange.fetch_my_trades(self.symbol, limit=10)
            filled_ids = set()
            for t in trades:
                oid = t.get("order") or (t.get("info") or {}).get("orderId")
                if oid: filled_ids.add(oid)
        except: filled_ids = set()

        now = time.time()
        changed = False

        if self.sell_oid and self.sell_oid not in open_ids:
            if self.sell_oid in filled_ids:
                self.cycle += 1
                self.fills += 1
                self.last_trade = now
                logger.info(f"✅ SELL filled @ {self.sell_target}")
                self.sell_oid = None
                self.sell_target = None
                changed = True
            elif self.sell_oid:
                await self.cancel(self.sell_oid)
                self.sell_oid = None
                self.sell_target = None
                changed = True

        if self.buy_oid and self.buy_oid not in open_ids:
            if self.buy_oid in filled_ids:
                self.cycle += 1
                self.fills += 1
                self.last_trade = now
                profit = (self.sell_target - self.buy_target) * 0.15 if self.sell_target else 0
                self.profit += profit
                logger.info(f"✅ BUY filled @ {self.buy_target} | est_profit={profit:.4f}€")
                self.buy_oid = None
                self.buy_target = None
                changed = True
            elif self.buy_oid:
                await self.cancel(self.buy_oid)
                self.buy_oid = None
                self.buy_target = None
                changed = True

        if changed:
            self._save_state()

    async def run(self):
        await self.connect()
        await self.cancel(None)
        logger.info("MarcoSOL — SOL/EUR reversal bot started")
        logger.info(f"Resumed: cycle={self.cycle} PnL={self.profit:.4f} fills={self.fills}")

        while True:
            try:
                p = await self.price()
                if p <= 0: await asyncio.sleep(5); continue

                await self.check_fills()

                if not self.sell_target and not self.buy_target:
                    b = await self.bal()
                    if b["SOL"] >= 0.1 and b["EUR"] >= MIN_NOTIONAL:
                        st = round(p * self.sell_raise, 2)
                        bt = round(p * self.buy_drop, 2)
                        if st > p: await self.place_sell(st)
                        if bt < p: await self.place_buy(bt)

                if int(time.time()) % 1800 < 2:
                    self._refresh_params()

                if int(time.time()) % 20 < 2:
                    b = await self.bal()
                    logger.info(f"SOL/EUR={p} | free: SOL={b['SOL']:.4f} EUR={b['EUR']:.2f} | "
                                f"sell={self.sell_target} buy={self.buy_target} | "
                                f"PnL={self.profit:.4f} fills={self.fills} cycles={self.cycle}")

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error: {e}", exc_info=True)
                await asyncio.sleep(10)

if __name__ == "__main__":
    b = MarcoSOL()
    try:
        asyncio.run(b.run())
    except KeyboardInterrupt:
        asyncio.run(b.cancel(None))
        asyncio.run(b.close())

#!/usr/bin/env python3
"""
ORION — Multi-asset reversal bot for mc2 (on-prem Zabbix hub)
Manages BTC/EUR, ETH/EUR, BNB/EUR simultaneously.
Each pair: sell crypto at +0.4%, buy back at -0.3%.
Shares EUR pool responsibly.
"""
import asyncio, ccxt.async_support as ccxt, json, logging, os, sys, time, urllib.request
from pathlib import Path

BASE = Path(__file__).parent
LOG_FILE = BASE / "orion.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout), logging.FileHandler(str(LOG_FILE))], force=True)
logger = logging.getLogger("ORION")

MIN_NOTIONAL = 5.0
FEE = 0.00075
OPTIMIZER_API = "http://localhost:8899/api/params/orion"

PAIRS = {
    "BTC/EUR": {"asset": "BTC", "sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.00015, "max_eur": 10, "decimals": 6, "paused": False},
    "ETH/EUR": {"asset": "ETH", "sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.003,   "max_eur": 10, "decimals": 4, "paused": False},
    "BNB/EUR": {"asset": "BNB", "sell_raise": 0.004, "buy_drop": -0.003, "sell_amt": 0.002,   "max_eur": 10, "decimals": 4, "paused": False},
}

class OrionBot:
    def __init__(self):
        self.ex = None
        self.orders = {}  # symbol -> {"sell_id", "buy_id", "sell_price", "buy_price", "state"}
        self.meta = {}    # symbol -> pair config
        for s, c in PAIRS.items():
            self.orders[s] = {"sell_id": None, "buy_id": None, "sell_price": None, "buy_price": None,
                              "trail_peak": None, "trail_active": False}
            self.meta[s] = c
        self.profit = 0.0
        self.fills = 0
        self._last_params_fetch = 0
        self._load()
        self._load_optimized_params()

    def _load_optimized_params(self):
        """Fetch optimized per-symbol params from Denaro optimizer (runs locally on mc2)"""
        try:
            with urllib.request.urlopen(OPTIMIZER_API, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                api_params = data.get("params", {})
                if not api_params:
                    return
                logger.info(f"Loaded optimized params from API")
                for sym, overrides in api_params.items():
                    if sym in self.meta:
                        for key, val in overrides.items():
                            self.meta[sym][key] = val
                        logger.info(f"  {sym}: {json.dumps(overrides)}")
        except Exception as e:
            logger.debug(f"Optimizer API fail: {e}")

    def _refresh_params(self):
        if time.time() - self._last_params_fetch > 1800:
            self._last_params_fetch = time.time()
            self._load_optimized_params()

    def _load(self):
        sf = BASE / ".tmp" / "orion_state.json"
        if sf.exists():
            try:
                d = json.loads(sf.read_text())
                self.profit = d.get("profit", 0.0)
                self.fills = d.get("fills", 0)
            except: pass

    def _save(self):
        sf = BASE / ".tmp" / "orion_state.json"
        sf.parent.mkdir(exist_ok=True)
        json.dump({"profit": self.profit, "fills": self.fills}, open(sf, "w"))

    async def connect(self):
        for env_path in [BASE / ".env", Path("/home/sergio/denaro/.env"), Path("/home/sergio/dollari/.env")]:
            if env_path.exists():
                lines = env_path.read_text().splitlines()
                key = secret = ""
                for l in lines:
                    if l.startswith("BINANCE_API_KEY="): key = l.split("=",1)[1].strip()
                    elif l.startswith("BINANCE_API_SECRET="): secret = l.split("=",1)[1].strip()
                if key: break
        if not key:
            key = os.environ.get("BINANCE_API_KEY", "")
            secret = os.environ.get("BINANCE_API_SECRET", "")
        if not key:
            logger.error("No API keys"); sys.exit(1)
        self.ex = ccxt.binance({"apiKey":key, "secret":secret, "enableRateLimit":True, "options":{"defaultType":"spot", "fetchCurrencies": False}})
        await self.ex.load_markets()
        logger.info(f"ORION connected | key={key[:8]}...")

    async def bal(self, asset):
        b = await self.ex.fetch_balance()
        return {"free": float(b["free"].get(asset,0) or 0), "total": float(b["total"].get(asset,0) or 0)}

    async def eur_free(self):
        b = await self.ex.fetch_balance()
        return float(b["free"].get("EUR",0) or 0)

    async def price(self, symbol):
        t = await self.ex.fetch_ticker(symbol)
        return float(t.get("last",0) or 0)

    async def cancel(self, symbol, oid=None):
        try:
            for o in await self.ex.fetch_open_orders(symbol):
                if oid is None or str(o["id"]) == str(oid):
                    await self.ex.cancel_order(o["id"], symbol)
        except: pass

    async def cancel_all_symbol(self, symbol):
        await self.cancel(symbol, None)

    async def check_order(self, symbol):
        try:
            os = await self.ex.fetch_open_orders(symbol)
            return {str(o["id"]) for o in os}
        except: return set()

    async def place_reversal(self, symbol):
        cfg = self.meta[symbol]
        ass = cfg["asset"]
        p = await self.price(symbol)
        if p <= 0: return

        b = await self.bal(ass)
        ef = await self.eur_free()
        st = self.orders[symbol]

        # ── Trailing sell: if we have an active sell and price ran up, adjust higher ──
        if st["sell_id"] and st["sell_price"] and p > st["sell_price"]:
            if not st.get("trail_peak") or p > st["trail_peak"]:
                st["trail_peak"] = p
            min_trail = st["sell_price"] * (1 + abs(cfg.get("sell_raise", 0.004)) * 0.5)
            if st["trail_peak"] >= min_trail and not st.get("trail_active"):
                st["trail_active"] = True
            if st["trail_active"] and p >= st["trail_peak"] * 0.998:
                new_price = round(p * (1 + cfg["sell_raise"]), 2)
                if new_price > st["sell_price"]:
                    await self.cancel(symbol, st["sell_id"])
                    sell_amt = round(min(cfg["sell_amt"], b["total"] * 0.6), cfg["decimals"])
                    if sell_amt >= 0.00001 and sell_amt * new_price >= MIN_NOTIONAL:
                        try:
                            o = await self.ex.create_limit_sell_order(symbol, sell_amt, new_price)
                            logger.info(f"  TRAIL SELL {sell_amt} {ass} {st['sell_price']}→{new_price}")
                            st["sell_id"] = str(o["id"]); st["sell_price"] = new_price
                            st["trail_peak"] = p
                        except Exception as e:
                            logger.error(f"  TRAIL SELL fail: {e}")
                    return

        # ── Normal reversal placement ──
        # v2: only cancel stale orders (>15 min old), don't reset on every cycle

        sell_amt = round(min(cfg["sell_amt"], b["total"] * 0.6), cfg["decimals"])
        if sell_amt >= 0.00001 and sell_amt * p * (1+cfg["sell_raise"]) >= MIN_NOTIONAL:
            sell_price = round(p * (1 + cfg["sell_raise"]), 2)
            try:
                o = await self.ex.create_limit_sell_order(symbol, sell_amt, sell_price)
                st["sell_id"] = str(o["id"]); st["sell_price"] = sell_price
                st["trail_peak"] = p
                st["trail_active"] = False
                logger.info(f"  SELL {sell_amt} {ass} @ {sell_price} | id={o['id'][:12]}")
            except Exception as e:
                logger.error(f"  SELL {ass} fail: {e}")

        elif ef >= cfg["max_eur"]:
            buy_eur = min(cfg["max_eur"], ef * 0.5)
            buy_amt = round(buy_eur / p, cfg["decimals"])
            if buy_amt >= 0.00001 and buy_amt * p >= MIN_NOTIONAL:
                buy_price = round(p * (1 + cfg["buy_drop"]), 2)
                try:
                    o = await self.ex.create_limit_buy_order(symbol, buy_amt, buy_price)
                    st["buy_id"] = str(o["id"]); st["buy_price"] = buy_price
                    st["sell_price"] = None; st["sell_id"] = None
                    logger.info(f"  BUY {buy_amt} {ass} @ {buy_price} | {buy_eur:.2f}€ | id={o['id'][:12]}")
                except Exception as e:
                    logger.error(f"  BUY {ass} fail: {e}")

    async def check_fills(self, symbol):
        cfg = self.meta[symbol]
        ass = cfg["asset"]
        st = self.orders[symbol]
        open_ids = await self.check_order(symbol)
        try:
            trades = await self.ex.fetch_my_trades(symbol, limit=10)
            filled = {str(t.get("order") or (t.get("info") or {}).get("orderId")) for t in trades}
        except: filled = set()
        changed = False

        if st["sell_id"] and st["sell_id"] not in open_ids:
            if st["sell_id"] in filled:
                self.fills += 1
                logger.info(f"  ✅ SELL filled {ass} @ {st['sell_price']}")
                st["sell_id"] = None
                changed = True
            else:
                st["sell_id"] = None

        if st["buy_id"] and st["buy_id"] not in open_ids:
            if st["buy_id"] in filled:
                self.fills += 1
                profit = (st["sell_price"] - st["buy_price"]) * cfg["sell_amt"] if st["sell_price"] else 0
                self.profit += profit
                logger.info(f"  ✅ BUY filled {ass} @ {st['buy_price']} | profit={profit:.4f}€")
                st["buy_id"] = None
                changed = True
            else:
                st["buy_id"] = None

        if changed: self._save()

    async def run(self):
        # Retry connect with backoff
        for attempt in range(5):
            try:
                await self.connect()
                logger.info("ORION — Multi-asset reversal bot v1")
                break
            except Exception as e:
                logger.warning(f"Connect attempt {attempt+1}/5 failed: {str(e)[:80]}")
                if attempt < 4:
                    await asyncio.sleep(15 * (attempt + 1))
                else:
                    logger.error("All connect attempts failed, retrying in 60s")
                    await asyncio.sleep(60)
                    # Keep trying forever
                    while True:
                        try:
                            await self.connect()
                            logger.info("ORION — reconnected")
                            break
                        except:
                            await asyncio.sleep(120)
        logger.info(f"Pairs: {', '.join(PAIRS.keys())}")
        logger.info(f"State: profit={self.profit:.4f} fills={self.fills}")
        status_interval = 60
        last_status = 0

        # Cancel stale ETH orders immediately
        logger.info("Cleaning stale orders...")
        for s in PAIRS:
            try:
                for o in await self.ex.fetch_open_orders(s):
                    await self.ex.cancel_order(o["id"], s)
            except: pass
        logger.info("Stale orders cleared")

        # Initial placement
        for s in PAIRS:
            await self.place_reversal(s)

        while True:
            try:
                if int(time.time()) % 1800 < 2:
                    self._refresh_params()

                # ── Regime-based throttling ──
                quiet_mult = 1.0
                try:
                    reg_path = BASE / "regime.json"
                    if reg_path.exists():
                        reg = json.loads(reg_path.read_text())
                        r = reg.get("regime", "ranging")
                        if r == "quiet":
                            quiet_mult = 0.5
                        elif r == "volatile":
                            quiet_mult = 0.7
                except: pass

                for s in PAIRS:
                    cfg = self.meta[s]
                    if cfg.get("paused", False):
                        continue
                    # Apply throttled sizes
                    cfg["sell_amt"] = PAIRS[s]["sell_amt"] * max(0.5, quiet_mult)  # floor at 50%
                    cfg["max_eur"] = max(PAIRS[s]["max_eur"], int(PAIRS[s]["max_eur"] * max(0.5, quiet_mult)))
                    await self.check_fills(s)
                    st = self.orders[s]
                    if not st["sell_id"] and not st["buy_id"]:
                        await self.place_reversal(s)

                now = time.time()
                if now - last_status > status_interval:
                    last_status = now
                    parts = []
                    for s in PAIRS:
                        st = self.orders[s]
                        action = "SELL" if st["sell_id"] else ("BUY" if st["buy_id"] else "IDLE")
                        parts.append(f"{self.meta[s]['asset']}={action}")
                    ef = await self.eur_free()
                    logger.info(f"{' | '.join(parts)} | EUR={ef:.2f} | profit={self.profit:.4f} fills={self.fills}")

                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Loop: {e}", exc_info=True)
                await asyncio.sleep(10)

if __name__ == "__main__":
    b = OrionBot()
    try:
        asyncio.run(b.run())
    except KeyboardInterrupt:
        asyncio.run(b.ex.close() if b.ex else None)
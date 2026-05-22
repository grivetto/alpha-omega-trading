#!/usr/bin/env python3
"""
STELLATRON v1 — Unified Intelligent Trading System
Single-instance, self-optimizing grid trading for Binance spot.

Scaltro, opportunista, veloce. Un bot per governarli tutti.
"""
import asyncio
import ccxt.async_support as ccxt
import logging
import os
import sys
import time
import json
import sqlite3
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, field

BASE_DIR = Path(__file__).parent
LOG_FILE = BASE_DIR / "stellatron.log"
DB_FILE = BASE_DIR / "stellatron.db"
STATE_DIR = BASE_DIR / ".tmp"
STATE_FILE = STATE_DIR / "stellatron_state.json"
CONFIG_FILE = BASE_DIR / "stellatron_config.json"
PARAMS_FILE = BASE_DIR / "params_stellatron.json"

OPTIMIZER_API = "http://192.168.1.99:8899/api/params/stellatron"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(str(LOG_FILE)),
    ],
    force=True,
)
logger = logging.getLogger("Stellatron")

# ── Constants ───────────────────────────────────────────────────────
MIN_NOTIONAL = 5.0
FEE_RATE = 0.00075
TELEGRAM_API = "https://api.telegram.org/bot"

# ── Default config (overridable via CONFIG_FILE) ────────────────────
DEFAULT_CONFIG = {
    "pairs": ["ADA/EUR", "SOL/EUR"],
    "primary_pair": "ADA/EUR",
    "grid_spacing": 0.003,
    "profit_pct": 0.004,
    "base_order_eur": 5.5,
    "min_grid_levels": 3,
    "max_grid_levels": 6,
    "max_invested_eur": 50.0,
    "daily_loss_limit_pct": -3.0,
    "max_drawdown_pct": -10.0,
    "rebalance_interval_sec": 180,
    "compound_enabled": True,
    "compound_cap": 1.8,
    "telegram_enabled": False,
    "telegram_token": "",
    "telegram_chat_id": "",
    "pair_switch_enabled": True,
    "pair_switch_min_interval_hours": 4,
    "momentum_rsi_threshold": 55,
    "momentum_volume_multiplier": 2.0,
    "pair_performance_window": 20,
}


def load_config():
    cfg = DEFAULT_CONFIG.copy()
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE) as f:
                cfg.update(json.load(f))
            logger.info(f"Config loaded from {CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to load config: {e}, using defaults")
    cfg["pair_configs"] = {}
    for p in cfg["pairs"]:
        asset = p.split("/")[0]
        if "ADA" in asset:
            cfg["pair_configs"][p] = {
                "grid_spacing": 0.002,
                "profit_pct": 0.003,
                "min_levels": 5,
                "max_levels": 10,
                "base_order": 5.5,
            }
        elif "SOL" in asset:
            cfg["pair_configs"][p] = {
                "grid_spacing": 0.003,
                "profit_pct": 0.004,
                "min_levels": 3,
                "max_levels": 6,
                "base_order": 5.5,
        }
    return cfg


class DB:
    def __init__(self, path=DB_FILE):
        self.path = path
        self._conn = None

    def conn(self):
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
            self._init()
        return self._conn

    def _init(self):
        c = self.conn()
        c.execute("""CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT, side TEXT, price REAL, amount REAL,
            eur_value REAL, fee REAL, net_pnl REAL,
            filled_at TEXT, strategy TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS daily_pnl (
            day TEXT PRIMARY KEY, symbol TEXT,
            pnl REAL, trades INTEGER, fees REAL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS state (
            key TEXT PRIMARY KEY, value TEXT, updated_at REAL
        )""")
        c.commit()

    def save_trade(self, symbol, side, price, amount, eur_value, fee, net_pnl, strategy="grid"):
        now = datetime.now(timezone.utc).isoformat()
        self.conn().execute(
            "INSERT INTO trades (symbol, side, price, amount, eur_value, fee, net_pnl, filled_at, strategy) VALUES (?,?,?,?,?,?,?,?,?)",
            (symbol, side, price, amount, eur_value, fee, net_pnl, now, strategy)
        )
        self.conn().commit()

    def get_daily_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        c = self.conn().execute(
            "SELECT COALESCE(SUM(net_pnl),0), COUNT(*), COALESCE(SUM(fee),0) FROM trades WHERE date(filled_at) = ?",
            (today,))
        row = c.fetchone()
        return {"pnl": row[0], "trades": row[1], "fees": row[2]}

    def get_total_stats(self):
        c = self.conn().execute(
            "SELECT COALESCE(SUM(net_pnl),0), COUNT(*), COALESCE(SUM(fee),0), "
            "COALESCE(SUM(CASE WHEN net_pnl>0 THEN 1 ELSE 0 END),0), "
            "COALESCE(SUM(CASE WHEN net_pnl<0 THEN 1 ELSE 0 END),0) FROM trades")
        row = c.fetchone()
        wins = row[3] or 0
        losses = row[4] or 0
        total = wins + losses
        return {
            "total_pnl": row[0], "total_trades": row[1], "total_fees": row[2],
            "wins": wins, "losses": losses,
            "win_rate": (wins / total * 100) if total > 0 else 0,
        }

    def get_pair_performance(self, symbol, n=20):
        c = self.conn().execute(
            "SELECT net_pnl FROM trades WHERE symbol=? ORDER BY id DESC LIMIT ?", (symbol, n))
        pnls = [r[0] for r in c.fetchall()]
        if not pnls: return {"avg_pnl": 0, "win_rate": 0, "total": 0}
        wins = sum(1 for p in pnls if p > 0)
        return {
            "avg_pnl": sum(pnls) / len(pnls),
            "win_rate": wins / len(pnls) * 100,
            "total": sum(pnls),
            "count": len(pnls),
        }

    def set_state(self, key, value):
        self.conn().execute(
            "INSERT OR REPLACE INTO state (key, value, updated_at) VALUES (?,?,?)",
            (key, json.dumps(value), time.time()))
        self.conn().commit()

    def get_state(self, key):
        c = self.conn().execute("SELECT value FROM state WHERE key=?", (key,))
        row = c.fetchone()
        return json.loads(row[0]) if row else None


class Telegram:
    def __init__(self, token, chat_id):
        self.token = token
        self.chat_id = chat_id
        self.enabled = bool(token and chat_id)

    async def send(self, text):
        if not self.enabled: return
        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                url = f"{TELEGRAM_API}{self.token}/sendMessage"
                async with session.post(url, json={
                    "chat_id": self.chat_id, "text": text,
                    "parse_mode": "HTML", "disable_web_page_preview": True,
                }, timeout=aiohttp.ClientTimeout(total=10)):
                    pass
        except ImportError:
            logger.warning("aiohttp not installed — skipping Telegram")
        except Exception as e:
            logger.debug(f"Telegram send error: {e}")

    async def send_async(self, text):
        await self.send(text)


class Stellatron:
    def __init__(self):
        self.cfg = load_config()
        self.db = DB()
        self.exchange = None
        self.symbol = self.cfg["primary_pair"]
        self.asset = self.symbol.split("/")[0]
        self.tg = Telegram(self.cfg["telegram_token"], self.cfg["telegram_chat_id"])
        self.running = True
        self.grid_buys = {}
        self.grid_sells = {}
        self.total_invested = 0.0
        self.total_profit = 0.0
        self.total_fees = 0.0
        self.fills = 0
        self.compound = 1.0
        self.last_rebalance = 0
        self.last_pair_switch = 0
        self.center_price = 0
        self.daily_start_pnl = 0.0
        self.session_start_pnl = 0.0
        self.last_notify = 0
        self._last_day = datetime.now().strftime("%Y-%m-%d")
        self.atr_cache = {}
        self._last_params_fetch = 0
        self._load_state()
        self._load_optimized_params()

    # ── Optimized Params (from Denaro Memory) ──────────────────────
    def _load_optimized_params(self):
        """Fetch params from Denaro optimizer API, fall back to local file or defaults."""
        params = None
        # Try HTTP API first
        try:
            with urllib.request.urlopen(OPTIMIZER_API, timeout=5) as resp:
                data = json.loads(resp.read().decode())
                params = data.get("params", {})
                if params:
                    logger.info(f"Loaded optimized params from API: {json.dumps(params)}")
        except Exception as e:
            logger.debug(f"Optimizer API unreachable ({e}), trying local file")

        # Fall back to local file
        if not params and PARAMS_FILE.exists():
            try:
                params = json.loads(PARAMS_FILE.read_text())
                logger.info(f"Loaded params from {PARAMS_FILE}")
            except Exception as e:
                logger.debug(f"Params file error: {e}")

        if not params:
            return

        # Apply params to config
        if "grid_spacing" in params:
            self.cfg["grid_spacing"] = params["grid_spacing"]
        if "base_order_eur" in params:
            self.cfg["base_order_eur"] = params["base_order_eur"]
        if "compound_cap" in params:
            self.cfg["compound_cap"] = params["compound_cap"]
        if "min_grid_levels" in params:
            self.cfg["min_grid_levels"] = params["min_grid_levels"]
        if "max_grid_levels" in params:
            self.cfg["max_grid_levels"] = params["max_grid_levels"]

        # Update pair_configs
        for p in self.cfg["pair_configs"]:
            pc = self.cfg["pair_configs"][p]
            if "grid_spacing" in params:
                pc["grid_spacing"] = params["grid_spacing"]
                pc["profit_pct"] = max(0.002, params["grid_spacing"] * 1.3)
            if "base_order_eur" in params:
                pc["base_order"] = params["base_order_eur"]
            if "min_grid_levels" in params:
                pc["min_levels"] = params["min_grid_levels"]
            if "max_grid_levels" in params:
                pc["max_levels"] = params["max_grid_levels"]

        logger.info(f"Optimized params applied: spacing={self.cfg['grid_spacing']}, "
                    f"order={self.cfg['base_order_eur']}€")

    def _refresh_params(self):
        """Periodic refresh — called from main loop every 30 min"""
        now = time.time()
        if now - self._last_params_fetch > 1800:
            self._last_params_fetch = now
            self._load_optimized_params()

    # ── API Connection ──────────────────────────────────────────────
    async def connect(self):
        api_key, api_secret = "", ""
        for env_path in [BASE_DIR / ".env"]:
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        line = line.strip()
                        if line.startswith("BINANCE_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                        elif line.startswith("BINANCE_API_SECRET="):
                            api_secret = line.split("=", 1)[1].strip()
        if not api_key:
            api_key = os.environ.get("BINANCE_API_KEY", "")
            api_secret = os.environ.get("BINANCE_API_SECRET", "")
        if not api_key:
            logger.error("No Binance API keys found!")
            await self.tg.send("STELLATRON: ❌ No API keys — aborting")
            sys.exit(1)

        self.exchange = ccxt.binance({
            "apiKey": api_key, "secret": api_secret,
            "enableRateLimit": True,
            "options": {"defaultType": "spot"},
        })
        await self.exchange.load_markets()
        logger.info(f"Connected to Binance | key={api_key[:8]}...")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    # ── Balance & Market Data ───────────────────────────────────────
    async def get_balances(self):
        bal = await self.exchange.fetch_balance()
        eur = bal.get("EUR", {})
        asset = bal.get(self.asset, {})
        return {
            "EUR_free": float(eur.get("free", 0) or 0),
            "EUR_used": float(eur.get("used", 0) or 0),
            "EUR_total": float(eur.get("total", 0) or 0),
            "asset_free": float(asset.get("free", 0) or 0),
            "asset_total": float(asset.get("total", 0) or 0),
        }

    async def get_price(self):
        t = await self.exchange.fetch_ticker(self.symbol)
        return float(t.get("last", 0))

    async def get_atr(self, symbol=None, limit=20):
        s = symbol or self.symbol
        ohlcv = await self.exchange.fetch_ohlcv(s, timeframe="1h", limit=limit + 1)
        if len(ohlcv) < 2: return 0
        trs = []
        for i in range(1, len(ohlcv)):
            h, l, pc = ohlcv[i][2], ohlcv[i][3], ohlcv[i - 1][4]
            trs.append(max(h - l, abs(h - pc), abs(l - pc)))
        return sum(trs[-14:]) / min(len(trs), 14)

    async def get_rsi(self, symbol=None):
        s = symbol or self.symbol
        ohlcv = await self.exchange.fetch_ohlcv(s, timeframe="5m", limit=15)
        closes = [c[4] for c in ohlcv]
        if len(closes) < 15: return 50
        deltas = [closes[i] - closes[i - 1] for i in range(1, len(closes))]
        gains = sum(d for d in deltas if d > 0) / 14
        losses = sum(-d for d in deltas if d < 0) / 14
        if losses == 0: return 100
        return 100 - (100 / (1 + gains / losses))

    async def get_volume_ratio(self, symbol=None):
        s = symbol or self.symbol
        ohlcv = await self.exchange.fetch_ohlcv(s, timeframe="5m", limit=20)
        vols = [c[5] for c in ohlcv]
        if len(vols) < 3: return 1.0
        recent = sum(vols[-3:]) / 3
        avg = sum(vols) / len(vols)
        return recent / avg if avg > 0 else 1.0

    # ── Pair Selection ──────────────────────────────────────────────
    async def pick_best_pair(self):
        if not self.cfg["pair_switch_enabled"]:
            return self.symbol
        now = time.time()
        interval = self.cfg["pair_switch_min_interval_hours"] * 3600
        if now - self.last_pair_switch < interval:
            return self.symbol

        best = self.symbol
        best_score = -999
        for p in self.cfg["pairs"]:
            try:
                ticker = await self.exchange.fetch_ticker(p)
                spread = ((ticker.get("ask", 0) or 0) - (ticker.get("bid", 0) or 0)) / (ticker.get("last", 1) or 1) * 100
                atr = await self.get_atr(p)
                price = float(ticker.get("last", 0) or 0)
                vol_pct = (atr / price * 100) if price > 0 else 0
                perf = self.db.get_pair_performance(p, self.cfg["pair_performance_window"])
                perf_count = perf.get("count", 0)
                perf_score = min(perf["total"] * 10, 5) if perf_count >= 3 else 0

                score = vol_pct * 3 + perf_score - spread * 2
                logger.info(f"Pair eval {p}: vol={vol_pct:.2f}% spread={spread:.3f}% perf={perf['total']:.4f} score={score:.2f}")
                if score > best_score:
                    best_score = score
                    best = p
            except Exception as e:
                logger.warning(f"Pair eval error for {p}: {e}")

        self.last_pair_switch = now
        if best != self.symbol:
            logger.info(f"Switching pair: {self.symbol} -> {best} (score delta: {best_score:.1f})")
            self.db.set_state("pair_switch", {
                "from": self.symbol, "to": best, "score": best_score, "time": now
            })
        return best

    # ── Grid Management ─────────────────────────────────────────────
    async def cancel_all(self):
        try:
            orders = await self.exchange.fetch_open_orders(self.symbol)
            for o in orders:
                try:
                    await self.exchange.cancel_order(o["id"], self.symbol)
                except Exception:
                    pass
        except Exception:
            pass
        self.grid_buys = {}
        self.grid_sells = {}
        self.total_invested = 0

    async def place_grid(self, price):
        await self.cancel_all()
        self.center_price = price
        self.last_rebalance = time.time()

        bal = await self.get_balances()
        eur_free = bal["EUR_free"]
        asset_free = bal["asset_free"]
        pc = self.cfg["pair_configs"].get(self.symbol, {})
        spacing = pc.get("profit_pct", self.cfg["grid_spacing"])
        profit = pc.get("profit_pct", self.cfg["profit_pct"])
        min_lv = pc.get("min_levels", self.cfg["min_grid_levels"])
        max_lv = pc.get("max_levels", self.cfg["max_grid_levels"])
        base_order = pc.get("base_order", self.cfg["base_order_eur"]) * self.compound
        order_eur = max(base_order, MIN_NOTIONAL)

        max_possible = int(eur_free * 0.85 / order_eur)
        grid_levels = max(min_lv, min(max_lv, max_possible))
        if grid_levels < 1: grid_levels = 1

        if eur_free < MIN_NOTIONAL:
            logger.info(f"Insufficient capital: EUR_free={eur_free:.2f} < {MIN_NOTIONAL}")
            return

        logger.info(f"Grid@{price} | EUR={eur_free:.2f} {self.asset}={asset_free:.4f} | "
                    f"order={order_eur:.2f} | levels={grid_levels} | compound={self.compound:.2f}x")

        half = grid_levels // 2
        actual_buys = 0

        for i in range(1, half + 1):
            buy_price = round(price * (1 - i * spacing), 2)
            size_eur = order_eur * (1 + i * 0.05)
            if self.total_invested + size_eur > self.cfg["max_invested_eur"]:
                break
            if size_eur > eur_free * 0.85:
                break
            if size_eur < MIN_NOTIONAL:
                break
            amount = round(size_eur / buy_price, 3)
            if amount < 0.001:
                continue
            notional = amount * buy_price
            if notional < MIN_NOTIONAL:
                continue
            try:
                order = await self.exchange.create_limit_buy_order(self.symbol, amount, buy_price)
                oid = order["id"]
                self.grid_buys[oid] = {"price": buy_price, "amount": amount, "eur": size_eur}
                self.total_invested += size_eur
                eur_free -= size_eur
                actual_buys += 1
                logger.info(f"BUY #{i} @ {buy_price} ({amount} {self.asset}, {size_eur:.2f}€)")
            except Exception as e:
                logger.error(f"Buy fail @ {buy_price}: {e}")

        asset_value = asset_free * price
        actual_sells = 0
        if asset_value >= MIN_NOTIONAL:
            for i in range(1, half + 1):
                sell_price = round(price * (1 + i * spacing), 2)
                sell_amount = round(min(asset_free * 0.2, order_eur / sell_price), 3)
                sell_notional = sell_amount * sell_price
                if sell_notional < MIN_NOTIONAL:
                    continue
                if sell_amount < 0.001:
                    break
                try:
                    order = await self.exchange.create_limit_sell_order(self.symbol, sell_amount, sell_price)
                    self.grid_sells[order["id"]] = {"price": sell_price, "amount": sell_amount}
                    asset_free -= sell_amount
                    actual_sells += 1
                    logger.info(f"SELL #{i} @ {sell_price} ({sell_amount} {self.asset})")
                except Exception as e:
                    logger.error(f"Sell fail @ {sell_price}: {e}")

        logger.info(f"Grid placed: {actual_buys} buys, {actual_sells} sells, invested={self.total_invested:.2f}€")

    async def check_fills(self, price):
        open_orders = await self.exchange.fetch_open_orders(self.symbol)
        open_ids = {o["id"] for o in open_orders}
        try:
            trades = await self.exchange.fetch_my_trades(self.symbol, limit=25)
            filled_ids = {t.get("order") or t.get("info", {}).get("orderId") for t in trades}
        except Exception:
            filled_ids = set()

        for oid in list(self.grid_buys.keys()):
            if oid not in open_ids:
                info = self.grid_buys.pop(oid)
                self.total_invested -= info["eur"]
                if oid in filled_ids:
                    sell_price = round(info["price"] * (1 + self.cfg["profit_pct"]), 2)
                    sell_amount = round(info["amount"] * 0.997, 3)
                    if sell_amount * sell_price >= MIN_NOTIONAL:
                        try:
                            order = await self.exchange.create_limit_sell_order(self.symbol, sell_amount, sell_price)
                            self.grid_sells[order["id"]] = {"price": sell_price, "amount": sell_amount}
                            self.fills += 1
                            logger.info(f"BUY filled @ {info['price']} -> sell @ {sell_price}")
                        except Exception as e:
                            logger.error(f"Sell after buy fill failed: {e}")
                    elif oid in filled_ids:
                        self.fills += 1
                else:
                    logger.info(f"Buy canceled @ {info['price']}")

        for oid in list(self.grid_sells.keys()):
            if oid not in open_ids:
                info = self.grid_sells.pop(oid)
                if oid in filled_ids:
                    buy_price = round(info["price"] * (1 - self.cfg["profit_pct"]), 2)
                    buy_eur = self.cfg["base_order_eur"] * self.compound
                    amount = round(buy_eur / buy_price, 3)
                    notional = amount * buy_price
                    if notional >= MIN_NOTIONAL and buy_eur <= (await self.get_balances())["EUR_free"] * 0.9:
                        try:
                            order = await self.exchange.create_limit_buy_order(self.symbol, amount, buy_price)
                            self.grid_buys[order["id"]] = {"price": buy_price, "amount": amount, "eur": buy_eur}
                            self.total_invested += buy_eur
                            self.fills += 1
                            profit = self.cfg["profit_pct"] * buy_eur
                            fee = buy_eur * FEE_RATE * 2
                            net = profit - fee
                            self.total_profit += net
                            self.total_fees += fee
                            self.db.save_trade(self.symbol, "sell", info["price"], info["amount"],
                                             info["amount"] * info["price"], fee, net)
                            self._update_compound()
                            logger.info(f"SELL filled @ {info['price']} -> buy @ {buy_price} | "
                                        f"net={net:.4f} | total_profit={self.total_profit:.4f}")
                        except Exception as e:
                            logger.error(f"Buy after sell fill failed: {e}")
                    else:
                        logger.info(f"Sell filled but insufficient EUR to re-buy")
                else:
                    logger.info(f"Sell canceled @ {info['price']}")

    def needs_rebalance(self, price):
        if not self.center_price:
            return True
        dist = abs(price - self.center_price) / self.center_price
        if dist > self.cfg["grid_spacing"] * 4:
            return True
        if time.time() - self.last_rebalance > self.cfg["rebalance_interval_sec"]:
            return True
        return False

    def _update_compound(self):
        if not self.cfg["compound_enabled"]:
            return
        if self.total_profit >= 1.0:
            self.compound = 1.0 + (self.total_profit / 50)
            self.compound = min(self.compound, self.cfg["compound_cap"])

    # ── State Persistence ────────────────────────────────────────────
    def _save_state(self):
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state = {
            "symbol": self.symbol, "total_profit": self.total_profit,
            "total_fees": self.total_fees, "fills": self.fills,
            "compound": self.compound, "center_price": self.center_price,
            "total_invested": self.total_invested, "last_rebalance": self.last_rebalance,
            "last_pair_switch": self.last_pair_switch, "session_start_pnl": self.session_start_pnl,
            "daily_start_pnl": self.daily_start_pnl,
        }
        try:
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"State save error: {e}")

    def _load_state(self):
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE) as f:
                state = json.load(f)
            self.symbol = state.get("symbol", self.symbol)
            self.total_profit = state.get("total_profit", 0)
            self.total_fees = state.get("total_fees", 0)
            self.fills = state.get("fills", 0)
            self.compound = state.get("compound", 1.0)
            self.center_price = state.get("center_price", 0)
            self.total_invested = state.get("total_invested", 0)
            self.last_rebalance = state.get("last_rebalance", 0)
            self.last_pair_switch = state.get("last_pair_switch", 0)
            self.session_start_pnl = state.get("session_start_pnl", 0)
            self.daily_start_pnl = state.get("daily_start_pnl", 0)
            logger.info(f"State restored: symbol={self.symbol} profit={self.total_profit:.4f} fills={self.fills}")
        except Exception as e:
            logger.warning(f"State load error: {e}")

    # ── Notifications ────────────────────────────────────────────────
    async def send_status(self, force=False):
        now = time.time()
        if not force and now - self.last_notify < 3600:
            return
        self.last_notify = now
        bal = await self.get_balances()
        price = await self.get_price()
        daily = self.db.get_daily_stats()
        total = self.db.get_total_stats()
        eur_total = bal["EUR_free"] + bal["EUR_used"]
        asset_val = bal["asset_total"] * price
        portfolio = eur_total + asset_val

        now_dt = datetime.now().strftime("%H:%M")
        msg = (
            f"🤖 <b>STELLATRON</b> | {now_dt}\n"
            f"📊 {self.symbol} @ {price:.4f}\n"
            f"💰 Portfolio: {portfolio:.2f}€ | Grid: {self.total_invested:.2f}€\n"
            f"📈 Today: {daily['pnl']:+.4f}€ ({daily['trades']} trades)\n"
            f"📊 All-time: {total['total_pnl']:+.4f}€ | {total['wins']}W/{total['losses']}L ({total['win_rate']:.0f}%)\n"
            f"🔄 Grid: {len(self.grid_buys)} buys / {len(self.grid_sells)} sells | {self.fills} fills\n"
            f"⚡ Compound: {self.compound:.2f}x"
        )
        await self.tg.send(msg)
        logger.info(f"Status sent: portfolio={portfolio:.2f}€ daily={daily['pnl']:+.4f}€")

    # ── Main Loop ───────────────────────────────────────────────────
    async def run(self):
        await self.connect()
        self.session_start_pnl = self.total_profit
        self.daily_start_pnl = self.total_profit

        await self.tg.send(f"🚀 <b>STELLATRON</b> avviato\n"
                          f"📊 Pair: {self.symbol}\n"
                          f"📈 Profit storico: {self.total_profit:+.4f}€ | {self.fills} fills\n"
                          f"⚡ Compound: {self.compound:.2f}x")

        logger.info(f"Stellatron started | {self.symbol} | profit={self.total_profit:.4f} | fills={self.fills}")

        try:
            while self.running:
                try:
                    price = await self.get_price()
                    if price <= 0:
                        await asyncio.sleep(2)
                        continue

                    today = datetime.now().strftime("%Y-%m-%d")
                    if self._last_day != today:
                        self._last_day = today
                        self.daily_start_pnl = self.total_profit
                        daily_summary = self.db.get_daily_stats()
                        logger.info(f"📅 Day rollover — today's PnL so far: {daily_summary['pnl']:+.4f}€")

                    # Check loss limits
                    daily_pnl = self.total_profit - self.daily_start_pnl
                    if daily_pnl < 0 and abs(daily_pnl) > abs(self.session_start_pnl * self.cfg["daily_loss_limit_pct"] / 100):
                        logger.warning(f"Daily loss limit hit: {daily_pnl:.2f}€ — pausing grid")
                        await self.tg.send(f"⚠️ <b>Daily loss limit</b>: {daily_pnl:.2f}€ — pausing 30 min")
                        await asyncio.sleep(1800)
                        self.daily_start_pnl = self.total_profit
                        continue

                    new_pair = await self.pick_best_pair()
                    if new_pair != self.symbol:
                        await self.cancel_all()
                        self.symbol = new_pair
                        self.asset = self.symbol.split("/")[0]
                        self.grid_buys = {}
                        self.grid_sells = {}
                        self.total_invested = 0
                        self.center_price = 0
                        logger.info(f"Switched to {self.symbol}")
                        await self.tg.send(f"Switched to <b>{self.symbol}</b>")

                    # Grid rebalance or check fills
                    if self.needs_rebalance(price):
                        await self.place_grid(price)
                    else:
                        await self.check_fills(price)

                    # Status log
                    if int(time.time()) % 30 < 2:
                        bal = await self.get_balances()
                        daily_pnl = self.total_profit - self.daily_start_pnl
                        logger.info(f"Price={price} | B={len(self.grid_buys)} S={len(self.grid_sells)} | "
                                    f"inv={self.total_invested:.2f} | profit={self.total_profit:.4f} | "
                                    f"fills={self.fills} | EUR_free={bal['EUR_free']:.2f} | "
                                    f"compound={self.compound:.2f}x | today={daily_pnl:+.4f}")

                    # Periodic param refresh (every 30 min)
                    if int(time.time()) % 1800 < 2:
                        self._refresh_params()

                    # Periodic status notification (every 4h)
                    if int(time.time()) % 14400 < 2:
                        await self.send_status()

                    # Save state every 30s
                    if int(time.time()) % 30 < 2:
                        self._save_state()

                    await asyncio.sleep(2)

                except Exception as e:
                    logger.error(f"Loop error: {e}", exc_info=True)
                    await asyncio.sleep(5)

        except KeyboardInterrupt:
            logger.info("Shutdown requested")
        finally:
            self._save_state()
            await self.cancel_all()
            await self.tg.send("🛑 <b>STELLATRON</b> spento")
            await self.close()


if __name__ == "__main__":
    bot = Stellatron()
    asyncio.run(bot.run())

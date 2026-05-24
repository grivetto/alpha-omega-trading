#!/usr/bin/env python3
import os, json, logging, time, asyncio, urllib.request, urllib.error
from pathlib import Path
from datetime import datetime, timezone
import ccxt
import pandas as pd
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH)

def setup_logger(name, log_file):
    log_path = BASE_DIR / log_file
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh = logging.FileHandler(str(log_path))
    fh.setFormatter(fmt)
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    logger.handlers.clear()
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger

def make_client():
    key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_API_SECRET")
    if not key or not secret:
        raise EnvironmentError("BINANCE_API_KEY/SECRET missing in .env")
    return ccxt.binance({
        "apiKey": key,
        "secret": secret,
        "enableRateLimit": True,
        "options": {
            "defaultType": "spot",
            "defaultFeeCurrency": "BNB",
        },
    })

async def fetch_balance(client):
    b = await asyncio.to_thread(client.fetch_balance)
    free = {}
    used = {}
    for k, v in b.items():
        if isinstance(v, dict):
            free[k] = v.get("free", 0)
            used[k] = v.get("used", 0)
    return {"free": free, "used": used, "total": b.get("total", {})}

async def get_asset_balance(client, asset="EUR"):
    b = await fetch_balance(client)
    return b["free"].get(asset, 0.0)

async def cancel_all_orders(client, symbol):
    orders = await asyncio.to_thread(client.fetch_open_orders, symbol)
    for o in orders:
        try:
            await asyncio.to_thread(client.cancel_order, o["id"], symbol)
        except Exception:
            pass
    return len(orders)

async def place_limit_order(client, side, symbol, price, amount, reduce_only=False):
    try:
        if side == "buy":
            order = await asyncio.to_thread(
                client.create_limit_buy_order, symbol, round(amount, 6), round(price, 6)
            )
        else:
            order = await asyncio.to_thread(
                client.create_limit_sell_order, symbol, round(amount, 6), round(price, 6)
            )
        return order
    except ccxt.InsufficientFunds:
        return None
    except Exception as e:
        return None

async def place_market_order(client, side, symbol, amount_or_quote, use_quote=False):
    try:
        params = {"quoteOrderQty": amount_or_quote} if use_quote else {}
        if side == "buy":
            order = await asyncio.to_thread(
                client.create_market_buy_order, symbol, amount_or_quote, params
            )
        else:
            order = await asyncio.to_thread(
                client.create_market_sell_order, symbol, amount_or_quote, params
            )
        return order
    except Exception as e:
        return None

async def send_telegram(logger, message):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = json.dumps({"chat_id": chat_id, "text": message}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logger.error(f"Telegram error: {e}")

class RegimeClassifier:
    def __init__(self):
        self.regime = "unknown"
        self.confidence = 0.0
        self.last_update = 0
        self.history = []

    async def classify(self, client, symbol, timeframe="1h"):
        try:
            ohlcv = await asyncio.to_thread(
                client.fetch_ohlcv, symbol, timeframe=timeframe, limit=200
            )
            if len(ohlcv) < 100:
                return "unknown", 0.0

            df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "vol"])
            close = df["close"]
            high = df["high"]
            low = df["low"]

            ema50 = close.ewm(span=50).mean().iloc[-1]
            ema200 = close.ewm(span=200).mean().iloc[-1] if len(close) >= 200 else close.mean()

            last = close.iloc[-1]
            ema_dist = (last - ema50) / ema50 * 100

            tr = pd.concat([high - low, (high - close.shift()).abs(), (low - close.shift()).abs()], axis=1).max(axis=1)
            atr = tr.rolling(14).mean().iloc[-1]
            atr_pct = atr / last * 100 if last > 0 else 0

            rsi = 50.0
            try:
                import pandas_ta as ta
                rsi_series = ta.rsi(close, length=14)
                if rsi_series is not None and not rsi_series.empty:
                    rsi = float(rsi_series.iloc[-1])
            except ImportError:
                delta = close.diff()
                gain = delta.where(delta > 0, 0).rolling(14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
                rs = gain / loss.replace(0, 0.001)
                rsi = 100 - (100 / (1 + rs.iloc[-1])) if not rs.empty else 50

            vol_ratio = 1.0
            if len(close) >= 20:
                avg_vol = close.tail(20).mean()
                vol_ratio = last / avg_vol if avg_vol > 0 else 1.0

            trend_strength = abs(ema_dist)
            is_uptrend = ema50 > ema200 and ema_dist > 0
            is_downtrend = ema50 < ema200 and ema_dist < 0

            if atr_pct > 3.0:
                regime = "volatile"
                confidence = min(atr_pct / 5.0, 1.0)
            elif is_uptrend and trend_strength > 1.0 and rsi > 50:
                regime = "bull"
                confidence = min(trend_strength / 3.0, 0.95)
            elif is_downtrend and trend_strength > 1.0 and rsi < 50:
                regime = "bear"
                confidence = min(trend_strength / 3.0, 0.95)
            elif atr_pct < 1.0 and abs(ema_dist) < 1.0:
                regime = "choppy"
                confidence = 0.6
            else:
                regime = "neutral"
                confidence = 0.5

            self.regime = regime
            self.confidence = confidence
            self.last_update = time.time()
            self.history.append({"regime": regime, "time": datetime.now(timezone.utc).isoformat()})
            if len(self.history) > 100:
                self.history.pop(0)

            return regime, confidence

        except Exception as e:
            return "unknown", 0.0

class BotState:
    def __init__(self, bot_name):
        self.bot_name = bot_name
        self.state_path = BASE_DIR / ".tmp" / f"{bot_name}_state.json"
        (BASE_DIR / ".tmp").mkdir(parents=True, exist_ok=True)
        self.data = self._load()

    def _load(self):
        if self.state_path.exists():
            try:
                with open(self.state_path) as f:
                    return json.load(f)
            except Exception:
                pass
        return {"bot_name": self.bot_name, "started_at": datetime.now(timezone.utc).isoformat(), "pnl": 0.0, "trades": 0, "regime": "unknown"}

    def save(self):
        with open(self.state_path, "w") as f:
            json.dump(self.data, f)

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

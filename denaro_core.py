#!/usr/bin/env python3
"""
DENARO CORE v3 — Base class for Denaro trading bots.
Provides: Binance connectivity, balance management, order sync, ATR calculation.

This module was MISSING from the project — grid_bot_v3.py imports from it
but no file existed, causing immediate crash on startup.
"""

import ccxt
import time
import logging
import json
from pathlib import Path

logger = logging.getLogger("DenaroCore")


class DenaroCore:
    """
    Base class for all Denaro bots. Provides:
    - Binance exchange connectivity
    - Balance fetching and caching
    - Order synchronization
    - ATR (Average True Range) calculation for volatility
    - State persistence via SQLite
    """

    def __init__(self, bot_name="DenaroBot"):
        self.bot_name = bot_name
        self.config = {}
        self._client = None
        self._balances_cache = None
        self._balances_ts = 0
        self._cache_ttl = 5  # seconds
        self._state_db = Path(".tmp") / "denaro.db"
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Ensure .tmp directory exists"""
        self._state_db.parent.mkdir(parents=True, exist_ok=True)

    def load_config(self, path=None):
        """Load grid configuration from JSON"""
        if path is None:
            path = Path(__file__).parent / "grid_config.json"
        if not Path(path).exists():
            # Try alternate locations
            for alt in ["./grid_config.json", "../grid_config.json"]:
                if Path(alt).exists():
                    path = alt
                    break
        with open(path, 'r') as f:
            self.config = json.load(f)
        logger.info(f"Config loaded: symbol={self.config.get('symbol')}, "
                     f"grid_levels={self.config.get('grid_levels')}, "
                     f"base_order_eur={self.config.get('base_order_eur')}")
        return self.config

    @property
    def client(self):
        """Lazy Binance client initialization"""
        if self._client is None:
            self._init_client()
        return self._client

    def _init_client(self):
        """Initialize ccxt Binance client with API keys"""
        env_path = Path(".env")
        dotenv = {}
        if env_path.exists():
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        key, val = line.split('=', 1)
                        dotenv[key.strip()] = val.strip()

        self._client = ccxt.binance({
            'apiKey': dotenv.get('BINANCE_API_KEY', ''),
            'secret': dotenv.get('BINANCE_SECRET_KEY', ''),
            'sandbox': False,
            'options': {
                'defaultType': 'spot',
            },
        })
        # Disable nonce to avoid sync issues
        self._client.nonce = lambda: int(time.time() * 1000)
        logger.info(f"Binance client initialized for bot: {self.bot_name}")

    async def get_balance(self, asset):
        """Get free balance for an asset (EUR, SOL, BTC, etc.)"""
        now = time.time()
        if self._balances_cache and (now - self._balances_ts) < self._cache_ttl:
            return self._balances_cache.get('free', {}).get(asset, 0.0)

        try:
            # ccxt's fetch_balance is sync, run in thread
            import asyncio
            balances = await asyncio.to_thread(self.client.fetch_balance)
            self._balances_cache = balances
            self._balances_ts = now
            free = balances.get('free', {})
            return free.get(asset, 0.0)
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            # Return cached if available
            if self._balances_cache:
                return self._balances_cache.get('free', {}).get(asset, 0.0)
            return 0.0

    def get_balance_sync(self, asset):
        """Synchronous balance fetch"""
        try:
            balances = self.client.fetch_balance()
            self._balances_cache = balances
            self._balances_ts = time.time()
            return balances.get('free', {}).get(asset, 0.0)
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return 0.0

    async def sync_orders(self, symbol):
        """Fetch all open orders for a symbol"""
        try:
            import asyncio
            orders = await asyncio.to_thread(self.client.fetch_open_orders, symbol)
            return [{
                'id': o['id'],
                'side': o['side'],
                'price': float(o['price']),
                'amount': float(o['amount']),
                'status': o['status'],
                'timestamp': o.get('timestamp', 0)
            } for o in orders]
        except Exception as e:
            logger.error(f"Sync orders error: {e}")
            return []

    async def get_atr(self, symbol, timeframe='1h', lookback=14):
        """Calculate Average True Range for volatility measurement"""
        try:
            import asyncio
            ohlcv = await asyncio.to_thread(
                self.client.fetch_ohlcv, symbol, timeframe=timeframe, limit=lookback + 1
            )
            if len(ohlcv) < 2:
                return 0.0

            tr_values = []
            for i in range(1, len(ohlcv)):
                high = ohlcv[i][2]
                low = ohlcv[i][3]
                prev_close = ohlcv[i-1][4]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                tr_values.append(tr)

            return sum(tr_values[-lookback:]) / min(len(tr_values), lookback)
        except Exception as e:
            logger.error(f"ATR calculation error: {e}")
            return 0.0

    def log_trade(self, symbol, side, price, amount, eur_value, fee, profit):
        """Log a completed trade"""
        logger.info(f"TRADE | {side} | {symbol} | Price: {price} | "
                     f"Amt: {amount:.4f} | EUR: {eur_value:.2f} | "
                     f"Fee: {fee:.4f} | P&L: {profit:+.4f}€")

    def save_state(self, state):
        """Save bot state to SQLite database (WAL mode for concurrency)"""
        try:
            import sqlite3
            self._ensure_dirs()
            conn = sqlite3.connect(str(self._state_db))
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bot_state (
                    bot_name TEXT PRIMARY KEY,
                    state_json TEXT NOT NULL,
                    updated_at REAL NOT NULL
                )
            """)
            conn.execute(
                "INSERT OR REPLACE INTO bot_state (bot_name, state_json, updated_at) VALUES (?, ?, ?)",
                (self.bot_name, json.dumps(state), time.time())
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"State save error: {e}")

    def load_state(self):
        """Load bot state from SQLite database"""
        try:
            import sqlite3
            if not self._state_db.exists():
                return None
            conn = sqlite3.connect(str(self._state_db))
            conn.execute("PRAGMA journal_mode=WAL")
            cursor = conn.execute(
                "SELECT state_json FROM bot_state WHERE bot_name = ? ORDER BY updated_at DESC LIMIT 1",
                (self.bot_name,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                return json.loads(row[0])
        except Exception as e:
            logger.error(f"State load error: {e}")
        return None
#!/usr/bin/env python3
"""
DENARO CORE ENGINE v1.0
Standardized base for all Denaro trading bots.
Provides: Unified Binance Client, State Recovery, ATR Volatility, and DB Logging.
"""

import os
import json
import logging
import asyncio
import ccxt
from dotenv import load_dotenv
from pathlib import Path
from trade_db import TradeDB

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - CORE - %(levelname)s - %(message)s'
)
logger = logging.getLogger("DenaroCore")

class DenaroCore:
    def __init__(self, bot_name, config_filename="grid_config.json"):
        self.bot_name = bot_name
        self.base_dir = Path(__file__).parent
        self.config_path = self.base_dir / config_filename
        self.env_path = self.base_dir / ".env"
        
        # Load environment
        load_dotenv(self.env_path)
        
        # Default Configuration (Sistemi di sicurezza)
        self.config = {
            "symbol": "SOL/EUR",
            "symbol_ws": "soleur",
            "grid_levels": 6,
            "grid_range_pct": 0.01,
            "profit_per_grid": 0.003,
            "base_order_eur": 10.0,
            "max_total_invested": 300.0,
            "min_order_eur": 5.0,
            "trailing_stop_pct": 1.5,
            "trailing_activation_pct": 2.0,
            "config_reload_sec": 600,
        }
        
        # Initialize Client
        self.client = self._init_client()
        self.db = TradeDB()
        
        # Override defaults with JSON config
        self.load_config()

    def _init_client(self):
        api_key = os.getenv("BINANCE_API_KEY")
        api_secret = os.getenv("BINANCE_API_SECRET")
        if not api_key or not api_secret:
            raise EnvironmentError("BINANCE_API_KEY/SECRET missing in .env")
            
        return ccxt.binance({
            'apiKey': api_key,
            'secret': api_secret,
            'enableRateLimit': True,
            'options': {'defaultType': 'spot', 'defaultFeeCurrency': 'BNB'},
        })

    def load_config(self):
        """Loads and updates configuration from JSON file with flexible key mapping"""
        if not self.config_path.exists():
            logger.error(f"Config file {self.config_path} not found!")
            return False
        try:
            with open(self.config_path, "r") as f:
                file_cfg = json.load(f)
            
            # Flexible mapping for common keys
            mapping = {
                "SYMBOLS": lambda v: v[0] if isinstance(v, list) else v,
                "symbols": lambda v: v[0] if isinstance(v, list) else v,
                "symbol_ws": lambda v: v.lower().replace("/", "") if isinstance(v, str) else v,
                "GRID_LEVELS": lambda v: int(v),
                "GRID_SPACING": lambda v: float(v),
                "ORDER_SIZE_EUR": lambda v: float(v),
                "base_order_eur": lambda v: float(v),
            }
            
            # Map synonyms
            synonyms = {
                "SYMBOLS": "symbol",
                "symbols": "symbol",
                "GRID_LEVELS": "grid_levels",
                "GRID_SPACING": "grid_range_pct",
                "ORDER_SIZE_EUR": "base_order_eur",
            }
            
            for k, v in file_cfg.items():
                mapped_k = k.lower() if k.lower() in self.config else k
                if mapped_k in self.config:
                    val = mapping[k](v) if k in mapping else v
                    self.config[mapped_k] = val
                elif k in synonyms:
                    self.config[synonyms[k]] = mapping[k](v) if k in mapping else v
            
            # Normalize symbol format (add slash if missing)
            if 'symbol' in self.config:
                sym = self.config['symbol']
                if '/' not in sym and len(sym) == 6:
                    # Assume format like "BTCEUR" -> "BTC/EUR"
                    self.config['symbol'] = f"{sym[:3]}/{sym[3:]}"
            
            # Auto‑generate symbol_ws if not provided, or update if symbol changed
            if 'symbol' in self.config:
                self.config['symbol_ws'] = self.config['symbol'].lower().replace('/', '')
            
            logger.info(f"[{self.bot_name}] Config loaded successfully: symbol={self.config.get('symbol')}, symbol_ws={self.config.get('symbol_ws')}")
            return True
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            return False

    async def get_atr(self, symbol, timeframe='1h', lookback=14):
        """Calculates Average True Range for volatility-adaptive trading"""
        try:
            ohlcv = self.client.fetch_ohlcv(symbol, timeframe=timeframe, limit=lookback+1)
            if len(ohlcv) < lookback: return None
            
            trs = []
            for i in range(1, len(ohlcv)):
                high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
                tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
                trs.append(tr)
            return sum(trs) / len(trs)
        except Exception as e:
            logger.error(f"ATR error for {symbol}: {e}")
            return None

    async def sync_orders(self, symbol):
        """Recovers active orders from exchange to prevent 'zombies'"""
        try:
            orders = self.client.fetch_open_orders(symbol)
            logger.info(f"[{self.bot_name}] Found {len(orders)} open orders on exchange")
            return orders
        except Exception as e:
            logger.error(f"Sync error: {e}")
            return []

    def log_trade(self, symbol, side, price, amount, cost, fee, profit, strategy="grid"):
        """Standardized trade logging to SQLite"""
        try:
            self.db.log_trade(
                symbol=symbol,
                side=side,
                price=price,
                amount=amount,
                cost=cost,
                fee=fee,
                fee_currency='EUR',
                profit=profit,
                strategy=strategy,
                bot_instance=self.bot_name
            )
            logger.info(f"[{self.bot_name}] Trade recorded in DB: {profit:.2f}€")
        except Exception as e:
            logger.error(f"DB Logging error: {e}")

    def get_balance(self, asset='EUR'):
        """Gets free balance for specific asset"""
        try:
            bal = self.client.fetch_balance()
            return bal['free'].get(asset, 0)
        except Exception as e:
            logger.error(f"Balance fetch error: {e}")
            return 0.0

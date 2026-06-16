from dataclasses import dataclass, field
import os
from pathlib import Path
from typing import Optional, List, Dict, Any
from loguru import logger
import ccxt
from ccxt.base.errors import NetworkError, ExchangeError
from dotenv import load_dotenv

BASE = Path(__file__).resolve().parents[1]
load_dotenv(BASE / ".env")

# Helper functions for environment variables
def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def _float(key: str, default: float) -> float:
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        return default

def _int(key: str, default: int) -> int:
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        return default

def _bool(key: str, default: bool = True) -> bool:
    return os.getenv(key, str(default)).lower() in ('true', '1', 't', 'y', 'yes')

@dataclass
class Settings:
    # ── Exchange Settings ────────────────────────────────────────────────────
    exchange_id: str = field(default_factory=lambda: _env("EXCHANGE_ID", "binance"))
    api_key: str = field(default_factory=lambda: _env("API_KEY", ""))
    api_secret: str = field(default_factory=lambda: _env("API_SECRET", ""))
    subaccount_name: Optional[str] = field(default_factory=lambda: _env("SUBACCOUNT_NAME", None))
    
    # ── Trading Settings ────────────────────────────────────────────────────
    symbol: str = field(default_factory=lambda: _env("SYMBOL", "SOL/USDT"))
    total_capital_eur: float = field(default_factory=lambda: _float("TOTAL_CAPITAL_EUR", 100.0))
    capital_split_scalper: float = field(default_factory=lambda: _float("CAPITAL_SPLIT_SCALPER", 0.3))
    
    @property
    def grid_capital(self) -> float:
        return self.total_capital_eur * (1.0 - self.capital_split_scalper)
    
    @property
    def scalper_capital(self) -> float:
        return self.total_capital_eur * self.capital_split_scalper
    
    # ── Telegram Notifications ────────────────────────────────────────────
    telegram_bot_token: str = field(default_factory=lambda: _env("TELEGRAM_BOT_TOKEN", ""))
    telegram_chat_id: str = field(default_factory=lambda: _env("TELEGRAM_CHAT_ID", ""))
    
    @property
    def telegram_token(self) -> str:
        return self.telegram_bot_token
    
    # ── Scalper Settings ──────────────────────────────────────────────────
    scalper_symbol: str = field(default_factory=lambda: _env("SCALPER_SYMBOL", "BTC/USDT"))
    scalper_grid_levels: int = field(default_factory=lambda: _int("SCALPER_GRID_LEVELS", 5))
    scalper_grid_spacing_pct: float = field(default_factory=lambda: _float("SCALPER_GRID_SPACING_PCT", 0.005))
    scalper_take_pct: float = field(default_factory=lambda: _float("SCALPER_TAKE_PCT", 0.5))
    
    # ── Main Grid Settings ─────────────────────────────────────────────────
    grid_symbol: str = field(default_factory=lambda: _env("GRID_SYMBOL", "SOL/USDC"))
    grid_levels: int = field(default_factory=lambda: _int("GRID_LEVELS", 8))
    grid_spacing_pct: float = field(default_factory=lambda: _float("GRID_SPACING_PCT", 0.04))
    grid_take_pct: float = field(default_factory=lambda: _float("GRID_TAKE_PCT", 1.0))
    grid_trailing_stop: bool = field(default_factory=lambda: _bool("GRID_TRAILING_STOP", True))
    
    # ── RSI Settings ────────────────────────────────────────────────────────
    rsi_symbol: str = field(default_factory=lambda: _env("RSI_SYMBOL", "SOL/USDC"))
    rsi_capital: float = field(default_factory=lambda: _float("RSI_CAPITAL", 5.0))
    
    # ── BTC/USDT Grid Settings ───────────────────────────────────────────
    btc_grid_symbol: str = field(default_factory=lambda: _env("BTC_GRID_SYMBOL", "BTC/USDT"))
    btc_grid_capital_usdt: float = field(default_factory=lambda: _float("BTC_GRID_CAPITAL_USDT", 5.0))
    btc_grid_levels: int = field(default_factory=lambda: _int("BTC_GRID_LEVELS", 3))
    btc_grid_spacing_pct: float = field(default_factory=lambda: _float("BTC_GRID_SPACING_PCT", 0.01))
    btc_grid_take_pct: float = field(default_factory=lambda: _float("BTC_GRID_TAKE_PCT", 0.8))
    btc_grid_trailing_stop: bool = field(default_factory=lambda: _bool("BTC_GRID_TRAILING_STOP", True))
    
    # ── ETH/USDT Grid Settings ───────────────────────────────────────────
    eth_grid_symbol: str = field(default_factory=lambda: _env("ETH_GRID_SYMBOL", "ETH/USDT"))
    eth_grid_capital_usdt: float = field(default_factory=lambda: _float("ETH_GRID_CAPITAL_USDT", 3.0))
    eth_grid_levels: int = field(default_factory=lambda: _int("ETH_GRID_LEVELS", 3))
    eth_grid_spacing_pct: float = field(default_factory=lambda: _float("ETH_GRID_SPACING_PCT", 0.015))
    eth_grid_take_pct: float = field(default_factory=lambda: _float("ETH_GRID_TAKE_PCT", 0.9))
    eth_grid_trailing_stop: bool = field(default_factory=lambda: _bool("ETH_GRID_TRAILING_STOP", True))
    
    # ── RSI Settings for BTC/ETH ─────────────────────────────────────────
    btc_rsi_symbol: str = field(default_factory=lambda: _env("BTC_RSI_SYMBOL", "BTC/USDT"))
    btc_rsi_capital_usdt: float = field(default_factory=lambda: _float("BTC_RSI_CAPITAL_USDT", 2.0))
    eth_rsi_symbol: str = field(default_factory=lambda: _env("ETH_RSI_SYMBOL", "ETH/USDT"))
    eth_rsi_capital_usdt: float = field(default_factory=lambda: _float("ETH_RSI_CAPITAL_USDT", 1.5))
    
    # ── Feature Flags ────────────────────────────────────────────────────
    enable_grid: bool = field(default_factory=lambda: _bool("ENABLE_GRID", True))
    enable_scalper: bool = field(default_factory=lambda: _bool("ENABLE_SCALPER", False))
    enable_rsi_reversion: bool = field(default_factory=lambda: _bool("ENABLE_RSI_REVERSION", False))
    enable_btc_grid: bool = field(default_factory=lambda: _bool("ENABLE_BTC_GRID", False))
    enable_eth_grid: bool = field(default_factory=lambda: _bool("ENABLE_ETH_GRID", False))
    enable_btc_rsi: bool = field(default_factory=lambda: _bool("ENABLE_BTC_RSI", False))
    enable_eth_rsi: bool = field(default_factory=lambda: _bool("ENABLE_ETH_RSI", False))
    enable_dynamic_grid: bool = field(default_factory=lambda: _bool("ENABLE_DYNAMIC_GRID", False))
    
    # ── Dynamic Grid Strategy Settings ───────────────────────────────────
    dynamic_grid_symbol: str = field(default_factory=lambda: _env("DYNAMIC_GRID_SYMBOL", "BTC/USDT"))
    dynamic_grid_capital_usdt: float = field(default_factory=lambda: _float("DYNAMIC_GRID_CAPITAL_USDT", 10.0))
    dynamic_grid_levels: int = field(default_factory=lambda: _int("DYNAMIC_GRID_LEVELS", 4))
    dynamic_grid_min_spacing_pct: float = field(default_factory=lambda: _float("DYNAMIC_GRID_MIN_SPACING_PCT", 0.0002))
    dynamic_grid_max_spacing_pct: float = field(default_factory=lambda: _float("DYNAMIC_GRID_MAX_SPACING_PCT", 0.005))
    dynamic_grid_take_pct: float = field(default_factory=lambda: _float("DYNAMIC_GRID_TAKE_PCT", 0.4))
    dynamic_grid_trailing_stop: bool = field(default_factory=lambda: _bool("DYNAMIC_GRID_TRAILING_STOP", True))
    dynamic_grid_price_precision: int = field(default_factory=lambda: _int("DYNAMIC_GRID_PRICE_PRECISION", 6))
    dynamic_grid_amount_precision: int = field(default_factory=lambda: _int("DYNAMIC_GRID_AMOUNT_PRECISION", 6))
    
    # ── Dashboard Settings ─────────────────────────────────────────────────
    dashboard_port: int = field(default_factory=lambda: _int("DASHBOARD_PORT", 8899))
    dashboard_host: str = field(default_factory=lambda: _env("DASHBOARD_HOST", "0.0.0.0"))
    
    # ── Database Settings ──────────────────────────────────────────────────
    db_path: str = field(default_factory=lambda: _env("DB_PATH", "denaro"))
    
    # ── Exchanges ──────────────────────────────────────────────────────────
    exchanges: str = field(default_factory=lambda: _env("EXCHANGES", "binance"))

settings = Settings()

class TradeDB:
    def __init__(self, db_name: str = "denaro"):
        self.path = BASE / ".tmp" / f"{db_name}.db"
        self.path.parent.mkdir(exist_ok=True)
        self._conn = None
        self._init()
    
    def _connect(self):
        if self._conn is None:
            import sqlite3
            self._conn = sqlite3.connect(str(self.path), timeout=10, check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA busy_timeout=5000")
        return self._conn
    
    async def connect(self):
        return self._connect()
    
    def _init(self):
        c = self._connect()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS trades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT,
                side TEXT,
                price REAL,
                amount REAL,
                timestamp INTEGER,
                status TEXT,
                profit REAL DEFAULT 0.0
            );
            CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);
            CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
        """)
        c.commit()
    
    def add_trade(self, symbol: str, side: str, price: float, amount: float, timestamp: int, status: str = "OPEN", profit: float = 0.0):
        c = self._connect()
        c.execute(
            "INSERT INTO trades (symbol, side, price, amount, timestamp, status, profit) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (symbol, side, price, amount, timestamp, status, profit),
        )
        c.commit()
        return c.lastrowid
    
    def update_trade(self, trade_id: int, status: str, profit: float):
        c = self._connect()
        c.execute("UPDATE trades SET status = ?, profit = ? WHERE id = ?", (status, profit, trade_id))
        c.commit()
    
    def get_trades(self, symbol: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        c = self._connect()
        query = "SELECT * FROM trades"
        params = []
        if symbol:
            query += " WHERE symbol = ?"
            params.append(symbol)
        if status:
            if symbol:
                query += " AND status = ?"
            else:
                query += " WHERE status = ?"
            params.append(status)
        cursor = c.execute(query, params)
        return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]

class RiskManager:
    def __init__(self, db: TradeDB, settings_ref: Settings = settings):
        self.db = db
        self.settings = settings_ref
        self._is_halted = False
        self._daily_baseline_equity = 0.0
        self._daily_baseline_set_ts = 0.0
        self._realized_pnl_today = 0.0
    
    def set_daily_baseline(self, equity: float):
        import time
        self._daily_baseline_equity = equity
        self._daily_baseline_set_ts = time.time()
        logger.info(f"RiskManager: Baseline set to {equity:.2f} USD. PnL Today: {self._realized_pnl_today:+.4f} USD")
    
    def update_pnl(self, pnl: float):
        self._realized_pnl_today += pnl
        logger.info(f"RiskManager: PnL Today: {self._realized_pnl_today:+.4f} USD")
    
    def check_risk_limits(self, current_equity: float) -> bool:
        if self._is_halted:
            return False
        if self._daily_baseline_equity <= 0:
            return True
        drawdown = (current_equity - self._daily_baseline_equity) / self._daily_baseline_equity * 100
        if drawdown < -5.0:
            logger.warning(f"RiskManager: Max drawdown exceeded ({drawdown:.2f}%). Halting trading.")
            self._is_halted = True
            return False
        return True

class ExchangeWrapper:
    def __init__(self, settings_ref: Settings = settings):
        self.settings = settings_ref
        self._exchange = None
        self._connect()
    
    def _connect(self):
        try:
            self._exchange = getattr(ccxt, self.settings.exchange_id)({
                "apiKey": self.settings.api_key,
                "secret": self.settings.api_secret,
            })
            if self.settings.subaccount_name:
                self._exchange.headers = {"BinanceSubAccount": self.settings.subaccount_name}
            logger.info(f"ExchangeWrapper: Connected to {self.settings.exchange_id}")
        except Exception as e:
            logger.error(f"ExchangeWrapper: Connection failed: {e}")
            raise
    
    async def connect(self):
        return self._exchange
    
    def fetch_balance(self) -> Dict[str, float]:
        try:
            balance = self._exchange.fetch_balance()
            return {k: v for k, v in balance["total"].items() if isinstance(v, (int, float))}
        except Exception as e:
            logger.error(f"ExchangeWrapper: Fetch balance failed: {e}")
            return {}
    
    def fetch_ohlcv(self, symbol: str, timeframe: str = "1h", limit: int = 100) -> List[List[float]]:
        try:
            return self._exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        except Exception as e:
            logger.error(f"ExchangeWrapper: Fetch OHLCV failed: {e}")
            return []

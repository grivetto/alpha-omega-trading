"""
types.py — Shared typed dataclasses per denaro-neo.
Strutture dati compatte, niente fronzoli.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL = "partial"

class StrategyMode(str, Enum):
    GRID = "grid"
    DCA = "dca"
    SCALP = "scalp"
    COOLDOWN = "cooldown"

class CBState(str, Enum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"

class SafeModeLevel(int, Enum):
    NORMAL = 0
    CAUTION = 1      # RAM > 70%: riduci frequenza calcoli
    SAFE = 2          # RAM > 85%: stop nuovi trade
    EMERGENCY = 3     # RAM > 95%: svuota tutto, close posizioni


@dataclass(slots=True)  # __slots__ attivi -> -40% memoria per istanza
class Ohlcv:
    """Unrecord OHLCV — float32 fields. 40 bytes total vs 72+ con dict."""
    timestamp: int = 0
    open: float = 0.0     # float32-size ok
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0

@dataclass(slots=True)
class Tick:
    price: float = 0.0
    volume: float = 0.0
    timestamp: int = 0
    side: Side = Side.BUY

@dataclass(slots=True)
class OrderBookLevel:
    price: float = 0.0
    size: float = 0.0

@dataclass(slots=True)
class OrderBookSnapshot:
    bids: list[OrderBookLevel] = field(default_factory=list)
    asks: list[OrderBookLevel] = field(default_factory=list)
    timestamp: int = 0

@dataclass(slots=True)
class Order:
    id: str = ""
    symbol: str = ""
    side: Side = Side.BUY
    price: float = 0.0
    amount: float = 0.0
    filled: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: int = 0

@dataclass(slots=True)
class TradeRecord:
    symbol: str = ""
    side: Side = Side.BUY
    entry_price: float = 0.0
    exit_price: float = 0.0
    amount: float = 0.0
    pnl_pct: float = 0.0
    pnl_abs: float = 0.0
    timestamp: int = 0

@dataclass(slots=True)
class ResourceState:
    """Snapshot delle risorse — aggiornato dal resource monitor ogni ~5s."""
    rss_mb: float = 0.0
    total_mb: float = 0.0
    pct: float = 0.0
    cpu_pct: float = 0.0
    fd_count: int = 0
    safe_level: SafeModeLevel = SafeModeLevel.NORMAL
    gc_collections: int = 0

@dataclass(slots=True)
class Config:
    """Config piatta — letta da env/TOML una volta, mai mutata."""
    symbol: str = "DOGE/EUR"
    capital: float = 100.0
    grid_levels: int = 5
    grid_spread: float = 0.025
    dca_max_entries: int = 5
    dca_entry_spacing: float = 0.03
    cooldown_sec: int = 30
    max_open_orders: int = 10
    ohlcv_window: int = 100   # buffer circolare OHLCV
    tick_window: int = 1000    # buffer circolare tick
    db_path: str = "denaro_neo.db"
    log_level: str = "WARNING"
    health_port: int = 8911

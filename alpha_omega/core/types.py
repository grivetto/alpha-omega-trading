"""
Unified typed dataclasses for Alpha-Omega Trading System.

Merges: shadowgrid_v2 state schema + neo/types.py compact dataclasses.
All dataclasses use __slots__ for memory efficiency.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, Dict, List
import time


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class OrderStatus(str, Enum):
    PENDING = "pending"
    OPEN = "open"
    FILLED = "filled"
    CANCELLED = "cancelled"
    PARTIAL = "partial"
    REJECTED = "rejected"


class StrategyMode(str, Enum):
    GRID = "grid"
    DCA = "dca"
    SCALP = "scalp"
    MEAN_REVERSION = "mean_reversion"
    MOMENTUM = "momentum"
    ARBITRAGE = "arbitrage"
    COOLDOWN = "cooldown"
    HYBRID = "hybrid"  # Grid + directional scalper in trend


class CBState(str, Enum):
    CLOSED = "closed"
    HALF_OPEN = "half_open"
    OPEN = "open"


class SafeModeLevel(int, Enum):
    NORMAL = 0
    CAUTION = 1      # RAM > 70%: reduce computation frequency
    SAFE = 2         # RAM > 85%: stop new trades
    EMERGENCY = 3    # RAM > 95%: liquidate all, shutdown


class PairLifecycleState(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"    # Stop new orders, let existing fill
    STOPPED = "stopped"
    ERROR = "error"


class MarketRegime(str, Enum):
    UNKNOWN = "unknown"         # Initial/undetermined state
    RANGE = "range"           # ADX < 25, suitable for grid
    TREND = "trend"           # ADX > 30, suitable for momentum/DCA
    TRANSITIONAL = "transitional"  # 25 <= ADX <= 30
    EXTREME_VOL = "extreme_vol"    # ATR > 3x median
    LOW_VOL = "low_vol"           # ATR < 0.5x median


class ExchangeId(str, Enum):
    KRAKEN = "kraken"
    OKX = "okx"
    BINANCE = "binance"
    BYBIT = "bybit"


@dataclass(slots=True)
class Ohlcv:
    """Single OHLCV record - float32 fields for memory efficiency."""
    timestamp: int = 0
    open: float = 0.0
    high: float = 0.0
    low: float = 0.0
    close: float = 0.0
    volume: float = 0.0


@dataclass(slots=True)
class Tick:
    """Single trade tick."""
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
    bids: List[OrderBookLevel] = field(default_factory=list)
    asks: List[OrderBookLevel] = field(default_factory=list)
    timestamp: int = 0


@dataclass(slots=True)
class Order:
    """Order representation - compatible with both shadowgrid_v2 and neo."""
    id: str = ""
    symbol: str = ""
    exchange: str = ""
    side: Side = Side.BUY
    price: float = 0.0
    amount: float = 0.0
    filled: float = 0.0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: int = 0
    strategy: str = ""
    client_order_id: str = ""
    fee: float = 0.0
    fee_currency: str = ""
    
    @property
    def remaining(self) -> float:
        return self.amount - self.filled
    
    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.OPEN, OrderStatus.PARTIAL)


@dataclass(slots=True)
class TradeRecord:
    """Completed trade record for PnL tracking."""
    trade_id: str = ""
    symbol: str = ""
    exchange: str = ""
    side: Side = Side.BUY
    entry_price: float = 0.0
    exit_price: float = 0.0
    amount: float = 0.0
    pnl_pct: float = 0.0
    pnl_abs: float = 0.0
    fee: float = 0.0
    fee_currency: str = ""
    entry_timestamp: int = 0
    exit_timestamp: int = 0
    strategy: str = ""
    hold_time_seconds: float = 0.0


@dataclass(slots=True)
class Position:
    """Current open position."""
    symbol: str = ""
    exchange: str = ""
    base: str = ""
    quote: str = ""
    size: float = 0.0              # Positive = long, negative = short
    entry_price: float = 0.0
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    entry_timestamp: int = 0
    last_update: int = 0
    strategy: str = ""
    
    @property
    def notional_value(self) -> float:
        return abs(self.size * self.current_price)
    
    @property
    def pnl_pct(self) -> float:
        if self.entry_price == 0:
            return 0.0
        return (self.current_price - self.entry_price) / self.entry_price * (1 if self.size > 0 else -1)


@dataclass(slots=True)
class RiskMetrics:
    """Portfolio-level risk metrics."""
    total_capital: float = 0.0
    current_equity: float = 0.0
    peak_equity: float = 0.0
    portfolio_dd: float = 0.0           # Fraction
    daily_loss: float = 0.0             # Fraction of day-start equity
    daily_pnl: float = 0.0
    exposure_per_base: Dict[str, float] = field(default_factory=dict)  # base -> fraction
    num_positions: int = 0
    max_correlation: float = 0.0
    kill_switch_triggered: bool = False
    kill_reason: str = ""
    volatility_regimes: Dict[str, Dict] = field(default_factory=dict)
    timestamp: int = field(default_factory=lambda: int(time.time()))


@dataclass(slots=True)
class BotHealth:
    """Bot health status."""
    symbol: str = ""
    exchange: str = ""
    port: int = 0
    state: PairLifecycleState = PairLifecycleState.STOPPED
    status: str = "stopped"           # running|stopped|error
    pid: Optional[int] = None
    restart_count: int = 0
    uptime: float = 0.0
    last_fill_time: float = 0.0
    health_reason: str = "healthy"
    mode: str = "paper"               # paper|live
    capital: float = 0.0
    equity: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    drawdown_pct: float = 0.0
    open_orders: int = 0
    timestamp: int = field(default_factory=lambda: int(time.time()))


@dataclass(slots=True)
class FleetStatus:
    """Complete fleet status."""
    status: str = "healthy"           # healthy|degraded|critical
    timestamp: int = field(default_factory=lambda: int(time.time()))
    total_bots: int = 0
    running_bots: int = 0
    total_capital: float = 0.0
    total_equity: float = 0.0
    total_realized_pnl: float = 0.0
    total_unrealized_pnl: float = 0.0
    portfolio_dd: float = 0.0
    bots: Dict[str, BotHealth] = field(default_factory=dict)
    risk: Optional[RiskMetrics] = None


@dataclass(slots=True)
class PairConfig:
    """Configuration for a single trading pair."""
    symbol: str = ""
    exchange: str = "kraken"
    port: int = 0
    capital: float = 50.0
    regime: MarketRegime = MarketRegime.RANGE
    suitability: str = "grid"         # grid|scalper|dca|avoid
    atr_pct: float = 0.0
    adx: float = 0.0
    rsi: float = 50.0
    grid_levels: int = 5
    spread_pct: float = 0.5
    per_level: float = 0.2
    
    # Risk params (can override fleet defaults)
    max_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.05
    use_momentum_filter: bool = True
    hybrid_mode: bool = False
    
    # State persistence
    state_file: str = ""
    log_file: str = ""


@dataclass(slots=True)
class FleetConfig:
    """Complete fleet configuration - versioned and generated by scanner."""
    version: str = ""
    total_fleet_capital: float = 0.0
    capital_per_exchange: Dict[str, float] = field(default_factory=dict)
    pairs: List[PairConfig] = field(default_factory=list)        # Kraken EUR pairs
    okx_pairs: List[PairConfig] = field(default_factory=list)    # OKX USDT pairs
    risk_params: Dict[str, float] = field(default_factory=dict)
    generated_at: str = ""
    scan_version: str = "2.2"
    
    def all_pairs(self) -> List[PairConfig]:
        return self.pairs + self.okx_pairs


class RiskLevel(int, Enum):
    NORMAL = 0
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class BotStatus(str, Enum):
    STARTING = "starting"
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"
    DRAINING = "draining"


# Signal type for strategy decisions
class Signal(str, Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"
    CLOSE_LONG = "close_long"
    CLOSE_SHORT = "close_short"


# Aliases for compatibility
OHLCV = Ohlcv
StrategyType = StrategyMode


class Ticker:
    """Simple ticker data class."""
    def __init__(self, symbol: str, price: float, timestamp: int = 0, volume: float = 0.0, bid: float = 0.0, ask: float = 0.0):
        self.symbol = symbol
        self.price = price
        self.timestamp = timestamp
        self.volume = volume
        self.bid = bid
        self.ask = ask


class Trade:
    """Simple trade data class."""
    def __init__(self, trade_id: str, symbol: str, side: str, price: float, amount: float, timestamp: int = 0, fee: float = 0.0, fee_currency: str = ""):
        self.trade_id = trade_id
        self.symbol = symbol
        self.side = side
        self.price = price
        self.amount = amount
        self.timestamp = timestamp
        self.fee = fee
        self.fee_currency = fee_currency


class Config:
    """Flat config - read from env once, never mutated."""
    # Exchange
    exchange: str = "kraken"
    symbol: str = "DOGE/EUR"
    capital: float = 100.0
    live_mode: bool = False
    
    # Grid parameters
    grid_levels: int = 5
    grid_spread: float = 0.025
    
    # DCA parameters
    dca_max_entries: int = 5
    dca_entry_spacing: float = 0.03
    
    # General
    cooldown_sec: int = 30
    max_open_orders: int = 10
    
    # Buffers
    ohlcv_window: int = 100
    tick_window: int = 1000
    
    # Storage
    db_path: str = "denaro_neo.db"
    state_file: str = "/tmp/shadowgrid_state.json"
    log_file: str = "/tmp/shadowgrid.log"
    
    # Network
    health_port: int = 8911
    zmq_pub_port: int = 5555
    zmq_sub_port: int = 5555
    
    # Risk (can be overridden by fleet config)
    use_momentum_filter: bool = True
    max_drawdown_pct: float = 0.15
    max_daily_loss_pct: float = 0.05
    atr_spread_multiplier: float = 0.7
    min_spread_pct: float = 0.2
    max_spread_pct: float = 2.5
    drift_pct: float = 6.0
    hybrid_mode: bool = False
    
    # Portfolio risk
    risk_manager_enabled: bool = True
    max_portfolio_dd: float = 0.20
    max_exposure_per_base: float = 0.30
    max_correlation: float = 0.7
    max_positions_per_base: int = 2
    volatility_targeting: bool = True
    
    # Alerts
    alert_enabled: bool = True
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""
    
    # Logging
    log_level: str = "INFO"

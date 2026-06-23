"""Denaro v3 Configuration.

Centralized, single source of truth. No JSON fragmentation.
All values are typed and documented.
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class GridConfig:
    symbol: str = "SOL/USDC"
    base_asset: str = "SOL"
    quote_asset: str = "USDC"
    levels: int = 4
    spacing_pct: float = 1.2  # 1.2% between levels
    take_profit_pct: float = 1.0  # TP at next level +1%
    min_order_usdc: float = 10.0  # Minimum order size
    max_order_usdc: float = 100.0  # Maximum order size
    atr_period: int = 14
    atr_spacing_factor: float = 1.5  # ATR multiplier for dynamic spacing


@dataclass
class RiskConfig:
    max_daily_loss_pct: float = 3.0  # Stop ALL trading for the day
    max_drawdown_pct: float = 5.0  # Total drawdown halt
    max_consecutive_losses: int = 3  # Reduce size after N losses
    reduced_size_pct: float = 50.0  # Size reduction when half-open
    kelly_fraction: float = 0.25  # Conservative Kelly
    var_confidence: float = 0.95  # VaR confidence level
    break_even_r: float = 1.0  # Move SL to entry when profit > risk
    atr_trail_multiplier: float = 1.5  # Trailing stop ATR multiplier
    max_risk_per_trade_pct: float = 1.0  # Max % equity at risk per trade


@dataclass
class APIConfig:
    cache_ttl_balance: int = 60  # seconds
    cache_ttl_ohlcv: int = 60
    cache_ttl_ticker: int = 30
    cache_ttl_orders: int = 15
    loop_interval: int = 60  # Main loop sleep (seconds)
    max_retries: int = 3
    request_timeout: int = 10


@dataclass
class Config:
    grid: GridConfig = field(default_factory=GridConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    api: APIConfig = field(default_factory=APIConfig)
    log_level: str = "INFO"
    health_port: Optional[int] = None  # Disabled by default


# Production defaults — override via env vars
PRODUCTION = Config()

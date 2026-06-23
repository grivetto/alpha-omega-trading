"""Centralized Pydantic settings for Denaro system."""
from pydantic import BaseModel, Field, field_validator
from typing import List, Optional
from pathlib import Path
import os

class BinanceConfig(BaseModel):
    api_key: str = Field(default="", validation_alias="BINANCE_API_KEY")
    api_secret: str = Field(default="", validation_alias="BINANCE_API_SECRET")
    symbol: str = Field(default="SOL/USDC")
    quote_asset: str = "USDC"
    base_asset: str = "SOL"
    testnet: bool = False

class RiskConfig(BaseModel):
    max_daily_loss_pct: float = Field(default=3.0, ge=0.5, le=10.0)
    circuit_breaker_pct: float = Field(default=5.0, ge=1.0, le=15.0)
    kelly_fraction: float = Field(default=0.5, ge=0.1, le=1.0)  # Half-Kelly
    max_consecutive_losses: int = Field(default=3, ge=1, le=10)
    var_confidence: float = Field(default=0.95, ge=0.90, le=0.99)
    var_max_drawdown_pct: float = Field(default=4.0)  # VaR 95% > 4% → reduce size
    min_bnb: float = Field(default=0.002)
    size_reduction_on_var: float = Field(default=0.5)  # 50% size when VaR triggers
    martingale_enabled: bool = False
    compound_enabled: bool = False

class GridConfig(BaseModel):
    base_eur: float = Field(default=8.0, ge=5.0)
    min_order_eur: float = Field(default=5.1)
    spacing_multiplier: float = Field(default=1.0)
    levels: int = Field(default=4, ge=1, le=10)

class ObservabilityConfig(BaseModel):
    health_port: int = Field(default=8909)
    metrics_enabled: bool = True
    telegram_alerts: bool = False
    structlog_enabled: bool = True

class Settings(BaseModel):
    """Master configuration for Denaro system."""
    exchange: BinanceConfig = BinanceConfig()
    risk: RiskConfig = RiskConfig()
    grid: GridConfig = GridConfig()
    observability: ObservabilityConfig = ObservabilityConfig()
    run_dry: bool = Field(default=False, validation_alias="DRY_RUN")
    log_level: str = Field(default="INFO")

    @field_validator("exchange", mode="before")
    @classmethod
    def load_exchange(cls, v):
        if isinstance(v, dict):
            return v
        cfg = {}
        for k in ["BINANCE_API_KEY", "BINANCE_API_SECRET"]:
            if os.getenv(k):
                cfg[k] = os.getenv(k)
        from pathlib import Path
        env_path = Path(os.getenv("DENARO_HOME", ".")) / ".env"
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        if key.strip() in ["BINANCE_API_KEY", "BINANCE_API_SECRET"]:
                            cfg[key.strip()] = val.strip()
        return cfg

    @classmethod
    def from_env(cls, env_path: Optional[Path] = None) -> "Settings":
        if env_path is None:
            env_path = Path(os.getenv("DENARO_HOME", ".")) / ".env"
        values = {}
        if env_path.exists():
            with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        values[key.strip()] = val.strip()
        for k, v in os.environ.items():
            values[k] = v
        return cls(**values)

settings = Settings()

def validate() -> bool:
    """Validate config at startup. Raise ValueError if critical issues."""
    if not settings.exchange.api_key:
        raise ValueError("BINANCE_API_KEY not set")
    if not settings.exchange.api_secret:
        raise ValueError("BINANCE_API_SECRET not set")
    if settings.risk.max_daily_loss_pct > settings.risk.circuit_breaker_pct:
        raise ValueError("max_daily_loss_pct must be < circuit_breaker_pct")
    return True

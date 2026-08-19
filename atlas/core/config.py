"""ATLAS Core Configuration - Pydantic Settings."""
from __future__ import annotations

from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class ExchangeConfig(BaseSettings):
    """Exchange connection configuration."""
    name: str
    api_key: str
    api_secret: str
    passphrase: str | None = None
    sandbox: bool = False
    testnet: bool = False
    rate_limit_rps: float = 5.0
    rate_limit_burst: int = 10


class StrategyConfig(BaseSettings):
    """Strategy configuration."""
    strategy_id: str
    class_path: str  # e.g. "atlas.strategy.grid.GridStrategy"
    params: dict = Field(default_factory=dict)
    symbols: list[str]
    exchanges: list[str]
    enabled: bool = True


class RiskConfig(BaseSettings):
    """Risk management limits."""
    max_portfolio_drawdown: float = 0.20
    max_daily_loss: float = 0.05
    max_position_size_pct: float = 0.25
    max_exposure_per_base: float = 0.30
    max_correlation_exposure: float = 0.70
    max_leverage: float = 1.0


class AtlasSettings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # Exchange configs (loaded from exchanges.yaml)
    exchanges: list[ExchangeConfig] = []

    # Strategy configs (loaded from strategies.yaml)
    strategies: list[StrategyConfig] = []

    # Risk limits
    risk: RiskConfig = RiskConfig()

    # Storage
    database_url: str = "sqlite+aiosqlite:///./atlas.db"
    redis_url: str = "redis://localhost:6379/0"

    # Health server
    health_port: int = 8080

    # Timezone
    timezone: str = "UTC"


# Global settings instance
settings = AtlasSettings()

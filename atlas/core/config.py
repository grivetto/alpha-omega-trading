"""ATLAS Core Configuration - Pydantic Settings."""
from __future__ import annotations

import os
import yaml
from pathlib import Path
from typing import Any, Literal, List

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
    hostname: str | None = None  # For OKX EEA

    model_config = SettingsConfigDict(extra="allow")


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
        extra="allow",
    )

    env: Literal["development", "staging", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True

    # OKX EEA endpoint
    OKX_EEA: bool = False

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

    @classmethod
    def load_from_yaml(cls, path: Path, settings: "AtlasSettings") -> List[ExchangeConfig]:
        with open(path) as f:
            data = yaml.safe_load(f)
        exchanges = []
        for ex_data in data.get("exchanges", []):
            # Add hostname for OKX EEA
            if ex_data.get("name") == "okx" and settings.OKX_EEA:
                ex_data["hostname"] = "eea.okx.com"
            exchanges.append(ExchangeConfig(**ex_data))
        return exchanges

    @classmethod
    def load_strategies(cls, path: Path) -> List[StrategyConfig]:
        with open(path) as f:
            data = yaml.safe_load(f)
        strategies = []
        for strat_data in data.get("strategies", []):
            strategies.append(StrategyConfig(**strat_data))
        return strategies


# Global settings instance
settings = AtlasSettings()
"""Central configuration manager for the multi-agent system."""
from __future__ import annotations
import os
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMConfig:
    """Configuration for the local LLM inference endpoint."""
    endpoint: str = os.getenv("LLM_ENDPOINT", "http://localhost:11434/v1")
    api_key: str = os.getenv("LLM_API_KEY", "ollama")
    model: str = os.getenv("LLM_MODEL", "llama3.2:3b")
    max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "512"))
    temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.3"))
    timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
    max_retries: int = int(os.getenv("LLM_MAX_RETRIES", "3"))


@dataclass
class ExchangeConfig:
    """Configuration for the exchange connection."""
    exchange_id: str = os.getenv("EXCHANGE_ID", "binance")
    api_key: str = os.getenv("BINANCE_API_KEY", "")
    api_secret: str = os.getenv("BINANCE_API_SECRET", "")
    testnet: bool = os.getenv("TESTNET", "false").lower() == "true"
    rate_limit: bool = True
    recv_window: int = 10000


@dataclass
class RiskConfig:
    """Configuration for the Risk Manager agent."""
    max_daily_loss_pct: float = float(os.getenv("MAX_DAILY_LOSS_PCT", "5.0"))
    max_drawdown_pct: float = float(os.getenv("MAX_DRAWDOWN_PCT", "10.0"))
    max_position_pct: float = float(os.getenv("MAX_POSITION_PCT", "25.0"))
    min_liquidity_usd: float = float(os.getenv("MIN_LIQUIDITY_USD", "10000"))
    llm_risk_threshold: float = float(os.getenv("LLM_RISK_THRESHOLD", "0.6"))
    evaluation_interval: int = int(os.getenv("RISK_EVAL_INTERVAL", "30"))


@dataclass
class OrchestratorConfig:
    """Configuration for the AgentOrchestrator."""
    symbols: list[str] = field(default_factory=lambda:
        os.getenv("TRADING_SYMBOLS", "SOL/USDC,ADA/USDC").split(","))
    analysis_interval: int = int(os.getenv("ANALYSIS_INTERVAL", "15"))
    execution_mode: str = os.getenv("EXECUTION_MODE", "paper")
    max_concurrent_analyses: int = int(os.getenv("MAX_CONCURRENT_ANALYSES", "3"))
    log_dir: str = os.getenv("LOG_DIR", "logs")


@dataclass
class AppConfig:
    """Root configuration aggregating all sub-configs."""
    llm: LLMConfig = field(default_factory=LLMConfig)
    exchange: ExchangeConfig = field(default_factory=ExchangeConfig)
    risk: RiskConfig = field(default_factory=RiskConfig)
    orchestrator: OrchestratorConfig = field(default_factory=OrchestratorConfig)

    @classmethod
    def from_env(cls) -> "AppConfig":
        return cls()

    def validate(self) -> list[str]:
        errors = []
        if not self.exchange.api_key or "placeholder" in self.exchange.api_key:
            errors.append("Exchange API key not configured")
        if not self.exchange.api_secret or "placeholder" in self.exchange.api_secret:
            errors.append("Exchange API secret not configured")
        return errors


settings = AppConfig.from_env()

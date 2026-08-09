"""
Configuration management for Alpha-Omega Trading System.

Reads from environment variables once at startup, never mutated.
Supports both per-bot config and fleet config.
"""
from __future__ import annotations
import os
import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from .types import Config, PairConfig, FleetConfig, ExchangeId, MarketRegime

log = logging.getLogger("alpha_omega.config")

def _get_bool(key: str, default: bool = False) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.lower() in ("1", "true", "yes", "on")

def _get_int(key: str, default: int = 0) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val)
    except ValueError:
        log.warning(f"Invalid int for {key}={val}, using default {default}")
        return default

def _get_float(key: str, default: float = 0.0) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val)
    except ValueError:
        log.warning(f"Invalid float for {key}={val}, using default {default}")
        return default

def _get_str(key: str, default: str = "") -> str:
    return os.getenv(key, default)


def load_config_from_env() -> Config:
    """Load flat config from environment variables."""
    cfg = Config()
    
    # Exchange
    cfg.exchange = _get_str("EXCHANGE", "kraken")
    cfg.symbol = _get_str("SYMBOL", "DOGE/EUR")
    cfg.capital = _get_float("CAPITAL", 100.0)
    cfg.live_mode = _get_bool("LIVE_MODE", False)
    
    # Grid parameters
    cfg.grid_levels = _get_int("LEVELS", 5)
    cfg.grid_spread = _get_float("BASE_SPREAD_PCT", 0.5) / 100.0
    
    # DCA parameters
    cfg.dca_max_entries = _get_int("DCA_MAX_ENTRIES", 5)
    cfg.dca_entry_spacing = _get_float("DCA_ENTRY_SPACING", 0.03)
    
    # General
    cfg.cooldown_sec = _get_int("COOLDOWN_SEC", 30)
    cfg.max_open_orders = _get_int("MAX_OPEN_ORDERS", 10)
    
    # Buffers
    cfg.ohlcv_window = _get_int("OHLCV_WINDOW", 100)
    cfg.tick_window = _get_int("TICK_WINDOW", 1000)
    
    # Storage
    cfg.db_path = _get_str("DB_PATH", "denaro_neo.db")
    cfg.state_file = _get_str("STATE_FILE", "/tmp/shadowgrid_state.json")
    cfg.log_file = _get_str("LOG_FILE", "/tmp/shadowgrid.log")
    
    # Network
    cfg.health_port = _get_int("HEALTH_PORT", 8911)
    cfg.zmq_pub_port = _get_int("ZMQ_PUB_PORT", 5555)
    cfg.zmq_sub_port = _get_int("ZMQ_SUB_PORT", 5555)
    
    # Risk (can be overridden by fleet config)
    cfg.use_momentum_filter = _get_bool("USE_MOMENTUM_FILTER", True)
    cfg.max_drawdown_pct = _get_float("MAX_DRAWDOWN_PCT", 0.15)
    cfg.max_daily_loss_pct = _get_float("MAX_DAILY_LOSS_PCT", 0.05)
    cfg.atr_spread_multiplier = _get_float("ATR_SPREAD_MULTIPLIER", 0.7)
    cfg.min_spread_pct = _get_float("MIN_SPREAD_PCT", 0.2) / 100.0
    cfg.max_spread_pct = _get_float("MAX_SPREAD_PCT", 2.5) / 100.0
    cfg.drift_pct = _get_float("DRIFT_PCT", 6.0) / 100.0
    cfg.hybrid_mode = _get_bool("HYBRID_MODE", False)
    
    # Portfolio risk
    cfg.risk_manager_enabled = _get_bool("RISK_MANAGER_ENABLED", True)
    cfg.max_portfolio_dd = _get_float("MAX_PORTFOLIO_DD", 0.20)
    cfg.max_exposure_per_base = _get_float("MAX_EXPOSURE_PER_BASE", 0.30)
    cfg.max_correlation = _get_float("MAX_CORRELATION", 0.7)
    cfg.max_positions_per_base = _get_int("MAX_POSITIONS_PER_BASE", 2)
    cfg.volatility_targeting = _get_bool("VOLATILITY_TARGETING", True)
    
    # Alerts
    cfg.alert_enabled = _get_bool("ALERT_ENABLED", True)
    cfg.telegram_bot_token = _get_str("TELEGRAM_BOT_TOKEN", "")
    cfg.telegram_chat_id = _get_str("TELEGRAM_CHAT_ID", "")
    
    # Logging
    cfg.log_level = _get_str("LOG_LEVEL", "INFO")
    
    log.info(f"Config loaded: {cfg.exchange} {cfg.symbol} capital={cfg.capital} live={cfg.live_mode}")
    return cfg


def load_fleet_config(path: str) -> FleetConfig:
    """Load fleet configuration from JSON file."""
    with open(path, 'r') as f:
        data = json.load(f)
    
    fleet = FleetConfig()
    fleet.version = data.get("version", "")
    fleet.total_fleet_capital = data.get("total_fleet_capital", 0.0)
    fleet.capital_per_exchange = data.get("capital_per_exchange", {})
    fleet.generated_at = data.get("generated_at", "")
    fleet.scan_version = data.get("scan_version", "2.2")
    
    # Parse pairs
    for p in data.get("pairs", []):
        pair = _parse_pair_config(p)
        fleet.pairs.append(pair)
    
    for p in data.get("okx_pairs", []):
        pair = _parse_pair_config(p)
        fleet.okx_pairs.append(pair)
    
    fleet.risk_params = data.get("risk_params", {})
    
    log.info(f"Fleet config loaded: {len(fleet.pairs)} pairs, {len(fleet.okx_pairs)} OKX pairs")
    return fleet


def _parse_pair_config(data: Dict[str, Any]) -> PairConfig:
    """Parse pair config from dict."""
    pair = PairConfig()
    pair.symbol = data.get("symbol", "")
    pair.exchange = data.get("exchange", "kraken")
    pair.port = data.get("port", 0)
    pair.capital = data.get("capital", 50.0)
    
    # Handle regime enum
    regime_str = data.get("regime", "range")
    try:
        pair.regime = MarketRegime(regime_str)
    except ValueError:
        pair.regime = MarketRegime.RANGE
    
    pair.suitability = data.get("suitability", "grid")
    pair.atr_pct = data.get("atr_pct", 0.0)
    pair.adx = data.get("adx", 0.0)
    pair.rsi = data.get("rsi", 50.0)
    pair.grid_levels = data.get("grid_levels", 5)
    pair.spread_pct = data.get("spread_pct", 0.5)
    pair.per_level = data.get("per_level", 0.2)
    
    # Risk params
    pair.max_drawdown_pct = data.get("max_drawdown_pct", 0.15)
    pair.max_daily_loss_pct = data.get("max_daily_loss_pct", 0.05)
    pair.use_momentum_filter = data.get("use_momentum_filter", True)
    pair.hybrid_mode = data.get("hybrid_mode", False)
    
    # State persistence
    pair.state_file = data.get("state_file", "")
    pair.log_file = data.get("log_file", "")
    
    return pair


def save_fleet_config(fleet: FleetConfig, path: str) -> None:
    """Save fleet configuration to JSON file with versioning."""
    # Create backup if exists
    if Path(path).exists():
        import time
        backup = f"{path}.v{int(time.time())}"
        Path(path).rename(backup)
    
    data = {
        "version": fleet.version,
        "total_fleet_capital": fleet.total_fleet_capital,
        "capital_per_exchange": fleet.capital_per_exchange,
        "pairs": [asdict(p) for p in fleet.pairs],
        "okx_pairs": [asdict(p) for p in fleet.okx_pairs],
        "risk_params": fleet.risk_params,
        "generated_at": fleet.generated_at,
        "scan_version": fleet.scan_version,
    }
    
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    
    log.info(f"Fleet config saved to {path}")


def apply_fleet_config_to_bot(config: Config, pair_config: PairConfig) -> Config:
    """Apply fleet pair config to bot config (returns new config)."""
    import copy
    new_config = copy.deepcopy(config)
    
    new_config.symbol = pair_config.symbol
    new_config.exchange = pair_config.exchange
    new_config.capital = pair_config.capital
    new_config.health_port = pair_config.port
    new_config.grid_levels = pair_config.grid_levels
    new_config.grid_spread = pair_config.spread_pct / 100.0
    
    # Apply risk params from pair config
    new_config.max_drawdown_pct = pair_config.max_drawdown_pct
    new_config.max_daily_loss_pct = pair_config.max_daily_loss_pct
    new_config.use_momentum_filter = pair_config.use_momentum_filter
    new_config.hybrid_mode = pair_config.hybrid_mode
    
    # State/log files
    if pair_config.state_file:
        new_config.state_file = pair_config.state_file
    if pair_config.log_file:
        new_config.log_file = pair_config.log_file
    
    return new_config


def get_exchange_config(exchange: str) -> Dict[str, str]:
    """Get exchange API credentials from environment."""
    prefix = exchange.upper()
    return {
        "api_key": os.getenv(f"{prefix}_API_KEY", ""),
        "api_secret": os.getenv(f"{prefix}_API_SECRET", ""),
        "passphrase": os.getenv(f"{prefix}_PASSPHRASE", ""),  # For OKX EEA
    }


def validate_exchange_config(config: Dict[str, str]) -> bool:
    """Validate that exchange has required credentials."""
    if not config.get("api_key") or not config.get("api_secret"):
        return False
    if config.get("api_key") in ("YOUR_API_KEY", "test", ""):
        return False
    return True

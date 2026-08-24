#!/usr/bin/env python3
"""Denaro — config unificata YAML + Pydantic (TODO punto 4).

Un unico parser Pydantic per tutti i config del Node, con interpolazione
delle variabili d'ambiente `${VAR}` nei secret (mai hardcoded nel file).
Sostituisce la frammentazione JSON/YAML/.env.

Esempio (config/node_live.yaml):
    bots:
      - symbol: ADA/EUR
        mode: okx
        api_key: ${OKX_API_KEY}     # interpolato dall'ambiente al load
        api_secret: ${OKX_API_SECRET}
        passphrase: ${OKX_PASSPHRASE}
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

_ENV_RE = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")


def interpolate(value: Any, env: Optional[Dict[str, str]] = None) -> Any:
    """Sostituisce ${VAR} ricorsivamente; lascia il placeholder se la var manca."""
    env = env if env is not None else os.environ
    if isinstance(value, str):
        return _ENV_RE.sub(lambda m: env.get(m.group(1), m.group(0)), value)
    if isinstance(value, dict):
        return {k: interpolate(v, env) for k, v in value.items()}
    if isinstance(value, list):
        return [interpolate(v, env) for v in value]
    return value


class HubConfig(BaseModel):
    ws_enabled: bool = False
    poll_interval: float = 10.0
    price_ttl: float = 30.0
    ws_max_retries: int = 5
    ws_retry_base_s: float = 2.0


class SupervisorConfig(BaseModel):
    ram_critical_pct: float = 0.85
    ram_throttle_pct: float = 0.70
    cpu_critical_pct: float = 0.90
    tick_max_factor: float = 5.0


class SafeModeConfig(BaseModel):
    caution_pct: float = 70.0
    safe_pct: float = 85.0
    emergency_pct: float = 95.0
    interval_s: float = 10.0


class BotConfigSchema(BaseModel):
    symbol: str
    mode: str = "paper"
    enabled: bool = True
    env_prefix: str = ""
    capital: float
    levels: int = 3
    buy_distance: float = 0.01
    profit_target: float = 0.015
    tick_interval: float = 60.0
    fee: float = 0.001
    daily_loss_limit: float = 0.05
    max_drawdown_limit: float = 0.15
    # secret: interpolati da ${VAR} al load — mai hardcoded nel file
    api_key: str = ""
    api_secret: str = ""
    passphrase: str = ""


class NodeConfig(BaseModel):
    data_dir: str = "node_data"
    exchange_rest: Dict[str, Any] = Field(default_factory=lambda: {"name": "okx", "eea": True})
    hub: HubConfig = Field(default_factory=HubConfig)
    supervisor: SupervisorConfig = Field(default_factory=SupervisorConfig)
    safemode: SafeModeConfig = Field(default_factory=SafeModeConfig)
    bots: List[BotConfigSchema] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump()


def load_node_config(path: Path, env: Optional[Dict[str, str]] = None) -> NodeConfig:
    """Carica un config YAML (o JSON) con interpolazione ${VAR}."""
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"config non valido: {path}")
    return NodeConfig(**interpolate(raw, env))

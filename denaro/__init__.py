#!/usr/bin/env python3
"""Denaro v6 — modular, adaptive, zero-touch trading package.

Public surface: the DenaroCore facade (v4-compatible), the DenaroOrchestrator
supervisor loop, and the individual engines (risk, regime, micro, DCA, grid,
rebalancer, exchange adapter, state store, config).
"""
from .config import DenaroConfig
from .core import DenaroCore
from .dca import AdaptiveDCA
from .exchange import ExchangeAdapter
from .grid import GridPolicy
from .micro import MicrostructureModel
from .orchestrator import DenaroOrchestrator
from .rebalancer import Rebalancer
from .regime import RegimeDetector
from .risk import RiskManager
from .state import DEFAULT_CB_PATH, StateStore
from .types import (CBState, CircuitBreakerState, CoreState, DCAState,
                    ExecutionState, MicroState, PerfMetrics, RegimeState,
                    StrategyMode, Trend, VaRState)

__version__ = "6.0.0"

__all__ = [
    "AdaptiveDCA", "CBState", "CircuitBreakerState", "CoreState", "DCAState",
    "DEFAULT_CB_PATH", "DenaroConfig", "DenaroCore", "DenaroOrchestrator",
    "ExecutionState", "ExchangeAdapter", "GridPolicy", "MicroState",
    "MicrostructureModel", "PerfMetrics", "Rebalancer", "RegimeDetector",
    "RegimeState", "RiskManager", "StateStore", "StrategyMode", "Trend",
    "VaRState", "__version__",
]

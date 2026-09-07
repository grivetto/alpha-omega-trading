"""Denaro domain layer — puro Python, zero I/O, zero dipendenze esterne.

Regole del layer:
- nessun import da `application` o `infrastructure`
- nessun side effect (niente file, rete, tempo reale nei moduli puri)
- ogni modulo e' testabile in isolamento
"""
from .types import (CBState, CoreState, CircuitBreakerState, DCAState,
                    ExecutionState, MicroState, PerfMetrics, RegimeState,
                    StrategyMode, Trend, VaRState, VolatilityRegime)
from .risk import RiskManager
from .grid import GridPolicy, GridDecision, GridLevel, GridParams
from .policy import Policy
from .momentum import MomentumPolicy, MomentumParams
from .meanrev import MeanReversionPolicy, MeanReversionParams
from .regime import Regime, RegimeFilter, RegimeParams
from .adaptive import AdaptiveEngine, AdaptiveParams
from .mincapture_grid import MinCaptureGridPolicy, MinCaptureConfig

__all__ = [
    "CBState", "CoreState", "CircuitBreakerState", "DCAState", "ExecutionState",
    "MicroState", "PerfMetrics", "RegimeState", "StrategyMode", "Trend",
    "VaRState", "VolatilityRegime",
    "RiskManager",
    "GridPolicy", "GridDecision", "GridLevel", "GridParams",
    "Policy",
    "MomentumPolicy", "MomentumParams",
    "MeanReversionPolicy", "MeanReversionParams",
    "Regime", "RegimeFilter", "RegimeParams",
    "AdaptiveEngine", "AdaptiveParams",
    "MinCaptureGridPolicy", "MinCaptureConfig",
]

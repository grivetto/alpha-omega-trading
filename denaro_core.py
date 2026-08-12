#!/usr/bin/env python3
"""
DENARO CORE — backward-compatibility shim.

v6 refactored the core into the modular `denaro` package. This module keeps
the v4 public surface (`DenaroCore` and friends) importable from the legacy
entry points (main_mexc.py, main_v5.py, mock_runner.py, test_denaro_core.py)
and the old state files load untouched.

v6 capabilities behind the same API:
  - Adaptive grid/DCA driven by regime + microstructure
  - Dump-defense state machine (buy orders frozen during market dumps)
  - Volatility-scaled daily loss limit + trend-aware compounding policy
  - ATR-based hard stops, drift retargeting, orphan reconciliation
"""
from __future__ import annotations

from denaro.core import DenaroCore
from denaro.state import DEFAULT_CB_PATH
from denaro.types import (CBState, CircuitBreakerState, CoreState, DCAState,
                          ExecutionState, MicroState, PerfMetrics,
                          RegimeState, StrategyMode, Trend, VaRState)

# Legacy name kept for v3-era imports
_default_state_path = DEFAULT_CB_PATH

__all__ = [
    "CBState", "CircuitBreakerState", "CoreState", "DCAState", "DEFAULT_CB_PATH",
    "DenaroCore", "ExecutionState", "MicroState", "PerfMetrics", "RegimeState",
    "StrategyMode", "Trend", "VaRState", "_default_state_path",
]

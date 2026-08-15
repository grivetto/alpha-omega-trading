#!/usr/bin/env python3
"""Denaro v6 — DenaroCore facade.

Public API is byte-compatible with v4 (used by main.py, main_mexc.py,
main_v5.py, mock_runner.py and the existing test suite), while the internals
delegate to the modular v6 engines:

  risk       → RiskManager (CB vol-scaled, Kelly, compounding policy)
  regime     → RegimeDetector (trend/vol/volume + dump-defense state machine)
  micro      → MicrostructureModel
  dca        → AdaptiveDCA (dynamic spacing/target/stop)
  grid       → GridPolicy (adaptive geometry + retargeting)
  state      → StateStore (atomic persistence + daily reset)
"""
from __future__ import annotations

import time
from collections import deque
from pathlib import Path
from typing import Deque, List, Optional, Tuple

from .dca import AdaptiveDCA
from .dynamic_grid import GridPolicy
from .micro import MicrostructureModel
from .regime_enhanced import RegimeDetector
from .risk import RiskManager
from .state import DEFAULT_CB_PATH, StateStore
from .types import CoreState, StrategyMode, Trend

_MIN_SAVE_INTERVAL = 30.0


class DenaroCore:
    """Zero-exchange risk/regime/execution core. All I/O goes through StateStore."""

    def __init__(self, initial_capital: float = 100.0,
                 daily_loss_limit: float = 0.05,
                 max_drawdown_limit: float = 0.15,
                 max_consecutive_losses: int = 4,
                 compound_threshold: float = 1.0,
                 compound_ratio: float = 0.5,
                 state_path: Optional[Path] = None,
                 kelly_cap: float = 0.50,
                 dump_threshold_mult: float = 2.5,
                 dump_volume_ratio: float = 1.8,
                 dump_recovery_cycles: int = 3) -> None:
        self.state_path = Path(state_path) if state_path else DEFAULT_CB_PATH
        self._store = StateStore(self.state_path, min_save_interval=_MIN_SAVE_INTERVAL)
        self.state: CoreState = self._store.load(initial_capital)

        self.risk = RiskManager(
            daily_loss_limit=daily_loss_limit,
            max_drawdown_limit=max_drawdown_limit,
            max_consecutive_losses=max_consecutive_losses,
            compound_threshold=compound_threshold,
            compound_ratio=compound_ratio,
            kelly_cap=kelly_cap,
        )
        self.regime_detector = RegimeDetector(
            dump_threshold_mult=dump_threshold_mult,
            dump_volume_ratio=dump_volume_ratio,
            dump_recovery_cycles=dump_recovery_cycles,
        )
        self.micro_model = MicrostructureModel()
        self.dca_engine = AdaptiveDCA()
        self.grid_policy = GridPolicy()

        self._last_ohlcv: List[List[float]] = []
        self._return_buffer: Deque[float] = deque(maxlen=200)
        self._kelly_updated_at: float = 0.0

    # === persistence =========================================================

    def _save_state(self) -> None:
        self._store.save(self.state)

    def flush_state(self) -> None:
        self._store.flush(self.state)

    # === microstructure ======================================================

    def update_microstructure(self, bid: float, ask: float,
                              bid_vol: float, ask_vol: float,
                              cum_bid: float, cum_ask: float,
                              price: float) -> None:
        self.micro_model.update(self.state.micro, bid, ask, bid_vol, ask_vol,
                                cum_bid, cum_ask, price)

    # === regime + indicators =================================================

    def calculate_atr(self, ohlcv: List[List[float]], period: int = 14) -> float:
        from . import indicators as ind
        if len(ohlcv) < period + 1:
            return 0.0          # v4 contract: insufficient data → 0.0
        atr_pct = ind.atr_percent(ohlcv, period)
        self.state.regime.atr_pct = atr_pct if atr_pct > 0 else self.state.regime.atr_pct
        self.state.regime.volatility_regime = ind.volatility_regime(self.state.regime.atr_pct)

        # v7: keep a copy of the last OHLCV for the enhanced indicators
        self._last_ohlcv = ohlcv
        return atr_pct

    def update_regime(self, ohlcv: List[List[float]]) -> None:
        if len(ohlcv) >= 20:
            self._last_ohlcv = ohlcv
        self.regime_detector.update(self.state.regime, self.state.micro, ohlcv)

    def update_var(self, current_price: float) -> None:
        from . import indicators as ind
        self._return_buffer.append(current_price)
        var95, var99, cvar95 = ind.historical_var(list(self._return_buffer))
        self.state.var.var_95_1h = var95
        self.state.var.var_99_1h = var99
        self.state.var.cvar_95_1h = cvar95
        # Recompute sampled lookback for state persistence
        buf = list(self._return_buffer)
        if len(buf) >= 20:
            step = max(1, len(buf) // 24)
            rets = [(buf[i] - buf[i - step]) / max(1e-10, buf[i - step])
                    for i in range(step, len(buf), step)]
            self.state.var.var_lookback = rets[-100:]

    # === circuit breaker / risk ==============================================

    def check_circuit_breaker(self, current_equity: float) -> bool:
        opened = self.risk.check_circuit_breaker(self.state, current_equity)
        if opened:
            self._save_state()
        return opened

    def update_kelly(self, pnl_pct: float) -> None:
        self.state.trade_results.append(pnl_pct)
        self.state.perf.update(pnl_pct)
        now = time.time()
        if len(self.state.trade_results) >= 10 and now - self._kelly_updated_at > 1800:
            self.state.kelly_fraction = self.risk.calculate_kelly(self.state)
            self._kelly_updated_at = now
        if len(self.state.trade_results) % 20 == 0:
            self.state.perf.recalc_ratios(
                self.state.trade_results, self.state.peak_capital,
                self.state.current_capital, self.state.initial_capital)
        self._save_state()

    @property
    def kelly_fraction(self) -> float:
        return self.risk.kelly_fraction(self.state)

    def position_size(self, capital: float, allocation_pct: float = 1.0) -> float:
        return self.risk.position_size(self.state, capital, allocation_pct)

    # === DCA =================================================================

    def dca_should_enter(self, current_price: float, equity: float) -> Tuple[bool, float, str]:
        return self.dca_engine.should_enter(self.state, current_price, equity,
                                            self.kelly_fraction)

    def dca_open_position(self, price: float, amount: float, cost: float) -> None:
        self.dca_engine.open_position(self.state, price, amount, cost)

    def dca_should_exit(self, current_price: float) -> Tuple[bool, float, str]:
        return self.dca_engine.should_exit(self.state, current_price)

    def dca_close_position(self, exit_price: float = 0.0) -> float:
        return self.dca_engine.close_position(self.state.dca, exit_price)

    # === compounding =========================================================

    def compound_profits(self, capital: float) -> float:
        new_base = self.risk.compound_profits(self.state, capital)
        self._save_state()
        return new_base

    # === strategy selection ==================================================

    def select_strategy(self) -> StrategyMode:
        r = self.state.regime
        m = self.state.micro
        if r.dump_mode:
            return StrategyMode.COOLDOWN          # defense: no new buys
        if r.volatility_regime == "extreme":
            return StrategyMode.COOLDOWN
        if r.trend_strength > 0.6 and r.trend in (Trend.BULL, Trend.BEAR):
            return StrategyMode.DCA
        if r.trend == Trend.RANGING and m.bid_ask_spread_pct < 0.002:
            return StrategyMode.GRID
        return StrategyMode.HYBRID

    # === adaptive grid =======================================================

    def get_grid_params(self) -> dict:
        return self.grid_policy.compute(self.state)

    def should_retarget_level(self, level: dict, price: float, params: dict) -> bool:
        return self.grid_policy.should_retarget(level, price, params)

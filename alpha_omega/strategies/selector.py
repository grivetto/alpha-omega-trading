"""
Strategy Selector for Alpha-Omega Trading System.

Regime-based strategy switching:
- ATR + momentum + trend strength → Grid/DCA/Scalp/Cooldown
- Minimum 5 minutes between switches
- Hysteresis to prevent oscillation
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Type

from .base import BaseStrategy, Signal
from .grid import GridStrategy
from ..core.buffers import OhlcvBuffer
from ..core.types import Position, Order, MarketRegime

log = logging.getLogger("alpha_omega.strategies.selector")


@dataclass
class StrategyConfig:
    """Configuration for a strategy."""
    strategy_class: Type[BaseStrategy]
    params: Dict[str, Any]
    regime_affinity: List[str]  # Which regimes this strategy prefers
    min_confidence: float = 0.6
    priority: int = 0  # Higher = preferred


class StrategySelector:
    """
    Selects and manages strategy based on market regime.
    
    Regime mapping:
    - RANGE (ADX < 25): GridStrategy (high affinity)
    - TREND (ADX > 30): ScalpStrategy / MomentumStrategy (high affinity)
    - TRANSITIONAL (25 <= ADX <= 30): DCA / MeanReversion (medium affinity)
    - EXTREME_VOL: Cooldown / Risk-off
    
    Switching rules:
    - Minimum 5 minutes between strategy switches
    - Hysteresis: require regime confirmation over 2-3 ticks
    - Track performance per regime for adaptive selection
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        min_switch_interval: int = 300,  # 5 minutes
        hysteresis_ticks: int = 3,
    ):
        self.symbol = symbol
        self.exchange = exchange
        self.min_switch_interval = min_switch_interval
        self.hysteresis_ticks = hysteresis_ticks
        
        # Strategy registry
        self._strategies: Dict[str, BaseStrategy] = {}
        self._strategy_configs: Dict[str, StrategyConfig] = {}
        
        # Current state
        self.current_strategy: Optional[BaseStrategy] = None
        self.current_strategy_name: str = ""
        self.last_switch_ts = 0
        self.regime_history: List[str] = []
        self.regime_confidence: Dict[str, float] = {}
        
        # Performance tracking per regime
        self.performance: Dict[str, Dict[str, float]] = {
            "grid": {"trades": 0, "wins": 0, "pnl": 0.0},
            "dca": {"trades": 0, "wins": 0, "pnl": 0.0},
            "scalp": {"trades": 0, "wins": 0, "pnl": 0.0},
            "momentum": {"trades": 0, "wins": 0, "pnl": 0.0},
            "mean_reversion": {"trades": 0, "wins": 0, "pnl": 0.0},
        }
        
        # Initialize default strategies
        self._init_default_strategies()

    def _init_default_strategies(self) -> None:
        """Register default strategies."""
        
        # Grid Strategy - best for range markets
        self.register_strategy(
            "grid",
            GridStrategy,
            {
                "grid_levels": 5,
                "base_spread_pct": 0.005,
                "per_level": 0.2,
                "atr_multiplier": 0.7,
                "min_spread_pct": 0.002,
                "max_spread_pct": 0.025,
                "drift_pct": 0.06,
                "use_momentum_filter": True,
                "hybrid_mode": True,
                "take_profit_pct": 0.01,
                "stop_loss_pct": 0.03,
            },
            regime_affinity=["range", "transitional"],
            priority=10
        )
        
        # DCA Strategy - for transitional/accumulation
        from .dca import DCAStrategy
        self.register_strategy(
            "dca",
            DCAStrategy,
            {
                "max_entries": 5,
                "entry_spacing_pct": 0.02,
                "take_profit_pct": 0.03,
                "stop_loss_pct": 0.05,
            },
            regime_affinity=["transitional", "range"],
            priority=5
        )
        
        # Scalp Strategy - for trending markets
        from .scalp import ScalpStrategy
        self.register_strategy(
            "scalp",
            ScalpStrategy,
            {
                "take_profit_pct": 0.005,
                "stop_loss_pct": 0.01,
                "max_hold_seconds": 300,
                "min_spread_pct": 0.001,
            },
            regime_affinity=["trend"],
            priority=8
        )
        
        # Momentum Strategy - for strong trends
        from .momentum import MomentumStrategy
        self.register_strategy(
            "momentum",
            MomentumStrategy,
            {
                "lookback_periods": 20,
                "entry_threshold": 0.02,
                "exit_threshold": 0.01,
                "stop_loss_pct": 0.02,
            },
            regime_affinity=["trend"],
            priority=7
        )
        
        # Mean Reversion - for overbought/oversold
        from .mean_reversion import MeanReversionStrategy
        self.register_strategy(
            "mean_reversion",
            MeanReversionStrategy,
            {
                "bb_period": 20,
                "bb_std": 2.0,
                "rsi_oversold": 30,
                "rsi_overbought": 70,
                "take_profit_pct": 0.02,
                "stop_loss_pct": 0.03,
            },
            regime_affinity=["transitional", "range"],
            priority=4
        )
        
        # Set default to grid
        self.current_strategy = self._strategies["grid"]
        self.current_strategy_name = "grid"
        log.info(f"Strategy selector initialized with {len(self._strategies)} strategies, default: grid")

    def register_strategy(
        self,
        name: str,
        strategy_class: Type[BaseStrategy],
        params: Dict[str, Any],
        regime_affinity: List[str],
        priority: int = 0,
        min_confidence: float = 0.6
    ) -> None:
        """Register a strategy with its configuration."""
        self._strategy_configs[name] = StrategyConfig(
            strategy_class=strategy_class,
            params=params,
            regime_affinity=regime_affinity,
            min_confidence=min_confidence,
            priority=priority
        )
        
        # Instantiate strategy
        strategy = strategy_class(
            symbol=self.symbol,
            exchange=self.exchange,
            **params
        )
        self._strategies[name] = strategy
        log.info(f"Registered strategy: {name} (affinity: {regime_affinity}, priority: {priority})")

    def select_strategy(
        self,
        regime: str,
        adx: float,
        rsi: float,
        atr_pct: float,
        trend_strength: float = 0.0
    ) -> Optional[BaseStrategy]:
        """Select best strategy for current market conditions."""
        
        now = time.time()
        
        # Check minimum switch interval
        if now - self.last_switch_ts < self.min_switch_interval:
            return self.current_strategy
        
        # Update regime history for hysteresis
        self.regime_history.append(regime)
        if len(self.regime_history) > self.hysteresis_ticks * 2:
            self.regime_history = self.regime_history[-(self.hysteresis_ticks * 2):]
        
        # Calculate regime confidence (how consistent is the regime?)
        if len(self.regime_history) >= self.hysteresis_ticks:
            recent = self.regime_history[-self.hysteresis_ticks:]
            regime_counts = {}
            for r in recent:
                regime_counts[r] = regime_counts.get(r, 0) + 1
            dominant_regime = max(regime_counts, key=regime_counts.get)
            confidence = regime_counts[dominant_regime] / len(recent)
            self.regime_confidence[dominant_regime] = confidence
            
            # Only consider switching if regime is stable
            if confidence < 0.67:  # Need 2/3 agreement
                return self.current_strategy
            
            regime = dominant_regime
        
        # Score each strategy for current conditions
        scores = {}
        for name, config in self._strategy_configs.items():
            score = config.priority
            
            # Regime affinity bonus
            if regime in config.regime_affinity:
                score += 20
            elif regime == "transitional" and "transitional" not in config.regime_affinity:
                score -= 10
            
            # Performance bonus
            perf = self.performance.get(name, {})
            if perf.get("trades", 0) >= 10:
                win_rate = perf.get("wins", 0) / perf.get("trades", 1)
                if win_rate > 0.55:
                    score += 10
                elif win_rate < 0.4:
                    score -= 10
            
            # ADX-based adjustments
            if name == "scalp" and adx > 35:
                score += 15
            elif name == "grid" and adx < 20:
                score += 15
            elif name == "momentum" and trend_strength > 0.03:
                score += 15
            elif name == "mean_reversion" and (rsi < 35 or rsi > 65):
                score += 10
            
            # Volatility adjustments
            if name == "dca" and atr_pct > 2.0:
                score += 10  # DCA good in high vol
            elif name == "scalp" and atr_pct < 0.5:
                score -= 10  # Scalp needs some vol
            
            scores[name] = score
        
        # Select best strategy
        if not scores:
            return self.current_strategy
        
        best_name = max(scores, key=scores.get)
        best_score = scores[best_name]
        
        # Only switch if significantly better
        current_score = scores.get(self.current_strategy_name, 0)
        if best_name != self.current_strategy_name and best_score > current_score + 10:
            old_name = self.current_strategy_name
            self.current_strategy = self._strategies[best_name]
            self.current_strategy_name = best_name
            self.last_switch_ts = now
            log.info(f"Strategy switched: {old_name} -> {best_name} (scores: {scores}) regime={regime} confidence={self.regime_confidence.get(regime, 0):.2f}")
        
        return self.current_strategy

    async def generate_signal(
        self,
        ohlcv: OhlcvBuffer,
        current_price: float,
        atr_pct: float,
        adx: float,
        rsi: float,
        regime: str,
        equity: float,
        positions: Dict[str, Position],
        open_orders: Dict[str, Order],
    ) -> Optional[Signal]:
        """Generate signal using current selected strategy."""
        
        # Select strategy for current regime
        trend_strength = abs(rsi - 50) / 50  # 0-1 scale
        strategy = self.select_strategy(regime, adx, rsi, atr_pct, trend_strength)
        
        if not strategy:
            return None
        
        # Generate signal from selected strategy
        signal = await strategy.generate_signal(
            ohlcv=ohlcv,
            current_price=current_price,
            atr_pct=atr_pct,
            adx=adx,
            rsi=rsi,
            regime=regime,
            equity=equity,
            positions=positions,
            open_orders=open_orders,
        )
        
        if signal:
            signal.strategy = self.current_strategy_name
        
        return signal

    def record_trade_result(self, strategy_name: str, pnl: float, won: bool) -> None:
        """Record trade result for performance tracking."""
        if strategy_name not in self.performance:
            self.performance[strategy_name] = {"trades": 0, "wins": 0, "pnl": 0.0}
        
        perf = self.performance[strategy_name]
        perf["trades"] += 1
        if won:
            perf["wins"] += 1
        perf["pnl"] += pnl

    def get_current_strategy(self) -> Optional[BaseStrategy]:
        return self.current_strategy

    def get_current_strategy_name(self) -> str:
        return self.current_strategy_name

    def get_performance_summary(self) -> Dict[str, Dict]:
        """Get performance summary per strategy."""
        summary = {}
        for name, perf in self.performance.items():
            trades = perf.get("trades", 0)
            wins = perf.get("wins", 0)
            summary[name] = {
                "trades": trades,
                "wins": wins,
                "losses": trades - wins,
                "win_rate": wins / trades if trades > 0 else 0,
                "total_pnl": perf.get("pnl", 0.0),
                "avg_pnl": perf.get("pnl", 0.0) / trades if trades > 0 else 0,
            }
        return summary

    def force_strategy(self, name: str) -> bool:
        """Force switch to specific strategy (for testing/manual override)."""
        if name in self._strategies:
            old = self.current_strategy_name
            self.current_strategy = self._strategies[name]
            self.current_strategy_name = name
            self.last_switch_ts = time.time()
            log.info(f"Strategy forced: {old} -> {name}")
            return True
        return False

    def get_regime_confidence(self) -> Dict[str, float]:
        return self.regime_confidence.copy()

    def get_strategy_scores(self, regime: str, adx: float, rsi: float, atr_pct: float) -> Dict[str, float]:
        """Get current scores for all strategies (for debugging/monitoring)."""
        trend_strength = abs(rsi - 50) / 50
        scores = {}
        for name, config in self._strategy_configs.items():
            score = config.priority
            if regime in config.regime_affinity:
                score += 20
            perf = self.performance.get(name, {})
            if perf.get("trades", 0) >= 10:
                win_rate = perf.get("wins", 0) / perf.get("trades", 1)
                if win_rate > 0.55:
                    score += 10
                elif win_rate < 0.4:
                    score -= 10
            if name == "scalp" and adx > 35:
                score += 15
            elif name == "grid" and adx < 20:
                score += 15
            elif name == "momentum" and trend_strength > 0.03:
                score += 15
            elif name == "mean_reversion" and (rsi < 35 or rsi > 65):
                score += 10
            if name == "dca" and atr_pct > 2.0:
                score += 10
            elif name == "scalp" and atr_pct < 0.5:
                score -= 10
            scores[name] = score
        return scores
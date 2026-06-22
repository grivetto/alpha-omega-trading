"""
Performance Analytics Suite – Sharpe optimization, win rate prediction, drawdown forecasting.
"""
import logging, math, statistics
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class TradeMetrics:
    win_rate: float
    avg_win: float
    avg_loss: float
    sharpe_ratio: float
    max_drawdown: float
    total_pnl: float
    trade_count: int

class PerformanceAnalytics:
    def __init__(self):
        self.logger = logging.getLogger("PerformanceAnalytics")
        
    def calculate_metrics(self, trades: List[Dict]) -> TradeMetrics:
        """Calculate comprehensive performance metrics from trade history."""
        if not trades:
            return TradeMetrics(0, 0, 0, 0, 0, 0, 0)
        
        wins = [t for t in trades if t.get("profit", 0) > 0]
        losses = [t for t in trades if t.get("profit", 0) <= 0]
        
        win_rate = len(wins) / len(trades) if trades else 0
        avg_win = statistics.mean([t["profit"] for t in wins]) if wins else 0
        avg_loss = statistics.mean([t["profit"] for t in losses]) if losses else 0
        
        # Sharpe ratio (simplified: assume risk-free rate = 0)
        returns = [t["profit"] / t.get("capital", 1) for t in trades if t.get("capital", 1) > 0]
        sharpe = statistics.mean(returns) / statistics.stdev(returns) if len(returns) > 1 and statistics.stdev(returns) > 0 else 0
        
        # Max drawdown
        equity_curve = self._build_equity_curve(trades)
        max_dd = self._calculate_max_drawdown(equity_curve)
        
        total_pnl = sum(t.get("profit", 0) for t in trades)
        
        return TradeMetrics(
            win_rate=win_rate,
            avg_win=avg_win,
            avg_loss=avg_loss,
            sharpe_ratio=sharpe,
            max_drawdown=max_dd,
            total_pnl=total_pnl,
            trade_count=len(trades)
        )
    
    def _build_equity_curve(self, trades: List[Dict]) -> List[float]:
        equity = [0.0]
        for t in trades:
            equity.append(equity[-1] + t.get("profit", 0))
        return equity
    
    def _calculate_max_drawdown(self, equity: List[float]) -> float:
        peak = equity[0]
        max_dd = 0.0
        for value in equity:
            if value > peak:
                peak = value
            dd = (peak - value) / peak * 100 if peak > 0 else 0
            if dd > max_dd:
                max_dd = dd
        return max_dd
    
    def predict_win_rate(self, recent_trades: List[Dict], window: int = 20) -> float:
        """Predict win rate based on recent performance."""
        if not recent_trades:
            return 0.5
        recent = recent_trades[-window:]
        wins = [t for t in recent if t.get("profit", 0) > 0]
        return len(wins) / len(recent) if recent else 0.5
    
    def forecast_drawdown(self, metrics: TradeMetrics, horizon: int = 50) -> float:
        """
        Simple drawdown forecast based on current metrics.
        Uses Monte Carlo simulation conceptually.
        """
        if metrics.win_rate <= 0:
            return 100.0
        
        # Expected return per trade
        expect_return = metrics.win_rate * metrics.avg_win + (1 - metrics.win_rate) * metrics.avg_loss
        
        # Volatility approximation
        returns = []
        for _ in range(1000):
            sample_return = metrics.avg_win if random.random() < metrics.win_rate else metrics.avg_loss
            returns.append(sample_return)
        
        # Simple projection
        if expect_return > 0:
            return metrics.max_drawdown * 0.8  # Improving
        else:
            return min(100.0, metrics.max_drawdown * 1.5)  # Degrading
    
    def optimize_sharpe(self, strategies: Dict[str, Dict]) -> str:
        """Return name of strategy with best Sharpe ratio."""
        best_strat = None
        best_sharpe = -float('inf')
        
        for name, data in strategies.items():
            sharpe = data.get("sharpe", 0)
            win_rate = data.get("win_rate", 0)
            # Penalize extremely low trade counts
            trade_count = data.get("trade_count", 0)
            if trade_count < 10:
                sharpe *= 0.5
            if sharpe > best_sharpe:
                best_sharpe = sharpe
                best_strat = name
        
        return best_strat or list(strategies.keys())[0]


import random  # For Monte Carlo forecast
"""
Portfolio Optimizer – dynamic capital allocation based on market regime and performance.
"""
import logging
from typing import Dict

class PortfolioOptimizer:
    def __init__(self):
        self.logger = logging.getLogger("PortfolioOptimizer")
        # Base allocations by regime
        self.regime_allocations = {
            "bull": {"grid": 0.6, "momentum": 0.3, "defensive": 0.1},
            "bear": {"grid": 0.2, "momentum": 0.1, "defensive": 0.7},
            "choppy": {"grid": 0.4, "momentum": 0.2, "defensive": 0.4},
            "volatile": {"grid": 0.3, "momentum": 0.3, "defensive": 0.4},
            "neutral": {"grid": 0.5, "momentum": 0.2, "defensive": 0.3}
        }
        
    def calculate_allocation(self, current_regime: str, bot_performance: Dict) -> Dict[str, float]:
        """
        Calculate capital allocation based on regime and bot performance.
        bot_performance: {bot_name: {"win_rate": float, "sharpe": float, "drawdown": float}}
        """
        # Start with base regime allocation
        base_alloc = self.regime_allocations.get(current_regime, self.regime_allocations["neutral"])
        adjusted_alloc = base_alloc.copy()
        
        # Performance adjustment (simplified)
        if bot_performance:
            # Boost bots with high Sharpe (>1.0) and low drawdown (<5%)
            for bot_name, metrics in bot_performance.items():
                sharpe = metrics.get("sharpe", 0)
                drawdown = metrics.get("drawdown", 0)
                
                if sharpe > 1.0 and drawdown < 0.05:
                    # Increase allocation by 10%
                    for key in adjusted_alloc:
                        if key in bot_name.lower():
                            adjusted_alloc[key] = min(1.0, adjusted_alloc[key] * 1.1)
        
        # Normalize allocations to sum to 1.0
        total = sum(adjusted_alloc.values())
        if total > 0:
            for key in adjusted_alloc:
                adjusted_alloc[key] /= total
                
        self.logger.debug(f"Portfolio allocation: {adjusted_alloc}")
        return adjusted_alloc

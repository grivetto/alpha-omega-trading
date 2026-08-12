"""
Portfolio Risk Manager for Alpha-Omega Trading System.

Portfolio-level risk controls:
- Max portfolio drawdown
- Max daily loss
- Max exposure per base currency
- Max correlation between positions
- Max positions per base currency
- Volatility targeting
- Kill switch integration
"""
from __future__ import annotations
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

log = logging.getLogger("alpha_omega.risk.manager")


@dataclass
class RiskMetrics:
    """Current risk metrics."""
    total_equity: float = 0.0
    portfolio_dd: float = 0.0
    daily_pnl: float = 0.0
    exposure_per_base: Dict[str, float] = field(default_factory=dict)
    positions_count: int = 0
    max_correlation: float = 0.0
    kill_switch_armed: bool = False
    last_update: int = field(default_factory=lambda: int(time.time()))


class PortfolioRiskManager:
    """
    Portfolio-level risk management.
    
    Monitors and enforces risk limits across all positions in the fleet.
    Integrates with kill switch for emergency shutdown.
    """

    def __init__(
        self,
        max_portfolio_dd: float = 0.20,  # 20%
        max_daily_loss: float = 0.05,  # 5%
        max_exposure_per_base: float = 0.30,  # 30%
        max_correlation: float = 0.7,
        max_positions_per_base: int = 2,
        volatility_targeting: bool = True,
        kill_switch_file: str = "/tmp/shadowgrid_kill",
    ):
        self.max_portfolio_dd = max_portfolio_dd
        self.max_daily_loss = max_daily_loss
        self.max_exposure_per_base = max_exposure_per_base
        self.max_correlation = max_correlation
        self.max_positions_per_base = max_positions_per_base
        self.volatility_targeting = volatility_targeting
        self.kill_switch_file = kill_switch_file
        
        # State
        self.metrics = RiskMetrics()
        self.daily_start_equity = 0.0
        self.peak_equity = 0.0
        self._position_history: Dict[str, List[float]] = {}  # For correlation calc
        self._correlation_matrix: Dict[str, Dict[str, float]] = {}
        
        # Kill switch
        self._kill_switch_armed = False
        
        log.info(f"PortfolioRiskManager initialized: max_dd={max_portfolio_dd:.1%}, max_daily_loss={max_daily_loss:.1%}, max_exposure={max_exposure_per_base:.1%}")

    async def check_limits(
        self,
        equity: float,
        positions: Dict[str, Any],
        daily_pnl: float,
    ) -> bool:
        """Check all risk limits. Returns True if within limits."""
        
        # Initialize on first call
        if self.daily_start_equity == 0:
            self.daily_start_equity = equity
            self.peak_equity = equity
        
        # Update peak equity
        if equity > self.peak_equity:
            self.peak_equity = equity
        
        # Update total equity
        self.metrics.total_equity = equity
        # 1. Portfolio drawdown check
        portfolio_dd = (self.peak_equity - equity) / self.peak_equity if self.peak_equity > 0 else 0
        self.metrics.portfolio_dd = portfolio_dd
        
        if portfolio_dd >= self.max_portfolio_dd:
            log.critical(f"PORTFOLIO DD LIMIT: {portfolio_dd:.2%} >= {self.max_portfolio_dd:.2%}")
            await self._trigger_kill_switch("portfolio_drawdown")
            return False
        
        # 2. Daily loss check - skip if equity not yet initialized
        if self.daily_start_equity > 0 and equity > 0:
            daily_loss_pct = (self.daily_start_equity - equity) / self.daily_start_equity
            self.metrics.daily_pnl = daily_pnl
            
            if daily_loss_pct >= self.max_daily_loss:
                log.critical(f"DAILY LOSS LIMIT: {daily_loss_pct:.2%} >= {self.max_daily_loss:.2%}")
                await self._trigger_kill_switch("daily_loss")
                return False
        
        # 3. Exposure per base currency
        exposure = self._calculate_exposure(positions, equity)
        self.metrics.exposure_per_base = exposure
        
        for base, exp_pct in exposure.items():
            if exp_pct > self.max_exposure_per_base:
                log.warning(f"EXPOSURE LIMIT {base}: {exp_pct:.2%} > {self.max_exposure_per_base:.2%}")
                # Don't kill switch, just warn and prevent new positions
        
        # 4. Positions per base
        positions_per_base = self._count_positions_per_base(positions)
        for base, count in positions_per_base.items():
            if count > self.max_positions_per_base:
                log.warning(f"POSITION COUNT {base}: {count} > {self.max_positions_per_base}")
        
        # 5. Correlation check (if enough history)
        max_corr = await self._check_correlation(positions)
        self.metrics.max_correlation = max_corr
        
        if max_corr > self.max_correlation:
            log.warning(f"CORRELATION HIGH: {max_corr:.2f} > {self.max_correlation}")
            # Don't kill, just warn
        
        # Update metrics
        self.metrics.total_equity = equity
        self.metrics.positions_count = len(positions)
        self.metrics.last_update = int(time.time())
        
        return True

    def _calculate_exposure(self, positions: Dict[str, Any], equity: float) -> Dict[str, float]:
        """Calculate exposure per base currency as % of equity."""
        if equity <= 0:
            return {}
        
        exposure = {}
        for pos in positions.values():
            base = pos.base if hasattr(pos, 'base') else pos.get('base', '')
            if not base:
                # Try to extract from symbol
                symbol = pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', '')
                if '/' in symbol:
                    base = symbol.split('/')[0]
            
            size = pos.size if hasattr(pos, 'size') else pos.get('size', 0)
            entry_price = pos.entry_price if hasattr(pos, 'entry_price') else pos.get('entry_price', 0)
            current_price = pos.current_price if hasattr(pos, 'current_price') else pos.get('current_price', entry_price)
            
            if base and size != 0 and current_price > 0:
                notional = abs(size) * current_price
                exposure[base] = exposure.get(base, 0) + notional
        
        # Convert to percentage
        return {base: notional / equity for base, notional in exposure.items()}

    def _count_positions_per_base(self, positions: Dict[str, Any]) -> Dict[str, int]:
        """Count open positions per base currency."""
        counts = {}
        for pos in positions.values():
            base = pos.base if hasattr(pos, 'base') else pos.get('base', '')
            if not base:
                symbol = pos.symbol if hasattr(pos, 'symbol') else pos.get('symbol', '')
                if '/' in symbol:
                    base = symbol.split('/')[0]
            if base:
                counts[base] = counts.get(base, 0) + 1
        return counts

    async def _check_correlation(self, positions: Dict[str, Any]) -> float:
        """Calculate max correlation between positions."""
        if len(positions) < 2:
            return 0.0
        
        # Update position price history
        for symbol, pos in positions.items():
            current_price = pos.current_price if hasattr(pos, 'current_price') else pos.get('current_price', 0)
            if current_price > 0:
                if symbol not in self._position_history:
                    self._position_history[symbol] = []
                self._position_history[symbol].append(current_price)
                # Keep only last 100 prices
                if len(self._position_history[symbol]) > 100:
                    self._position_history[symbol] = self._position_history[symbol][-100:]
        
        # Calculate correlation matrix
        symbols = list(self._position_history.keys())
        if len(symbols) < 2:
            return 0.0
        
        max_corr = 0.0
        
        for i, s1 in enumerate(symbols):
            for s2 in symbols[i+1:]:
                hist1 = self._position_history[s1]
                hist2 = self._position_history[s2]
                
                if len(hist1) >= 20 and len(hist2) >= 20:
                    # Align histories (use min length)
                    min_len = min(len(hist1), len(hist2))
                    h1 = hist1[-min_len:]
                    h2 = hist2[-min_len:]
                    
                    # Calculate returns
                    r1 = [(h1[i] - h1[i-1]) / h1[i-1] for i in range(1, len(h1))]
                    r2 = [(h2[i] - h2[i-1]) / h2[i-1] for i in range(1, len(h2))]
                    
                    if len(r1) == len(r2) and len(r1) > 10:
                        corr = self._pearson_correlation(r1, r2)
                        max_corr = max(max_corr, abs(corr))
        
        return max_corr

    def _pearson_correlation(self, x: List[float], y: List[float]) -> float:
        """Calculate Pearson correlation coefficient."""
        n = len(x)
        if n != len(y) or n < 2:
            return 0.0
        
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
        std_x = (sum((xi - mean_x) ** 2 for xi in x) / n) ** 0.5
        std_y = (sum((yi - mean_y) ** 2 for yi in y) / n) ** 0.5
        
        if std_x == 0 or std_y == 0:
            return 0.0
        
        return cov / (std_x * std_y)

    async def _trigger_kill_switch(self, reason: str) -> None:
        """Trigger kill switch by writing file."""
        if self._kill_switch_armed:
            return
        
        self._kill_switch_armed = True
        self.metrics.kill_switch_armed = True
        
        try:
            import json
            with open(self.kill_switch_file, 'w') as f:
                json.dump({
                    "triggered": True,
                    "reason": reason,
                    "timestamp": int(time.time()),
                    "equity": self.metrics.total_equity,
                    "drawdown": self.metrics.portfolio_dd,
                }, f)
            log.critical(f"KILL SWITCH TRIGGERED: {reason} - written to {self.kill_switch_file}")
        except Exception as e:
            log.error(f"Failed to write kill switch file: {e}")

    def check_kill_switch(self) -> bool:
        """Check if kill switch is armed."""
        return self._kill_switch_armed

    def reset_daily(self, equity: float) -> None:
        """Reset daily counters (call at midnight)."""
        self.daily_start_equity = equity
        self._kill_switch_armed = False
        self.metrics.kill_switch_armed = False
        self.metrics.daily_pnl = 0.0
        
        # Remove kill switch file
        try:
            import os
            if os.path.exists(self.kill_switch_file):
                os.remove(self.kill_switch_file)
        except Exception:
            pass
        
        log.info(f"Daily risk counters reset: equity={equity:.2f}")

    def get_status(self) -> Dict[str, Any]:
        """Get current risk status."""
        return {
            "total_equity": self.metrics.total_equity,
            "portfolio_dd_pct": round(self.metrics.portfolio_dd * 100, 2),
            "daily_pnl": round(self.metrics.daily_pnl, 2),
            "exposure_per_base": {k: round(v * 100, 2) for k, v in self.metrics.exposure_per_base.items()},
            "positions_count": self.metrics.positions_count,
            "max_correlation": round(self.metrics.max_correlation, 3),
            "kill_switch_armed": self.metrics.kill_switch_armed,
            "limits": {
                "max_portfolio_dd_pct": round(self.max_portfolio_dd * 100, 1),
                "max_daily_loss_pct": round(self.max_daily_loss * 100, 1),
                "max_exposure_per_base_pct": round(self.max_exposure_per_base * 100, 1),
                "max_correlation": round(self.max_correlation, 2),
                "max_positions_per_base": self.max_positions_per_base,
            },
            "last_update": self.metrics.last_update,
        }

    def can_open_position(self, base: str, notional: float, equity: float, positions: Dict[str, Any]) -> bool:
        """Check if a new position can be opened."""
        # Check exposure limit
        current_exposure = self._calculate_exposure(positions, equity)
        new_exposure = current_exposure.get(base, 0) + (notional / equity)
        
        if new_exposure > self.max_exposure_per_base:
            return False
        
        # Check position count
        counts = self._count_positions_per_base(positions)
        if counts.get(base, 0) >= self.max_positions_per_base:
            return False
        
        # Check portfolio DD
        if self.metrics.portfolio_dd >= self.max_portfolio_dd * 0.8:
            return False
        
        # Check daily loss
        if self.daily_start_equity > 0:
            daily_loss = (self.daily_start_equity - equity) / self.daily_start_equity
            if daily_loss >= self.max_daily_loss * 0.8:
                return False
        
        return True
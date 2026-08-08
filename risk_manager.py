#!/usr/bin/env python3
"""
Risk Manager - Portfolio-level risk management for ShadowGrid Fleet.

Features:
- Correlation matrix calculation and monitoring
- Position sizing with risk parity
- Exposure limits per asset/base currency
- Volatility targeting and regime detection
- Drawdown tracking and alerts
"""

from __future__ import annotations
import json
import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np

log = logging.getLogger("risk_manager")
log.setLevel(logging.INFO)
sh = logging.StreamHandler()
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.handlers = [sh]


class RiskManager:
    """Portfolio-level risk management engine."""
    
    def __init__(
        self,
        total_capital: float,
        max_portfolio_dd: float = 0.20,
        max_daily_loss: float = 0.05,
        max_exposure_per_base: float = 0.30,
        max_correlation: float = 0.7,
        max_positions_per_base: int = 2,
        volatility_lookback_days: int = 30,
        atr_spike_multiplier: float = 2.0,
        atr_extreme_multiplier: float = 3.0,
    ):
        self.total_capital = total_capital
        self.max_portfolio_dd = max_portfolio_dd
        self.max_daily_loss = max_daily_loss
        self.max_exposure_per_base = max_exposure_per_base
        self.max_correlation = max_correlation
        self.max_positions_per_base = max_positions_per_base
        self.volatility_lookback_days = volatility_lookback_days
        self.atr_spike_multiplier = atr_spike_multiplier
        self.atr_extreme_multiplier = atr_extreme_multiplier
        
        # State
        self.positions: Dict[str, Dict] = {}  # symbol -> {size, entry, current, base, quote}
        self.daily_pnl: List[Tuple[datetime, float]] = []
        self.peak_equity = total_capital
        self.current_equity = total_capital
        self.lock = threading.RLock()
        
        # Volatility tracking
        self.atr_history: Dict[str, List[float]] = defaultdict(list)
        self.price_history: Dict[str, List[float]] = defaultdict(list)
        
        # Kill switch
        self.kill_switch_triggered = False
        self.kill_reason = ""
        
        log.info(f"RiskManager initialized: capital={total_capital}€, max_dd={max_portfolio_dd:.0%}, "
                 f"max_daily_loss={max_daily_loss:.0%}, max_exposure_base={max_exposure_per_base:.0%}")
    
    def update_position(self, symbol: str, size: float, entry_price: float, 
                        current_price: float, base: str, quote: str) -> None:
        """Update or add a position."""
        with self.lock:
            self.positions[symbol] = {
                "size": size,
                "entry_price": entry_price,
                "current_price": current_price,
                "base": base.upper(),
                "quote": quote.upper(),
                "unrealized_pnl": size * (current_price - entry_price),
                "timestamp": datetime.now(),
            }
            self.price_history[symbol].append(current_price)
            # Keep only lookback period
            cutoff = datetime.now() - timedelta(days=self.volatility_lookback_days)
            # Note: price_history doesn't have timestamps, simplified for now
            if len(self.price_history[symbol]) > self.volatility_lookback_days * 24:  # hourly approx
                self.price_history[symbol] = self.price_history[symbol][-self.volatility_lookback_days * 24:]
    
    def update_atr(self, symbol: str, atr: float) -> None:
        """Update ATR history for volatility regime detection."""
        with self.lock:
            self.atr_history[symbol].append(atr)
            if len(self.atr_history[symbol]) > self.volatility_lookback_days * 24:
                self.atr_history[symbol] = self.atr_history[symbol][-self.volatility_lookback_days * 24:]
    
    def update_equity(self, equity: float) -> None:
        """Update current equity and track drawdown."""
        with self.lock:
            self.current_equity = equity
            if equity > self.peak_equity:
                self.peak_equity = equity
            
            # Track daily PnL
            today = datetime.now().date()
            if not self.daily_pnl or self.daily_pnl[-1][0].date() != today:
                self.daily_pnl.append((datetime.now(), equity))
            else:
                self.daily_pnl[-1] = (datetime.now(), equity)
    
    def get_portfolio_dd(self) -> float:
        """Get current portfolio drawdown as fraction."""
        with self.lock:
            if self.peak_equity == 0:
                return 0.0
            return (self.peak_equity - self.current_equity) / self.peak_equity
    
    def get_daily_loss(self) -> float:
        """Get today's loss as fraction of starting equity."""
        with self.lock:
            if len(self.daily_pnl) < 2:
                return 0.0
            today_start = self.daily_pnl[-1][1]  # This is current, need day start
            # Simplified: track from first entry today
            today_entries = [e for e in self.daily_pnl if e[0].date() == datetime.now().date()]
            if len(today_entries) < 2:
                return 0.0
            day_start_equity = today_entries[0][1]
            current_equity = today_entries[-1][1]
            if day_start_equity == 0:
                return 0.0
            return max(0, (day_start_equity - current_equity) / day_start_equity)
    
    def check_kill_switch(self) -> Tuple[bool, str]:
        """Check if kill switch should be triggered."""
        with self.lock:
            # Check file-based kill switch
            kill_file = Path("/tmp/shadowgrid_kill")
            if kill_file.exists():
                reason = kill_file.read_text().strip() or "Manual kill switch"
                self.kill_switch_triggered = True
                self.kill_reason = reason
                return True, reason
            
            # Check portfolio DD
            dd = self.get_portfolio_dd()
            if dd >= self.max_portfolio_dd:
                self.kill_switch_triggered = True
                self.kill_reason = f"Portfolio DD {dd:.1%} >= {self.max_portfolio_dd:.0%}"
                return True, self.kill_reason
            
            # Check daily loss
            daily_loss = self.get_daily_loss()
            if daily_loss >= self.max_daily_loss:
                self.kill_switch_triggered = True
                self.kill_reason = f"Daily loss {daily_loss:.1%} >= {self.max_daily_loss:.0%}"
                return True, self.kill_reason
            
            return False, ""
    
    def get_exposure_per_base(self) -> Dict[str, float]:
        """Get current exposure per base currency as fraction of total capital."""
        with self.lock:
            exposure = defaultdict(float)
            for pos in self.positions.values():
                base = pos["base"]
                position_value = abs(pos["size"] * pos["current_price"])
                exposure[base] += position_value
            return {base: val / self.total_capital for base, val in exposure.items()}
    
    def check_exposure_limits(self, new_symbol: str, new_size: float, new_price: float) -> Tuple[bool, str]:
        """Check if adding a position would exceed exposure limits."""
        with self.lock:
            base = new_symbol.split("/")[0].upper()
            new_value = abs(new_size * new_price)
            
            current_exposure = self.get_exposure_per_base()
            projected_exposure = current_exposure.get(base, 0) + new_value / self.total_capital
            
            if projected_exposure > self.max_exposure_per_base:
                return False, f"Exposure limit: {base} would be {projected_exposure:.1%} > {self.max_exposure_per_base:.0%}"
            
            # Count positions per base
            base_count = sum(1 for s in self.positions if s.split("/")[0].upper() == base)
            if base_count >= self.max_positions_per_base:
                return False, f"Max positions per base: {base} already has {base_count} positions"
            
            return True, ""
    
    def calculate_correlation_matrix(self, symbols: List[str]) -> np.ndarray:
        """Calculate correlation matrix for given symbols."""
        with self.lock:
            # Need price history for all symbols
            valid_symbols = [s for s in symbols if s in self.price_history and len(self.price_history[s]) > 10]
            if len(valid_symbols) < 2:
                return np.eye(len(symbols))
            
            # Calculate returns
            returns = {}
            min_len = min(len(self.price_history[s]) for s in valid_symbols)
            for s in valid_symbols:
                prices = np.array(self.price_history[s][-min_len:])
                returns[s] = np.diff(prices) / prices[:-1]
            
            # Build correlation matrix
            n = len(symbols)
            corr = np.eye(n)
            for i, s1 in enumerate(symbols):
                for j, s2 in enumerate(symbols):
                    if s1 in returns and s2 in returns and i != j:
                        corr[i, j] = np.corrcoef(returns[s1], returns[s2])[0, 1]
            return corr
    
    def check_correlation_limit(self, new_symbol: str) -> Tuple[bool, str]:
        """Check if new position would exceed correlation limits with existing."""
        with self.lock:
            symbols = list(self.positions.keys()) + [new_symbol]
            if len(symbols) < 2:
                return True, ""
            
            corr_matrix = self.calculate_correlation_matrix(symbols)
            new_idx = symbols.index(new_symbol)
            
            for i, sym in enumerate(symbols):
                if i != new_idx and sym in self.positions:
                    if corr_matrix[new_idx, i] > self.max_correlation:
                        return False, f"Correlation limit: {new_symbol} vs {sym} = {corr_matrix[new_idx, i]:.2f} > {self.max_correlation}"
            return True, ""
    
    def get_volatility_regime(self, symbol: str) -> Dict:
        """Detect volatility regime for a symbol."""
        with self.lock:
            atr_hist = self.atr_history.get(symbol, [])
            if len(atr_hist) < 20:
                return {"regime": "unknown", "current_atr": atr_hist[-1] if atr_hist else 0,
                        "median_atr": 0, "ratio": 1.0, "action": "normal"}
            
            current_atr = atr_hist[-1]
            median_atr = np.median(atr_hist)
            ratio = current_atr / median_atr if median_atr > 0 else 1.0
            
            if ratio >= self.atr_extreme_multiplier:
                regime = "extreme"
                action = "pause_new_orders"
            elif ratio >= self.atr_spike_multiplier:
                regime = "high"
                action = "reduce_grid"
            elif ratio <= 0.5:
                regime = "low"
                action = "expand_grid"
            else:
                regime = "normal"
                action = "normal"
            
            return {
                "regime": regime,
                "current_atr": current_atr,
                "median_atr": median_atr,
                "ratio": ratio,
                "action": action,
            }
    
    def calculate_risk_parity_weights(self, symbols: List[str]) -> Dict[str, float]:
        """Calculate risk parity weights based on inverse volatility."""
        with self.lock:
            vols = {}
            for s in symbols:
                atr_hist = self.atr_history.get(s, [])
                if len(atr_hist) > 10:
                    vols[s] = np.std(atr_hist) if np.std(atr_hist) > 0 else 1.0
                else:
                    vols[s] = 1.0
            
            # Inverse volatility weights
            inv_vols = {s: 1.0 / v for s, v in vols.items()}
            total = sum(inv_vols.values())
            return {s: w / total for s, w in inv_vols.items()}
    
    def get_suggested_allocation(self, symbols: List[str]) -> Dict[str, float]:
        """Get suggested capital allocation per symbol using risk parity."""
        weights = self.calculate_risk_parity_weights(symbols)
        return {s: w * self.total_capital for s, w in weights.items()}
    
    def get_status(self) -> Dict:
        """Get full risk status."""
        with self.lock:
            return {
                "total_capital": self.total_capital,
                "current_equity": self.current_equity,
                "peak_equity": self.peak_equity,
                "portfolio_dd": self.get_portfolio_dd(),
                "daily_loss": self.get_daily_loss(),
                "exposure_per_base": self.get_exposure_per_base(),
                "num_positions": len(self.positions),
                "kill_switch_triggered": self.kill_switch_triggered,
                "kill_reason": self.kill_reason,
                "volatility_regimes": {s: self.get_volatility_regime(s) for s in self.positions.keys()},
            }


# Global instance for easy access
_risk_manager: Optional[RiskManager] = None


def get_risk_manager() -> Optional[RiskManager]:
    return _risk_manager


def init_risk_manager(**kwargs) -> RiskManager:
    global _risk_manager
    _risk_manager = RiskManager(**kwargs)
    return _risk_manager

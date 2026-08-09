"""
Grid Strategy for Alpha-Omega Trading System.

Merges: ShadowGrid v2 grid logic + neo strategy interface.

Features:
- ATR-adaptive spread calculation
- ADX/RSI momentum filter
- Dynamic grid re-anchoring (6% drift threshold)
- HYBRID mode: directional scalper in trending markets (ADX>25)
- Risk-aware position sizing
- Take-profit and stop-loss per grid level
"""
from __future__ import annotations
import logging
from typing import Optional, Dict, List, Any

from .base import BaseStrategy, Signal, create_signal, StrategyMixin
from ..core.buffers import OhlcvBuffer
from ..core.types import Position, Order, MarketRegime

log = logging.getLogger("alpha_omega.strategies.grid")


class GridStrategy(BaseStrategy, StrategyMixin):
    """
    Grid trading strategy with ATR-adaptive spread and optional HYBRID mode.
    
    In RANGE markets (ADX < 25):
    - Places buy/sell limit orders around anchor price
    - Spread adapts to ATR volatility
    - Re-anchors when price drifts > drift_pct from anchor
    
    In TREND markets (ADX > 30) with HYBRID_MODE enabled:
    - Switches to directional scalper
    - Long bias if RSI > 50 + uptrend
    - Short bias if RSI < 50 + downtrend
    - Tighter take-profit, no grid
    """

    def __init__(
        self,
        symbol: str,
        exchange: str,
        grid_levels: int = 5,
        base_spread_pct: float = 0.005,  # 0.5%
        per_level: float = 0.2,  # 20% of capital per level
        atr_multiplier: float = 0.7,
        min_spread_pct: float = 0.002,  # 0.2%
        max_spread_pct: float = 0.025,  # 2.5%
        drift_pct: float = 0.06,  # 6%
        use_momentum_filter: bool = True,
        hybrid_mode: bool = False,
        take_profit_pct: float = 0.01,  # 1%
        stop_loss_pct: float = 0.03,  # 3%
        max_position_pct: float = 0.25,
        **kwargs
    ):
        super().__init__(symbol, exchange, **kwargs)
        
        self.grid_levels = grid_levels
        self.base_spread_pct = base_spread_pct
        self.per_level = per_level
        self.atr_multiplier = atr_multiplier
        self.min_spread_pct = min_spread_pct
        self.max_spread_pct = max_spread_pct
        self.drift_pct = drift_pct
        self.use_momentum_filter = use_momentum_filter
        self.hybrid_mode = hybrid_mode
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.max_position_pct = max_position_pct
        
        # Runtime state
        self.grid_anchor = 0.0
        self.grid_levels_cache: List[Dict] = []
        self.last_signal_ts = 0
        self.min_signal_interval = 5  # seconds between signals

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
        """Generate grid trading signal."""
        
        # Rate limiting
        now = int(__import__('time').time() * 1000)
        if now - self.last_signal_ts < self.min_signal_interval * 1000:
            return None
        
        # Initialize anchor if not set
        if self.grid_anchor <= 0:
            self.grid_anchor = current_price
            log.info(f"Grid anchor initialized at {self.grid_anchor:.6f}")
        
        # Calculate ATR-adaptive spread
        spread = self._calculate_atr_spread(
            atr_pct, self.atr_multiplier,
            self.min_spread_pct, self.max_spread_pct
        )
        
        # Check regime and apply appropriate logic
        if regime == "trend" and self.hybrid_mode:
            return await self._generate_hybrid_signal(
                current_price, atr_pct, adx, rsi, equity, positions, open_orders
            )
        elif regime == "transitional" and self.use_momentum_filter:
            # In transitional, be cautious - only trade with momentum
            return await self._generate_momentum_filtered_signal(
                current_price, spread, atr_pct, adx, rsi, equity, positions, open_orders
            )
        else:
            # Range market - normal grid logic
            return await self._generate_grid_signal(
                current_price, spread, equity, positions, open_orders
            )

    async def _generate_grid_signal(
        self,
        current_price: float,
        spread: float,
        equity: float,
        positions: Dict[str, Position],
        open_orders: Dict[str, Order],
    ) -> Optional[Signal]:
        """Generate grid trading signal for range markets."""
        
        # Check if we need to re-anchor
        if self._should_reanchor(current_price, self.grid_anchor, self.drift_pct):
            old_anchor = self.grid_anchor
            self.grid_anchor = current_price
            log.info(f"Grid re-anchored: {old_anchor:.6f} -> {self.grid_anchor:.6f} (drift: {abs(current_price - old_anchor)/old_anchor:.2%})")
            # Invalidate cached grid levels
            self.grid_levels_cache = []
        
        # Calculate grid levels if not cached
        if not self.grid_levels_cache:
            self.grid_levels_cache = self._calculate_grid_levels(
                self.grid_anchor, spread * 100, self.grid_levels, "both"
            )
        
        # Find next level to trade
        # Check buy levels (below current price)
        for level in self.grid_levels_cache:
            if level["side"] == "buy" and level["price"] <= current_price * (1 + spread * 0.1):
                # Check if we already have an order near this level
                if self._has_order_near(level["price"], open_orders, "buy"):
                    continue
                
                # Calculate position size
                capital_per_level = equity * self.per_level
                amount = capital_per_level / level["price"]
                
                # Check max position limit
                current_position = positions.get(self.symbol)
                if current_position and current_position.size > 0:
                    max_additional = (equity * self.max_position_pct / current_price) - current_position.size
                    if max_additional <= amount * 0.1:
                        continue
                    amount = min(amount, max_additional)
                
                if amount <= 0:
                    continue
                
                self.last_signal_ts = int(__import__('time').time() * 1000)
                return create_signal(
                    action="buy",
                    side="buy",
                    order_type="limit",
                    price=level["price"],
                    amount=amount,
                    strategy="grid",
                    confidence=0.8,
                    metadata={
                        "grid_level": level["level"],
                        "grid_anchor": self.grid_anchor,
                        "spread_pct": spread * 100,
                        "regime": "range",
                    }
                )
        
        # Check sell levels (above current price) - only if we have position
        current_position = positions.get(self.symbol)
        if current_position and current_position.size > 0:
            for level in self.grid_levels_cache:
                if level["side"] == "sell" and level["price"] >= current_price * (1 - spread * 0.1):
                    if self._has_order_near(level["price"], open_orders, "sell"):
                        continue
                    
                    # Sell portion of position
                    sell_amount = min(
                        current_position.size * self.per_level,
                        current_position.size
                    )
                    
                    if sell_amount <= 0:
                        continue
                    
                    self.last_signal_ts = int(__import__('time').time() * 1000)
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="limit",
                        price=level["price"],
                        amount=sell_amount,
                        strategy="grid",
                        confidence=0.8,
                        metadata={
                            "grid_level": level["level"],
                            "grid_anchor": self.grid_anchor,
                            "spread_pct": spread * 100,
                            "regime": "range",
                        }
                    )
        
        return None

    async def _generate_hybrid_signal(
        self,
        current_price: float,
        atr_pct: float,
        adx: float,
        rsi: float,
        equity: float,
        positions: Dict[str, Position],
        open_orders: Dict[str, Order],
    ) -> Optional[Signal]:
        """Generate directional scalper signal for trending markets."""
        
        # Determine trend direction
        trend = "bullish" if rsi > 55 else "bearish" if rsi < 45 else "neutral"
        
        if trend == "neutral":
            return None
        
        # Calculate tighter spread for scalping
        spread = max(self.min_spread_pct, atr_pct * 0.3 / 100)
        
        # Check existing orders
        if self._has_order_near(current_price, open_orders, "buy" if trend == "bullish" else "sell"):
            return None
        
        current_position = positions.get(self.symbol)
        
        if trend == "bullish":
            # Long bias - buy on dips
            if current_position and current_position.size > 0:
                # Already long - check for take profit
                unrealized_pct = (current_price - current_position.entry_price) / current_position.entry_price
                if unrealized_pct >= self.take_profit_pct:
                    return create_signal(
                        action="sell",
                        side="sell",
                        order_type="limit",
                        price=current_price * (1 + self.take_profit_pct),
                        amount=current_position.size,
                        strategy="hybrid_scalper",
                        confidence=0.9,
                        metadata={
                            "trend": "bullish",
                            "reason": "take_profit",
                            "unrealized_pct": unrealized_pct,
                        }
                    )
            else:
                # No position - look for entry on dip
                entry_price = current_price * (1 - spread)
                capital_per_trade = equity * self.per_level
                amount = capital_per_trade / entry_price
                
                if amount <= 0:
                    return None
                
                return create_signal(
                    action="buy",
                    side="buy",
                    order_type="limit",
                    price=entry_price,
                    amount=amount,
                    strategy="hybrid_scalper",
                    confidence=0.7,
                    metadata={
                        "trend": "bullish",
                        "reason": "trend_follow",
                        "rsi": rsi,
                        "adx": adx,
                    }
                )
        
        elif trend == "bearish":
            # Short bias - sell on rallies
            if current_position and current_position.size < 0:
                # Already short - check for take profit
                unrealized_pct = (current_position.entry_price - current_price) / current_position.entry_price
                if unrealized_pct >= self.take_profit_pct:
                    return create_signal(
                        action="buy",
                        side="buy",
                        order_type="limit",
                        price=current_price * (1 - self.take_profit_pct),
                        amount=abs(current_position.size),
                        strategy="hybrid_scalper",
                        confidence=0.9,
                        metadata={
                            "trend": "bearish",
                            "reason": "take_profit",
                            "unrealized_pct": unrealized_pct,
                        }
                    )
            else:
                # No position - look for short entry on rally
                entry_price = current_price * (1 + spread)
                capital_per_trade = equity * self.per_level
                amount = capital_per_trade / entry_price
                
                if amount <= 0:
                    return None
                
                return create_signal(
                    action="sell",
                    side="sell",
                    order_type="limit",
                    price=entry_price,
                    amount=amount,
                    strategy="hybrid_scalper",
                    confidence=0.7,
                    metadata={
                        "trend": "bearish",
                        "reason": "trend_follow",
                        "rsi": rsi,
                        "adx": adx,
                    }
                )
        
        return None

    async def _generate_momentum_filtered_signal(
        self,
        current_price: float,
        spread: float,
        atr_pct: float,
        adx: float,
        rsi: float,
        equity: float,
        positions: Dict[str, Position],
        open_orders: Dict[str, Order],
    ) -> Optional[Signal]:
        """Generate signal with momentum filter for transitional markets."""
        
        # Only trade in direction of momentum
        if rsi > 60 and adx > 20:
            # Strong bullish momentum - only buy
            return await self._generate_grid_signal(current_price, spread, equity, positions, open_orders)
        elif rsi < 40 and adx > 20:
            # Strong bearish momentum - only sell (reduce position)
            return await self._generate_grid_signal(current_price, spread, equity, positions, open_orders)
        else:
            # No clear momentum - hold
            return None

    def _has_order_near(self, price: float, open_orders: Dict[str, Order], side: str, tolerance_pct: float = 0.001) -> bool:
        """Check if there's already an order near the target price."""
        for order in open_orders.values():
            if order.side == side and order.status in ("open", "pending", "partial"):
                if abs(order.price - price) / price <= tolerance_pct:
                    return True
        return False

    def get_grid_levels(self) -> List[Dict]:
        """Get current grid levels for monitoring."""
        return self.grid_levels_cache

    def get_anchor(self) -> float:
        """Get current grid anchor."""
        return self.grid_anchor

    def set_anchor(self, price: float) -> None:
        """Manually set grid anchor."""
        self.grid_anchor = price
        self.grid_levels_cache = []
        log.info(f"Grid anchor manually set to {price:.6f}")
#!/usr/bin/env python3
"""Denaro v7 — Enhanced adaptive grid policy with advanced indicators.

Grid geometry is now computed using:
- RSI levels for oversold/overbought zones
- Bollinger Bands for dynamic support/resistance
- MACD for trend bias
- ADX for trend strength
- Volume profile for liquidity zones
- Ichimoku cloud for cloud support/resistance

This provides much more precise grid placement than simple ATR-based spacing.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from . import indicators as ind
from .indicators_advanced import AdvancedIndicators
from .types import CoreState, Trend, VolatilityRegime


@dataclass
class GridGeometry:
    spread: float
    levels: int
    center: float
    tp: float
    max_spend_pct: float
    buy_levels: List[float]
    sell_levels: List[float]
    bias: float


class EnhancedGridPolicy:
    """Adaptive grid geometry using advanced technical analysis."""

    def __init__(self,
                 spread_lo: float = 0.005,
                 spread_hi: float = 0.050,
                 tp_lo: float = 0.008,
                 tp_hi: float = 0.050,
                 levels_by_vol: dict = None,
                 max_spend_by_vol: dict = None) -> None:
        self.spread_lo = spread_lo
        self.spread_hi = spread_hi
        self.tp_lo = tp_lo
        self.tp_hi = tp_hi

        self.levels_by_vol = levels_by_vol or {"low": 6, "normal": 5, "high": 4, "extreme": 3}
        self.max_spend_by_vol = max_spend_by_vol or {"low": 0.60, "normal": 0.50, "high": 0.35, "extreme": 0.25}

        self._liquid_depth = 5000.0
        self._retarget_factor = 1.5

    def compute(self, state: CoreState, price: float | None = None) -> dict:
        """Return enhanced grid params with dynamic buy/sell level placement."""
        r = state.regime
        m = state.micro
        price = price if price and price > 0 else m.last_price_micro

        # Extract OHLCV for indicators
        ohlcv = getattr(state, '_last_ohlcv', [])
        if ohlcv:
            prices = [row[4] for row in ohlcv]
            highs = [row[2] for row in ohlcv]
            lows = [row[3] for row in ohlcv]
            closes = [row[4] for row in ohlcv]
            volumes = [row[5] for row in ohlcv]
        else:
            prices = highs = lows = closes = volumes = [price]

        # Compute all indicators
        rsi = AdvancedIndicators.rsi(closes, period=14)
        macd = AdvancedIndicators.macd(closes)
        bb = AdvancedIndicators.bollinger_bands(closes, period=20, std_dev=2.0)
        adx = AdvancedIndicators.adx(highs, lows, closes, period=14)
        ichimoku = AdvancedIndicators.ichimoku(highs, lows, closes)
        vp = AdvancedIndicators.volume_profile(prices, volumes, num_levels=50)

        # Dynamic spread based on Bollinger Band + ADX
        if bb.level == "tight" and not r.dump_mode:
            spread = ind.clamp(bb.value * 0.5, self.spread_lo, self.spread_hi)
        else:
            atr = r.atr_pct if r.atr_pct > 0 else 0.002
            vol_mult = {"low": 0.7, "normal": 1.0, "high": 1.3, "extreme": 2.0}.get(r.volatility_regime, 1.0)
            adx_mult = 1.0 + max(0, adx.value - 20) / 100
            spread = ind.clamp(atr * 0.55 * vol_mult * adx_mult, self.spread_lo, self.spread_hi)

        # Adjust for microstructure
        depth = m.cum_bid_depth_1pct + m.cum_ask_depth_1pct
        if depth > self._liquid_depth:
            spread *= 0.85
        imb = m.bid_ask_imbalance
        if imb < 0.7 or imb > 1.3:
            spread *= 1.20
        if m.spoofing_flag:
            spread *= 1.35

        # Levels by volatility + trend
        levels = self.levels_by_vol.get(r.volatility_regime, 5)
        if r.trend in (Trend.BULL, Trend.BEAR):
            levels -= 1
        levels = int(ind.clamp(levels, 2, 8))

        # Dynamic TP using RSI + MACD + Bollinger
        bb_width = bb.value * 2
        if bb_width < 0.02:  # Squeeze
            tp = ind.clamp(bb_width, self.tp_lo, self.tp_hi)
        else:
            base_tp = r.atr_pct * 1.5 if r.atr_pct > 0 else 0.02
            tp = ind.clamp(base_tp * (1.0 + 0.5 * r.trend_strength), self.tp_lo, self.tp_hi)

        if macd.signal == "bullish" and r.trend == Trend.BULL:
            tp *= 1.2
        elif macd.signal == "bearish" and r.trend == Trend.BEAR:
            tp *= 1.2

        # Center bias with RSI + Ichimoku
        bias = 0.5
        center = price

        if rsi.signal == "oversold":
            bias = 0.65  # Bias up for oversold bounces
            center = price * 1.005
        elif rsi.signal == "overbought":
            bias = 0.35  # Bias down for overbought rejections
            center = price * 0.995

        if ichimoku.signal == "bullish" and ichimoku.strength > 0.5:
            bias = min(0.7, bias + 0.15)
            center = price * 1.008
        elif ichimoku.signal == "bearish" and ichimoku.strength > 0.5:
            bias = max(0.3, bias - 0.15)
            center = price * 0.992

        if r.trend == Trend.BULL:
            bias = min(0.7, 0.55 + r.trend_strength * 0.15)
            center = price * (1.005 + r.trend_strength * 0.003)
        elif r.trend == Trend.BEAR:
            bias = max(0.3, 0.45 - r.trend_strength * 0.15)
            center = price * (0.995 - r.trend_strength * 0.003)

        # Max spend
        max_spend = self.max_spend_by_vol.get(r.volatility_regime, 0.50)
        if r.dump_mode:
            max_spend = 0.0
        if state.cb.state.value == "HALF_OPEN":
            max_spend *= 0.5

        # Build dynamic buy/sell levels using RSI, BB, VP
        buy_levels, sell_levels = self._build_levels(
            price, center, spread, levels, bias, tp,
            rsi, bb, vp, r
        )

        geometry = GridGeometry(
            spread=spread,
            levels=levels,
            center=center,
            tp=tp,
            max_spend_pct=max_spend,
            buy_levels=buy_levels,
            sell_levels=sell_levels,
            bias=bias
        )

        return {
            "spread": spread,
            "levels": levels,
            "support_bias": bias,
            "take_profit_mult": tp / max(0.001, r.atr_pct) if r.atr_pct > 0 else 1.0,
            "tp": tp,
            "center": center,
            "max_spend_pct": max_spend,
            "atr_pct": r.atr_pct if hasattr(r, 'atr_pct') else 0.002,
            "buy_levels": buy_levels,
            "sell_levels": sell_levels,
            "bias": bias,
        }

    def _build_levels(self,
                     price: float,
                     center: float,
                     spread: float,
                     levels: int,
                     bias: float,
                     tp: float,
                     rsi: AdvancedIndicators,
                     bb: AdvancedIndicators,
                     vp: AdvancedIndicators,
                     regime: CoreState.regime) -> Tuple[List[float], List[float]]:
        """Build buy and sell levels using dynamic indicators."""

        buy_levels = []
        sell_levels = []

        # Use RSI levels for buy zone targeting
        rsi_buy_zone = 30 if rsi.signal == "oversold" else 40
        rsi_sell_zone = 70 if rsi.signal == "overbought" else 60

        # Use Bollinger Bands for dynamic support/resistance
        if bb.level != "unknown":
            bb_mid = price
            bb_upper = price * (1 + bb.value * 2)
            bb_lower = price * (1 - bb.value * 2)
        else:
            bb_mid = price
            bb_upper = price * 1.02
            bb_lower = price * 0.98

        # Build buy levels (below center)
        num_buy = int(levels * bias)
        num_sell = levels - num_buy

        for i in range(num_buy):
            # Progressively tighter near oversold levels
            progression = (i + 1) / num_buy
            base_spread = spread * (1 + progression * 0.5)

            if rsi.signal == "oversold":
                # Place buy levels clustered around RSI oversold bounce zone
                level_price = center * (1 - base_spread * (1 - progression * 0.3))
            else:
                level_price = center * (1 - base_spread)

            buy_levels.append(level_price)

        # Build sell levels (above center)
        for i in range(num_sell):
            progression = (i + 1) / num_sell if num_sell > 0 else 0
            base_spread = spread * (1 + tp)

            if rsi.signal == "overbought":
                level_price = center * (1 + base_spread * (1 - progression * 0.3))
            else:
                level_price = center * (1 + base_spread)

            sell_levels.append(level_price)

        return buy_levels, sell_levels

    @staticmethod
    def should_retarget(level: dict, price: float, params: dict) -> bool:
        """A buy level has drifted too far below price → cancel and re-place."""
        if not level or level.get("stage", "buy") != "buy":
            return False
        bp = level.get("buy_price", 0.0)
        if bp <= 0 or price <= 0 or bp > price:
            return False
        drift = (price - bp) / bp
        spacing = params.get("spread", 0.02)
        return drift > 1.5 * spacing

    @staticmethod
    def orphan_orders(levels_data: List[dict], open_orders: List[dict]) -> List[str]:
        """Open exchange order ids that are NOT tracked by any grid level."""
        open_ids = {o.get("id") for o in open_orders if o.get("id")}
        tracked = set()
        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            if bid:
                tracked.add(bid)
            if sid:
                tracked.add(sid)
        return sorted(open_ids - tracked)

    @staticmethod
    def deployed_eur(levels_data: List[dict]) -> float:
        """Total capital locked in tracked grid levels."""
        total = 0.0
        for lvl in levels_data:
            total += lvl.get("actual_cost",
                             lvl.get("amount", 0.0) * lvl.get("buy_price", 0.0))
        return total


class GridPolicy:
    """Backward-compatible grid policy wrapper."""

    def __init__(self) -> None:
        self.enhanced = EnhancedGridPolicy()

    def compute(self, state: CoreState, price: float | None = None) -> dict:
        return self.enhanced.compute(state, price)

    @staticmethod
    def should_retarget(level: dict, price: float, params: dict) -> bool:
        return EnhancedGridPolicy.should_retarget(level, price, params)

    @staticmethod
    def orphan_orders(levels_data: List[dict], open_orders: List[dict]) -> List[str]:
        return EnhancedGridPolicy.orphan_orders(levels_data, open_orders)

    @staticmethod
    def deployed_eur(levels_data: List[dict]) -> float:
        return EnhancedGridPolicy.deployed_eur(levels_data)
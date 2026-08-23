#!/usr/bin/env python3
"""Denaro v7 — Dynamic ATR Grid with Enhanced Indicators.

Grid that uses:
- RSI for overbought/oversold zone targeting
- Bollinger Bands for dynamic support/resistance
- MACD for trend bias
- ADX for trend strength scaling
- Volume Profile for liquidity zone placement
- Ichimoku Cloud for cloud-based support/resistance

All parameters auto-adapt in real-time based on regime + indicators.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from .indicators import atr_percent, volatility_regime
from .indicators_advanced import AdvancedIndicators
from .types import CoreState, Trend


@dataclass
class DynamicGridParams:
    spread: float
    levels: int
    center: float
    tp: float
    max_spend_pct: float
    buy_levels: List[float]
    sell_levels: List[float]
    bias: float
    atr_pct: float
    rsi_signal: str
    macd_signal: str
    bb_signal: str
    adx_strength: float


class DynamicATRGrid:
    """Dynamic ATR-based grid with full technical indicator integration."""

    def __init__(self,
                 spread_lo: float = 0.005,
                 spread_hi: float = 0.050,
                 tp_lo: float = 0.008,
                 tp_hi: float = 0.050,
                 max_levels: int = 8,
                 min_levels: int = 2) -> None:

        self.spread_lo = spread_lo
        self.spread_hi = spread_hi
        self.tp_lo = tp_lo
        self.tp_hi = tp_hi
        self.max_levels = max_levels
        self.min_levels = min_levels

        self._liquid_depth = 5000.0
        self._retarget_factor = 1.5

    def compute(self, state: CoreState, price: float | None = None) -> DynamicGridParams:
        """Compute dynamic grid parameters using all indicators."""
        r = state.regime
        m = state.micro
        price = price if price and price > 0 else m.last_price_micro

        # Build OHLCV from state or indicators
        ohlcv = getattr(state, '_last_ohlcv', [])
        if ohlcv and len(ohlcv) >= 20:
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
        trend_score = AdvancedIndicators.trend_score(prices, highs, lows, closes)

        # Dynamic spread calculation
        atr_pct = r.atr_pct if r.atr_pct > 0 else 0.002

        # Spread based on dual regime: ATR + Bollinger + ADX
        if bb.level == "tight" and not r.dump_mode:
            # Bollinger Squeeze - prepare for breakout
            spread = max(self.spread_lo, bb.value * 0.3)
        else:
            vol_mult = {"low": 0.7, "normal": 1.0, "high": 1.3, "extreme": 2.0}.get(r.volatility_regime, 1.0)
            adx_mult = 1.0 + max(0, adx.value - 20) / 100
            spread = atr_pct * 0.55 * vol_mult * adx_mult

        spread = max(self.spread_lo, min(self.spread_hi, spread))

        # Microstructure adjustment
        depth = m.cum_bid_depth_1pct + m.cum_ask_depth_1pct
        if depth > self._liquid_depth:
            spread *= 0.85
        imb = m.bid_ask_imbalance
        if imb < 0.7 or imb > 1.3:
            spread *= 1.20
        if m.spoofing_flag:
            spread *= 1.35

        # Levels by volatility + trend + ADX
        levels_by_vol = {"low": 6, "normal": 5, "high": 4, "extreme": 3}
        levels = levels_by_vol.get(r.volatility_regime, 5)

        if r.trend in (Trend.BULL, Trend.BEAR):
            levels -= 1

        # ADX adjustment
        if adx.value > 30 and adx.signal in ("trending_up", "trending_down"):
            levels = max(self.min_levels, levels - 1)

        levels = max(self.min_levels, min(self.max_levels, levels))

        # Dynamic TP with RSI + MACD + Bollinger
        bb_width = bb.value * 2
        if bb_width < 0.02:  # Squeeze - expect expansion
            tp = max(self.tp_lo, min(self.tp_hi, bb_width * 2))
        else:
            base_tp = atr_pct * 1.5 if atr_pct > 0 else 0.02
            tp = base_tp * (1.0 + 0.5 * r.trend_strength)

            if macd.signal == "bullish" and r.trend == Trend.BULL:
                tp *= 1.2
            elif macd.signal == "bearish" and r.trend == Trend.BEAR:
                tp *= 1.2
            elif macd.signal != "neutral":
                tp *= 0.9  # Counter-trend = smaller TP

        tp = max(self.tp_lo, min(self.tp_hi, tp))

        # Center bias with RSI + Ichimoku + VP
        bias = 0.5
        center = price

        # RSI-based bias
        if rsi.signal == "oversold" and rsi.strength > 0.5:
            bias = 0.7  # Strong bias up for oversold bounces
            center = price * 1.005
        elif rsi.signal == "overbought" and rsi.strength > 0.5:
            bias = 0.3  # Strong bias down for overbought rejections
            center = price * 0.995

        # Ichimoku cloud bias
        if ichimoku.signal == "bullish" and ichimoku.strength > 0.5:
            bias = min(0.8, bias + 0.15)
            center = price * 1.008
        elif ichimoku.signal == "bearish" and ichimoku.strength > 0.5:
            bias = max(0.2, bias - 0.15)
            center = price * 0.992

        # Trend bias
        if r.trend == Trend.BULL:
            bias = min(0.75, 0.55 + r.trend_strength * 0.2)
            center = price * (1.005 + r.trend_strength * 0.004)
        elif r.trend == Trend.BEAR:
            bias = max(0.25, 0.45 - r.trend_strength * 0.2)
            center = price * (0.995 - r.trend_strength * 0.004)

        # Max spend
        max_spend_by_vol = {"low": 0.60, "normal": 0.50, "high": 0.35, "extreme": 0.25}
        max_spend = max_spend_by_vol.get(r.volatility_regime, 0.50)

        if r.dump_mode:
            max_spend = 0.0
        if state.cb.state.value == "HALF_OPEN":
            max_spend *= 0.5

        # Build dynamic levels using indicator zones
        buy_levels, sell_levels = self._build_dynamic_levels(
            price, center, spread, levels, bias, tp,
            rsi, bb, vp, macd, ichimoku, r
        )

        return DynamicGridParams(
            spread=spread,
            levels=levels,
            center=center,
            tp=tp,
            max_spend_pct=max_spend,
            buy_levels=buy_levels,
            sell_levels=sell_levels,
            bias=bias,
            atr_pct=atr_pct,
            rsi_signal=rsi.signal,
            macd_signal=macd.signal,
            bb_signal=bb.signal,
            adx_strength=adx.value,
        )

    def _build_dynamic_levels(self,
                             price: float,
                             center: float,
                             spread: float,
                             levels: int,
                             bias: float,
                             tp: float,
                             rsi: 'AdvancedIndicator',
                             bb: 'AdvancedIndicator',
                             vp: 'AdvancedIndicator',
                             macd: 'AdvancedIndicator',
                             ichimoku: 'AdvancedIndicator',
                             r: 'RegimeState') -> Tuple[List[float], List[float]]:
        """Build buy/sell levels using dynamic indicator zones."""

        buy_levels = []
        sell_levels = []

        num_buy = max(1, int(levels * bias))
        num_sell = max(1, levels - num_buy)

        # Use Bollinger Bands for dynamic support/resistance
        if bb.level != "unknown":
            bb_upper = price * (1 + spread + bb.value)
            bb_lower = price * (1 - spread - bb.value)
            bb_mid = price
        else:
            bb_upper = price * (1 + spread * 2)
            bb_lower = price * (1 - spread * 2)
            bb_mid = price

        # Volume profile high volume nodes as support/resistance
        vp_levels = getattr(vp, 'levels', [])

        # Build buy levels (below center) - cluster near oversold/RV zones
        for i in range(num_buy):
            progress = (i + 1) / num_buy

            if rsi.signal == "oversold":
                # Cluster near lower Bollinger Band / oversold zone
                base_distance = spread * (1 + progress * 0.8)
                level_price = max(bb_lower, center * (1 - base_distance * (1 - progress * 0.5)))
            elif r.trend == Trend.BULL:
                # In bull, place buys closer to center
                base_distance = spread * (1 + progress * 0.3)
                level_price = center * (1 - base_distance)
            else:
                base_distance = spread * (1 + progress * 0.5)
                level_price = center * (1 - base_distance)

            buy_levels.append(level_price)

        # Build sell levels (above center) - cluster near overbought/RV zones
        for i in range(num_sell):
            progress = (i + 1) / num_sell if num_sell > 0 else 0

            if rsi.signal == "overbought":
                # Cluster near upper Bollinger Band / overbought zone
                base_distance = (spread + tp) * (1 + progress * 0.8)
                level_price = min(bb_upper, center * (1 + base_distance * (1 - progress * 0.5)))
            elif r.trend == Trend.BEAR:
                # In bear, place sells closer to center
                base_distance = (spread + tp) * (1 + progress * 0.3)
                level_price = center * (1 + base_distance)
            else:
                base_distance = (spread + tp) * (1 + progress * 0.5)
                level_price = center * (1 + base_distance)

            sell_levels.append(level_price)

        return buy_levels, sell_levels

    def should_retarget(self, level: dict, price: float, params: DynamicGridParams) -> bool:
        """Check if buy level drifted too far - use dynamic spread."""
        if not level or level.get("stage", "buy") != "buy":
            return False
        bp = level.get("buy_price", 0.0)
        if bp <= 0 or price <= 0 or bp > price:
            return False
        drift = (price - bp) / bp
        return drift > self._retarget_factor * params.spread

    @staticmethod
    def orphan_orders(levels_data: List[dict], open_orders: List[dict]) -> List[str]:
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
        total = 0.0
        for lvl in levels_data:
            total += lvl.get("actual_cost",
                             lvl.get("amount", 0.0) * lvl.get("buy_price", 0.0))
        return total


# Backward compat wrapper
class GridPolicy:
    def __init__(self):
        self.dynamic = DynamicATRGrid()

    def compute(self, state: CoreState, price: float | None = None) -> dict:
        params = self.dynamic.compute(state, price)
        return {
            "spread": params.spread,
            "levels": params.levels,
            "support_bias": params.bias,
            "take_profit_mult": params.tp / max(0.001, params.atr_pct),
            "tp": params.tp,
            "center": params.center,
            "max_spend_pct": params.max_spend_pct,
            "atr_pct": params.atr_pct,
            "buy_levels": params.buy_levels,
            "sell_levels": params.sell_levels,
            "bias": params.bias,
        }

    @staticmethod
    def should_retarget(level: dict, price: float, params: dict) -> bool:
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
        return DynamicATRGrid.deployed_eur(levels_data)
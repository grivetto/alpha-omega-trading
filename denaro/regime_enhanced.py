#!/usr/bin/env python3
"""Denaro v7 — Enhanced regime detector with advanced indicators.

Integra RSI, MACD, Bollinger, Stochastic, ADX, Ichimoku, Volume Profile.
Regime detection ora usa multi-signal fusion + machine-learning-like scoring.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from . import indicators as ind
from .indicators_advanced import AdvancedIndicators
from .types import CoreState, RegimeState, Trend


@dataclass
class SignalFusion:
    rsi_signal: str
    macd_signal: str
    bb_signal: str
    trend_score: float
    volume_profile: str
    combined_signal: str
    confidence: float


class EnhancedRegimeDetector:
    """Multi-indicator regime detection with adaptive thresholds."""

    def __init__(self,
                 dump_threshold_mult: float = 2.5,
                 dump_volume_ratio: float = 1.8,
                 dump_recovery_cycles: int = 3,
                 volatility_lookback: int = 50) -> None:
        self.dump_threshold_mult = dump_threshold_mult
        self.dump_volume_ratio = dump_volume_ratio
        self.dump_recovery_cycles = dump_recovery_cycles
        self.volatility_lookback = volatility_lookback

        self._dump_mode_timer: int = 0

    def update(self, regime: RegimeState, micro: dict, ohlcv: List[List[float]]) -> None:
        """Detect regime using RSI, MACD, Bollinger, ADX, Ichimoku, Volume Profile."""
        prices = [row[4] for row in ohlcv]
        highs = [row[2] for row in ohlcv]
        lows = [row[3] for row in ohlcv]
        closes = [row[4] for row in ohlcv]
        volumes = [row[5] for row in ohlcv]

        if len(prices) < 30:
            return

        current = prices[-1]
        prev = prices[-2] if len(prices) > 1 else current

        rsi = AdvancedIndicators.rsi(prices, period=14)
        macd = AdvancedIndicators.macd(prices)
        bb = AdvancedIndicators.bollinger_bands(prices, period=20, std_dev=2.0)
        adx = AdvancedIndicators.adx(highs, lows, closes, period=14)
        ichimoku = AdvancedIndicators.ichimoku(highs, lows, closes)
        vp = AdvancedIndicators.volume_profile(prices, volumes, num_levels=20)
        trend_score = AdvancedIndicators.trend_score(prices, highs, lows, closes)

        self._analyze_signals(regime, rsi, macd, bb, adx, ichimoku, vp, trend_score)

        self._detect_trend(regime, rsi, macd, trend_score)
        self._detect_volatility(regime, rsi, bb, adx)
        self._detect_volume_regime(regime, volumes)
        self._detect_momentum(regime, closes, volumes)

        self._detect_dump_mode(regime, current, prev, volumes, closes, trend_score)

        regime.last_regime_update = len(prices)

    def _analyze_signals(self,
                        regime: RegimeState,
                        rsi: AdvancedIndicators,
                        macd: AdvancedIndicators,
                        bb: AdvancedIndicators,
                        adx: AdvancedIndicators,
                        ichimoku: AdvancedIndicators,
                        vp: AdvancedIndicators,
                        trend_score: AdvancedIndicators) -> None:
        """Fusion of all signals into a single regime classification."""
        rsi_str = rsi.signal
        macd_str = macd.signal
        bb_str = bb.signal
        vp_str = vp.signal

        signal_weights = {
            "bullish": 1.0,
            "bearish": -1.0,
            "oversold": 0.5,
            "overbought": -0.5,
            "squeeze": 0.0,
            "neutral": 0.0,
            "trending_up": 1.0,
            "trending_down": -1.0,
            "bullish_depth": 1.0,
            "bearish_depth": -1.0,
            "neutral": 0.0
        }

        total_signal = 0.0
        signal_strength = 0.0
        dominant_signal = "neutral"
        signal_count = 0

        signals = [rsi_str, macd_str, bb_str, adx.signal, vp.signal]

        for sig in signals:
            if sig in signal_weights:
                total_signal += signal_weights[sig]
                signal_count += 1

                if abs(signal_weights[sig]) > abs(signal_weights.get(dominant_signal, 0)):
                    dominant_signal = sig

        if signal_count > 0:
            total_signal /= signal_count

        regime.combined_signal = dominant_signal
        regime.signal_confidence = min(1.0, abs(total_signal) + 0.2)

        regime.rsi_signal = rsi_str
        regime.macd_signal = macd_str
        regime.bb_signal = bb_str
        regime.volume_profile = vp_str

    def _detect_trend(self, regime: RegimeState, rsi: AdvancedIndicators,
                     macd: AdvancedIndicators, trend_score: AdvancedIndicators) -> None:
        """Determine trend direction using RSI, MACD and trend score."""
        trend_strength = 0.0
        trend = Trend.RANGING

        if trend_score.signal == "bullish" and trend_score.strength > 0.5:
            if trend_score.value > 0.5:
                trend = Trend.BULL
                trend_strength = trend_score.strength
            else:
                trend = Trend.BULL
                trend_strength = trend_score.strength * 0.7
        elif trend_score.signal == "bearish" and trend_score.strength > 0.5:
            if trend_score.value < -0.5:
                trend = Trend.BEAR
                trend_strength = trend_score.strength
            else:
                trend = Trend.BEAR
                trend_strength = trend_score.strength * 0.7

        regime.trend = trend
        regime.trend_strength = max(0.0, min(1.0, trend_strength + 0.1))

    def _detect_volatility(self, regime: RegimeState, rsi: AdvancedIndicators,
                          bb: AdvancedIndicators, adx: AdvancedIndicators) -> None:
        """Detect volatility regime using Bollinger Bands and ADX."""
        bb_width = (bb.value * 2 - 1) if bb.level != "unknown" else 0.5
        adx_val = adx.value

        if bb_width < 0.01:
            regime.volatility_regime = "low"
        elif bb_width > 0.05:
            regime.volatility_regime = "high"
        elif adx_val >= 40:
            regime.volatility_regime = "extreme"
        elif adx_val >= 25:
            regime.volatility_regime = "high"
        else:
            regime.volatility_regime = "normal"

        regime.atr_pct = bb.value * 100 if bb.level != "unknown" else 1.0

    def _detect_volume_regime(self, regime: RegimeState, volumes: List[float]) -> None:
        """Detect low/normal/high/spike volume regimes."""
        if not volumes:
            return

        avg_vol = sum(volumes[-20:]) / len(volumes[-20:])
        current_vol = volumes[-1]

        if current_vol > avg_vol * 3.0:
            regime.volume_regime = "spike"
        elif current_vol > avg_vol * 1.5:
            regime.volume_regime = "high"
        elif current_vol > avg_vol * 0.5:
            regime.volume_regime = "normal"
        else:
            regime.volume_regime = "low"

        regime.volume_ratio = current_vol / avg_vol if avg_vol > 0 else 1.0

    def _detect_momentum(self, regime: RegimeState, closes: List[float],
                         volumes: List[float]) -> None:
        """Calculate 24h momentum with volume confirmation."""
        if len(closes) < 24:
            return

        current_24h = closes[-1]
        prev_24h = closes[-24] if len(closes) >= 24 else closes[0]

        momentum = (current_24h - prev_24h) / prev_24h if prev_24h > 0 else 0.0

        regime.momentum_24h = momentum

        if regime.volume_regime == "high" and abs(momentum) > 0.02:
            regime.momentum_confidence = min(1.0, abs(momentum) * 10)
        else:
            regime.momentum_confidence = min(1.0, abs(momentum) * 5)

    def _detect_dump_mode(self, regime: RegimeState, current: float, prev: float,
                         volumes: List[float], closes: List[float],
                         trend_score: AdvancedIndicators) -> None:
        """Detect market dump with volume confirmation and trend reversal."""
        if self._dump_mode_timer > 0:
            self._dump_mode_timer -= 1
            regime.dump_mode = True
            return

        price_drop = (prev - current) / prev if prev > 0 else 0.0
        volume_spike = regime.volume_ratio >= self.dump_volume_ratio

        if price_drop > 0.03 and volume_spike:
            regime.dump_mode = True
            regime.dump_reason = f"price_drop_{price_drop * 100:.1f}%_volume_spike"
            self._dump_mode_timer = self.dump_recovery_cycles
            return

        if price_drop > self.dump_threshold_mult * max(0.01, regime.atr_pct):
            regime.dump_mode = True
            regime.dump_reason = f"price_drop_{price_drop * 100:.1f}%"

            if trend_score.signal == "bearish" and trend_score.strength > 0.6:
                regime.dump_reason += "_trend_reversal"
            return

        regime.dump_mode = False
        regime.dump_reason = "none"

    def should_retarget_grid(self, regime: RegimeState, price: float,
                            current_grid_levels: int, total_deployed: float,
                            target_levels: int) -> bool:
        """Decide if grid needs retargeting based on price drift."""
        if not regime.dump_mode and regime.trend != Trend.RANGING:
            return False

        if current_grid_levels >= target_levels:
            return False

        if total_deployed / (price * current_grid_levels + 1e-10) > 0.9:
            return True

        return False


class RegimeDetector:
    """Backward-compatible regime detector wrapper for v6 compatibility."""

    def __init__(self,
                 dump_threshold_mult: float = 2.5,
                 dump_volume_ratio: float = 1.8,
                 dump_recovery_cycles: int = 3) -> None:
        self.enhanced = EnhancedRegimeDetector(
            dump_threshold_mult=dump_threshold_mult,
            dump_volume_ratio=dump_volume_ratio,
            dump_recovery_cycles=dump_recovery_cycles
        )

    def update(self, regime: RegimeState, micro: dict, ohlcv: List[List[float]]) -> None:
        """Update regime using enhanced detection."""
        self.enhanced.update(regime, micro, ohlcv)

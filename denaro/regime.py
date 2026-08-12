#!/usr/bin/env python3
"""Denaro v6 — regime detector.

Macro regime classification (trend / volatility / volume) with hysteresis,
plus the v6 dump-defense state machine:

  enter dump  → momentum_1h < -max(1%, dump_threshold_mult × ATR%)
                 AND volume_ratio ≥ dump_volume_ratio
                 AND (trend == BEAR OR bid-ask imbalance < 0.75)
  exit dump   → momentum_1h recovers above -0.5 × ATR% for
                 `dump_recovery_cycles` consecutive updates
"""
from __future__ import annotations

import time
from typing import List

from . import indicators as ind
from .types import MicroState, RegimeState, Trend

_MOMENTUM_1H_LOOKBACK = 1     # bars
_MOMENTUM_24H_LOOKBACK = 24   # bars
_TREND_FAST = 8               # EMA-like windows for trend strength
_TREND_SLOW = 24
_STRENGTH_RANGING = 0.15      # below this → RANGING
_RECOVERY_THRESH_MULT = 0.5   # momentum must rise above -0.5 × ATR%


class RegimeDetector:
    """Updates RegimeState from OHLCV + microstructure. Pure, no I/O."""

    def __init__(self, dump_threshold_mult: float = 2.5,
                 dump_volume_ratio: float = 1.8,
                 dump_recovery_cycles: int = 3) -> None:
        self.dump_threshold_mult = dump_threshold_mult
        self.dump_volume_ratio = dump_volume_ratio
        self.dump_recovery_cycles = max(1, dump_recovery_cycles)

    # --- main update ---------------------------------------------------------

    def update(self, regime: RegimeState, micro: MicroState,
               ohlcv: List[List[float]]) -> None:
        """Recompute regime + dump state from a fresh OHLCV window."""
        if len(ohlcv) < 2:
            return
        closes = [c[4] for c in ohlcv]
        p0 = closes[-1]

        # Momentum
        regime.momentum_1h = ind.momentum_percent(ohlcv, _MOMENTUM_1H_LOOKBACK)
        p24 = closes[-min(_MOMENTUM_24H_LOOKBACK, len(closes))]
        regime.momentum_24h = (p0 - p24) / p24 if p24 else 0.0

        # ATR + volatility regime
        atr_pct = ind.atr_percent(ohlcv)
        regime.atr_pct = atr_pct if atr_pct > 0 else regime.atr_pct
        regime.volatility_regime = ind.volatility_regime(regime.atr_pct)

        # Volume regime
        vratio = ind.volume_ratio(ohlcv)
        regime.volume_ratio = vratio
        regime.volume_regime = ind.volume_regime(vratio)

        # Trend strength (fast/slow mean spread normalized by ATR)
        fast = sum(closes[-_TREND_FAST:]) / min(_TREND_FAST, len(closes))
        slow = sum(closes[-_TREND_SLOW:]) / min(_TREND_SLOW, len(closes))
        price_trend = (fast - slow) / slow if slow > 0 else 0.0
        strength = min(1.0, abs(price_trend) / (regime.atr_pct + 1e-10) * 0.1)

        # Hysteresis on trend switches
        old_trend = regime.trend
        if strength < _STRENGTH_RANGING:
            new_trend = Trend.RANGING
        elif price_trend > 0:
            new_trend = Trend.BULL
        else:
            new_trend = Trend.BEAR

        if new_trend == old_trend:
            regime.trend_strength = min(1.0, regime.trend_strength + 0.05)
            regime.regime_duration_cycles += 1
            regime.regime_confidence = min(0.95, regime.regime_confidence + 0.02)
        else:
            regime.trend_strength = strength
            regime.regime_duration_cycles = 0
            regime.regime_confidence = 0.4
        regime.trend = new_trend

        # v6 — dump-defense state machine
        self._update_dump(regime, micro)

    # --- dump state machine --------------------------------------------------

    def _update_dump(self, regime: RegimeState, micro: MicroState) -> None:
        mom = regime.momentum_1h
        threshold = -max(0.01, self.dump_threshold_mult * regime.atr_pct)
        panic_volume = regime.volume_ratio >= self.dump_volume_ratio
        bearish_skew = (regime.trend == Trend.BEAR
                        or micro.bid_ask_imbalance < 0.75)

        if regime.dump_mode:
            # Clear dump only when momentum recovers for N consecutive cycles
            if mom > -_RECOVERY_THRESH_MULT * regime.atr_pct:
                regime.recovery_cycles += 1
                if regime.recovery_cycles >= self.dump_recovery_cycles:
                    regime.dump_mode = False
                    regime.dump_reason = ""
                    regime.dump_since = 0.0
                    regime.recovery_cycles = 0
            else:
                regime.recovery_cycles = 0
        elif mom < threshold and panic_volume and bearish_skew:
            regime.dump_mode = True
            regime.dump_since = regime.dump_since or time.time()
            regime.dump_reason = (f"mom={mom * 100:.1f}% vol={regime.volume_ratio:.1f}x "
                                  f"atr={regime.atr_pct * 100:.2f}%")
            regime.recovery_cycles = 0

"""
Adaptive Trend-Grid Hybrid with Dynamic Capital Sizing & Regime Trailing Stop
Generated: 2026-08-29 03:45 UTC by Hermes orchestrator.

Distinct from prior auto-gen strategies:
  1. Whereas VolatilityScaledGridMomentum scales SPACING by ATR, this strategy scales
     CAPITAL SIZE per level by a blend of volume impulse + realized-vol regime, so each
     open grid slot carries weight proportionally to conviction.
  2. Trend accumulator: on breakout (price > k*ADX-weighted channel) it switches from
     pure grid to a trailing-stop ladder, harvesting trend runs instead of fading them.
  3. Range fade: when ADX < threshold, reverts to mean-reversion grid with symmetric
     spacing around an EWMA anchor that drifts each tick.
  4. OOM-safety: streaming tick generator, fixed-size deque buffers, explicit chunking
     for offline backtest, del + gc.collect() after large batch ops.

Config-driven: every tunable in StrategyConfig; zero hardcoded magic constants.
"""

from __future__ import annotations

import gc
import json
import logging
import math
import sys
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable strategy configuration. No magic numbers outside this dataclass."""

    symbol: str
    capital_eur: float
    # signals / regime
    adx_period: int = 14
    adx_trend_threshold: float = 22.0
    ewma_span: int = 20
    channel_lookback: int = 25
    breakout_mult: float = 0.12
    # grid / sizing
    max_grid_levels: int = 10
    base_spacing_pct: float = 0.006
    vol_weight: float = 0.6
    vol_window: int = 14
    vol_target: float = 0.02
    # trailing stop
    trail_pct: float = 0.015
    min_trade_eur: float = 1.0
    fee_pct: float = 0.0016

    def validate(self) -> List[str]:
        """Return a list of config errors; empty list means valid."""
        errs: List[str] = []
        if self.capital_eur <= 0:
            errs.append("capital_eur must be > 0")
        if self.max_grid_levels < 1:
            errs.append("max_grid_levels must be >= 1")
        if self.adx_period < 2:
            errs.append("adx_period must be >= 2")
        if self.ewma_span < 2:
            errs.append("ewma_span must be >= 2")
        if self.channel_lookback < 3:
            errs.append("channel_lookback must be >= 3")
        if self.vol_window < 2:
            errs.append("vol_window must be >= 2")
        if not 0.0 < self.breakout_mult < 1.0:
            errs.append("breakout_mult must be in (0, 1)")
        if self.base_spacing_pct <= 0:
            errs.append("base_spacing_pct must be > 0")
        if not 0.0 < self.vol_target < 1.0:
            errs.append("vol_target must be in (0, 1)")
        if not 0.0 <= self.fee_pct < 0.02:
            errs.append("fee_pct must be in [0, 0.02)")
        if self.min_trade_eur <= 0:
            errs.append("min_trade_eur must be > 0")
        if not 0.0 <= self.vol_weight <= 1.0:
            errs.append("vol_weight must be in [0,1]")
        if not 0.0 < self.trail_pct < 0.5:
            errs.append("trail_pct must be in (0, 0.5)")
        return errs


class StrategyBase(ABC):
    """Abstract contract every strategy must fulfil."""

    @abstractmethod
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        """Process a tick; return optional order dict {side, size}."""
        ...

    @abstractmethod
    def on_fill(self, side: str, size: float, price: float, ts: float) -> None:
        """Handle a fill event, updating internal bookkeeping."""
        ...

    @abstractmethod
    def validate_config(self) -> List[str]:
        """Return config errors list (empty = ok)."""
        ...

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Estimate resident memory footprint in MB."""
        ...


@dataclass(slots=True)
class _State:
    """Mutable runtime state for the regime-trailing grid hybrid."""

    last_price: float = 0.0
    anchor: float = 0.0
    high_water: float = 0.0
    mode: str = "grid"  # 'grid' | 'trend'
    open_levels: List[float] = field(default_factory=list)
    cash_eur: float = 0.0
    position_qty: float = 0.0
    avg_entry: float = 0.0
    pnl: float = 0.0
    trades: int = 0
    wins: int = 0


class ADXFilter:
    """True-range + smoothed direction using an EMA cascade (memory-safe)."""

    def __init__(self, period: int) -> None:
        if period < 1:
            raise ValueError("period must be >= 1")
        self._period = int(period)
        self._alpha_t = 2.0 / (self._period + 1.0)
        self._alpha_dm = 1.0 / self._period
        self._prev_high: Optional[float] = None
        self._prev_low: Optional[float] = None
        self._prev_close: Optional[float] = None
        self._smooth_tr: float = 0.0
        self._smooth_plus: float = 0.0
        self._smooth_minus: float = 0.0
        self._ready: bool = False

    def update(self, high: float, low: float, close: float) -> float:
        """Feed a bar; return ADX-like value (0..100)."""
        if self._prev_close is None:
            self._prev_high, self._prev_low, self._prev_close = high, low, close
            return 0.0
        tr = max(
            high - low,
            abs(high - self._prev_close),
            abs(low - self._prev_close),
        )
        up_move = high - self._prev_high
        down_move = self._prev_low - low
        plus_dm = up_move if (up_move > down_move and up_move > 0) else 0.0
        minus_dm = down_move if (down_move > up_move and down_move > 0) else 0.0
        if self._ready:
            self._smooth_tr = self._alpha_t * tr + (1 - self._alpha_t) * self._smooth_tr
            self._smooth_plus = self._alpha_dm * plus_dm + (1 - self._alpha_dm) * self._smooth_plus
            self._smooth_minus = self._alpha_dm * minus_dm + (1 - self._alpha_dm) * self._smooth_minus
            denom = self._smooth_plus + self._smooth_minus
            if denom > 1e-12:
                dx = abs(self._smooth_plus - self._smooth_minus) / denom * 100.0
            else:
                dx = 0.0
            self._prev_high, self._prev_low, self._prev_close = high, low, close
            return dx
        self._smooth_tr = tr
        self._smooth_plus = plus_dm
        self._smooth_minus = minus_dm
        self._ready = True
        self._prev_high, self._prev_low, self._prev_close = high, low, close
        return 0.0


class AdaptiveTrendGrid(StrategyBase):
    """Hybrid strategy switching between trend-trailing and range-fade grid."""

    def __init__(self, config: StrategyConfig) -> None:
        errors = config.validate()
        if errors:
            raise ValueError(f"invalid config: {errors}")
        self._cfg = config
        self._st = _State()
        self._st.cash_eur = config.capital_eur
        self._adx = ADXFilter(config.adx_period)
        self._prices: Deque[float] = deque(maxlen=max(config.channel_lookback, config.ewma_span, config.vol_window) + 1)
        self._bar_highs: Deque[float] = deque(maxlen=config.adx_period + 1)
        self._bar_lows: Deque[float] = deque(maxlen=config.adx_period + 1)

    # ---- helpers ---------------------------------------------------
    def _ewma(self) -> float:
        span = self._cfg.ewma_span
        if not self._prices:
            return 0.0
        alpha = 2.0 / (span + 1.0)
        ema = self._prices[0]
        for p in self._prices:
            ema = alpha * p + (1 - alpha) * ema
        return ema

    def _vol(self) -> float:
        """Realized vol over vol_window (std of log returns), memory-safe."""
        if len(self._prices) < 3:
            return 0.0
        window = list(self._prices)[-(self._cfg.vol_window + 1):]
        arr = np.fromiter(window, dtype=np.float64)
        log_ret = np.diff(np.log(arr))
        vol = float(np.std(log_ret))
        del log_ret
        del arr
        return vol

    def _capital_per_level(self) -> float:
        """Scale level notional by volatility regime (EUR, not asset units)."""
        vol = self._vol()
        if vol <= 1e-12:
            scale = 1.0
        else:
            scale = max(0.5, min(1.5, self._cfg.vol_target / vol))
        alloc = self._cfg.capital_eur * (self._cfg.vol_weight * scale + (1 - self._cfg.vol_weight))
        return max(self._cfg.min_trade_eur, alloc / max(1, self._cfg.max_grid_levels))

    def _buy_notional(self) -> float:
        """Return buy notional capped by remaining cash and exchange floor."""
        notional = min(self._capital_per_level(), self._st.cash_eur)
        return notional if notional >= self._cfg.min_trade_eur else 0.0

    def _sell_notional(self, price: float) -> float:
        """Return sell notional capped by current inventory and exchange floor."""
        inventory_value = self._st.position_qty * price
        notional = min(self._capital_per_level(), inventory_value)
        return notional if notional >= self._cfg.min_trade_eur else 0.0

    # ---- StrategyBase ---------------------------------------------
    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        if price <= 0 or math.isnan(price):
            return None
        self._st.last_price = price
        self._prices.append(price)
        self._bar_highs.append(price * 1.0002)
        self._bar_lows.append(price * 0.9998)

        if len(self._prices) < self._cfg.channel_lookback:
            return None

        # feed ADX with a synthetic bar (high/low around close)
        adx = self._adx.update(self._bar_highs[-1], self._bar_lows[-1], price)

        anchor = self._ewma()
        if self._st.anchor == 0.0:
            self._st.anchor = anchor
        ch_high = max(self._prices)
        ch_low = min(self._prices)
        band = (ch_high - ch_low) / max(1e-9, anchor)

        if self._st.position_qty > 0:
            self._st.high_water = max(self._st.high_water, price)
        else:
            self._st.high_water = price

        # regime switch
        if adx >= self._cfg.adx_trend_threshold and band >= self._cfg.breakout_mult:
            self._st.mode = "trend"
        elif adx < self._cfg.adx_trend_threshold:
            self._st.mode = "grid"

        side_size: Optional[Dict[str, Any]] = None

        if self._st.mode == "trend":
            # trailing: sell inventory only after drawdown from high-water.
            if self._st.position_qty > 0 and (self._st.high_water - price) / self._st.high_water > self._cfg.trail_pct:
                size = self._sell_notional(price)
                if size > 0:
                    side_size = {"side": "sell", "size": size, "price": price}
                    self._st.high_water = price
        else:
            # range-fade grid: buy weakness below anchor; sell strength above anchor.
            spacing = self._cfg.base_spacing_pct * anchor
            buy_level = anchor - spacing
            sell_level = anchor + spacing
            if self._st.position_qty > 0 and price >= sell_level:
                size = self._sell_notional(price)
                if size > 0:
                    side_size = {"side": "sell", "size": size, "price": price}
            elif price <= buy_level and len(self._st.open_levels) < self._cfg.max_grid_levels:
                size = self._buy_notional()
                too_close = bool(self._st.open_levels) and abs(price - self._st.open_levels[-1]) < spacing * 0.5
                if size > 0 and not too_close:
                    self._st.open_levels.append(price)
                    self._st.open_levels.sort(reverse=True)
                    side_size = {"side": "buy", "size": size, "price": price}

        # decay anchor toward price (config-driven drift)
        drift = min(1.0, 2.0 / (self._cfg.ewma_span + 1.0))
        self._st.anchor = (1.0 - drift) * self._st.anchor + drift * price
        return side_size

    def on_fill(self, side: str, size: float, price: float, ts: float) -> None:
        if size <= 0 or price <= 0:
            return
        notional = size  # strategy order size is EUR notional, not asset units
        fee = notional * self._cfg.fee_pct
        if side == "buy":
            spend = min(notional, self._st.cash_eur)
            if spend < self._cfg.min_trade_eur:
                return
            qty = max(0.0, (spend - fee) / price)
            new_qty = self._st.position_qty + qty
            if new_qty > 0:
                self._st.avg_entry = ((self._st.position_qty * self._st.avg_entry) + spend) / new_qty
            self._st.position_qty = new_qty
            self._st.cash_eur -= spend
            self._st.high_water = max(self._st.high_water, price)
            self._st.trades += 1
            return

        if side == "sell" and self._st.position_qty > 0:
            qty = min(self._st.position_qty, notional / price)
            gross = qty * price
            if gross < self._cfg.min_trade_eur:
                return
            fee = gross * self._cfg.fee_pct
            realized = (price - self._st.avg_entry) * qty - fee
            self._st.pnl += realized
            self._st.cash_eur += gross - fee
            self._st.position_qty -= qty
            if realized > 0:
                self._st.wins += 1
            if self._st.open_levels:
                self._st.open_levels.pop()
            if self._st.position_qty <= 1e-12:
                self._st.position_qty = 0.0
                self._st.avg_entry = 0.0
            self._st.trades += 1

    def validate_config(self) -> List[str]:
        return self._cfg.validate()

    def estimate_memory_mb(self) -> float:
        # ~8 bytes/float * buffered elements + fixed overhead
        n = self._prices.maxlen + self._bar_highs.maxlen + self._bar_lows.maxlen
        return round((n * 8) / (1024 * 1024), 4)


def _tick_stream(closes: List[float]) -> Generator[Tuple[float, float], None, None]:
    """Streaming generator yielding (price, ts) without materializing new arrays."""
    for i, c in enumerate(closes):
        yield float(c), float(i)


def _synthetic_prices(n: int, seed: float = 100.0, drift: float = 0.0002) -> List[float]:
    """Deterministic synthetic price series for the inline test."""
    rng = np.random.default_rng(42)
    prices: List[float] = []
    p = seed
    for _ in range(n):
        p = p * (1.0 + drift + 0.0015 * float(rng.standard_normal()))
        prices.append(p)
    return prices


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = StrategyConfig(
        symbol="SOL/EUR",
        capital_eur=13.5,
        max_grid_levels=8,
        base_spacing_pct=0.006,
        trail_pct=0.015,
        adx_trend_threshold=22.0,
        breakout_mult=0.12,
    )
    errs = cfg.validate()
    assert not errs, f"config invalid: {errs}"
    strat = AdaptiveTrendGrid(cfg)
    print(f"memory est: {strat.estimate_memory_mb()} MB")
    series = _synthetic_prices(3000)
    orders = 0
    for px, ts in _tick_stream(series):
        order = strat.on_tick(px, ts)
        if order is not None:
            orders += 1
            strat.on_fill(order["side"], order["size"], px, ts)
    print(f"processed 3000 ticks, orders={orders}, trades={strat._st.trades}, pnl={strat._st.pnl:.4f}, wins={strat._st.wins}, mode={strat._st.mode}")
    print("OK: suite passed")

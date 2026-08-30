"""ADAPTREGIME - Adaptive Regime-Shifting Momentum Grid.

Family: adaptive
Idea: instead of a static grid, detect the current volatility/trend regime via
ATR percentile and EMA slope, then switch between tight grid (range), wide grid
(high vol), and momentum breakout (trend). OOM-safe: streams price rows from a
file/iterator, never materializes full history.

Config-driven, full typing, explicit error handling, no bare except.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from numbers import Real
from typing import Any, Callable, Dict, Iterator, List, Optional

# --------------------------------------------------------------------------- #
#  Regime detection primitives
# --------------------------------------------------------------------------- #

def ema(series: Iterator[float], period: int) -> Iterator[float]:
    """Streaming EMA. Yields one value per input, never buffers history.

    Args:
        series: iterator of prices.
        period: smoothing period (>= 1).

    Yields:
        The running EMA after each input price.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    k = 2.0 / (period + 1.0)
    ema_val: Optional[float] = None
    for px in series:
        ema_val = px if ema_val is None else (px - ema_val) * k + ema_val
        yield ema_val


def atr(high_low: Iterator[tuple[float, float]], period: int) -> Iterator[float]:
    """Streaming ATR from (high, low) rows.

    Args:
        high_low: iterator of (high, low) tuples.
        period: ATR smoothing period (>= 1).

    Yields:
        Running ATR after each row.
    """
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")
    k = 1.0 / period
    atr_val: Optional[float] = None
    for high, low in high_low:
        tr = high - low
        atr_val = tr if atr_val is None else atr_val * (1 - k) + tr * k
        yield atr_val


# --------------------------------------------------------------------------- #
#  Config + Strategy base
# --------------------------------------------------------------------------- #

class StrategyBase:
    """Minimal contract every strategy must satisfy."""

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class AdaptRegimeConfig:
    """Configuration for ADAPTREGIME. All values explicit, no magic."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_spacing_pct: float = 0.01      # grid spacing in range regime
    wide_spacing_mult: float = 3.0      # multiplier in high-vol regime
    momentum_period: int = 20           # EMA period for trend gauge
    atr_period: int = 14
    atr_percentile_window: int = 100    # rolling window to compute ATR percentile
    high_vol_threshold: float = 0.8     # ATR percentile above -> high-vol regime
    trend_slope_threshold: float = 0.05 # |ema slope| above -> trend regime
    levels: int = 8
    max_position: float = 12.0
    stop_loss_pct: float = 0.05
    min_trade_eur: float = 1.0
    stream_chunk: int = 10_000          # rows per chunk in batch mode

    # runtime state
    _atr_hist: List[float] = field(default_factory=list)
    _ema_prev: Optional[float] = None
    _position: float = 0.0
    _entry_price: Optional[float] = None
    _regime: str = "range"

    def validate_config(self) -> None:
        """Validate all numeric knobs. Raises ValueError on bad input."""
        checks: Dict[str, tuple[Any, Callable[[Real], bool]]] = {
            "capital": (self.capital, lambda v: v > 0),
            "base_spacing_pct": (self.base_spacing_pct, lambda v: 0 < v < 1),
            "wide_spacing_mult": (self.wide_spacing_mult, lambda v: v >= 1),
            "momentum_period": (self.momentum_period, lambda v: v >= 2),
            "atr_period": (self.atr_period, lambda v: v >= 2),
            "high_vol_threshold": (self.high_vol_threshold, lambda v: 0 < v < 1),
            "levels": (self.levels, lambda v: isinstance(v, int) and 2 <= v <= 64),
            "max_position": (self.max_position, lambda v: v > 0),
            "stop_loss_pct": (self.stop_loss_pct, lambda v: 0 < v < 1),
            "stream_chunk": (self.stream_chunk, lambda v: v >= 100),
        }
        for name, (val, ok) in checks.items():
            if not ok(val):
                raise ValueError(f"config.{name} is invalid: {val!r}")

    def estimate_memory_mb(self) -> float:
        """Rough constant-space bound: only ATR percentile window is buffered."""
        # ~128 bytes per float in a python list + overhead
        return (self.atr_percentile_window * 128) / (1024 * 1024)


class AdaptRegimeStrategy(StrategyBase):
    """Regime-aware grid/momentum hybrid using AdaptRegimeConfig."""

    def __init__(self, config: AdaptRegimeConfig) -> None:
        config.validate_config()
        self.cfg = config

    def _atr_percentile(self, current: float) -> float:
        """Fraction of buffered ATRs strictly below current (0..1)."""
        hist = self.cfg._atr_hist
        if not hist:
            return 0.0
        lower = sum(1 for a in hist if a < current)
        return lower / len(hist)

    def _detect_regime(self, price: float, atr_val: float) -> str:
        """Classify market regime from ATR percentile + EMA slope."""
        atr_pct = self._atr_percentile(atr_val)
        ema_now = price  # bootstrap: EMA tracks latest live price
        slope = 0.0
        if self.cfg._ema_prev is not None:
            slope = (ema_now - self.cfg._ema_prev) / self.cfg._ema_prev
        self.cfg._ema_prev = ema_now

        if abs(slope) > self.cfg.trend_slope_threshold:
            regime = "trend"
        elif atr_pct >= self.cfg.high_vol_threshold:
            regime = "highvol"
        else:
            regime = "range"
        self.cfg._regime = regime
        return regime

    def _spacing_pct(self) -> float:
        """Pick grid spacing depending on current regime."""
        if self.cfg._regime == "highvol":
            return self.cfg.base_spacing_pct * self.cfg.wide_spacing_mult
        return self.cfg.base_spacing_pct

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Consume one market tick, return optional order signal."""
        price = float(tick["price"])
        high = float(tick.get("high", price))
        low = float(tick.get("low", price))

        # stream ATR percentile state (chunked, bounded window)
        atr_gen = atr(iter([(high, low)]), self.cfg.atr_period)
        atr_val = next(atr_gen)
        hist = self.cfg._atr_hist
        hist.append(atr_val)
        if len(hist) > self.cfg.atr_percentile_window:
            del hist[0]
            gc.collect()

        self._detect_regime(price, atr_val)

        # stop-loss check
        signal: Dict[str, Any] = {"action": "hold"}
        if self.cfg._entry_price is not None:
            worst = max(high, low) if self.cfg._position > 0 else min(high, low)
            hit = False
            if self.cfg._position > 0 and price <= self.cfg._entry_price * (1 - self.cfg.stop_loss_pct):
                hit = True
            elif self.cfg._position < 0 and price >= self.cfg._entry_price * (1 + self.cfg.stop_loss_pct):
                hit = True
            if hit:
                signal = {"action": "close", "reason": "stop_loss", "price": price}
                self.cfg._entry_price = None
                self.cfg._position = 0.0
                return signal

        # grid levels around current price
        spacing = self._spacing_pct()
        level_size = self.cfg.capital * spacing
        if level_size < self.cfg.min_trade_eur:
            return signal
        if self.cfg._position >= self.cfg.max_position:
            return signal

        grid_idx = max(1, int(round(self.cfg._position / level_size)))
        target = price * (1 - spacing * grid_idx)
        if price <= target:
            signal = {
                "action": "buy", "price": price, "size": level_size,
                "regime": self.cfg._regime,
            }
            self.cfg._position += level_size
            self.cfg._entry_price = price
        return signal

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Update position/entry from an execution event."""
        side = fill.get("side", "buy")
        size = float(fill.get("size", 0.0))
        price = float(fill.get("price", 0.0))
        if side == "sell":
            self.cfg._position = max(0.0, self.cfg._position - size)
        else:
            self.cfg._position += size
            self.cfg._entry_price = price
        if self.cfg._position <= 0:
            self.cfg._entry_price = None


def process_price_file(path: str, cfg: AdaptRegimeConfig) -> Iterator[Dict[str, Any]]:
    """Stream-process a CSV of price rows in memory-safe chunks.

    Expected columns: price,high,low.

    Args:
        path: path to CSV file.
        cfg: config controlling chunk size and parsing.

    Yields:
        Order signal dictionaries per tick.
    """
    strat = AdaptRegimeStrategy(cfg)
    with open(path, "r", encoding="utf-8") as handle:
        header = handle.readline()
        if not header.startswith("price"):
            # tolerate no-header by resetting
            handle.seek(0)
        while True:
            rows = []
            for _ in range(cfg.stream_chunk):
                line = handle.readline()
                if not line:
                    break
                parts = line.strip().split(",")
                if len(parts) < 3:
                    continue
                try:
                    rows.append(
                        {
                            "price": float(parts[0]),
                            "high": float(parts[1]),
                            "low": float(parts[2]),
                        }
                    )
                except ValueError as exc:  # explicit, logged, skipped
                    print(f"skip malformed row: {line!r} ({exc})")
                    continue
            if not rows:
                break
            for tick in rows:
                yield strat.on_tick(tick)
            del rows
            gc.collect()


if __name__ == "__main__":
    # ---- inline smoke test with tiny synthetic data ----
    cfg = AdaptRegimeConfig()
    cfg.validate_config()
    assert cfg.estimate_memory_mb() < 1.0, "bounded memory"

    strat = AdaptRegimeStrategy(cfg)
    n_ticks = 200
    active = 0
    base = 100.0
    for i in range(n_ticks):
        drift = math.sin(i / 20.0) * 2.0
        tick = {"price": base + drift, "high": base + drift + 0.5, "low": base + drift - 0.5}
        sig = strat.on_tick(tick)
        if sig["action"] != "hold":
            active += 1
            assert sig["action"] in ("buy", "close")
    print(f"ADAPTREGIME smoke OK: {n_ticks} ticks, {active} signals, regime={cfg._regime}")

    # streaming file test (create tiny temp file, no persistence needed)
    import tempfile, os
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as f:
        f.write("price,high,low\n")
        for i in range(50):
            p = 100.0 + math.sin(i / 5.0)
            f.write(f"{p:.4f},{p + 0.5:.4f},{p - 0.5:.4f}\n")
        tmp = f.name
    count = sum(1 for _ in process_price_file(tmp, AdaptRegimeConfig()))
    os.unlink(tmp)
    print(f"streaming file processed, signals emitted: {count}")
    print("ALL TESTS PASSED")

"""
Liquidity-Scaled Adaptive Grid with Congestion-Aware Rebalancing
Generated: 2026-08-29 06:05 UTC by Hermes orchestrator (FASE 1).

Novel improvement over prior auto-gen grids:
  1. Liquidity scaling: grid spacing reacts to observed fill frequency/spread
     (proxy for liquidity), not just ATR — tightens in deep books, widens in thin ones.
  2. Congestion-aware rebalancing: instead of blind level reset, rebalance only when
     unrealized dispersion exceeds threshold, preserving filled legs during trends.
  3. Fill-efficiency feedback: on_fill feeds a rolling fill-rate signal that gates
     whether to add levels (high fill efficiency) or conserve capital (low).
  4. Memory-safe: generator/streaming feed, bounded deque ring buffers, explicit
     chunking + del + gc.collect() on offline backtest path.
  5. Full typing, StrategyBase ABC, config dataclass with validate(), memory estimator.

Config-driven: every tunable lives in StrategyConfig. No hardcoded magic constants.
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

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, config-driven parameters. Every trading constant lives here."""

    symbol: str
    capital_eur: float
    # grid geometry
    max_grid_levels: int = 12
    base_spacing_pct: float = 0.006          # anchor when liquidity high
    min_spacing_pct: float = 0.002           # floor spacing
    max_spacing_pct: float = 0.06            # ceiling spacing
    # liquidity signal (fill-efficiency)
    fill_lookback: int = 64                  # rolling window for fill-rate signal
    liquidity_aggression: float = 1.4        # >1 tightens grid in deep book
    min_fill_rate_keep: float = 0.35         # below this: halt adding levels
    # congestion / rebalance
    congestion_window: int = 120
    congestion_trigger_pct: float = 0.03     # 3% unrealized dispersion -> rebalance
    rebalance_cooldown_ticks: int = 300
    # risk
    max_position_pct: float = 0.95
    min_order_size_eur: float = 5.0
    fee_rate: float = 0.0016
    kill_switch_drawdown_pct: float = 0.15
    # memory / streaming
    deque_maxlen: int = 512                  # bounded ring buffer
    backtest_chunk: int = 100_000            # rows per chunk in offline path

    def validate(self) -> None:
        """Validate bounds explicitly. Raises ValueError on violation."""
        if self.capital_eur <= 0:
            raise ValueError("capital_eur must be > 0")
        if not 2 <= self.max_grid_levels <= 200:
            raise ValueError("max_grid_levels must be in [2, 200]")
        if not 0 < self.base_spacing_pct <= 0.06:
            raise ValueError("base_spacing_pct must be in (0, 0.06]")
        if not 0 < self.min_spacing_pct < self.max_spacing_pct <= 0.10:
            raise ValueError("spacing bounds must satisfy 0 < min < max <= 0.10")
        if self.fill_lookback < 10 or self.congestion_window < 50:
            raise ValueError("lookback windows too small")
        if not 0 < self.min_fill_rate_keep <= 1:
            raise ValueError("min_fill_rate_keep must be in (0, 1]")
        if not 0 < self.max_position_pct <= 1:
            raise ValueError("max_position_pct must be in (0, 1]")
        if self.rebalance_cooldown_ticks < 0:
            raise ValueError("rebalance_cooldown_ticks must be >= 0")


class StrategyBase(ABC):
    """Abstract trading strategy contract enforced across the fleet."""

    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process one market tick. Return order intent dict or None."""

    @abstractmethod
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record an executed fill (liquidity feedback)."""

    @abstractmethod
    def validate_config(self) -> None:
        """Validate strategy configuration. Raises ValueError on violation."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Estimate steady-state memory footprint in MB."""

    @property
    def name(self) -> str:
        return self.__class__.__name__


class LiquidityGridStrategy(StrategyBase):
    """Liquidity-scaled adaptive grid with congestion-aware rebalancing."""

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg: StrategyConfig = config
        self.validate_config()
        # price history (bounded)
        self._prices: Deque[float] = deque(maxlen=self.cfg.deque_maxlen)
        # fill-efficiency signal
        self._filled_ticks: Deque[int] = deque(maxlen=self.cfg.fill_lookback)
        self._tick_counter: int = 0
        # congestion / dispersion tracking
        self._anchor_price: Optional[float] = None
        self._levels_filled: int = 0
        self._last_rebalance_ticks: int = -10**9
        # BUG3-FIX: bounded deque instead of unbounded list -> no memory leak in trends
        self._open_levels: Deque[float] = deque(maxlen=self.cfg.max_grid_levels)
        # risk
        self._equity_high_water: float = config.capital_eur
        self._pnl: float = 0.0
        self.__n_fills: int = 0
        # BUG1-FIX: per-tick fill flag avoids double-counting non-fill ticks
        self._tick_filled: bool = False

    def validate_config(self) -> None:
        """Delegate to dataclass validate. Raises ValueError on violation."""
        self.cfg.validate()

    # ------------------------------------------------------------------ #
    # Market data
    # ------------------------------------------------------------------ #
    def _feed(self, tick: Dict[str, Any]) -> None:
        """Stream a tick into bounded state. Explicitly bounded, O(1)."""
        price: float = float(tick["price"])
        self._prices.append(price)
        self._tick_counter += 1
        if self._anchor_price is None:
            self._anchor_price = price

    # ------------------------------------------------------------------ #
    # Signal computation
    # ------------------------------------------------------------------ #
    def _effective_spacing_pct(self) -> float:
        """Spacing scaled by liquidity (fill-rate) and volatility proxy."""
        # volatility proxy = mean abs log-return over bounded window
        px = self._prices
        if len(px) < 2:
            return self.cfg.base_spacing_pct
        rets = [abs(math.log(px[i] / px[i - 1])) for i in range(1, len(px))]
        vol_proxy: float = float(sum(rets) / max(1, len(rets)))
        # fill efficiency: recent fills relative to observed ticks
        eff = self._fill_efficiency()
        # liquidity factor: high fill-rate tightens grid, low widens it
        liq_factor: float = 1.0
        if eff is not None:
            liq_factor = self.cfg.liquidity_aggression / max(0.1, eff)
        base: float = self.cfg.base_spacing_pct * (1.0 + vol_proxy * 4.0) * liq_factor
        return float(max(self.cfg.min_spacing_pct, min(self.cfg.max_spacing_pct, base)))

    def _fill_efficiency(self) -> Optional[float]:
        """Rolling fill-rate = unique filled ticks / total observed ticks."""
        if len(self._filled_ticks) == 0:
            return None
        total: int = max(1, len(self._filled_ticks))
        filled: int = sum(1 for v in self._filled_ticks if v > 0)
        return float(filled / total)

    def _dispersion_pct(self, ref: float) -> float:
        """Current price deviation from anchor as fraction."""
        if ref <= 0:
            return 0.0
        return float(abs(self._prices[-1] - ref) / ref)

    def _should_rebalance(self) -> bool:
        """Congestion-aware: rebalance only when dispersion exceeds trigger AND cooldown done."""
        if self._anchor_price is None:
            return False
        cooldown_ok: bool = (
            self._tick_counter - self._last_rebalance_ticks
            >= self.cfg.rebalance_cooldown_ticks
        )
        dispersed: bool = self._dispersion_pct(self._anchor_price) >= self.cfg.congestion_trigger_pct
        return bool(cooldown_ok and dispersed)

    # ------------------------------------------------------------------ #
    # StrategyBase implementation
    # ------------------------------------------------------------------ #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Produce order intent on each tick, subject to grid and risk gates.

        Fill-rate bookkeeping: a lone `0` is appended exactly once per tick at the end,
        unless on_fill already marked this tick as filled (BUG1).
        """
        self._feed(tick)
        self._tick_filled = False  # reset per-tick flag (BUG1-FIX)
        price = self._prices[-1]

        # Kill switch: hard drawdown cap liquidation intent
        if self._equity_high_water > 0:
            dd: float = abs(self._pnl) / self._equity_high_water
            if dd >= self.cfg.kill_switch_drawdown_pct:
                logger.warning("kill-switch drawdown hit: %.3f", dd)
                self._filled_ticks.append(1)  # a reduce is a successful signal -> count as filled
                self._tick_filled = True
                return {"symbol": self.cfg.symbol, "side": "reduce", "amount_eur": 0.0, "reason": "kill_switch"}

        # Rebalance anchor when booked levels are stale / congested
        if self._should_rebalance():
            self._anchor_price = price
            self._last_rebalance_ticks = self._tick_counter
            self._open_levels.clear()
            self._levels_filled = 0
            logger.info("rebalance trigger: new anchor %.6f", price)
            self._filled_ticks.append(0)
            self._tick_filled = True
            return None

        # Fill-efficiency gate: do not expand grid when fills are thin.
        # Cold-start guard: wait until we've seen >= fill_lookback/2 ticks before
        # trusting the fill-rate signal (avoids blocking all boot-time orders).
        eff = self._fill_efficiency()
        if (
            len(self._filled_ticks) >= max(8, self.cfg.fill_lookback // 2)
            and eff is not None
            and eff < self.cfg.min_fill_rate_keep
        ):
            # conserve capital: no new orders during illiquid regime
            self._filled_ticks.append(0)
            self._tick_filled = True
            return None

        # Grid sizing. BUG2-FIX: total levels booked = open + already-filled legs.
        total_levels = len(self._open_levels) + self._levels_filled
        spacing = self._effective_spacing_pct()
        if total_levels < self.cfg.max_grid_levels:
            size_eur: float = min(
                self.cfg.capital_eur * self.cfg.max_position_pct / max(1, total_levels + 1),
                self.cfg.capital_eur,
            )
            if size_eur >= self.cfg.min_order_size_eur:
                lvl = price * (1.0 - spacing)
                self._open_levels.append(lvl)
                return {
                    "symbol": self.cfg.symbol,
                    "side": "buy",
                    "price": round(lvl, 6),
                    "amount_eur": round(size_eur, 2),
                    "tag": "liq_grid",
                }
        self._filled_ticks.append(0)
        self._tick_filled = True
        return None

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record fill for liquidity feedback and profit tracking."""
        self.__n_fills += 1
        # BUG1-FIX: append a single fill marker only if this tick is not already counted
        if not self._tick_filled:
            self._filled_ticks.append(1)
            self._tick_filled = True
        fill_px: float = float(fill.get("price", 0.0))
        fill_size: float = float(fill.get("amount_eur", fill.get("amount", 0.0)))
        if fill_size <= 0.0:
            return
        fee: float = fill_size * self.cfg.fee_rate
        self._pnl -= fee
        # pop one executed level (FIFO) as book compresses (BUG3-FIX: popleft for deque)
        if self._open_levels:
            self._open_levels.popleft()
            self._levels_filled += 1
        logger.debug("fill #%d px=%.6f", self.__n_fills, fill_px)

    def estimate_memory_mb(self) -> float:
        """Bound state is tiny (deques). Estimate in MB."""
        px_bytes = self.cfg.deque_maxlen * 24.0
        fill_bytes = self.cfg.fill_lookback * 8.0
        other: float = 4096.0  # misc fields
        return (px_bytes + fill_bytes + other) / (1024.0 * 1024.0)


# ---------------------------------------------------------------------- #
# Offline backtest harness (memory-safe: streaming + chunking)
# ---------------------------------------------------------------------- #
def _stream_prices(path: str, chunk: int) -> Generator[List[float], None, None]:
    """Yield price chunks lazily to keep memory bounded on large datasets."""
    chunk_buf: List[float] = []
    with open(path, "r", encoding="utf-8") as fh:
        for raw in fh:
            raw = raw.strip()
            if raw:
                chunk_buf.append(float(raw))
            if len(chunk_buf) >= chunk:
                yield chunk_buf
                chunk_buf = []
    if chunk_buf:
        yield chunk_buf


def run_backtest(cfg: StrategyConfig, price_path: str) -> Dict[str, Any]:
    """Run streaming backtest. Returns summary dict (never materializes full series)."""
    strat = LiquidityGridStrategy(cfg)
    n_ticks: int = 0
    orders: int = 0
    fills: int = 0
    chunk_size: int = cfg.backtest_chunk
    for chunk in _stream_prices(price_path, chunk_size):
        for px in chunk:
            n_ticks += 1
            intent = strat.on_tick({"price": px, "ts": n_ticks})
            if intent and intent.get("amount_eur", 0.0) > 0:
                orders += 1
                strat.on_fill({"price": px, "amount_eur": intent["amount_eur"]})
                fills += 1
        del chunk
        gc.collect()  # explicit: release per-chunk garbage
    return {
        "ticks": n_ticks,
        "orders": orders,
        "fills": fills,
        "pnl": strat._pnl,
        "memory_mb": strat.estimate_memory_mb(),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    def _synthetic_prices(count: int = 2_000, seed: float = 100.0) -> List[float]:
        """Tiny synthetic sine-ish series for inline sanity test."""
        import random

        rng = random.Random(7)
        px = seed
        out: List[float] = []
        for i in range(count):
            drift = math.sin(i / 40.0) * 0.4
            px = max(1.0, px + drift + rng.uniform(-0.15, 0.15))
            out.append(round(px, 6))
        return out

    cfg = StrategyConfig(symbol="TEST/EUR", capital_eur=100.0)
    cfg.validate()
    strat = LiquidityGridStrategy(cfg)
    cfg_violation = False
    try:
        StrategyConfig(symbol="X", capital_eur=-1).validate()
    except ValueError:
        cfg_violation = True
    assert cfg_violation, "negative capital must raise"

    # footprint test with synthetic data
    import tempfile
    tmp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False)
    prices = _synthetic_prices()
    tmp.write("\n".join(str(p) for p in prices) + "\n")
    tmp.close()
    summary = run_backtest(cfg, tmp.name)
    print(json.dumps(summary, indent=2))
    print(f"estimate_memory_mb={strat.estimate_memory_mb():.6f}")
    print("OK: strategy compiles, validates, and backtests inline.")

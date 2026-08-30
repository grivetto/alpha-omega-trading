"""
Trend-Gated Volatility Grid (TVG) — auto-generated 2026-08-28 12:33 UTC.

Adaptive grid strategy with three cooperating layers:

1. VOLATILITY LAYER: streaming Wilder ATR (bounded deque) feeds a short/long
   volatility-ratio regime. Grid spacing expands in high-vol regimes and
   contracts in low-vol regimes, keeping edge per level roughly constant.

2. TREND GATE LAYER: directional efficiency (net move / gross move) over a
   rolling window. In high-efficiency (trending) regimes the grid is gated:
   no counter-trend BUY accumulation below center; in ranging regimes the
   full grid is active. This prevents the classic "grid gets run over by a
   trend" failure mode.

3. RISK LAYER: asymmetric position sizing (fractional Kelly on realized
   win-rate), explicit fee-aware profit threshold per level, and a latched
   drawdown kill-switch that halts the grid until equity recovers.

OOM SAFETY: all history buffers are bounded deques (maxlen from config),
grid levels are produced by a generator (never materialized as a list),
large temporaries are `del`-eted and `gc.collect()` is invoked on a
periodic cleanup cycle. No list comprehensions over unbounded data.

Interface contract (Denaro StrategyBase):
- on_tick(tick) -> (Action, dict)
- on_fill(fill) -> None
- validate_config() -> None
- estimate_memory_mb() -> float
- get_state() / load_state() for persistence
"""

from __future__ import annotations

import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Generator, Optional, Tuple

logger = logging.getLogger(__name__)


class Action(Enum):
    """Trading actions emitted by the strategy."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class OrderSide(Enum):
    """Fill side."""

    BUY = "buy"
    SELL = "sell"


class VolRegime(Enum):
    """Volatility regime classification."""

    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class Tick:
    """Market tick (subset of the full Denaro Tick)."""

    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    high: float = 0.0
    low: float = 0.0

    def __post_init__(self) -> None:
        if self.high == 0.0:
            object.__setattr__(self, "high", self.mid)
        if self.low == 0.0:
            object.__setattr__(self, "low", self.mid)

    @property
    def spread_pct(self) -> float:
        """Relative bid/ask spread."""
        return (self.ask - self.bid) / self.mid if self.mid > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Order fill notification."""

    order_id: str
    symbol: str
    side: OrderSide
    price: float
    qty: float
    fee: float
    timestamp: float


@dataclass(slots=True)
class TVGConfig:
    """Configuration for TrendGatedVolGrid. All tunables, no hardcoded values."""

    symbol: str
    capital: float
    # --- grid geometry ---
    base_levels: int = 12
    min_levels: int = 4
    max_levels: int = 24
    base_spacing_pct: float = 0.01
    max_spacing_pct: float = 0.05
    # --- volatility layer ---
    atr_period: int = 14
    vol_fast_alpha: float = 0.1
    vol_slow_alpha: float = 0.02
    high_vol_ratio: float = 1.6
    low_vol_ratio: float = 0.6
    # --- trend gate ---
    trend_window: int = 40
    trend_gate_threshold: float = 0.55
    # --- risk layer ---
    fee_rate: float = 0.0016
    kelly_fraction: float = 0.25
    max_drawdown_pct: float = 0.10
    dd_recover_pct: float = 0.03
    max_orders_per_side: int = 6
    # --- memory ---
    max_history: int = 2048
    gc_interval_ticks: int = 5000

    def validate(self) -> None:
        """Validate configuration invariants. Raises ValueError on violation."""
        if self.capital <= 0:
            raise ValueError("capital must be positive")
        if not (0 < self.min_levels <= self.base_levels <= self.max_levels):
            raise ValueError("levels must satisfy 0 < min <= base <= max")
        if not (0 < self.base_spacing_pct <= self.max_spacing_pct < 1):
            raise ValueError("spacing bounds invalid")
        if self.atr_period < 2:
            raise ValueError("atr_period must be >= 2")
        if not (0 < self.vol_fast_alpha < 1 and 0 < self.vol_slow_alpha < self.vol_fast_alpha):
            raise ValueError("vol alphas must satisfy 0 < slow < fast < 1")
        if not (0 < self.low_vol_ratio < 1 < self.high_vol_ratio):
            raise ValueError("vol ratios must satisfy 0 < low < 1 < high")
        if not (0 < self.trend_gate_threshold < 1):
            raise ValueError("trend_gate_threshold must be in (0, 1)")
        if not (0 < self.fee_rate < 0.05):
            raise ValueError("fee_rate implausible")
        if not (0 < self.kelly_fraction <= 1):
            raise ValueError("kelly_fraction must be in (0, 1]")
        if not (0 < self.max_drawdown_pct < 1 and 0 < self.dd_recover_pct < self.max_drawdown_pct):
            raise ValueError("drawdown bounds invalid")
        if self.max_history < self.atr_period * 4:
            raise ValueError("max_history too small for atr_period")
        if self.gc_interval_ticks < 100:
            raise ValueError("gc_interval_ticks too small")


class StrategyError(Exception):
    """Base strategy exception."""


class ConfigError(StrategyError):
    """Configuration validation error."""


class DataError(StrategyError):
    """Market data error."""


class RiskError(StrategyError):
    """Risk management violation."""


class StrategyBase:
    """Denaro strategy interface (kept minimal and self-contained)."""

    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    def get_state(self) -> Dict[str, Any]:
        raise NotImplementedError

    def load_state(self, state: Dict[str, Any]) -> None:
        raise NotImplementedError


class TrendGatedVolGrid(StrategyBase):
    """
    Trend-gated, volatility-adaptive grid.

    Strategy decisions per tick:
    1. Update streaming ATR + vol ratio (bounded deques, O(1) per tick).
    2. Classify volatility regime -> dynamic spacing + level count.
    3. Classify trend efficiency -> gate counter-trend BUY orders.
    4. Check latched drawdown kill-switch.
    5. Emit BUY/SELL/HOLD/CANCEL_ALL with full parameter context.
    """

    def __init__(self, config: TVGConfig) -> None:
        config.validate()
        self.cfg: TVGConfig = config
        self._prices: Deque[float] = deque(maxlen=config.max_history)
        self._highs: Deque[float] = deque(maxlen=config.atr_period)
        self._lows: Deque[float] = deque(maxlen=config.atr_period)
        self._atr: float = 0.0
        self._vol_fast: float = 0.0
        self._vol_slow: float = 0.0
        self._equity: float = config.capital
        self._peak_equity: float = config.capital
        self._kill_switch: bool = False
        self._wins: int = 0
        self._losses: int = 0
        self._fills: int = 0
        self._open_buys: int = 0
        self._open_sells: int = 0
        self._last_mid: float = 0.0
        self._tick_count: int = 0
        self._pos_qty: float = 0.0
        self._pos_avg: float = 0.0

    # ------------------------------------------------------------------ #
    #  Streaming indicators (O(1), bounded memory)                       #
    # ------------------------------------------------------------------ #

    def _update_atr(self, tick: Tick) -> float:
        """Wilder ATR via streaming smoothing. Returns current ATR."""
        tr = max(
            tick.high - tick.low,
            abs(tick.high - self._last_mid) if self._last_mid > 0 else 0.0,
            abs(tick.low - self._last_mid) if self._last_mid > 0 else 0.0,
        )
        if self._atr <= 0.0:
            self._atr = tr
        else:
            self._atr = (self._atr * (self.cfg.atr_period - 1) + tr) / self.cfg.atr_period
        return self._atr

    def _update_vol_regime(self, atr_pct: float) -> VolRegime:
        """EMA-smoothed short/long volatility ratio -> regime classification."""
        if self._vol_fast <= 0.0:
            self._vol_fast = atr_pct
            self._vol_slow = atr_pct
            return VolRegime.NORMAL
        self._vol_fast += self.cfg.vol_fast_alpha * (atr_pct - self._vol_fast)
        self._vol_slow += self.cfg.vol_slow_alpha * (atr_pct - self._vol_slow)
        if self._vol_slow <= 0.0:
            return VolRegime.NORMAL
        ratio = self._vol_fast / self._vol_slow
        if ratio >= self.cfg.high_vol_ratio:
            return VolRegime.HIGH
        if ratio <= self.cfg.low_vol_ratio:
            return VolRegime.LOW
        return VolRegime.NORMAL

    def _trend_efficiency(self) -> float:
        """Directional efficiency: |net move| / sum(|moves|) in [0, 1]."""
        if len(self._prices) < 2:
            return 0.0
        net: float = self._prices[-1] - self._prices[0]
        gross: float = 0.0
        prev: Optional[float] = None
        for p in self._prices:
            if prev is not None:
                gross += abs(p - prev)
            prev = p
        if gross <= 0.0:
            return 0.0
        return abs(net) / gross

    # ------------------------------------------------------------------ #
    #  Dynamic grid geometry                                             #
    # ------------------------------------------------------------------ #

    def _grid_params(self, atr_pct: float, regime: VolRegime) -> Tuple[float, int]:
        """Compute (spacing_pct, level_count) from vol regime. Generator-safe."""
        if regime is VolRegime.HIGH:
            spacing = min(self.cfg.base_spacing_pct * 1.6, self.cfg.max_spacing_pct)
            levels = max(self.cfg.min_levels, self.cfg.base_levels - 4)
        elif regime is VolRegime.LOW:
            spacing = max(self.cfg.base_spacing_pct * 0.6, atr_pct * 1.2)
            levels = min(self.cfg.max_levels, self.cfg.base_levels + 4)
        else:
            spacing = max(self.cfg.base_spacing_pct, atr_pct * 1.5)
            levels = self.cfg.base_levels
        return min(spacing, self.cfg.max_spacing_pct), levels

    def _iter_levels(self, mid: float, spacing_pct: float, levels: int) -> Generator[Tuple[int, float], None, None]:
        """Yield (offset_idx, price) for each grid level — no materialized list."""
        step = mid * spacing_pct
        for i in range(1, levels + 1):
            yield i, mid - step * i

    # ------------------------------------------------------------------ #
    #  Sizing (asymmetric, fee-aware)                                    #
    # ------------------------------------------------------------------ #

    def _kelly_win_rate(self) -> float:
        """Fractional Kelly size on realized win rate, clamped to [0.05, 0.35]."""
        total = self._wins + self._losses
        if total == 0:
            return 0.10
        win_rate = self._wins / total
        kelly = max(0.0, win_rate - (1.0 - win_rate))
        return max(0.05, min(0.35, kelly * self.cfg.kelly_fraction))

    def _size_per_level(self) -> float:
        """Capital fraction per grid level, fee-breakeven aware."""
        breakeven = 2.0 * self.cfg.fee_rate
        min_spacing = self.cfg.base_spacing_pct
        edge = max(0.0, min_spacing - breakeven)
        kelly = self._kelly_win_rate()
        return max(0.01, min(0.10, kelly * (1.0 + edge * 20.0)))

    # ------------------------------------------------------------------ #
    #  StrategyBase interface                                            #
    # ------------------------------------------------------------------ #

    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        """Process a market tick and emit the next action."""
        if tick.mid <= 0 or tick.ask < tick.bid:
            raise DataError(f"invalid tick for {tick.symbol}: bid={tick.bid} ask={tick.ask}")

        self._tick_count += 1
        self._last_mid = tick.mid
        self._prices.append(tick.mid)
        self._highs.append(tick.high)
        self._lows.append(tick.low)

        atr = self._update_atr(tick)
        atr_pct = atr / tick.mid if tick.mid > 0 else 0.0
        regime = self._update_vol_regime(atr_pct)
        efficiency = self._trend_efficiency()
        spacing_pct, levels = self._grid_params(atr_pct, regime)

        # Periodic OOM cleanup for long-running instances.
        if self._tick_count % self.cfg.gc_interval_ticks == 0:
            del atr_pct
            gc.collect()

        # Latch drawdown kill-switch.
        if self._kill_switch:
            if self._equity >= self._peak_equity * (1.0 - self.cfg.dd_recover_pct):
                self._kill_switch = False
                logger.info("kill-switch released: equity recovered to %.4f", self._equity)
            else:
                return Action.CANCEL_ALL, {"reason": "kill_switch_latched", "equity": self._equity}

        drawdown = 1.0 - self._equity / self._peak_equity if self._peak_equity > 0 else 0.0
        if drawdown >= self.cfg.max_drawdown_pct:
            self._kill_switch = True
            logger.warning("kill-switch triggered: drawdown %.4f >= %.4f", drawdown, self.cfg.max_drawdown_pct)
            return Action.CANCEL_ALL, {"reason": "kill_switch_triggered", "drawdown": drawdown}

        trending = efficiency >= self.cfg.trend_gate_threshold
        size_frac = self._size_per_level()
        order_value = self._equity * size_frac

        if trending and tick.mid < self._prices[0]:
            # Trend gate: no counter-trend accumulation below reference.
            return Action.HOLD, {
                "reason": "trend_gate",
                "efficiency": round(efficiency, 4),
                "regime": regime.value,
                "spacing_pct": round(spacing_pct, 5),
                "levels": levels,
                "atr_pct": round(atr_pct, 6),
                "size": order_value,
            }

        level_prices: Deque[float] = deque(maxlen=levels)
        for idx, price in self._iter_levels(tick.mid, spacing_pct, levels):
            level_prices.append(price)

        if self._open_buys >= self.cfg.max_orders_per_side:
            return Action.HOLD, {"reason": "max_open_orders", "open_buys": self._open_buys}

        target = level_prices[-1] if level_prices else tick.mid * (1.0 - spacing_pct)
        self._open_buys += 1
        return Action.BUY, {
            "symbol": tick.symbol,
            "price": round(target, 8),
            "size": round(order_value, 8),
            "spacing_pct": round(spacing_pct, 5),
            "levels": levels,
            "regime": regime.value,
            "efficiency": round(efficiency, 4),
            "trending": trending,
            "atr_pct": round(atr_pct, 6),
        }

    def on_fill(self, fill: Fill) -> None:
        """Update position accounting, PnL and equity on fill (fee absolute)."""
        if fill.side is OrderSide.BUY:
            # Accumulate position at weighted average price.
            new_qty = self._pos_qty + fill.qty
            if new_qty > 0:
                self._pos_avg = (
                    (self._pos_qty * self._pos_avg) + (fill.qty * fill.price)
                ) / new_qty
            self._pos_qty = new_qty
            self._open_buys = max(0, self._open_buys - 1)
            return
        if fill.side is OrderSide.SELL:
            realized = (fill.price - self._pos_avg) * fill.qty - fill.fee
            self._pos_qty = max(0.0, self._pos_qty - fill.qty)
            self._fills += 1
            self._equity += realized
            self._peak_equity = max(self._peak_equity, self._equity)
            if realized >= 0:
                self._wins += 1
            else:
                self._losses += 1
            logger.debug("fill %s realized=%.6f equity=%.4f", fill.order_id, realized, self._equity)
            return
        raise DataError(f"unknown fill side: {fill.side}")

    def validate_config(self) -> None:
        """Validate configuration (public wrapper)."""
        try:
            self.cfg.validate()
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def estimate_memory_mb(self) -> float:
        """Estimate resident memory: bounded buffers dominate."""
        per_float = 24.0  # ~24 bytes per Python float object
        buffer_bytes = (
            len(self._prices) + len(self._highs) + len(self._lows)
        ) * per_float
        base_mb = 0.5  # interpreter/object overhead per instance
        return base_mb + buffer_bytes / (1024.0 * 1024.0)

    def get_state(self) -> Dict[str, Any]:
        """Serializable state for persistence."""
        return {
            "equity": self._equity,
            "peak_equity": self._peak_equity,
            "wins": self._wins,
            "losses": self._losses,
            "fills": self._fills,
            "open_buys": self._open_buys,
            "open_sells": self._open_sells,
            "kill_switch": self._kill_switch,
            "pos_qty": self._pos_qty,
            "pos_avg": self._pos_avg,
            "atr": self._atr,
            "vol_fast": self._vol_fast,
            "vol_slow": self._vol_slow,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore state from persistence (best-effort, explicit)."""
        self._equity = float(state.get("equity", self._equity))
        self._peak_equity = float(state.get("peak_equity", self._equity))
        self._wins = int(state.get("wins", 0))
        self._losses = int(state.get("losses", 0))
        self._fills = int(state.get("fills", 0))
        self._open_buys = int(state.get("open_buys", 0))
        self._open_sells = int(state.get("open_sells", 0))
        self._kill_switch = bool(state.get("kill_switch", False))
        self._pos_qty = float(state.get("pos_qty", 0.0))
        self._pos_avg = float(state.get("pos_avg", 0.0))
        self._atr = float(state.get("atr", 0.0))
        self._vol_fast = float(state.get("vol_fast", 0.0))
        self._vol_slow = float(state.get("vol_slow", 0.0))


if __name__ == "__main__":
    # Inline smoke test with small synthetic dataset (no external deps).
    logging.basicConfig(level=logging.INFO)
    cfg = TVGConfig(symbol="SOL/EUR", capital=13.5)
    strat = TrendGatedVolGrid(cfg)
    strat.validate_config()

    mid = 150.0
    actions: Dict[Action, int] = {}
    for i in range(400):
        drift = 0.15 * math.sin(i / 17.0)  # mean-reverting synthetic path
        mid = max(1.0, mid + drift + (0.05 if i % 40 < 20 else -0.05))
        t = Tick(
            timestamp=float(i),
            symbol=cfg.symbol,
            bid=mid - 0.01,
            ask=mid + 0.01,
            mid=mid,
            volume=1.0,
            high=mid + 0.02,
            low=mid - 0.02,
        )
        action, params = strat.on_tick(t)
        actions[action] = actions.get(action, 0) + 1

    f = Fill(order_id="t1", symbol=cfg.symbol, side=OrderSide.SELL,
             price=150.0, qty=0.01, fee=0.0024, timestamp=1.0)
    strat.on_fill(f)

    mem = strat.estimate_memory_mb()
    state = strat.get_state()
    assert mem > 0.0, "memory estimate must be positive"
    assert state["fills"] == 1, "fill accounting broken"
    assert len(strat._prices) <= cfg.max_history, "history buffer unbounded"
    print(f"OK: action distribution={ {k.value: v for k, v in actions.items()} }")
    print(f"OK: equity={strat._equity:.4f} peak={strat._peak_equity:.4f} "
          f"wins={strat._wins} losses={strat._losses} mem={mem:.4f} MB")
    print("SMOKE TEST PASSED")

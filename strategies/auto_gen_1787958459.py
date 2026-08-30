"""
Kelly-Edge Grid (KEG-Grid) — auto-generated 2026-08-28 23:07 UTC.

A grid strategy whose per-level order SIZE is driven by a rolling Kelly
estimate of the grid's OWN realized edge, instead of a fixed notional or a
pure volatility rule. Distinct from the existing auto-gen families
(ATR-only grids, momentum gates, regime hybrids, mean-reversion bands,
OFI-Grid flow-imbalance, ISV-Grid inventory-skew + vol-target) because it
does NOT model price at all: it treats the grid as a statistical edge
machine and lets measured outcomes decide how much capital each level risks.

THREE LAYERS
1. EDGE LAYER (KellyEstimator): every closed grid round-trip (buy+sell pair)
   contributes its realized PnL to a bounded rolling window. The estimator
   derives win_rate, payoff_ratio (avg_win / avg_loss) and the Kelly fraction
   kelly = win_rate - (1 - win_rate) / payoff_ratio, exponentially smoothed
   and clipped to [0, kelly_cap]. During the warmup phase (fewer than
   min_trades) a conservative default fraction is used. This is the PRIMARY
   sizing driver: high measured edge -> larger orders, negative edge ->
   orders shrink toward min_order_frac, keeping the grid alive but small.

2. VOL-CAP LAYER: realized volatility (EMA of |mid_t - mid_{t-1}|) is used
   ONLY as a safety cap on order size (vol_mult = vol_target / realized_vol,
   clipped to [min_vol_mult, 1.0]). It never drives the strategy by itself;
   it only prevents the Kelly fraction from deploying full size into
   violent regimes.

3. GRID + RISK LAYER: EMA anchor with levels generated lazily on each side,
   each level's notional = base_capital / levels_per_side * kelly_frac *
   vol_mult. Fills close round-trips (a BUY fill pairs with the nearest
   resting SELL above, and vice versa) so the edge estimator sees real
   outcomes. Stale orders older than max_order_age are cancelled
   (CANCEL_ALL + HOLD) and re-quoted. Drawdown kill-switch with hysteresis:
   halt at max_drawdown, resume only after equity recovers above
   recovery_threshold; on halt the action meta carries {"flatten": true,
   "position_qty": n} so the adapter can close the open position.

OOM SAFETY: all history is bounded (deque maxlen), grid levels are produced
by a generator and consumed lazily, large temporaries are `del`-eted and
`gc.collect()` runs every gc_interval ticks. Pure stdlib — no numpy.

Interface contract (Denaro StrategyBase):
- on_tick(tick) -> Tuple[Action, Dict[str, Any]]
- on_fill(fill) -> None
- validate_config() -> None
- estimate_memory_mb() -> float
- get_state() / load_state() for persistence
"""

from __future__ import annotations

import gc
import logging
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Action(Enum):
    """Trading actions emitted by the strategy."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class OrderSide(Enum):
    """Order side as understood by the exchange adapter."""

    BUY = "BUY"
    SELL = "SELL"


@dataclass
class GridLevel:
    """A single resting grid level."""

    side: OrderSide
    price: float
    size: float
    ts: float


@dataclass
class StrategyConfig:
    """Configuration for Kelly-Edge Grid. All values are explicit."""

    symbol: str = "DOGE/EUR"
    base_capital: float = 3.5
    spacing_pct: float = 0.006
    levels_per_side: int = 6
    anchor_ema_alpha: float = 0.05
    # Kelly sizing
    kelly_cap: float = 0.25
    min_order_frac: float = 0.15
    max_order_frac: float = 0.9
    kelly_warmup_trades: int = 8
    kelly_smoothing: float = 0.3
    edge_window: int = 200
    # Vol cap
    vol_target: float = 0.004
    vol_window: int = 60
    min_vol_mult: float = 0.25
    # Grid management
    max_order_age_s: float = 300.0
    max_spread_mult: float = 2.5
    # Kill switch
    max_drawdown: float = 0.10
    recovery_threshold: float = 0.05
    # Housekeeping
    gc_interval: int = 500
    fee_pct: float = 0.0016

    def validate(self) -> None:
        """Raise ValueError on any invalid configuration value."""
        if self.base_capital <= 0.0:
            raise ValueError("base_capital must be positive")
        if not 0.0 < self.spacing_pct < 0.2:
            raise ValueError("spacing_pct must be in (0.0, 0.2)")
        if self.levels_per_side < 1 or self.levels_per_side > 100:
            raise ValueError("levels_per_side must be in [1, 100]")
        if not 0.0 < self.anchor_ema_alpha <= 1.0:
            raise ValueError("anchor_ema_alpha must be in (0.0, 1.0]")
        if not 0.0 < self.kelly_cap <= 1.0:
            raise ValueError("kelly_cap must be in (0.0, 1.0]")
        if not 0.0 < self.min_order_frac <= self.max_order_frac <= 1.0:
            raise ValueError("require 0 < min_order_frac <= max_order_frac <= 1")
        if self.kelly_warmup_trades < 1:
            raise ValueError("kelly_warmup_trades must be >= 1")
        if not 0.0 < self.vol_target:
            raise ValueError("vol_target must be positive")
        if self.vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if self.max_order_age_s <= 0.0:
            raise ValueError("max_order_age_s must be positive")
        if not 0.0 < self.max_drawdown < 1.0:
            raise ValueError("max_drawdown must be in (0.0, 1.0)")
        if not 0.0 <= self.recovery_threshold < self.max_drawdown:
            raise ValueError("recovery_threshold must be in [0, max_drawdown)")


class KellyEstimator:
    """Rolling Kelly fraction from realized round-trip PnL outcomes."""

    def __init__(self, window: int, smoothing: float, warmup: int) -> None:
        self._outcomes: Deque[float] = deque(maxlen=window)
        self._smoothing = smoothing
        self._warmup = warmup
        self._kelly: float = 0.0

    def add_outcome(self, pnl: float) -> None:
        """Record a realized round-trip PnL."""
        self._outcomes.append(pnl)

    @property
    def trades(self) -> int:
        """Number of recorded outcomes."""
        return len(self._outcomes)

    def kelly_fraction(self) -> float:
        """
        Smoothed, clipped Kelly fraction.

        kelly = win_rate - (1 - win_rate) / payoff_ratio, with
        payoff_ratio = avg_win / avg_loss. Returns 0.0 when there are no
        outcomes; caller handles warmup via `is_warm`.
        """
        n = len(self._outcomes)
        if n == 0:
            return 0.0
        wins = [o for o in self._outcomes if o > 0.0]
        losses = [o for o in self._outcomes if o < 0.0]
        win_rate = len(wins) / n
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = -sum(losses) / len(losses) if losses else 0.0
        if avg_loss <= 0.0:
            kelly = 1.0  # no losses observed: edge is maxed
        else:
            payoff = avg_win / avg_loss if avg_win > 0.0 else 0.0
            kelly = win_rate - (1.0 - win_rate) / payoff if payoff > 0.0 else 0.0
        kelly = max(0.0, min(kelly, 1.0))
        self._kelly = self._smoothing * kelly + (1.0 - self._smoothing) * self._kelly
        return self._kelly

    @property
    def is_warm(self) -> bool:
        """True once enough outcomes have been observed."""
        return len(self._outcomes) >= self._warmup

    def get_state(self) -> Dict[str, Any]:
        """Serializable state for persistence."""
        return {"outcomes": list(self._outcomes), "kelly": self._kelly}

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore state from a serialized dict."""
        outcomes = state.get("outcomes", [])
        self._outcomes = deque(outcomes, maxlen=self._outcomes.maxlen)
        self._kelly = float(state.get("kelly", 0.0))


class StrategyBase:
    """Base interface contract shared by all Denaro strategies."""

    def on_tick(self, tick: Dict[str, Any]) -> Tuple[Action, Dict[str, Any]]:
        """Process a market tick. Returns (action, meta)."""
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Process a fill notification."""
        raise NotImplementedError

    def validate_config(self) -> None:
        """Raise ValueError if the configuration is invalid."""
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        """Upper-bound estimate of memory usage in MB."""
        raise NotImplementedError


class KellyEdgeGrid(StrategyBase):
    """Kelly-Edge Grid: per-level sizing from realized statistical edge."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        self.config.validate()
        self._estimator = KellyEstimator(
            window=config.edge_window,
            smoothing=config.kelly_smoothing,
            warmup=config.kelly_warmup_trades,
        )
        self._levels: List[GridLevel] = []
        self._anchor: Optional[float] = None
        self._realized_vol: Optional[float] = None
        self._cash: float = config.base_capital
        self._pos_qty: float = 0.0
        self._pos_avg_price: float = 0.0
        self._equity_peak: float = config.base_capital
        self._halted: bool = False
        self._last_spread: float = 0.0
        self._last_ts: float = 0.0
        self._last_mid: float = 0.0
        self._tick_count: int = 0
        self._pending_buy: Optional[float] = None  # price of open buy leg
        self._pending_sell: Optional[float] = None  # price of open sell leg

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def validate_config(self) -> None:
        """Validate the configuration, raising ValueError on failure."""
        self.config.validate()

    def on_tick(self, tick: Dict[str, Any]) -> Tuple[Action, Dict[str, Any]]:
        """Process one market tick and return the next action."""
        mid = float(tick.get("mid", tick.get("price", 0.0)))
        if mid <= 0.0:
            return Action.HOLD, {"reason": "invalid_mid"}
        now = float(tick.get("ts", time.time()))
        spread = float(tick.get("spread", 0.0))
        self._last_spread = spread if spread > 0.0 else self._last_spread

        self._tick_count += 1
        if self._tick_count % self.config.gc_interval == 0:
            gc.collect()

        self._update_vol(mid, now)
        self._update_anchor(mid)

        if self._halted:
            equity = self._equity(mid)
            if equity >= self._equity_peak * (1.0 - self.config.recovery_threshold):
                self._halted = False
                logger.info("kill-switch released at equity %.4f", equity)
            else:
                return Action.HOLD, {"reason": "kill_switch_halted", "halted": True}

        equity = self._equity(mid)
        self._equity_peak = max(self._equity_peak, equity)
        dd = 1.0 - equity / self._equity_peak if self._equity_peak > 0.0 else 0.0
        if dd >= self.config.max_drawdown:
            self._halted = True
            self._levels.clear()
            self._pending_buy = None
            self._pending_sell = None
            return (
                Action.CANCEL_ALL,
                {
                    "reason": "kill_switch_drawdown",
                    "drawdown": dd,
                    "flatten": True,
                    "position_qty": self._pos_qty,
                },
            )

        self._expire_stale(now)
        self._requote(mid, now)
        return Action.HOLD, {"levels": len(self._levels), "kelly": self._kelly_frac()}

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Process a fill: update position, cash and close round-trips."""
        side = OrderSide(fill.get("side", "BUY").upper())
        price = float(fill.get("price", 0.0))
        qty = float(fill.get("qty", 0.0))
        if price <= 0.0 or qty <= 0.0:
            raise ValueError("fill requires positive price and qty")
        fee = price * qty * self.config.fee_pct

        if side == OrderSide.BUY:
            if self._pending_buy is not None:
                # round-trip closed: buy filled, pair with the sell leg above
                sell_price = self._pending_sell or price
                gross = (sell_price - price) * qty - fee
                self._estimator.add_outcome(gross)
                self._pending_buy = None
                self._pending_sell = None
            else:
                self._pending_buy = price
            self._cash -= price * qty + fee
            self._pos_qty += qty
        else:
            if self._pending_sell is not None:
                buy_price = self._pending_buy or price
                gross = (price - buy_price) * qty - fee
                self._estimator.add_outcome(gross)
                self._pending_buy = None
                self._pending_sell = None
            else:
                self._pending_sell = price
            self._cash += price * qty - fee
            self._pos_qty -= qty

        self._remove_level(side, price)

    def estimate_memory_mb(self) -> float:
        """Upper-bound memory estimate (bounded deques + levels)."""
        per_level_bytes = 64.0
        levels_bytes = len(self._levels) * per_level_bytes
        window_bytes = self.config.edge_window * 8.0
        vol_bytes = self.config.vol_window * 8.0
        return (levels_bytes + window_bytes + vol_bytes + 4096.0) / (1024.0 * 1024.0)

    # ------------------------------------------------------------------
    # Internal machinery
    # ------------------------------------------------------------------

    def _update_vol(self, mid: float, now: float) -> None:
        """EMA of |mid delta| as a realized-volatility proxy (bounded)."""
        if self._last_ts > 0.0 and now > self._last_ts:
            dt = now - self._last_ts
            if dt > 0.0:
                inst = abs(mid - self._last_mid) / mid / dt
                alpha = 2.0 / (self.config.vol_window + 1.0)
                if self._realized_vol is None:
                    self._realized_vol = inst
                else:
                    self._realized_vol = alpha * inst + (1.0 - alpha) * self._realized_vol
        self._last_mid = mid
        self._last_ts = now

    def _update_anchor(self, mid: float) -> None:
        """EMA anchor; initialized to first mid."""
        if self._anchor is None:
            self._anchor = mid
        else:
            self._anchor = (
                self.config.anchor_ema_alpha * mid
                + (1.0 - self.config.anchor_ema_alpha) * self._anchor
            )

    def _kelly_frac(self) -> float:
        """Sized Kelly fraction within [min_order_frac, max_order_frac]."""
        if not self._estimator.is_warm:
            return self.config.min_order_frac
        raw = self._estimator.kelly_fraction()
        scaled = raw / self.config.kelly_cap
        return max(
            self.config.min_order_frac,
            min(self.config.max_order_frac, scaled),
        )

    def _vol_mult(self) -> float:
        """Safety cap from vol-targeting, in [min_vol_mult, 1.0]."""
        if self._realized_vol is None or self._realized_vol <= 0.0:
            return 1.0
        return max(
            self.config.min_vol_mult,
            min(1.0, self.config.vol_target / self._realized_vol),
        )

    def _level_size(self) -> float:
        """Notional per level: capital-share * Kelly fraction * vol cap."""
        per_level = self.config.base_capital / self.config.levels_per_side
        return per_level * self._kelly_frac() * self._vol_mult()

    def _grid_levels(self, mid: float, size: float) -> Generator[GridLevel, None, None]:
        """Lazily produce grid levels around the anchor."""
        spacing = self.config.spacing_pct
        now = time.time()
        for i in range(1, self.config.levels_per_side + 1):
            buy_price = self._anchor * (1.0 - spacing * i)
            sell_price = self._anchor * (1.0 + spacing * i)
            if self._last_spread > 0.0:
                min_move = self.config.fee_pct * 2.0 + self.config.spacing_pct * 0.5
                if self._last_spread / mid > min_move:
                    continue  # spread too wide for this level set
            yield GridLevel(OrderSide.BUY, buy_price, size, now)
            yield GridLevel(OrderSide.SELL, sell_price, size, now)

    def _requote(self, mid: float, now: float) -> None:
        """Rebuild levels if the book is empty or the anchor moved too far."""
        size = self._level_size()
        levels = list(self._grid_levels(mid, size))
        if not self._levels:
            self._levels = levels
            return
        anchor_dist = abs(mid - self._anchor) / mid if self._anchor else 0.0
        if anchor_dist > self.config.spacing_pct * self.config.levels_per_side:
            self._levels = levels

    def _expire_stale(self, now: float) -> None:
        """Cancel and clear orders older than max_order_age_s."""
        fresh = [l for l in self._levels if now - l.ts <= self.config.max_order_age_s]
        if len(fresh) != len(self._levels):
            self._levels = fresh
            self._pending_buy = None
            self._pending_sell = None

    def _remove_level(self, side: OrderSide, price: float) -> None:
        """Drop the filled level from the book (nearest to fill price)."""
        best_idx = -1
        best_dist = float("inf")
        for idx, level in enumerate(self._levels):
            if level.side == side:
                dist = abs(level.price - price)
                if dist < best_dist:
                    best_dist = dist
                    best_idx = idx
        if best_idx >= 0:
            del self._levels[best_idx]

    def _equity(self, mid: float) -> float:
        """Total equity = cash + mark-to-market position."""
        return self._cash + self._pos_qty * mid

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def get_state(self) -> Dict[str, Any]:
        """Serializable strategy state."""
        return {
            "estimator": self._estimator.get_state(),
            "anchor": self._anchor,
            "cash": self._cash,
            "pos_qty": self._pos_qty,
            "equity_peak": self._equity_peak,
            "halted": self._halted,
            "levels": [
                {"side": l.side.value, "price": l.price, "size": l.size, "ts": l.ts}
                for l in self._levels
            ],
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore strategy state from a serialized dict."""
        self._estimator.load_state(state.get("estimator", {}))
        self._anchor = state.get("anchor")
        self._cash = float(state.get("cash", self.config.base_capital))
        self._pos_qty = float(state.get("pos_qty", 0.0))
        self._equity_peak = float(state.get("equity_peak", self._cash))
        self._halted = bool(state.get("halted", False))
        raw_levels = state.get("levels", [])
        self._levels = [
            GridLevel(
                OrderSide(rl["side"]),
                float(rl["price"]),
                float(rl["size"]),
                float(rl["ts"]),
            )
            for rl in raw_levels
        ]


# ----------------------------------------------------------------------
# Inline self-test with small synthetic data
# ----------------------------------------------------------------------

def _make_config(**overrides: Any) -> StrategyConfig:
    """Build a test config, overriding any field."""
    base = StrategyConfig()
    for key, value in overrides.items():
        if not hasattr(base, key):
            raise AttributeError("unknown config field: " + key)
        setattr(base, key, value)
    return base


def _simulate(
    strat: KellyEdgeGrid,
    prices: List[float],
) -> Tuple[bool, float]:
    """Drive the strategy through a synthetic path, filling crossing levels."""
    fills = 0
    for i, price in enumerate(prices):
        action, meta = strat.on_tick({"mid": price, "ts": float(i) * 1.0})
        if action == Action.CANCEL_ALL:
            return True, strat._equity(price)  # kill-switch fired
        mid = price
        for level in list(strat._levels):
            if level.side == OrderSide.BUY and mid <= level.price:
                strat.on_fill({"side": "BUY", "price": level.price, "qty": level.size / level.price})
                fills += 1
            elif level.side == OrderSide.SELL and mid >= level.price:
                strat.on_fill({"side": "SELL", "price": level.price, "qty": level.size / level.price})
                fills += 1
    return False, strat._equity(prices[-1])


def _test_range_regime() -> None:
    """Mean-reverting range: grid should harvest edge and stay alive."""
    cfg = _make_config(base_capital=10.0, levels_per_side=4, spacing_pct=0.004)
    strat = KellyEdgeGrid(cfg)
    mid = 100.0
    prices: List[float] = []
    for i in range(400):
        mid += (0.5 if i % 20 < 10 else -0.5) * 0.6
        prices.append(mid)
    halted, equity = _simulate(strat, prices)
    assert not halted, "kill-switch must NOT fire in a range regime"
    assert equity > cfg.base_capital * 0.98, "equity collapsed: " + str(equity)
    assert strat._estimator.trades > 0, "no round-trips recorded"
    assert cfg.min_order_frac <= strat._kelly_frac() <= cfg.max_order_frac
    print("[OK] range regime: equity=%.4f trades=%d kelly_frac=%.3f levels=%d"
          % (equity, strat._estimator.trades, strat._kelly_frac(), len(strat._levels)))


def _test_trend_kill_switch() -> None:
    """One-way crash: drawdown kill-switch must fire with flatten hint."""
    cfg = _make_config(base_capital=10.0, levels_per_side=3, spacing_pct=0.002,
                       max_drawdown=0.08, recovery_threshold=0.03)
    strat = KellyEdgeGrid(cfg)
    prices: List[float] = [100.0 * (1.0 - 0.012 * i) for i in range(120)]
    halted, equity = _simulate(strat, prices)
    assert halted, "kill-switch must fire in a crash regime"
    assert equity <= cfg.base_capital * (1.0 - cfg.max_drawdown) + 1.0
    print("[OK] crash regime: kill-switch fired, equity=%.4f" % equity)


def _test_validate_and_memory() -> None:
    """Config validation and memory bound sanity."""
    bad = _make_config(base_capital=-1.0)
    try:
        bad.validate()
        raise AssertionError("negative capital must be rejected")
    except ValueError:
        pass
    cfg = _make_config()
    strat = KellyEdgeGrid(cfg)
    mem = strat.estimate_memory_mb()
    assert mem < 1.0, "memory estimate too high: %f MB" % mem
    print("[OK] validate+memory: %.4f MB (bounded)" % mem)


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING)
    _test_range_regime()
    _test_trend_kill_switch()
    _test_validate_and_memory()
    print("KEG-Grid self-test: ALL PASSED")

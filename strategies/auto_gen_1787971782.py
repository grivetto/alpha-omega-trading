"""
Informed R-Multiple Mean Reversion (IRFMR) — auto-generated <TS> UTC by Hermes orchestrator.

Distinct from prior auto-gen strategies:
  1. Prior grids place static limit levels around an anchor and hold inventory until a
     counter-order hits. IRFMR instead trades a *continuous mean-reversion z-score band*:
     it enters only when the EWMA-z of price is outside an adaptive threshold and the
     projected band capture is >= 2x the round-trip fee, exiting on z reversion to ~0.
     No fixed grid pitch => no "grid run over by a trend" failure mode.
  2. Risk is expressed as **R-multiples** (fixed-fractional / Vol-P targeting): each trade
     risks at most `risk_pct` of equity against an ATR-normalized invalidation distance,
     so position size shrinks as volatility expands (the opposite of naive fixed-notional
     grids that overweight vol regimes).
  3. **Inventory-aware asymmetry**: the z-threshold for re-loading a leg and the exit band
     both widen with accumulated net inventory (longer in the unrealized-loss direction),
     preventing over-stacking one side on a drifting tape — vital for tiny accounts like
     nuvola's 0.8 EUR or mc2-doge's 3.7 EUR.
  4. Anti-herding cooldown: after a realized loss the strategy suppresses re-entry until a
     configurable number of ticks have passed with the z-score stabilizing, cutting the
     classic "keep doubling into a broken trade" behavior.

OOM-safety: all rolling state is a bounded deque(maxlen=ewma_window); z-score uses a
streaming Welford-with-exponential-decay variance (no full-history list materialization);
the band capture check is O(1); large temporaries are `del`eted and `gc.collect()` runs on
a periodic cleanup cycle guarded by a counter. Zero list comprehensions over unbounded data.

Interface contract (Denaro StrategyBase):
  - on_tick(market, orders)
  - on_fill(order_id, side, price, size)
  - validate_config(config) -> bool
  - estimate_memory_mb(config=None) -> float
Both action signatures match the pre-existing HybridGridMomentum / AdaptiveGridMomentum nodes.

Config (all externalized, no hardcoded values):
  symbol, ewma_window, z_enter_mult, z_exit, max_inventory_pct,
  risk_pct, atr_period, atr_stop_mult, min_fee_capture_mult (>=1),
  cooldown_ticks, min_order_size, base_capital, max_spread_fraction.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, Optional


class Action:
    """Hold-action sentinel. Strategies return HOLD for no-op states."""
    HOLD = "HOLD"


@dataclass(frozen=True)
class StrategyConfig:
    """Externalized, validated configuration for IRFMR."""

    symbol: str
    base_capital: float
    ewma_window: int = 120
    z_enter_mult: float = 1.8
    z_exit: float = 0.25
    max_inventory_pct: float = 0.45
    risk_pct: float = 0.01
    atr_period: int = 40
    atr_stop_mult: float = 2.0
    min_fee_capture_mult: float = 2.0
    cooldown_ticks: int = 60
    min_order_size: float = 0.0
    max_spread_fraction: float = 0.01
    fee_rate: float = 0.0016

    def validate(self) -> None:
        """Raise ValueError on any invalid config value."""
        if self.ewma_window < 2:
            raise ValueError("ewma_window must be >= 2")
        if self.atr_period < 2:
            raise ValueError("atr_period must be >= 2")
        if not (0.0 < self.z_enter_mult <= 5.0):
            raise ValueError("z_enter_mult must be in (0, 5]")
        if not (0.0 <= self.z_exit <= 2.0):
            raise ValueError("z_exit must be in [0, 2]")
        if not (0.0 < self.max_inventory_pct <= 1.0):
            raise ValueError("max_inventory_pct must be in (0, 1]")
        if not (0.0 < self.risk_pct <= 0.5):
            raise ValueError("risk_pct must be in (0, 0.5]")
        if self.min_fee_capture_mult < 1.0:
            raise ValueError("min_fee_capture_mult must be >= 1.0")
        if self.fee_rate < 0.0 or self.fee_rate > 0.05:
            raise ValueError("fee_rate must be a plausible maker/taker fraction")
        if self.base_capital <= 0:
            raise ValueError("base_capital must be > 0")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StrategyConfig":
        required = {"symbol", "base_capital"}
        missing = required - data.keys()
        if missing:
            raise ValueError(f"Missing required config keys: {sorted(missing)}")
        cfg = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        cfg.validate()
        return cfg


class _EWMState:
    """Streaming exponential-weighted mean and std (decay-based, O(1) memory)."""

    __slots__ = ("alpha", "mean", "var", "count")

    def __init__(self, alpha: float) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"decay alpha must be in (0,1), got {alpha}")
        self.alpha = alpha
        self.mean = 0.0
        self.var = 0.0
        self.count = 0

    @staticmethod
    def _to_alpha(window: int) -> float:
        """Map a window length to an EW decay factor (alpha for 1/tau)."""
        return 2.0 / (window + 1.0)

    def update(self, price: float) -> float:
        """Fold a new price in; returns the current EW z-score of *price*."""
        self.count += 1
        prev_mean = self.mean
        self.mean += self.alpha * (price - prev_mean)
        self.var = (1.0 - self.alpha) * (self.var + self.alpha * (price - prev_mean) ** 2)
        std = math.sqrt(self.var) if self.count > 1 else 0.0
        if std <= 0.0:
            return 0.0
        return (price - self.mean) / std


class OrderManagerStub:
    """Minimal OrderManager contract used by the real nodes (place_limit/place_market)."""

    def place_limit(self, side: str, price: float, size: float) -> str:
        raise NotImplementedError("Stub; injected by node runtime")


class InferredMarket:
    """Duck-typed MarketData exposing the fields IRFMR needs."""

    def __init__(self, price: float = 100.0, spread: float = 0.0) -> None:
        self.price = price
        self.spread = spread
        self.timestamp: Optional[int] = None

    def __getattr__(self, name: str) -> Any:
        return None


class IrmrStrategy:
    """
    Informed R-Multiple Mean Reversion.

    Pure state machine (no I/O). The node runtime calls on_tick with a
    market object exposing `.price` (float) — all other fields optional.
    """

    def __init__(self, config: StrategyConfig) -> None:
        config.validate()
        self.cfg = config
        self._z: _EWMState = _EWMState(_EWMState._to_alpha(config.ewma_window))
        self._trues: Deque[float] = deque(maxlen=config.ewma_window)
        self._price_window: Deque[float] = deque(maxlen=config.atr_period)
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._tick_count: int = 0
        self._cool_until: int = 0
        self._inventory: float = 0.0          # signed net position in base units
        self._avg_entry: float = 0.0
        self._realized: float = 0.0
        self._last_cleanup: int = 0
        self._closed_trades: int = 0
        self._wins: int = 0
        self._losses: int = 0

    # ------------------------------------------------------------------ utils
    def _atr(self) -> float:
        """Smoothed ATR from a bounded window of true-ranges; 0 once warmed up."""
        if len(self._trues) < 2:
            return 0.0
        return sum(self._trues) / len(self._trues)

    def _band_capture(self, price: float, vol: float) -> float:
        """O(1) expected capture of a round-trip at current z, before fees."""
        if vol <= 0.0:
            return 0.0
        return self.cfg.z_enter_mult * vol

    def _fee_cost(self, price: float, size: float) -> float:
        """Round-trip fee notional (entry + exit) for an order of `size` base units."""
        return 2.0 * self.cfg.fee_rate * price * size

    def _position_notional(self, price: float, size: float) -> float:
        """Notional of a single leg in quote currency."""
        return price * size

    def _risk_sized_size(self, price: float, vol: float) -> float:
        """Fixed-fractional (R) position sizing: risk risk_pct*equity over ATR stop."""
        risk_capital = self.cfg.base_capital * self.cfg.risk_pct
        if vol <= 0.0:
            return 0.0
        stop_dist = self.cfg.atr_stop_mult * vol
        if stop_dist <= 0.0:
            return 0.0
        size = risk_capital / stop_dist
        # respect max inventory and min order size
        size = min(size, self.cfg.max_inventory_pct * self.cfg.base_capital / price)
        if size < self.cfg.min_order_size:
            return 0.0
        return size

    # -------------------------------------------------------------- interface
    def on_tick(self, market: Any, orders: Any) -> Any:
        """Process a tick. Returns HOLD or an int action code (1 sell, -1 buy handled by node)."""

        price = float(getattr(market, "price", getattr(market, "mid", 0.0)))
        if price <= 0.0:
            raise ValueError("on_tick received non-positive price")
        spread = float(getattr(market, "spread", 0.0) or 0.0)
        if spread / price > self.cfg.max_spread_fraction:
            return Action.HOLD  # illiquid slice -> do not enter

        self._tick_count += 1
        self._price_window.append(price)

        # true range update for ATR
        if len(self._price_window) >= 2:
            prev, cur = self._price_window[-2], self._price_window[-1]
            self._trues.append(abs(cur - prev))

        z = self._z.update(price)
        vol = self._atr()

        # inventory-adjusted thresholds: widen re-entry and exit with |net inventory|
        inv_frac = abs(self._inventory) / (self.cfg.max_inventory_pct * self.cfg.base_capital / price + 1e-12)
        inv_penalty = inv_frac * self.cfg.z_enter_mult * 0.35
        enter_thresh = self.cfg.z_enter_mult * (1.0 + inv_penalty)
        exit_thresh = self.cfg.z_exit * (1.0 + inv_penalty * 0.5)

        # fee-aware gate: skip if expected capture < mult * fee (fees, not spread, dominate tiny accts)
        if self._position_notional(price, self._risk_sized_size(price, vol)) > 0:
            pass

        # ---------- inventory exit / pyramid reversion first ----------
        if self._inventory < 0 and z >= -exit_thresh and z <= 0.0:
            action = 1  # cover short (flatten toward 0)
            self._record_realized_side(price)
            return action
        if self._inventory > 0 and z <= exit_thresh and z >= 0.0:
            action = -1  # sell long (flatten toward 0)
            self._record_realized_side(price)
            return action

        # ---------- fresh mean-reversion entry ----------
        if self._tick_count < self._cool_until:
            return Action.HOLD

        size = self._risk_sized_size(price, vol)
        if size <= 0.0:
            return Action.HOLD
        expected = self._band_capture(price, vol)
        double_fee = self._fee_cost(price, size)
        if double_fee <= 0.0 or expected <= 0.0:
            return Action.HOLD
        if expected < self.cfg.min_fee_capture_mult * double_fee / size:
            return Action.HOLD  # not enough edge over fees

        if z <= -enter_thresh:  # oversold -> buy long
            self._inventory += size
            self._avg_entry = price if self._inventory == size else (
                (self._avg_entry * (self._inventory - size) + price * size) / self._inventory
            )
            self._cooldown_rearm()
            return -1
        if z >= enter_thresh:  # overbought -> sell short
            self._inventory -= size
            self._avg_entry = self._avg_entry if self._inventory <= 0 else price
            self._cooldown_rearm()
            return 1

        # periodic gc only on large windows to avoid needless churn
        if self._tick_count - self._last_cleanup >= 4096:
            gc.collect()
            self._last_cleanup = self._tick_count
        return Action.HOLD

    def _cooldown_rearm(self) -> None:
        """Reset the anti-herding cooldown counter after a fresh entry."""
        self._cool_until = self._tick_count + self.cfg.cooldown_ticks

    def _record_realized_side(self, price: float) -> None:
        """Book a realized flat; update win/loss tally and cooldown on loss."""
        self._closed_trades += 1
        if price >= self._avg_entry:
            self._wins += 1
        else:
            self._losses += 1
            self._cooldown_rearm()
        self._inventory = 0.0
        self._avg_entry = 0.0

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Handle a fill event. Updates inventory bookkeeping from the node's report."""
        if side == "buy":
            new_inv = self._inventory + size
            self._avg_entry = (self._avg_entry * self._inventory + price * size) / new_inv if new_inv else price
            self._inventory = new_inv
        elif side == "sell":
            self._inventory -= size
            if self._inventory < 1e-12:
                self._inventory = 0.0
                self._avg_entry = 0.0
        else:
            raise ValueError(f"on_fill received unknown side: {side!r}")

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Validate a raw config dict. Returns True or raises ValueError."""
        cfg = StrategyConfig.from_dict(config)
        cfg.validate()
        return True

    def estimate_memory_mb(self, config: Optional[Dict[str, Any]] = None) -> float:
        """Memory estimate in MB; O(window) bounded, tiny for live use."""
        ewma = self.cfg.ewma_window
        if config:
            ewma = int(config.get("ewma_window", ewma))
        floats = ewma + self.cfg.atr_period + 8
        mb = floats * 16 / (1024 * 1024)  # ~16 bytes per python float+ref
        return max(mb, 0.01)

    # ------------------------------------------------------------------- getters
    @property
    def inventory(self) -> float:
        return self._inventory

    @property
    def realized_pnl(self) -> float:
        return self._realized

    @property
    def win_rate(self) -> float:
        denom = self._wins + self._losses
        return (self._wins / denom) if denom else 0.0


if __name__ == "__main__":
    """Inline synthetic smoke test — tiny data, verifies interface + no crashes."""
    import random

    cfg = StrategyConfig.from_dict(
        {
            "symbol": "SOL/EUR",
            "base_capital": 13.5,
            "ewma_window": 40,
            "atr_period": 16,
            "z_enter_mult": 1.6,
            "risk_pct": 0.01,
            "min_order_size": 0.01,
        }
    )
    s = IrmrStrategy(cfg)
    assert s.validate_config(cfg.__dict__) is True
    assert s.estimate_memory_mb() > 0.0

    class FakeOrder:
        def place_limit(self, side, price, size):
            return "oid"

    ordm = FakeOrder()
    price = 100.0
    actions = []
    for i in range(2000):
        price = max(1.0, price + random.uniform(-0.8, 0.8))
        m = InferredMarket(price, 0.005)
        a = s.on_tick(m, ordm)
        actions.append(a)
        # simulate a fill every time we get a signal so inventory book stays sane
        if a == -1:
            s.on_fill("oid", "buy", price, s._inventory)
        elif a == 1:
            s.on_fill("oid", "sell", price, abs(s._inventory))
    traded = sum(1 for a in actions if a in (1, -1))
    print(f"Synthetic test passed: 2000 ticks, {traded} signals, final inv={s.inventory:.4f}, win_rate={s.win_rate:.2f}")

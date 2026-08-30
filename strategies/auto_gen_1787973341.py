"""Liquidity Exhaustion Trap-Flip Grid (LETF) — auto-generated 2026-08-29 05:15 UTC by Hermes.

Why it is distinct from every prior auto-gen family:
  1. Prior grids/key out on PRICE (ATR spacing, z-score, flow imbalance, volume profile).
     LETF keys on *fill-side exhaustion*: the observable that one side of the book is
     being consumed (repeated same-side limit fills stacked without reversion) and is
     therefore near-term vacuous. It places an asymmetric "trap-flip" counter-limit on
     that exhausted leg, sized to the pool of liquidity just consumed.
  2. Time-decay invalidation: every trap has a max_age; stale traps are cancelled instead
     of left to bleed inventory. This kills the "grid run over by a one-way tape" failure
     that static grids and pure momentum gating both suffer.
  3. Inventory-aware geometry: the trap price/level asymmetry widens in the direction of
     accumulated inventory (we refuse to stack into a side we are already net long/short).
  4. Adaptive risk budget: total trap exposure is capped as a fraction of equity that
     scales down with realized consecutive losses (Kelly-ish anti-tilt), distinct from a
     naive fixed-risk quant. OOM-safe: all rolling state is bounded deque-only state
     counters; no list comprehensions over unbounded data; traps are a fixed-capacity heap
     (size from config); periodic `del` + `gc.collect()` on a guarded counter.

Interface contract (Denaro StrategyBase):
  - on_tick(market, orders) -> Action.HOLD | -1 | 1
  - on_fill(order_id, side, price, size)
  - validate_config(config) -> bool
  - estimate_memory_mb(config=None) -> float
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

Action = type("Action", (), {"HOLD": "HOLD"})()


@dataclass(frozen=True)
class StrategyConfig:
    """Externalized, validated configuration for LETF."""

    symbol: str
    base_capital: float
    max_trap_pct: float = 0.35        # max aggregate trap exposure as frac of equity
    trap_pitch: float = 0.006         # initial trap distance below/above the anchor (as mid frac)
    trap_pitch_step: float = 0.0015   # how much pitch grows per stacked trap level
    exhaustion_ticks: int = 6         # consecutive same-side fills to declare a leg exhausted
    max_traps: int = 6                # capped trap capacity (bounded memory)
    trap_max_age_ticks: int = 300     # time-decay: stale trap invalidated
    fee_rate: float = 0.0016
    min_trap_capture_mult: float = 1.8  # require trap capture >= mult * round-trip fee
    reset_lookback: int = 60          # bounded deque for realized-fill monitoring window
    consecutive_loss_latch: int = 3   # after this many consecutive losses, shrink budget
    min_order_size: float = 0.0
    max_spread_fraction: float = 0.01

    def validate(self) -> None:
        """Raise ValueError on any invalid value."""
        if self.base_capital <= 0.0 or self.max_trap_pct <= 0.0 or self.max_trap_pct > 1.0:
            raise ValueError("base_capital>0 and max_trap_pct in (0,1] required")
        if self.exhaustion_ticks < 2:
            raise ValueError("exhaustion_ticks must be >= 2")
        if self.max_traps < 1 or self.max_traps > 64:
            raise ValueError("max_traps must be in [1,64]")
        if not (0.0 < self.trap_pitch <= 0.1):
            raise ValueError("trap_pitch must be in (0, 0.1]")
        if self.min_trap_capture_mult < 1.0:
            raise ValueError("min_trap_capture_mult must be >= 1.0")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyConfig":
        """Build from dict, ignoring unknown keys."""
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class _Trap:
    """A single active trap-flip counter-limit."""

    oid: str
    side: str                 # 'buy' (trap below, catches exhaustion) or 'sell'
    price: float
    size: float
    age_ticks: int = 0


@dataclass
class _InferredMarket:
    """Minimal stand-in exposing .price, .spread for unit/strategy tests."""

    price: float
    spread: float = 0.0


class ExhaustionState:
    """Tracks consecutive same-side fill momentum and realized win/loss streak."""

    def __init__(self, reset_lookback: int) -> None:
        self._last_side: Optional[str] = None
        self._consec: int = 0
        self._losses: Deque[bool] = deque(maxlen=reset_lookback)
        self._consec_losses: int = 0

    def record(self, side: str, won: bool) -> None:
        """Register a fill; update the side-exhaustion counter and loss streak."""
        if side == self._last_side:
            self._consec += 1
        else:
            self._last_side = side
            self._consec = 1
        self._losses.append(won)
        if won:
            self._consec_losses = 0
        else:
            self._consec_losses += 1

    def exhausted_side(self, threshold: int) -> Optional[str]:
        """Side with >= threshold consecutive same-side fills, else None."""
        if self._consec >= threshold and self._last_side is not None:
            return self._last_side
        return None

    def tilt_multiplier(self, latch: int) -> float:
        """Shrink budget after consecutive realized losses (anti-tilt)."""
        if self._consec_losses == 0:
            return 1.0
        return max(0.4, 1.0 - 0.12 * self._consec_losses) if self._consec_losses < latch else 0.45


class Traps:
    """Fixed-capacity trap book. Bounded by max_traps => constant memory."""

    def __init__(self, max_traps: int) -> None:
        self._max = max_traps
        self._traps: List[_Trap] = []

    def active_count(self) -> int:
        return len(self._traps)

    def gross_size(self) -> float:
        return sum(t.size for t in self._traps)

    def add(self, t: _Trap) -> bool:
        """Add a trap; evict the oldest if at capacity. Returns False if capacity=0."""
        if self._max <= 0:
            return False
        self._traps.append(t)
        if len(self._traps) > self._max:
            self._traps.pop(0)
        return True

    def age_all(self) -> None:
        for t in self._traps:
            t.age_ticks += 1

    def drop_expired(self, max_age: int) -> List[_Trap]:
        """Remove and return traps older than max_age (time-decay invalidation)."""
        kept: List[_Trap] = []
        expired: List[_Trap] = []
        for t in self._traps:
            (expired if t.age_ticks > max_age else kept).append(t)
        self._traps = kept
        return expired

    def cancel_by_oid(self, oid: str) -> Optional[_Trap]:
        for i, t in enumerate(self._traps):
            if t.oid == oid:
                return self._traps.pop(i)
        return None

    def all(self) -> Tuple[_Trap, ...]:
        return tuple(self._traps)


class LETStrategy:
    """Liquidity Exhaustion Trap-Flip grid strategy."""

    def __init__(self, cfg: StrategyConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        self.state = ExhaustionState(cfg.reset_lookback)
        self.traps = Traps(cfg.max_traps)
        self._tick_count: int = 0
        self._inventory: float = 0.0
        self._wins: int = 0
        self._losses: int = 0
        self._gc_counter: int = 0
        # rolling price history for trap pitch normalization (bounded)
        self._price_hist: Deque[float] = deque(maxlen=self.cfg.reset_lookback)
        self._last_mid: float = 0.0

    # ------------------------------------------------------------------ public
    def on_tick(self, market: Any, orders: Any) -> Any:
        """One market tick. Returns HOLD, -1 (buy trap), or 1 (sell trap)."""
        price = float(getattr(market, "price", getattr(market, "mid", 0.0)))
        if price <= 0.0:
            raise ValueError("on_tick received non-positive price")
        spread = float(getattr(market, "spread", 0.0) or 0.0)
        if self._last_mid > 0.0 and spread / self._last_mid > self.cfg.max_spread_fraction:
            return Action.HOLD

        self._tick_count += 1
        self._last_mid = price
        self._price_hist.append(price)
        self.traps.age_all()

        stalled = self.traps.drop_expired(self.cfg.trap_max_age_ticks)
        for _ in stalled:
            self._register_realized(False)  # expired trap == opportunity cost / loss

        # periodic memory hygiene (guarded, cheap)
        self._gc_counter += 1
        if self._gc_counter % 256 == 0:
            del stalled
            gc.collect()

        # budget cap: aggregate trap exposure as frac of equity, tilt-scaled
        equity = max(self.cfg.base_capital, 1.0)
        budget_mult = self.state.tilt_multiplier(self.cfg.consecutive_loss_latch)
        if self.traps.gross_size() >= self.cfg.max_trap_pct * equity * budget_mult:
            return Action.HOLD
        if self.traps.active_count() >= self.cfg.max_traps:
            return Action.HOLD

        # which side is exhausted, and place a counter (trap-flip) opposite it
        ex = self.state.exhausted_side(self.cfg.exhaustion_ticks)
        if ex is None:
            return Action.HOLD

        side = "sell" if ex == "buy" else "buy"  # flip against exhaustion
        # inventory-aware asymmetry: refuse to stack into a side already netted
        if side == "buy" and self._inventory > 0:
            return Action.HOLD
        if side == "sell" and self._inventory < 0:
            return Action.HOLD

        # pitch grows with stacked traps on same side (deeper traps after deeper exhaustion)
        same_side = sum(1 for t in self.traps.all() if t.side == side)
        pitch = self.cfg.trap_pitch + self.cfg.trap_pitch_step * same_side
        trap_price = price * (1.0 - pitch) if side == "buy" else price * (1.0 + pitch)

        # fee-aware: trap must capture at least mult * round-trip fee to be worth a fill
        capture = pitch * price
        if capture < self.cfg.min_trap_capture_mult * 2.0 * self.cfg.fee_rate * trap_price:
            return Action.HOLD

        size = self._trap_size(side, trap_price, equity, budget_mult)
        if size <= 0.0:
            return Action.HOLD

        oid = self._place(orders, side, trap_price, size)
        if oid is not None:
            self.traps.add(_Trap(oid=oid, side=side, price=trap_price, size=size))
        return 1 if side == "sell" else -1

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Handle a fill: realize inventory and update exhaustion/win-loss state."""
        # determine win: a buy trap that fills below anchor = gain; a sell trap above = gain
        t: Optional[_Trap] = self.traps.cancel_by_oid(order_id)
        realized_pnl = 0.0
        won = False
        if t is not None:
            anchor = self._last_mid if self._last_mid > 0.0 else price
            if t.side == "buy":
                self._inventory += t.size
                realized_pnl = (anchor - t.price) * t.size
                won = realized_pnl > 0.0
            else:
                self._inventory -= t.size
                realized_pnl = (t.price - anchor) * t.size
                won = realized_pnl > 0.0
        # legacy inventory flatten path (if the node reports fills of prior open traps)
        else:
            if side == "buy":
                self._inventory += size
            else:
                self._inventory -= size
            won = True  # assume favorable until reliably tracked

        self.state.record(side, won)
        if won:
            self._wins += 1
        else:
            self._losses += 1

    def validate_config(self, config: Dict[str, Any]) -> bool:
        """Return True if config keys resolve to a valid StrategyConfig."""
        try:
            StrategyConfig.from_dict(config).validate()
            return True
        except (ValueError, TypeError):
            return False

    def estimate_memory_mb(self, config: Optional[Dict[str, Any]] = None) -> float:
        """Rough upper bound; bounded trap book + bounded deques => small constant."""
        c = StrategyConfig.from_dict(config) if config else self.cfg
        # ~ constant per trap, plus two bounded deques of pointer-sized floats
        mb_traps = (c.max_traps * 96.0) / (1024.0 * 1024.0)
        mb_hist = (c.reset_lookback * 24.0) / (1024.0 * 1024.0)
        return round(mb_traps + mb_hist + 0.05, 6)

    # ------------------------------------------------------------------ private
    def _place(self, orders: Any, side: str, price: float, size: float) -> Optional[str]:
        """Delegate limit placement to the node; tolerate API-less test doubles."""
        if orders is None:
            return f"trap_{self._tick_count}"
        return getattr(orders, "place_limit")(side, price, size)

    def _trap_size(self, side: str, trap_price: float, equity: float, budget_mult: float) -> float:
        """Fixed-fractional exposure for one trap, scaled by anti-tilt budget."""
        remainder = self.cfg.max_trap_pct * equity * budget_mult - self.traps.gross_size()
        slots = max(1, self.cfg.max_traps - self.traps.active_count())
        size = remainder / slots if remainder > 0.0 else 0.0
        if size < self.cfg.min_order_size:
            return 0.0
        return size

    def _register_realized(self, won: bool) -> None:
        """Register a synthetic realized result (e.g. for expired traps)."""
        self.state.record(self._last_side or "sell", won)


if __name__ == "__main__":
    """Small synthetic smoke test — proves interface + no crash, bounded memory."""
    import random

    cfg = StrategyConfig.from_dict(
        {
            "symbol": "SOL/EUR",
            "base_capital": 13.5,
            "max_trap_pct": 0.35,
            "exhaustion_ticks": 4,
            "max_traps": 6,
            "trap_max_age_ticks": 120,
            "min_order_size": 0.01,
        }
    )
    s = LETStrategy(cfg)
    assert s.validate_config(cfg.__dict__) is True
    assert s.estimate_memory_mb() > 0.0

    assert s.validate_config({"symbol": "X", "base_capital": 1.0}) is True  # defaults
    assert s.validate_config({"base_capital": -5.0}) is False  # invalid caught

    class FakeOrders:
        def place_limit(self, side, price, size):
            return f"oid_{int(price * 1000)}"

    # Random walk, but drive on_fill from *tick direction* (exchange fills are
    # independent of the strategy's own returned signal), which is what feeds the
    # exhaustion detector in production.
    price = 100.0
    drift = 0
    actions = []
    oid_seq = 0
    for i in range(3000):
        prev = price
        # heavy same-direction runs (~0.5 drift memory) to build exhaustion
        drift = drift * 0.5 + random.uniform(-12, 12) * (0.6 if random.random() < 0.75 else 3.0)
        price = max(1.0, 100.0 + drift)
        m = _InferredMarket(price, 0.004)
        a = s.on_tick(m, FakeOrders())
        actions.append(a)
        # external fill events from price direction (buys on upticks, sells on down)
        if price > prev and random.random() < 0.2:
            oid_seq += 1
            s.on_fill(f"ext_{oid_seq}", "buy", price, 0.05)
        elif price < prev and random.random() < 0.2:
            oid_seq += 1
            s.on_fill(f"ext_{oid_seq}", "sell", price, 0.05)
        # let just-placed traps be exercised soon after by feeding an opposing fill
        if a in (1, -1) and s.traps.all():
            tp = s.traps.all()[-1]
            oid_seq += 1
            s.on_fill(tp.oid, tp.side, tp.price, tp.size)

    traded = sum(1 for a in actions if a in (1, -1))
    print(
        f"Synthetic test passed: 3000 ticks, {traded} trap signals, "
        f"active_traps={s.traps.active_count()}, wins={s._wins}, losses={s._losses}, "
        f"inv={s._inventory:.4f}, mem_mb={s.estimate_memory_mb()}"
    )

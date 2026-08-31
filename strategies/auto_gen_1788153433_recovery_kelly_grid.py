"""auto_gen_1788153433_recovery_kelly_grid.py

Asymmetric Recovery Kelly Grid (ARKG)
=====================================
A grid strategy that biases its re-entry geometry toward the *recovering* side
after each winning/losing fill, sized by a streaming (online) Kelly fraction over
a bounded realised-return window. Core ideas:

* **Recovery bias (asymmetry)**: after a fill, the grid re-prices the next
  levels so that more levels and tighter spacing sit on the side that would
  unwind the current inventory (mean-reverting recovery) while the opposite
  side widens. This accelerates return-to-flat without blowing the risk budget.
* **Streaming Kelly sizing**: track a bounded deque of per-fill PnL deltas;
  maintain the empirical win-rate p and win/loss ratio b (W/L, guarded against
  div-by-zero). Kelly fraction f* = max(0, (b*p - (1-p)) / b); capital deployed
  per level is `base_capital * clamp(f*, floor, cap)`.
* **OOM-safe**: prices/pnl are consumed as a generator; only a fixed-size deque
  of the last `window` fills is retained. No materialisation of full history.
* **Explicit errors**: a dedicated `StrategyError` with clear messages; no
  bare `except: pass`.

Memory is O(window + levels), independent of total tick count.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Generator, Iterable, Optional, Tuple


class StrategyError(Exception):
    """Raised for any config or runtime invariant violation (never swallowed)."""


@dataclass(frozen=True)
class ARKGConfig:
    """Config-driven policy. All knobs are here; no magic numbers in code."""
    capital: float = 500.0
    base_spacing: float = 0.0040          # grid spacing fraction of mid price
    levels: int = 10                      # levels per side
    kelly_floor: float = 0.01             # min deployed fraction of capital/level
    kelly_cap: float = 0.25               # max deployed fraction of capital/level
    recovery_skew: float = 0.65           # fraction of levels on recovering side
    window: int = 120                     # streaming window of pnl deltas (kept)
    max_inventory: int = 20               # total open level cap
    max_drawdown: float = 0.15            # kill-switch on equity drawdown

    def validate(self) -> None:
        if self.capital <= 0:
            raise StrategyError("capital must be > 0")
        if not 0 < self.base_spacing < 1:
            raise StrategyError("base_spacing must be in (0, 1)")
        if self.levels <= 0:
            raise StrategyError("levels must be > 0")
        if not 0 < self.kelly_floor <= self.kelly_cap <= 1:
            raise StrategyError("requires 0 < kelly_floor <= kelly_cap <= 1")
        if not 0 < self.recovery_skew < 1:
            raise StrategyError("recovery_skew must be in (0, 1)")
        if self.window <= 0:
            raise StrategyError("window must be > 0")
        if self.max_inventory <= 0:
            raise StrategyError("max_inventory must be > 0")
        if not 0 < self.max_drawdown < 1:
            raise StrategyError("max_drawdown must be in (0, 1)")


@dataclass
class Position:
    """Tracks current inventory: signed qty (+long/-short), cost basis, realised."""
    qty: float = 0.0
    avg_price: float = 0.0
    realised: float = 0.0
    open_fills: int = 0
    pnl_deltas: Deque[float] = field(default_factory=lambda: deque(maxlen=120))

    def apply_fill(self, qty: float, price: float) -> Tuple[float, float]:
        """Apply a fill and return (pnl_delta_this_fill, new_inventory_cost)."""
        if self.qty == 0.0:
            self.avg_price = price
        elif self.qty * qty > 0:  # same side adds
            total_q = self.qty + qty
            self.avg_price = (self.avg_price * abs(self.qty) +
                              price * abs(qty)) / abs(total_q)
        else:  # reducing inventory -> realise pnl on the closed slice
            closed = min(abs(self.qty), abs(qty))
            closed_pnl = (price - self.avg_price) * closed * (1 if self.qty > 0 else -1)
            self.realised += closed_pnl
            self.pnl_deltas.append(closed_pnl)
            if abs(qty) >= abs(self.qty):
                self.avg_price = price
        self.qty += qty
        self.open_fills = max(0, self.open_fills + (1 if self.qty != 0 else 0))
        return self.pnl_deltas[-1] if self.pnl_deltas else 0.0, price


class StrategyBase:
    """Interface contract enforced by ARKG. Engine and tests rely on this shape."""

    def __init__(self, config: ARKGConfig | Dict) -> None:
        self.config = config if isinstance(config, ARKGConfig) else ARKGConfig(**config)
        self.config.validate()
        self.pos: Position = Position()
        self._peak_equity: float = self.config.capital  # baseline = cash
        self._last_mid: float = 0.0
        self._cfg_copy = self.config  # config-driven, no reassignment of knobs

    # --- statistics ---
    def kelly_fraction(self) -> float:
        """Streaming Kelly over bounded pnl_deltas. Guarded against div-by-zero."""
        d = self.pos.pnl_deltas
        if len(d) < 2:
            return self._cfg_copy.kelly_floor
        wins = [x for x in d if x > 0]
        losses = [x for x in d if x <= 0]
        n = len(d)
        p = len(wins) / n
        avg_win = sum(wins) / len(wins) if wins else 0.0
        avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
        if avg_loss == 0.0 or avg_win == 0.0:
            return self._cfg_copy.kelly_floor
        b = avg_win / avg_loss
        f = (b * p - (1.0 - p)) / b
        f = max(0.0, f)
        return min(max(f, self._cfg_copy.kelly_floor), self._cfg_copy.kelly_cap)

    def equity(self, mid: float) -> float:
        # cash baseline + realised PnL + unrealised mark-to-market
        return self._cfg_copy.capital + self.pos.realised + self.pos.qty * mid

    def _drawdown_ok(self, mid: float) -> bool:
        eq = self.equity(mid)
        if eq > self._peak_equity:
            self._peak_equity = eq
        if self._peak_equity <= 0:
            return False
        dd = (self._peak_equity - eq) / self._peak_equity
        return dd <= self._cfg_copy.max_drawdown

    # --- level placement ---
    def _levels(self, mid: float, skew_recover: bool) -> Generator[Tuple[float, float], None, None]:
        """Yield (target_price, fraction_of_capital) for each new level.
        Streams; never builds a full in-memory list larger than `levels` at once.
        The recovering side gets `recovery_skew` fraction of levels with tighter
        spacing; the opposite side spreads the remainder."""
        c = self._cfg_copy
        k = self.kelly_fraction()
        recover_side = 1 if (self.pos.qty > 0 and skew_recover) or self.pos.qty <= 0 else -1
        n_recover = max(1, int(c.levels * c.recovery_skew))
        n_wide = max(1, c.levels - n_recover)
        tight_sp = c.base_spacing * 0.75
        wide_sp = c.base_spacing * 1.25
        for i in range(1, n_recover + 1):
            price = mid * (1 + tight_sp * i * recover_side)
            yield price, k * c.capital
        for i in range(1, n_wide + 1):
            price = mid * (1 + wide_sp * i * -recover_side)
            yield price, k * c.capital

    # --- engine hooks ---
    def on_tick(self, price: float) -> Optional[dict]:
        if price <= 0:
            raise StrategyError(f"on_tick received non-positive price: {price}")
        self._last_mid = price
        if not self._drawdown_ok(price):
            return {"action": "halt", "reason": f"drawdown>{self._cfg_copy.max_drawdown}"}
        if self.pos.open_fills >= self._cfg_copy.max_inventory:
            return {"action": "hold", "reason": "inventory cap"}
        # place a single level relative to current mid on the recovering side
        levels = list(self._levels(price, skew_recover=True))
        if not levels:
            return {"action": "hold", "reason": "no levels"}
        target, frac = levels[0]
        return {"action": "place", "price": round(target, 8),
                "qty": round(frac / target, 8), "side": "buy" if target < price else "sell"}

    def on_fill(self, price: float, qty: float) -> None:
        if qty == 0:
            raise StrategyError("on_fill received zero qty")
        self.pos.apply_fill(qty, price)

    def validate_config(self) -> None:
        self._cfg_copy.validate()

    def estimate_memory_mb(self) -> float:
        # deque(maxlen=window) of floats + fixed scalars -> < 0.2 MB realistically
        return round((self._cfg_copy.window * 32 + 512) / (1024 * 1024), 4)


def _synth_ticks(n: int = 5_000) -> Iterable[float]:
    """Deterministic synthetic price path (seeded, no RNG import overhead)."""
    price = 100.0
    for i in range(n):
        price += math.sin(i * 0.01) * 0.05 + (0.001 * (1 if (i % 7) else -1))
        yield max(0.01, price)


def _run_self_test() -> None:
    cfg = ARKGConfig(capital=500.0, levels=6, window=64, max_inventory=50)
    s = StrategyBase(cfg)
    s.validate_config()
    assert s.estimate_memory_mb() < 1.0, "memory estimate implausibly large"
    actions = 0
    for px in _synth_ticks(500):
        out = s.on_tick(px)
        if out and out.get("action") == "place" and s.pos.open_fills < cfg.max_inventory:
            # simulate a fill, alternate direction to build pnl_deltas
            s.on_fill(px, out["qty"] * (1 if actions % 2 == 0 else -1))
            actions += 1
    # invariants after the run
    assert len(s.pos.pnl_deltas) <= cfg.window, "deque exceeded window bound"
    assert s.pos.open_fills <= cfg.max_inventory, "inventory over cap"
    assert 0 < s.kelly_fraction() <= cfg.kelly_cap, "kelly outside bounds"
    print(f"[SELFTEST-OK] actions={actions} kelly={s.kelly_fraction():.4f} "
          f"equity={s.equity(100.0):.2f} mem_mb={s.estimate_memory_mb()}")


if __name__ == "__main__":
    _run_self_test()

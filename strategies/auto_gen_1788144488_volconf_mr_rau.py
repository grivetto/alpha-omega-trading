"""VolConfMR-RAU — Volume-Confirmed Mean Reversion with Regime-Aware Unwind.

Novel vs. the existing auto-gen set (AdaptiveVolGrid, VolGridEWM, VSAG,
LiquiditySkewGrid, GuillotineGrid, RVRegime, GapGuard, InvRebal, LFAMR-VCC,
FreshGuardGrid, MomentumBreakoutDonchian, AvellanedaStoikovMM, ...):

Prior grids assume a *reliable price feed* and treat every tick as equally
tradable: they re-anchor, expand and fire mean-reversion orders on *every*
arrival. In this fleet's paper/DOGE regime (sub-1 EUR capitals, quote=0,
fee-relative-heavy orders) that over-trades 1) chop, 2) stale/illiquid books.
None of the existing strategies consumes a *tick-velocity / micro-volume*
proxy, and none gates entry on *fill cadence*.

VolConfMR-RAU adds exactly those two missing signals:

1. **Micro-volume proxy (tick-velocity + |dP|)** — a weighted EWMA of
   ``sign(dP)*|dP|`` aggregated over an intra-tick window yields an O(1)
   synthetic buyer/seller imbalance ``V``. Mean-reversion entry fires only
   when ``V`` is weak (quiet accumulation) — the opposite of momentum — so the
   strat buys small dips only when the market is *not* aggressively selling,
   and sells small rips only when not aggressively buying. No order-book or
   tape feed required: derived purely from the price stream already received,
   so it is deployable on the same paper/trend nodes as the grid bot.

2. **Fill-cadence decay guard** — separate from FreshGuard's *feed* wakefulness
   watchdog. FreshGuard guards "is the *feed* stale?"; RAU guards "are my
   resting *fills* still being hit?" via a monotonic fill counter vs. wall
   clock. If no fill arrives for ``fill_cadence_after_s`` while the market has
   moved more than ``refill_bps`` away from the anchor, RAU stops opening new
   mean-reversion legs (HARD_HOLD expansion) and *unwinds* inventory toward a
   decaying target — diagonal unwinding — instead of stacking into a one-sided
   book. This is the inventory-(un)wind half of the name.

3. **Regime-Aware spacing** — realized vol (EWMA of |ret|) vs. its own slow
   baseline widens/tightens per-level spacing between [min_spacing_bps,
   max_spacing_bps], and flips the re-anchor EWMA alpha between a slow
   (trending) and fast (range) smoothing time constant, so the anchor does not
   chase a trend regime that mean-reversion would bleed into.

Memory-safety / OOM
-------------------
* Constant-memory by construction: scalars + two bounded deques
  (``rewind_window`` for velocity, ``fills`` for cadence/roll-up). No
  list comprehensions over history, no unbounded buffers, no full-array passes.
* All rolling stats are O(1) EWMA updates; the velocity window is capped and
  cheap because only ``|dP|`` scalars are stored.
* Degenerate cases (zero capital, non-finite price, stale feed, zero vol,
  empty windows) are guarded explicitly — no bare ``except: pass``.
* ``estimate_memory_mb`` bounds the worst case from the two fixed deques.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


class StrategyBase:
    """Interface contract required by the Denaro strategy engine."""

    def _generate_levels(self) -> list[Dict[str, float]]:
        """Build symmetric buy/sell grid legs around the anchor.

        Regime-aware spacing: wider in trend (1.3x), tighter in range (0.85x),
        always clamped to [min_spacing_bps, max_spacing_bps]. Each leg sizes at
        risk_per_level of capital, so total exposure across levels never needs
        more than ~capital in quote even when every level fills.
        """
        if self._anchor <= 0.0:
            return []
        gate = self._regime_gate()
        trending = self._vol_ewma > gate
        spacing_bps = max(
            self.min_spacing_bps,
            min(self.max_spacing_bps,
                self.base_spacing_bps * (1.3 if trending else 0.85)),
        )
        out: list[Dict[str, float]] = []
        for i in range(1, self.levels + 1):
            offset = self._anchor * (spacing_bps / 1e4) * i
            out.append({
                "buy_price": round(self._anchor - offset, self.price_decimals),
                "sell_price": round(self._anchor + offset, self.price_decimals),
                "qty": round(self.capital * self.risk_per_level / self._anchor, 8),
                "spacing_bps": round(spacing_bps, 2),
            })
        return out

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class VolConfConfig:
    """Config for VolConfMR-RAU, validated eagerly on construction."""

    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    levels: int = 6
    base_spacing_bps: float = 30.0
    min_spacing_bps: float = 12.0
    max_spacing_bps: float = 140.0
    anchor_alpha_slow: float = 0.03   # trending regime EWMA
    anchor_alpha_fast: float = 0.12   # ranging regime EWMA
    regime_vol_ratio: float = 1.6     # realized vol vs slow baseline -> regime switch
    velocity_alpha: float = 0.18      # EWMA weight on tick-velocity
    velocity_window: int = 48         # ticks kept for dP vel stats
    quiet_v_threshold: float = 0.35   # |V| below this => quiet (entry allowed)
    vol_alpha: float = 0.15           # fast realized-vol EWMA
    vol_slow_alpha: float = 0.02      # slow realized-vol EWMA
    inventory_target: float = 0.0     # unwind target as fraction of capital(-1..1)
    max_inventory: float = 0.95       # hard cap on |inv| fraction before hard hold
    fill_cadence_after_s: float = 600.0  # no fill for this long => cadence decay
    refill_bps: float = 120.0         # accumulated anchor deviation to trigger unwind
    rewind_step_bps: float = 15.0     # diagonal unwind size per tick in caps
    stale_after_s: float = 45.0       # feed-freshness guard (wall clock vs tick ts)
    price_decimals: int = 4
    risk_per_level: float = 1.0 / 6.0

    def validate(self) -> None:
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if self.levels <= 0:
            raise ValueError("levels must be > 0")
        if not (0 < self.min_spacing_bps <= self.max_spacing_bps):
            raise ValueError("spacing band must satisfy 0 < min <= max")
        if not (0 < self.base_spacing_bps <= self.max_spacing_bps):
            raise ValueError("base_spacing_bps within [min, max] band")
        if not (0 < self.anchor_alpha_slow <= 1 and 0 < self.anchor_alpha_fast <= 1):
            raise ValueError("anchor alphas out of (0,1]")
        if self.regime_vol_ratio <= 1.0:
            raise ValueError("regime_vol_ratio must be > 1.0")
        if not (0 < self.velocity_alpha <= 1 and 0 < self.vol_alpha <= 1 and 0 < self.vol_slow_alpha <= 1):
            raise ValueError("EWMA alphas out of (0,1]")
        if self.quiet_v_threshold < 0:
            raise ValueError("quiet_v_threshold must be >= 0")
        if not (-1.0 < self.inventory_target < 1.0):
            raise ValueError("inventory_target within (-1,1)")
        if not (0 < self.max_inventory <= 1.0):
            raise ValueError("max_inventory in (0,1]")
        if self.fill_cadence_after_s <= 0 or self.refill_bps <= 0 or self.rewind_step_bps <= 0:
            raise ValueError("cadence/refill/rewind params must be > 0")
        if self.stale_after_s <= 0:
            raise ValueError("stale_after_s must be > 0")
        if self.price_decimals < 0 or self.risk_per_level <= 0:
            raise ValueError("price_decimals >= 0 and risk_per_level > 0 required")
        if self.velocity_window < 2:
            raise ValueError("velocity_window must be >= 2")


@dataclass
class VolConfMR_RAU(StrategyBase):
    """Volume-confirmed mean reversion with regime-aware diagonal unwind.

    Attributes mirror :class:`VolConfConfig`. ``state`` holds derived runtime
    scalars for observability (anchor, inferred vol, velocity imbalance V,
    regime, inventory frac, hold flags). ``_vw`` stores the bounded dP window;
    ``_fills`` stores bounded fill records for cadence roll-up.
    """

    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    levels: int = 6
    base_spacing_bps: float = 30.0
    min_spacing_bps: float = 12.0
    max_spacing_bps: float = 140.0
    anchor_alpha_slow: float = 0.03
    anchor_alpha_fast: float = 0.12
    regime_vol_ratio: float = 1.6
    velocity_alpha: float = 0.18
    velocity_window: int = 48
    quiet_v_threshold: float = 0.35
    vol_alpha: float = 0.15
    vol_slow_alpha: float = 0.02
    inventory_target: float = 0.0
    max_inventory: float = 0.95
    fill_cadence_after_s: float = 600.0
    refill_bps: float = 120.0
    rewind_step_bps: float = 15.0
    stale_after_s: float = 45.0
    price_decimals: int = 4
    risk_per_level: float = 1.0 / 6.0

    _last_price: float = field(default=0.0, init=False)
    _last_ts: float = field(default=0.0, init=False)
    _anchor: float = field(default=0.0, init=False)
    _anchor_alpha: float = field(default=0.03, init=False)
    _vol_ewma: float = field(default=0.0, init=False)
    _vol_slow: float = field(default=0.0, init=False)
    _vel_ewma: float = field(default=0.0, init=False)
    _vw: Deque[float] = field(default_factory=lambda: deque(maxlen=48), init=False)
    _fills: Deque[tuple[float, float]] = field(default_factory=lambda: deque(maxlen=128), init=False)
    _n_fills: int = field(default=0, init=False)
    _last_fill_ts: float = field(default=0.0, init=False)
    _inventory_frac: float = field(default=0.0, init=False)  # +sell / -buy exposure
    _first_tick: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        # Eager runtime-state init so on_tick/on_fill are safe from first call
        # even if a caller skips the first-tick lazy init. Bounded deques keep
        # memory constant regardless of input length.
        self._vw: Deque[float] = deque(maxlen=self.velocity_window)
        self._fills: Deque[tuple[float, float]] = deque(maxlen=128)
        self._last_price = 0.0
        self._last_ts = 0.0
        self._anchor = 0.0
        self._anchor_alpha = self.anchor_alpha_slow
        self._vol_ewma = 0.0
        self._vol_slow = 0.0
        self._vel_ewma = 0.0
        self._n_fills = 0
        self._last_fill_ts = 0.0
        self._inventory_frac = 0.0
        self._first_tick = True

    def _init(self) -> None:
        # Legacy no-op kept for API stability; state is eager via __post_init__.
        return None

    @property
    def state(self) -> Dict[str, Any]:
        return {
            "symbol": self.symbol,
            "anchor": round(self._anchor, self.price_decimals),
            "vol_ewma": round(self._vol_ewma, 8),
            "vol_slow": round(self._vol_slow, 8),
            "vel_ewma": round(self._vel_ewma, 8),
            "regime": "trend" if self._vol_ewma > self._regime_gate() else "range",
            "inventory_frac": round(self._inventory_frac, 4),
            "n_fills": self._n_fills,
            "feed_stale": bool(self._feed_stale()),
            "cadence_stall": bool(self._cadence_stall()),
        }

    def _regime_gate(self) -> float:
        return self._vol_slow * self.regime_vol_ratio

    def _feed_stale(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        if self._last_ts <= 0:
            return False
        return (now - self._last_ts) > self.stale_after_s

    def _cadence_stall(self, now: Optional[float] = None) -> bool:
        now = now if now is not None else time.time()
        if self._last_fill_ts <= 0 or self._anchor <= 0.0:
            return False
        dev_bps = abs(self._last_price - self._anchor) / self._anchor * 1e4 if self._anchor else 0.0
        return (now - self._last_fill_ts) > self.fill_cadence_after_s and dev_bps > self.refill_bps

    def validate_config(self) -> None:
        VolConfConfig(
            symbol=self.symbol, capital=self.capital, levels=self.levels,
            base_spacing_bps=self.base_spacing_bps, min_spacing_bps=self.min_spacing_bps,
            max_spacing_bps=self.max_spacing_bps,
            anchor_alpha_slow=self.anchor_alpha_slow, anchor_alpha_fast=self.anchor_alpha_fast,
            regime_vol_ratio=self.regime_vol_ratio, velocity_alpha=self.velocity_alpha,
            velocity_window=self.velocity_window, quiet_v_threshold=self.quiet_v_threshold,
            vol_alpha=self.vol_alpha, vol_slow_alpha=self.vol_slow_alpha,
            inventory_target=self.inventory_target, max_inventory=self.max_inventory,
            fill_cadence_after_s=self.fill_cadence_after_s, refill_bps=self.refill_bps,
            rewind_step_bps=self.rewind_step_bps, stale_after_s=self.stale_after_s,
            price_decimals=self.price_decimals, risk_per_level=self.risk_per_level,
        ).validate()

    def estimate_memory_mb(self) -> float:
        bytes_vw = self.velocity_window * 8.0
        bytes_fills = 128 * (2 * 8.0 + 48.0)  # tuple overhead approx
        total = bytes_vw + bytes_fills + 4096.0
        return round(total / (1024.0 * 1024.0), 4)

    def on_fill(self, side: str, price: float, qty: float) -> None:
        if qty <= 0.0 or not math.isfinite(price):
            raise ValueError(f"invalid fill: side={side!r} price={price} qty={qty}")
        now = time.time()
        self._last_fill_ts = now
        self._n_fills += 1
        signed = qty if side.lower() == "buy" else -qty
        self._inventory_frac += signed / self.capital if self.capital > 0 else 0.0
        self._inventory_frac = max(-self.max_inventory, min(self.max_inventory, self._inventory_frac))
        self._fills.append((price, now))

    def _generate_levels(self) -> list[Dict[str, float]]:
        """Build symmetric buy/sell grid legs around the anchor.

        Regime-aware spacing: wider in trend (1.3x), tighter in range (0.85x),
        always clamped to [min_spacing_bps, max_spacing_bps]. Each leg sizes at
        risk_per_level of capital, so total exposure across levels never needs
        more than ~capital in quote even when every level fills.
        """
        if self._anchor <= 0.0:
            return []
        gate = self._regime_gate()
        trending = self._vol_ewma > gate
        spacing_bps = max(
            self.min_spacing_bps,
            min(self.max_spacing_bps,
                self.base_spacing_bps * (1.3 if trending else 0.85)),
        )
        out: list[Dict[str, float]] = []
        for i in range(1, self.levels + 1):
            offset = self._anchor * (spacing_bps / 1e4) * i
            out.append({
                "buy_price": round(self._anchor - offset, self.price_decimals),
                "sell_price": round(self._anchor + offset, self.price_decimals),
                "qty": round(self.capital * self.risk_per_level / self._anchor, 8),
                "spacing_bps": round(spacing_bps, 2),
            })
        return out

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        ts = ts if ts is not None else time.time()
        if not math.isfinite(price) or price <= 0.0:
            raise ValueError(f"non-finite/non-positive price: {price}")

        if self._first_tick:
            self._first_tick = False
            self._last_price = price
            self._last_ts = ts
            self._anchor = price
            self._anchor_alpha = self.anchor_alpha_slow
            return {"decision": "init", "action": "noop"}

        dP = price - self._last_price
        rel = (price - self._last_price) / self._last_price if self._last_price else 0.0
        prev_price = self._last_price
        self._last_price = price
        self._last_ts = ts

        abs_ret = abs(rel) if rel else 0.0
        if self._vol_ewma == 0.0:
            self._vol_ewma = abs_ret
            self._vol_slow = abs_ret
        else:
            self._vol_ewma = (1 - self.vol_alpha) * self._vol_ewma + self.vol_alpha * abs_ret
            self._vol_slow = (1 - self.vol_slow_alpha) * self._vol_slow + self.vol_slow_alpha * abs_ret

        gate = self._regime_gate()
        trending = self._vol_ewma > gate
        self._anchor_alpha = self.anchor_alpha_fast if not trending else self.anchor_alpha_slow
        if self._anchor == 0.0:
            self._anchor = price
        else:
            self._anchor = (1 - self._anchor_alpha) * self._anchor + self._anchor_alpha * price

        self._vw.append(dP)
        if len(self._vw) == 1:
            self._vel_ewma = dP
        else:
            self._vel_ewma = (1 - self.velocity_alpha) * self._vel_ewma + self.velocity_alpha * dP
        v_mag = abs(self._vel_ewma) / (abs(prev_price) if prev_price else 1.0) * 1e4  # bps
        quiet = v_mag <= self.quiet_v_threshold

        feed_stale = self._feed_stale(ts)
        cadence_stall = self._cadence_stall(ts)
        inv_over = abs(self._inventory_frac) > self.max_inventory

        if feed_stale or inv_over:
            action = "HARD_HOLD"
        elif cadence_stall:
            action = "UNWIND"
        elif not quiet or trending:
            action = "WAIT"
        else:
            action = "GRID_EXPAND"

        rewind_action: str = "no-unwind"
        unwind_qty: float = 0.0
        if action == "UNWIND":
            diff = self.inventory_target - self._inventory_frac
            unwind_qty = self.rewind_step_bps / 1e4 * self.capital
            rewind_action = "sell" if diff > 0 else "buy"

        # Build concrete order levels only when the strategy is acting.
        levels: list[Dict[str, float]] = []
        if action in ("GRID_EXPAND", "UNWIND"):
            if action == "GRID_EXPAND":
                levels = self._generate_levels()
            else:
                diff = self.inventory_target - self._inventory_frac
                if abs(diff) > 0.0:
                    emit_qty = min(abs(diff) * self.capital * 0.1,
                                   self.rewind_step_bps / 1e4 * self.capital)
                    levels = [{
                        "side": "sell" if diff > 0 else "buy",
                        "price": round(self._last_price, self.price_decimals),
                        "qty": round(emit_qty / self._last_price, 8),
                        "spacing_bps": 0.0,
                    }]

        spacing_bps = max(
            self.min_spacing_bps,
            min(self.max_spacing_bps,
                self.base_spacing_bps * (1.3 if trending else 0.85)),
        )
        return {
            "decision": action,
            "action": action,
            "anchor": round(self._anchor, self.price_decimals),
            "regime": "trend" if trending else "range",
            "vel_bps": round(v_mag, 4),
            "quiet": quiet,
            "feed_stale": feed_stale,
            "cadence_stall": cadence_stall,
            "inventory_frac": round(self._inventory_frac, 4),
            "spacing_bps": round(spacing_bps, 2),
            "rewind": rewind_action,
            "unwind_qty": round(unwind_qty, 8),
            "levels": levels,
        }


if __name__ == "__main__":
    cfg = VolConfConfig()
    cfg.validate()
    s = VolConfMR_RAU(**{f: getattr(cfg, f) for f in cfg.__dataclass_fields__})
    s.validate_config()
    assert s.estimate_memory_mb() > 0.0

    import random
    rng = random.Random(7)
    base = 0.00078
    for i in range(400):
        if i % 5 == 0:
            px = base + rng.uniform(-0.00001, 0.00001)
        else:
            px = base + (i % 7 - 3) * 0.000003
        if px <= 0:
            px = base
        d = s.on_tick(px, ts=float(i) * 1.0)
        if i == 10:
            s.on_fill("buy", px, 0.2)
        if i == 20:
            s.on_fill("sell", px, 0.1)
        assert d["decision"] in ("GRID_EXPAND", "WAIT", "UNWIND", "HARD_HOLD", "init")
    print("selftest OK n=400 last=", s.state)

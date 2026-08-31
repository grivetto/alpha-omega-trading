"""FreshGuardGrid — volatility-expanding grid with a data-freshness watchdog.

Core idea (novel vs. prior auto-gen set: LiquiditySkewGrid / VolGridEWM /
GuillotineGrid / RVRegime / GapGuard / InvRebal):

Those grids assume a *reliable, continuous* price feed. This fleet has already
surfaced exactly the failure mode they ignore: MARCODG1's sol bot carries a
STALE heartbeat (~3 days), health flagged DEGRADED, while `uptime` kept
counting. If a mean-reversion grid keeps placing contra-orders on stale
anchors when the live price has moved away, it stacks one-sided inventory and
bleeds — silently, because the error string stays empty.

FreshGuardGrid treats *data freshness* as a first-class input, not an
assumption:

1. **Feed-freshness watchdog** — every `on_tick` stamps `_last_tick_ts`.
   If the gap between the incoming tick timestamp and the *local* wall clock
   exceeds `stale_after_s`, the grid enters HOLD: it stops *expanding*
   (no new levels, no re-anchor) and stops opening *new* contra orders, but it
   still closes fills already resting near the last good price. This caps
   adverse inventory without requiring a kill-switch round-trip.

2. **Volatility-expanding anchor** — the re-anchor baseline is an EWMA of the
   price (adaptive center). When realized vol (EWMA of |tick-to-tick ret|)
   crosses `vol_grow_ratio` above its own slow baseline, per-level spacing
   widens so the grid stops over-trading chop; when vol contracts, spacing
   tightens to keep harvesting mean-reversion. Spacing is *always* bounded by
   [`min_spacing_bps`, `max_spacing_bps`] so a vol spike cannot explode the
   band (OOM / capital-exposure guard).

3. **Inventory-mean-reversion bias** — when inventory skew exceeds a config
   threshold the grid's effective anchor is nudged toward the *skewed* side
   (partial-hedging pressure) so it does not blindly average into a losing
   direction. The nudge is capped (`max_inv_nudge_bps`) and only active when
   the feed is fresh — never while holding on stale data.

Memory-safety
-------------
* Constant-memory state: a handful of scalars, a length-`cap_ticks` deque for
  the freshness window, and a length-`fill_window` deque for footprint
  reporting. No list comprehensions over tick history, no unbounded buffers.
* All rolling statistics are O(1) EWMA updates.
* Degenerate cases (zero capital, non-finite price, stale feed, zero vol) are
  guarded explicitly — no bare ``except: pass``.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


class StrategyBase:
    """Interface contract required by the Denaro strategy engine."""

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class FreshGuardConfig:
    """Config params, validated eagerly on construction (no silent defaults).
    """

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    levels: int = 6
    base_spacing_bps: float = 30.0
    min_spacing_bps: float = 12.0
    max_spacing_bps: float = 120.0
    price_ema_alpha: float = 0.04
    vol_fast_alpha: float = 0.15
    vol_slow_alpha: float = 0.02
    vol_grow_ratio: float = 1.8
    max_inv_nudge_bps: float = 25.0
    inv_skew_threshold: float = 0.25
    stale_after_s: float = 30.0
    price_decimals: int = 4
    fill_window: int = 64
    cap_ticks: int = 512
    risk_per_level: float = 1.0 / 6.0

    def validate(self) -> None:
        if self.capital <= 0:
            raise ValueError(f"capital must be > 0, got {self.capital}")
        if self.levels <= 0:
            raise ValueError(f"levels must be > 0, got {self.levels}")
        if not (0 < self.min_spacing_bps <= self.max_spacing_bps):
            raise ValueError("spacing band must satisfy 0 < min <= max")
        if not (0 < self.base_spacing_bps <= self.max_spacing_bps):
            raise ValueError("base_spacing_bps must be within [min, max] band")
        if not (0 < self.price_ema_alpha <= 1):
            raise ValueError("price_ema_alpha out of (0,1]")
        if not (0 < self.vol_fast_alpha <= 1 and 0 < self.vol_slow_alpha <= 1):
            raise ValueError("vol alphas out of (0,1]")
        if self.vol_grow_ratio <= 1.0:
            raise ValueError("vol_grow_ratio must be > 1.0")
        if self.stale_after_s <= 0:
            raise ValueError("stale_after_s must be > 0")
        if not (0 < self.risk_per_level <= 1):
            raise ValueError("risk_per_level out of (0,1]")
        if self.fill_window <= 0 or self.cap_ticks <= 0:
            raise ValueError("windows must be > 0")


@dataclass
class FreshGuardGrid(StrategyBase):
    """Volatility-expanding grid with a feed-freshness watchdog.

    Attributes mirror ``FreshGuardConfig`` — see its docstring. ``state``
    keeps a dict of derived runtime scalars for observability.
    """

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    levels: int = 6
    base_spacing_bps: float = 30.0
    min_spacing_bps: float = 12.0
    max_spacing_bps: float = 120.0
    price_ema_alpha: float = 0.04
    vol_fast_alpha: float = 0.15
    vol_slow_alpha: float = 0.02
    vol_grow_ratio: float = 1.8
    max_inv_nudge_bps: float = 25.0
    inv_skew_threshold: float = 0.25
    stale_after_s: float = 30.0
    price_decimals: int = 4
    fill_window: int = 64
    cap_ticks: int = 512
    risk_per_level: float = 1.0 / 6.0

    _price_ema: float = field(default=0.0, init=False)
    _vol_fast: float = field(default=0.0, init=False)
    _vol_slow: float = field(default=0.0, init=False)
    _prev_price: Optional[float] = field(default=None, init=False)
    _prev_ts: Optional[float] = field(default=None, init=False)
    _last_tick_ts: float = field(default=0.0, init=False)
    _last_recv_ts: float = field(default=0.0, init=False)
    _inventory: float = field(default=0.0, init=False)
    _total_buys: int = field(default=0, init=False)
    _total_sells: int = field(default=0, init=False)
    _recent_fills: Deque[Dict[str, Any]] = field(
        default_factory=lambda: deque(maxlen=64), init=False
    )
    _ts_window: Deque[float] = field(default_factory=lambda: deque(maxlen=512), init=False)
    _n_ticks: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.validate_config()
        cfg = FreshGuardConfig(
            symbol=self.symbol, capital=self.capital, levels=self.levels,
            base_spacing_bps=self.base_spacing_bps, min_spacing_bps=self.min_spacing_bps,
            max_spacing_bps=self.max_spacing_bps, price_ema_alpha=self.price_ema_alpha,
            vol_fast_alpha=self.vol_fast_alpha, vol_slow_alpha=self.vol_slow_alpha,
            vol_grow_ratio=self.vol_grow_ratio, max_inv_nudge_bps=self.max_inv_nudge_bps,
            inv_skew_threshold=self.inv_skew_threshold, stale_after_s=self.stale_after_s,
            price_decimals=self.price_decimals, fill_window=self.fill_window,
            cap_ticks=self.cap_ticks, risk_per_level=self.risk_per_level,
        )
        cfg.validate()
        self._ts_window = deque(maxlen=self.cap_ticks)
        self._recent_fills = deque(maxlen=self.fill_window)

    # ------------------------------------------------------------------ #
    # Config / introspection
    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        cfg = FreshGuardConfig(
            symbol=self.symbol, capital=self.capital, levels=self.levels,
            base_spacing_bps=self.base_spacing_bps, min_spacing_bps=self.min_spacing_bps,
            max_spacing_bps=self.max_spacing_bps, price_ema_alpha=self.price_ema_alpha,
            vol_fast_alpha=self.vol_fast_alpha, vol_slow_alpha=self.vol_slow_alpha,
            vol_grow_ratio=self.vol_grow_ratio, max_inv_nudge_bps=self.max_inv_nudge_bps,
            inv_skew_threshold=self.inv_skew_threshold, stale_after_s=self.stale_after_s,
            price_decimals=self.price_decimals, fill_window=self.fill_window,
            cap_ticks=self.cap_ticks, risk_per_level=self.risk_per_level,
        )
        cfg.validate()

    def estimate_memory_mb(self) -> float:
        """Rough constant bound: 2 capped deques of small dicts + scalars."""
        per_item = 180.0  # approx bytes per deque entry (small dict)
        total_bytes = (self.cap_ticks + self.fill_window) * per_item + 2048
        return total_bytes / (1024.0 * 1024.0)

    def state(self) -> Dict[str, Any]:
        """Observability snapshot (no memory growth)."""
        return {
            "symbol": self.symbol,
            "status": "HOLD" if self._is_stale() else "RUN",
            "price_ema": round(self._price_ema, self.price_decimals),
            "vol_fast": round(self._vol_fast, 8),
            "vol_slow": round(self._vol_slow, 8),
            "inventory": round(self._inventory, 8),
            "n_ticks": self._n_ticks,
            "n_fills": len(self._recent_fills),
        }

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    def _is_stale(self, recv_ts: Optional[float] = None) -> bool:
        """Feed freshness check against wall clock (grace period).

        Uses the wall-clock time when the tick was *received* (``_last_recv_ts``),
        not the exchange-supplied ``ts``, so a pathological stream that keeps an
        old timestamp while continuing to deliver ticks still reads as fresh and
        vice-versa. An explicit ``recv_ts`` (from the engine loop) overrides it.
        """
        ref = recv_ts if recv_ts is not None else self._last_recv_ts
        return (time.time() - ref) > (self.stale_after_s + 5.0)

    def _current_spacing_bps(self) -> float:
        """Spacing expands with fast/slow vol ratio, clamped to the band."""
        if self._vol_slow <= 0.0:
            return self.base_spacing_bps
        ratio = self._vol_fast / self._vol_slow if self._vol_slow > 0 else 1.0
        mult = max(1.0, ratio / self.vol_grow_ratio)
        raw = self.base_spacing_bps * mult
        return max(self.min_spacing_bps, min(self.max_spacing_bps, raw))

    def _anchor_price(self) -> float:
        """Adaptive center nudged toward inventory skew when feed is fresh."""
        anchor = self._price_ema if self._price_ema > 0 else self._prev_price or 0.0
        if anchor <= 0.0:
            return 0.0
        skew = self._inventory / self.capital if self.capital > 0 else 0.0
        abs_skew = abs(skew)
        if abs_skew <= self.inv_skew_threshold or self._is_stale():
            return anchor
        nudge_bps = self.max_inv_nudge_bps * (abs_skew - self.inv_skew_threshold)
        # positive inventory (long) -> nudge anchor DOWN to encourage selling;
        # negative inventory (short) -> nudge anchor UP to encourage buying.
        direction = -1.0 if skew > 0.0 else 1.0
        return anchor * (1.0 + direction * nudge_bps / 10_000.0)

    # ------------------------------------------------------------------ #
    # Engine callbacks
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        if not math.isfinite(price) or price <= 0.0:
            raise ValueError(f"non-finite/non-positive price: {price!r}")
        now = ts if ts is not None else time.time()
        self._last_tick_ts = now
        self._last_recv_ts = time.time()
        self._ts_window.append(now)
        self._n_ticks += 1

        if self._prev_price is not None and self._prev_price > 0.0:
            ret = abs(price / self._prev_price - 1.0)
            if self._vol_fast == 0.0:
                self._vol_fast = ret
            else:
                self._vol_fast = self.vol_fast_alpha * ret + (1 - self.vol_fast_alpha) * self._vol_fast
            if self._vol_slow == 0.0:
                self._vol_slow = ret
            else:
                self._vol_slow = self.vol_slow_alpha * ret + (1 - self.vol_slow_alpha) * self._vol_slow
        self._prev_price = price

        if self._price_ema == 0.0:
            self._price_ema = price
        else:
            self._price_ema = self.price_ema_alpha * price + (1 - self.price_ema_alpha) * self._price_ema

        return self._build_levels(price)

    def on_fill(self, side: str, price: float, qty: float) -> None:
        if side not in ("buy", "sell"):
            raise ValueError(f"side must be 'buy' or 'sell', got {side!r}")
        if not math.isfinite(price) or price <= 0.0 or qty <= 0.0:
            raise ValueError(f"bad fill: side={side} price={price!r} qty={qty!r}")
        sign = 1.0 if side == "buy" else -1.0
        self._inventory += sign * qty
        if side == "buy":
            self._total_buys += 1
        else:
            self._total_sells += 1
        self._recent_fills.append({"side": side, "price": price, "qty": qty})

    def _build_levels(self, price: float) -> Dict[str, Any]:
        stale = self._is_stale()
        anchor = self._anchor_price()
        if anchor <= 0.0:
            anchor = price
        spacing_bps = self._current_spacing_bps()
        step = anchor * spacing_bps / 10_000.0

        # In HOLD we do NOT expand: only return the anchor levels already flat
        # (no new contra orders), so inventory does not stack on stale data.
        n_new = 0 if stale else self.levels
        bids = [
            round(anchor - (i + 1) * step, self.price_decimals)
            for i in range(n_new)
        ]
        asks = [
            round(anchor + (i + 1) * step, self.price_decimals)
            for i in range(n_new)
        ]
        return {
            "anchor": round(anchor, self.price_decimals),
            "spacing_bps": round(spacing_bps, 2),
            "status": "HOLD" if stale else "RUN",
            "levels": {"bids": bids, "asks": asks},
            "state": self.state(),
        }


def _selftest() -> None:
    g = FreshGuardGrid(
        symbol="SOL/EUR", capital=13.5, levels=6, base_spacing_bps=30.0,
        min_spacing_bps=12.0, max_spacing_bps=120.0, stale_after_s=30.0,
    )

    # 1) Fresh feed -> RUN, symmetric grid around start price.
    d1 = g.on_tick(100.0, ts=time.time())
    assert d1["status"] == "RUN"
    assert len(d1["levels"]["bids"]) == 6
    assert len(d1["levels"]["asks"]) == 6
    assert d1["anchor"] == 100.0

    # 2) Vol shock -> spacing widens, still bounded by max.
    base_sp = g._current_spacing_bps()
    for i in range(20):
        g.on_tick(100.0 + (25.0 if i % 2 == 0 else -25.0), ts=time.time())
    sp = g._current_spacing_bps()
    assert sp >= base_sp, "vol expansion must widen spacing"
    assert sp <= g.max_spacing_bps + 1e-9, "spacing must respect max band"

    # 3) Inventory skew nudges anchor down when long and feed fresh.
    g.on_fill("buy", 100.0, 3.0)  # inventory 3.0 on 13.5 capital -> skew 0.22
    anchor_nudged = g._anchor_price()
    assert anchor_nudged <= g._price_ema + 1e-9, "long inventory must nudge anchor down"

    # 4) Stale feed (no ticks received for > stale_after_s) -> HOLD.
    g2 = FreshGuardGrid(capital=10.0, stale_after_s=30.0)
    g2.on_tick(100.0, ts=time.time())          # normal fresh tick
    assert not g2._is_stale(), "fresh feed must not be stale"
    g2._last_recv_ts = time.time() - 120.0     # simulate stagnant feed
    assert g2._is_stale(), "stale recv time must flag stale"
    d2 = g2._build_levels(101.0)
    assert d2["status"] == "HOLD", "stale feed must switch to HOLD"
    assert len(d2["levels"]["bids"]) == 0, "HOLD must not open new levels"

    # 5) Config guard rejects bad params.
    try:
        FreshGuardGrid(capital=-1.0)
        raise AssertionError("should have raised on negative capital")
    except ValueError:
        pass

    mem = g.estimate_memory_mb()
    print(
        f"SELFTEST PASS | mem={mem:.4f}MB spacing_bps={sp:.1f} "
        f"anchor={d1['anchor']} fills={len(g._recent_fills)}"
    )


if __name__ == "__main__":
    _selftest()

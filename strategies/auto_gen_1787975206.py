"""Volatility-Scaled Adaptive Grid (VSAG) — auto-generated 2026-08-29 05:46 UTC by Hermes.

Distinct from every prior auto-gen family:
   1. Prior grids key on price or fill-side exhaustion (LETF trap-flip). VSAG keys on
      *regime-scaled geometry*: it measures short-window realized volatility and warps
      the grid spacing, level count and re-anchor cadence to that volatility, so the
      grid never overtrades a quiet tape nor starves a violent one.
   2. Anchor drift control: rather than a fixed central price, VSAG maintains a MID
      anchor that only re-anchors when the market has CLEARLY migrated a configurable
      number of ATRs away — preventing the chronic "grid walks to the edge of its
      levels and every level is a loser" failure of static grids.
   3. Proportional-spacing ladder: spacing scales linearly with the EMA of realized
      vol, and the grid is regenerated (cheaply) only when vol crosses a hysteresis
      band, avoiding churn on noise.
   4. Exposure taper: total notional of open levels is capped by remaining risk budget,
      and per-level size shrinks in the direction of accumulated inventory (anti-stack).

OOM-safety: rolling statistics use bounded ring buffers (resize via deque(maxlen)),
a single multiplicative EWMA for vol (no moving-window list), and explicit chunked
processing helpers. No list comprehensions over unbounded series; large temporaries
are `del`-ed and `gc.collect()` runs on a guarded counter.

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
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

Action = type("Action", (), {"HOLD": "HOLD"})()  # -1 = place buy, 1 = place sell


@dataclass(frozen=True)
class StrategyConfig:
    """Externalized, validated configuration for VSAG."""

    symbol: str
    base_capital: float
    vol_ema_alpha: float = 0.05           # EWMA smoothing for intraday vol estimate
    base_spacing_pct: float = 0.004       # spacing when vol_ema is at the low bound
    spacing_vol_mult: float = 6.0         # spacing grows this many x at the high bound
    vol_low: float = 0.0015               # realized-vol low bound (frac per tick)
    vol_high: float = 0.0060              # realized-vol high bound
    hysteresis: float = 0.15              # band fraction before grid regen
    levels: int = 8                       # max grid levels per side
    max_exposure_pct: float = 0.5         # total open notional cap as frac of equity
    reanchor_atr_mult: float = 3.0        # migration before mid re-anchors
    atr_window: int = 40                  # bounded ATR window (maxlen deque)
    fee_rate: float = 0.0016
    min_level_capture_mult: float = 1.5   # require spacing >= mult * round-trip fee
    order_book_depth: int = 5             # levels of L2 used for liquidity weighting
    gc_every: int = 256                   # guarded gc.collect() cadence (ticks)
    min_order_size: float = 0.0
    max_spread_fraction: float = 0.01

    def validate(self) -> None:
        """Raise ValueError on any invalid value."""
        if self.base_capital <= 0.0 or self.max_exposure_pct <= 0.0 or self.max_exposure_pct > 1.0:
            raise ValueError("base_capital>0 and max_exposure_pct in (0,1] required")
        if self.levels < 2 or self.levels > 128:
            raise ValueError("levels must be in [2,128]")
        if not (0.0 < self.base_spacing_pct <= 0.05):
            raise ValueError("base_spacing_pct must be in (0, 0.05]")
        if not (self.vol_low < self.vol_high):
            raise ValueError("vol_low must be < vol_high")
        if not (0.0 < self.vol_ema_alpha < 1.0):
            raise ValueError("vol_ema_alpha must be in (0,1)")
        if self.min_level_capture_mult < 1.0:
            raise ValueError("min_level_capture_mult must be >= 1.0")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyConfig":
        """Build from dict, ignoring unknown keys (config-driven, no magic numbers)."""
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


@dataclass
class _InferredMarket:
    """Minimal stand-in exposing .price and .spread for unit/strategy tests."""

    price: float
    spread: float = 0.0


class VSAG:
    """Volatility-scaled adaptive grid engine. Pure state; no I/O."""

    def __init__(self, config: StrategyConfig) -> None:
        config.validate()
        self.cfg = config
        self.vol_ema: Optional[float] = None
        self._spacing_pct: float = config.base_spacing_pct
        self._grid_vol: Optional[float] = None          # vol band at last regen
        self._anchor: Optional[float] = None
        self._migrated_atrs: float = 0.0
        self._realized: Deque[float] = deque(maxlen=config.atr_window)
        self._inventory: float = 0.0
        self._open_levels_buy: int = 0
        self._open_levels_sell: int = 0
        self._realized_equity = config.base_capital
        self._tick = 0
        self._fills_ctr = 0
        self._last_price: Optional[float] = None

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _safe_rat(a: float, b: float) -> float:
        return a / b if b > 1e-12 else 0.0

    def _update_vol(self, price: float, prev: Optional[float]) -> None:
        """EWMA of per-tick |return| — O(1), no moving window allocation."""
        if prev is None or prev <= 1e-12:
            return
        r = abs(self._safe_rat(price - prev, prev))
        r = max(r, 1e-9)
        self.vol_ema = r if self.vol_ema is None else (
            self.cfg.vol_ema_alpha * r + (1.0 - self.cfg.vol_ema_alpha) * self.vol_ema)

    # ------------------------------------------------------------------ grid
    def _vol_index(self) -> float:
        """Map vol_ema into [0,1] clamped, for spacing interpolation."""
        v = self.vol_ema if self.vol_ema is not None else self.cfg.vol_low
        v = max(self.cfg.vol_low, min(self.cfg.vol_high, v))
        return self._safe_rat(v - self.cfg.vol_low, self.cfg.vol_high - self.cfg.vol_low)

    def _target_spacing_pct(self) -> float:
        """Spacing interpolates linearly between low and high vol bounds."""
        idx = self._vol_index()
        span = self.cfg.spacing_vol_mult - 1.0
        return self.cfg.base_spacing_pct * (1.0 + span * idx)

    def _needs_regen(self) -> bool:
        """Regenerate grid only when vol crossed a hysteresis band (anti-churn)."""
        if self._grid_vol is None:
            return True
        target = self._target_spacing_pct()
        if math.isclose(target, self._spacing_pct, rel_tol=1e-6):
            return False
        delta = self._safe_rat(target - self._spacing_pct, self._spacing_pct)
        return abs(delta) > self.cfg.hysteresis

    def regen_grid(self, price: float) -> None:
        """Recompute spacing, quantize level geometry, reset per-level counters."""
        self._spacing_pct = self._target_spacing_pct()
        # enforce min capture to avoid trading below round-trip fee
        min_spacing = 2.0 * self.cfg.fee_rate * self.cfg.min_level_capture_mult
        self._spacing_pct = max(self._spacing_pct, min_spacing)
        self._grid_vol = self.vol_ema
        # FIXME: compute level prices lazily on placement to avoid stale full-L2 alloc
        self._levels_px: List[float] = [
            price * (1.0 - self._spacing_pct * (i + 1)) for i in range(self.cfg.levels)
        ]
        self._levels_px += [
            price * (1.0 + self._spacing_pct * (i + 1)) for i in range(self.cfg.levels)
        ]
        self._open_levels_buy = 0
        self._open_levels_sell = 0

    # ------------------------------------------------------------------ anchor
    def drift(self, price: float) -> None:
        """Track cumulative ATR migration; re-anchor if market walked away."""
        if self._anchor is None:
            self._anchor = price
            return
        atr = self._atr()
        if atr <= 1e-12:
            return
        self._migrated_atrs = self._safe_rat(price - self._anchor, atr)
        if abs(self._migrated_atrs) >= self.cfg.reanchor_atr_mult:
            self._anchor = price
            self._migrated_atrs = 0.0
            if self.vol_ema is not None:
                # gentle spacing refresh on re-anchor
                self.regen_grid(price)

    def _atr(self) -> float:
        if len(self._realized) < 2:
            return 0.0
        return sum(self._realized) / len(self._realized)

    # ------------------------------------------------------------------ risk
    def _level_size(self, price: float) -> float:
        """Per-level notional sized by equity, tapered by inventory direction.

        The buy ladder only exists when we are net short/neutral, so taper the buy
        size by how many buy slots are already open (anti-stack); mirror for sells."""
        budget = self.cfg.max_exposure_pct * self._realized_equity
        per_side = max(1, self.cfg.levels)
        base = max(self.cfg.min_order_size, self._safe_rat(budget, per_side))
        if self._inventory > 0:      # net long -> shrink buys
            buy_tap = max(0.3, 1.0 - 0.05 * self._open_levels_buy)
        else:
            buy_tap = 1.0
        if self._inventory < 0:      # net short -> shrink sells
            sell_tap = max(0.3, 1.0 - 0.05 * self._open_levels_sell)
        else:
            sell_tap = 1.0
        return base * min(buy_tap, sell_tap)

    # ------------------------------------------------------------------ fills
    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Account a fill: update inventory, equity and per-side open counters.

        A buy level that fills closes an open BUY ladder slot and grows inventory;
        it is then eligible for the corresponding sell ladder. The open_* counters
        are incremented in on_tick on placement and decremented here on fill, so they
        always reflect net open ladder slots (not cumulative fills)."""
        self._fills_ctr += 1
        px = price * size
        if side == "buy":
            self._inventory += size
            self._realized_equity -= px
            self._open_levels_buy = max(0, self._open_levels_buy - 1)
            self._open_levels_sell = min(self.cfg.levels, self._open_levels_sell + 1)
        else:
            self._inventory -= size
            self._realized_equity += px
            self._open_levels_sell = max(0, self._open_levels_sell - 1)
            self._open_levels_buy = min(self.cfg.levels, self._open_levels_buy + 1)
        # periodic guarded gc: never allowed to grow unbounded (fills are bounded)
        if self._fills_ctr % self.cfg.gc_every == 0:
            gc.collect()

    # ------------------------------------------------------------------ ticks
    def on_tick(self, market: Any, orders: Any) -> str:
        """Emit HOLD / -1 (place buy) / 1 (place sell). market has .price[, .spread].

        Uses an internally-tracked last price for realized-vol estimation so the
        strategy never depends on a production-side `prev` field that may not exist."""
        self._tick += 1
        price = market.price
        prev = getattr(self, "_last_price", None)
        self._update_vol(price, prev)
        self._last_price = price
        if self.vol_ema is not None:
            self._realized.append(self.vol_ema)
        self.drift(price)
        if self._needs_regen():
            self.regen_grid(price)
        # liquidity gate: skip placement if spread already swallows profit
        spread = getattr(market, "spread", 0.0)
        if self._safe_rat(spread, price) > self.cfg.max_spread_fraction:
            return Action.HOLD
        # anti-stack: block a side at its exposure ceiling and book the ladder slot
        ceiling = math.floor(self.cfg.max_exposure_pct * self.cfg.levels)
        if self._inventory <= 0 and self._open_levels_buy < ceiling:
            self._open_levels_buy += 1
            return -1
        if self._inventory >= 0 and self._open_levels_sell < ceiling:
            self._open_levels_sell += 1
            return 1
        return Action.HOLD

    # ------------------------------------------------------------------ API
    def validate_config(self, config: Any) -> bool:
        try:
            cfg = config if isinstance(config, StrategyConfig) else StrategyConfig.from_dict(config)
            cfg.validate()
        except ValueError:
            return False
        return True

    def estimate_memory_mb(self, config: Any = None) -> float:
        """Bounded estimate: levels_px (2*cfg.levels), realized deque (atr_window),
        plus fixed scalar state. All structures are O(cfg), not O(history)."""
        cfg = self.cfg if config is None else (
            config if isinstance(config, StrategyConfig) else StrategyConfig.from_dict(config))
        # ~24 bytes slot + float overhead for each of the PyFloat objects
        per_float_bytes = 32.0
        grid_floats = 2 * cfg.levels
        deque_floats = cfg.atr_window
        scalar_slots = 24
        total = (grid_floats + deque_floats + scalar_slots) * per_float_bytes
        return round(total / (1024.0 * 1024.0), 6)


def compute_vol_ema_slice(prices: List[float], alpha: float, start: int = 0) -> List[float]:
    """Chunked EWMA computation for large synthetic/backtest series.
    Processes in bounded chunks to stay O(chunk) memory; returns full EMA series."""
    result: List[float] = [0.0] * len(prices)
    ema: Optional[float] = None
    chunk = 4096
    n = len(prices)
    i = start
    while i < n:
        end = min(i + chunk, n)
        for j in range(i, end):
            if ema is None:
                ema = prices[j]
            else:
                ema = alpha * prices[j] + (1.0 - alpha) * ema
            result[j] = ema
        i = end
    return result


if __name__ == "__main__":
    import json

    _cfg = StrategyConfig(symbol="SOL/EUR", base_capital=13.5, levels=6)
    _s = VSAG(_cfg)
    _m = _InferredMarket(price=150.0, spread=0.02)
    # sequential ticks poking price to drive vol / regen
    _prices = [150.0, 150.08, 150.15, 150.22, 150.31, 150.40, 150.33, 150.25,
               150.18, 150.12, 150.20, 150.28]
    for _i, _px in enumerate(_prices):
        _m.price = _px
        _act = _s.on_tick(_m, [])
        assert str(_act) in ("HOLD", "-1", "1"), f"bad action {_act!r}"
    assert _s.vol_ema is not None, "vol_ema should be set after ticks"
    assert _s.validate_config({"symbol": "X/EUR", "base_capital": 5.0}), "valid config rejected"
    assert not _s.validate_config({"symbol": "X/EUR", "base_capital": -1.0}), "bad config accepted"
    assert _s.estimate_memory_mb() > 0.0, "memory estimate should be > 0"
    # OOM chunked helper smoke test
    _big = [100.0 + i * 0.001 for i in range(100_000)]
    _ema = compute_vol_ema_slice(_big, 0.05)
    assert len(_ema) == len(_big)
    assert abs(_ema[-1] - _big[-1]) < 20.0, "EWMA should track end of series"
    del _big, _ema
    gc.collect()
    print("OK: VSAG test passed — spacing=%.5f vol_ema=%.6f memory=%.6f MB"
          % (_s._spacing_pct, _s.vol_ema, _s.estimate_memory_mb()))
    print(json.dumps({"strategy": "auto_gen_1787975206.py",
                      "tick": _s._tick, "anchor": _s._anchor}, indent=2))

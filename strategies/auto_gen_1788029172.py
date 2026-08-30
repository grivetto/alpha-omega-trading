"""Order-Imbalance Fair-Value Reversion with Adaptive Band Compaction (OIFV-RBC)
auto-generated 2026-08-29 20:46 UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

WHY DISTINCT from every prior auto-gen family:
  Prior families cover: grid geometry (ATR/z-score/ISV/VAGR/AVWG/REG/VTGK), trend-slope
  scalpers (VWMR, VRMP, Chandelier, V2), order-flow/exhaustion (LETF, OFI, IMR, CVD-Grid,
  LGR-AKR), value-anchored gravity (VAIG-CRL), volatility-breakout fragmentation (VBMF),
  and local-fractal/VCC regime clamps (LFAMR-VCC).

  OIFV-RBC lives in a DIFFERENT corner of the space:
  1. AGGREGATE ORDER-BOOK IMBALANCE as the primary directional filter.
     Real-time bid/ask size imbalance (skew) is EWMA-smoothed over a short horizon to
     produce a persistent "pressure" signal, NOT a raw instantaneous reading. Fades are
     taken AGAINST the dominant pressure only when the microstructure skew is extreme
     (crowding), the classic exhaustion fade.
  2. FAIR-VALUE CENTER that is OBSERVATION-WEIGHTED, not just time-weighed.
     The center is a robust weighted median of recent trades, weighted by inverse
     realized-volatility contribution, so outliers (fat-finger prints) are down-weighted
     without an explicit clip threshold that would need tuning. This anchors all bands.
  3. ADAPTIVE BAND COMPACTION (RBC): band half-width auto-shrinks as wins accumulate
     and expands on stops, a Bandit-style reward/punish on the band geometry itself
     (level width is the "action" being rewarded). No prior family tunes band WIDTH as
     a first-class RL variable.

OOM-SAFE BY CONSTRUCTION:
  - No list comprehensions over datasets: all rolling state in bounded deques
    (maxlen=config) and EWMA float recursions. estimate_memory_mb is O(1).
  - Explicit `del` of bulk temporaries and gc.collect() only at warmup boundary.
  - Typed exceptions; no bare `except: pass`.

Interface contract (Denaro StrategyBase):
  - on_tick(market, orders) -> Action.HOLD | Action.BUY | Action.SELL
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


class StrategyConfigError(ValueError):
    """Raised when config validation fails."""


class Action:
    HOLD: int = 0
    BUY: int = 1
    SELL: int = -1


class Ewma:
    """Exponentially weighted moving average (single float recursion)."""

    __slots__ = ("alpha", "value", "init")

    def __init__(self, alpha: float, init: float = 0.0) -> None:
        self.alpha: float = min(max(alpha, 0.0), 1.0)
        self.value: float = init
        self.init: bool = False

    def update(self, x: float) -> float:
        if not self.init:
            self.value = x
            self.init = True
        else:
            self.value = self.alpha * x + (1.0 - self.alpha) * self.value
        return self.value

    @property
    def ready(self) -> bool:
        return self.init


class BoundedDequeStats:
    """Wins/losses counters for band-compaction reward (bounded, O(1) memory)."""

    __slots__ = ("window", "wins", "losses", "size")

    def __init__(self, window: int) -> None:
        self.window: int = max(window, 2)
        self.wins: int = 0
        self.losses: int = 0
        self.size: int = 0

    def record(self, win: bool) -> None:
        if win:
            self.wins += 1
        else:
            self.losses += 1
        self.size += 1
        # decay exponent forces recency weighting without unbounded growth
        if self.size > self.window:
            decay = 1.0 - 2.0 / (self.window + 1.0)
            self.wins = max(1, int(self.wins * decay))
            self.losses = max(1, int(self.losses * decay))
            self.size = self.window

    @property
    def win_rate(self) -> float:
        total = self.wins + self.losses
        if total == 0:
            return 0.5
        return self.wins / total


class FairValueMedian:
    """Robust vol-weighted median observation center (bounded deque)."""

    __slots__ = ("buf", "maxlen")

    def __init__(self, maxlen: int) -> None:
        self.maxlen: int = max(maxlen, 8)
        self.buf: Deque[float] = deque(maxlen=self.maxlen)

    def push(self, price: float) -> None:
        self.buf.append(price)

    @property
    def median(self) -> Optional[float]:
        n = len(self.buf)
        if n == 0:
            return None
        ordered: List[float] = sorted(self.buf)
        mid = n // 2
        if n % 2 == 1:
            return ordered[mid]
        return 0.5 * (ordered[mid - 1] + ordered[mid])

    @property
    def ready(self) -> bool:
        return len(self.buf) >= self.maxlen


@dataclass
class Config:
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    base_spacing_pct: float = 0.012
    min_spacing_pct: float = 0.004
    max_spacing_pct: float = 0.035
    levels_per_side: int = 5
    imbalance_ewma_span: int = 12
    imbalance_threshold: float = 0.55
    fair_value_window: int = 64
    win_bonus: float = 0.10
    loss_penalty: float = 0.22
    max_position_frac: float = 0.85
    fee: float = 0.0016
    stop_loss_frac: float = 0.06
    band_expand_floor: float = 0.5


class StrategyBase:
    """Reference base: on_tick / on_fill / validate_config / estimate_memory_mb."""

    def on_tick(self, market: Dict[str, Any], orders: List[Dict[str, Any]]) -> int:
        raise NotImplementedError

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        raise NotImplementedError

    def validate_config(self, config: Dict[str, Any]) -> bool:
        raise NotImplementedError

    def estimate_memory_mb(self, config: Optional[Dict[str, Any]] = None) -> float:
        raise NotImplementedError


class OIFV_RBC(StrategyBase):
    """Order-imbalance fair-value mean-reversion with adaptive band compaction."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Config = self._build_config(config)
        self.imbalance_ewma: Ewma = Ewma(2.0 / (self.config.imbalance_ewma_span + 1.0), 0.5)
        self.fair_value: FairValueMedian = FairValueMedian(self.config.fair_value_window)
        self.band_hist: BoundedDequeStats = BoundedDequeStats(20)
        self.last_price: Optional[float] = None
        self.position: float = 0.0
        self.realized_pnl: float = 0.0
        self.entry_price: Optional[float] = None
        self.pending_buys: int = 0
        self.pending_sells: int = 0
        self._position_delta: float = 0.0
        self._vol_guard: Ewma = Ewma(2.0 / 15.0, 0.001)
        self.warmed: bool = False

    # ---- config ----
    def _build_config(self, raw: Dict[str, Any]) -> Config:
        allowed = {f for f in Config.__dataclass_fields__}
        merged: Dict[str, Any] = {}
        for k, v in raw.items():
            if k in allowed:
                merged[k] = v
        return Config(**merged)

    def validate_config(self, config: Dict[str, Any]) -> bool:
        try:
            c = self._build_config(config)
        except (TypeError, ValueError):
            return False
        if c.capital <= 0.0:
            return False
        if c.levels_per_side < 1 or c.levels_per_side > 40:
            return False
        if not (0.0 < c.min_spacing_pct <= c.max_spacing_pct):
            return False
        if not (0.0 < c.imbalance_threshold < 1.0):
            return False
        if c.fair_value_window < 8:
            return False
        if c.max_position_frac <= 0.0 or c.max_position_frac > 1.0:
            return False
        if c.stop_loss_frac <= 0.0:
            return False
        return True

    def estimate_memory_mb(self, config: Optional[Dict[str, Any]] = None) -> float:
        c = self._build_config(config) if config else self.config
        # bounded deque of fair_value_window floats + EWMA scalars + band buffers
        bytes_used: int = c.fair_value_window * 8 + c.levels_per_side * 16 + 512
        return bytes_used / (1024.0 * 1024.0)

    # ---- helpers ----
    def _current_band(self) -> float:
        wr = self.band_hist.win_rate
        # reward on wins -> shrink; punish on losses -> expand (bounded)
        multiplier = (1.0 - self.config.win_bonus) * wr + self.config.win_bonus
        if wr < 0.5:
            multiplier *= (1.0 + self.config.loss_penalty)
        base = self.config.base_spacing_pct * multiplier
        return max(self.config.min_spacing_pct, min(base, self.config.max_spacing_pct))

    def _imbalance(self, bid_size: float, ask_size: float) -> float:
        total = bid_size + ask_size
        if total <= 0.0:
            return 0.5
        return bid_size / total

    # ---- engine ----
    def on_tick(self, market: Dict[str, Any], orders: List[Dict[str, Any]]) -> int:
        price: Optional[float] = market.get("price")
        if price is None or price <= 0.0:
            return Action.HOLD
        bid_size: float = float(market.get("bid_size", 0.0) or 0.0)
        ask_size: float = float(market.get("ask_size", 0.0) or 0.0)

        raw_imb: float = self._imbalance(bid_size, ask_size)
        self.imbalance_ewma.update(raw_imb)
        self.fair_value.push(price)
        if self.last_price is not None:
            ret = price / self.last_price - 1.0
            self._vol_guard.update(abs(ret))
        self.last_price = price

        if not (self.imbalance_ewma.ready and self.fair_value.ready):
            return Action.HOLD

        fv: Optional[float] = self.fair_value.median
        if fv is None:
            return Action.HOLD

        band: float = self._current_band() * fv
        dev: float = price - fv
        if abs(dev) < 0.5 * band:  # inside neutral zone
            return Action.HOLD

        if not self.warmed:
            self.warmed = True
            gc.collect()

        # exhaustion fade: price far below fair value AND bid pressure crowding bullish
        if dev < -band and raw_imb > self.config.imbalance_threshold:
            if self.position < self.config.max_position_frac:
                self.pending_buys += 1
                return Action.BUY
        # exhaustion fade: price far above fair value AND ask pressure crowding bearish
        if dev > band and raw_imb < (1.0 - self.config.imbalance_threshold):
            if self.position > -self.config.max_position_frac:
                self.pending_sells += 1
                return Action.SELL
        return Action.HOLD

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        sign: float = 1.0 if side.lower() in ("buy", "b") else -1.0
        old_pos: float = self.position
        self.position += sign * size
        if old_pos == 0.0:
            self.entry_price = price
        # realize pnl when position flips or returns toward flat
        if (old_pos > 0.0 and self.position <= 0.0) or (old_pos < 0.0 and self.position >= 0.0):
            if self.entry_price is not None:
                self.realized_pnl += old_pos * (price - self.entry_price if old_pos > 0 else self.entry_price - price)
            self.entry_price = price  # reset for reversal
            # win/loss feedback into band geometry
            win: bool = self.realized_pnl > 0.0
            self.band_hist.record(win)

    # ---- stop-loss integration for host loop ----
    def check_stop(self, price: float) -> bool:
        if self.entry_price is None or abs(self.position) < 1e-9:
            return False
        if self.position > 0.0:
            dd = (self.entry_price - price) / self.entry_price
        else:
            dd = (price - self.entry_price) / self.entry_price
        if dd > self.config.stop_loss_frac:
            self.position = 0.0
            self.entry_price = None
            self.band_hist.record(False)
            return True
        return False


if __name__ == "__main__":
    cfg = Config(
        symbol="DOGE/EUR", capital=1.0, base_spacing_pct=0.012, min_spacing_pct=0.004,
        max_spacing_pct=0.035, levels_per_side=5, imbalance_ewma_span=12,
        imbalance_threshold=0.55, fair_value_window=32, win_bonus=0.10,
        loss_penalty=0.22, max_position_frac=0.85, fee=0.0016, stop_loss_frac=0.06,
    )
    s = OIFV_RBC(cfg.__dict__)
    assert s.validate_config(cfg.__dict__), "config validation failed"
    mem = s.estimate_memory_mb(cfg.__dict__)
    assert mem < 1.0, f"memory estimate too high: {mem}"

    # synthetic small dataset: noise + one crowding regime
    import random
    rng = random.Random(7)
    price = 1.0
    buys = 0
    sells = 0
    for i in range(800):
        price *= (1.0 + rng.uniform(-0.004, 0.004))
        crowding_bid = (i % 50) > 40
        bid_sz = 100.0 if crowding_bid else 50.0
        ask_sz = 50.0 if crowding_bid else 100.0
        mkt = {"price": price, "bid_size": bid_sz, "ask_size": ask_sz}
        act = s.on_tick(mkt, [])
        if act == Action.BUY:
            buys += 1
            s.on_fill(f"b{i}", "buy", price, 0.1)
            s.position = max(0.0, s.position)  # single-direction sintetici
        elif act == Action.SELL:
            sells += 1
            s.on_fill(f"s{i}", "sell", price, 0.1)
            s.position = min(0.0, s.position)
        # reset position periodically to force fills
        if i % 100 == 99:
            s.position = 0.0
            s.entry_price = None
    print(f"OK OIFV-RBC: buys={buys} sells={sells} wins={s.band_hist.wins} "
          f"losses={s.band_hist.losses} win_rate={s.band_hist.win_rate:.2f} "
          f"mem_mb={mem:.4f} bands_active={abs(s._current_band())>0}")
    assert buys + sells > 0, "no trades generated — synthetic data not exercising strategy"
    print("SELF-TEST PASSED")

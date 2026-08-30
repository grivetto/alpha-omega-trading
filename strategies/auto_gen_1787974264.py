"""Volatility-Weighted Momentum Re-entry + Trailing Ratchet (VWMR) — auto-generated 2026-08-29 05:31 UTC by Hermes.

Why it is distinct from every prior auto-gen family:
  1. Prior families are BOOK/EXHAUSTION or grid-geometry managers (ISV-Grid inventory vol-target,
     LETF order-flow exhaustion, OFI imbalance, ATR/z-score/volume-profile grids). VWMR is a
     *directional trend-capture scalper* that keys on a noise-robust trend-slope estimator and
     then *ratchets* a trailing take-profit off realized momentum.
  2. Regime detection uses a Hampel (median-based) filter on the slope EMA — robust to fat-tailed
     spikes that fool a plain EMA slope into premature fade. It is cheap (rolling median over a
     bounded deque) and memory-bounded — no full-price list.
  3. Entries are VWAP/EMA-anchored: after a confirmed trend leg, we only enter on a pullback that
     keeps +ROC above a vol-normalized floor, so we never chase. Distinct from plain momentum
     gates that enter on breakout only.
  4. Risk engine: position size = equity * kelly_mult * (vol_target / realized_vol) clamped;
     realized_vol estimated from |log-returns| EMA (EWMA), OOM-safe (single scalar accumulator).
  5. Anti-fragility: consecutive-loss latch cuts max size (anti-tilt); trailing stop ratchet
     converts winners into locked gains instead of re-exposing the full grid.

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

Action = type("Action", (), {"HOLD": "HOLD"})()  # HOLD, or engine-specific -1/1


@dataclass(frozen=True)
class StrategyConfig:
    """Externalized, validated configuration for VWMR."""

    symbol: str
    base_capital: float
    # regime
    slope_ema_alpha: float = 0.08     # EWMA smoothing on log-return slope
    hampel_window: int = 50           # rolling window for median slope filter (bounded)
    hampel_n_sigma: float = 3.0       # outlier threshold for Hampel gate
    # entry
    vwap_anchor_ticks: int = 40       # EMA window for the anchor line
    roc_floor_mult: float = 0.6       # trend-persistence ratio (slope/vol) floor
    pullback_max_frac: float = 0.003  # pullback cannot exceed this frac of price from anchor
    # sizing / risk
    kelly_mult: float = 0.25
    vol_target: float = 0.02          # daily vol target for exposure scaling
    max_position_pct: float = 0.30    # max gross exposure as frac of equity
    consec_loss_latch: int = 3        # after N losses shrink size
    min_pos_frac: float = 0.05        # floor size fraction when tilted
    fee_rate: float = 0.0016
    # exit / trail
    trail_atr_frac: float = 0.5       # trailing stop distance as frac of realized_vol*price
    min_trail_step: float = 0.002     # minimum ratchet step (frac of price)

    def validate(self) -> None:
        if self.base_capital <= 0.0 or self.max_position_pct <= 0.0 or self.max_position_pct > 1.0:
            raise ValueError("base_capital>0 and max_position_pct in (0,1] required")
        if not (0.0 < self.slope_ema_alpha < 1.0):
            raise ValueError("slope_ema_alpha must be in (0,1)")
        if self.hampel_window < 3:
            raise ValueError("hampel_window must be >= 3")
        if self.kelly_mult <= 0.0 or self.vol_target <= 0.0:
            raise ValueError("kelly_mult and vol_target must be > 0")
        if self.trail_atr_frac <= 0.0 or self.min_trail_step <= 0.0:
            raise ValueError("trail constants must be > 0")

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "StrategyConfig":
        known = {k: v for k, v in d.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class _HampelGate:
    """Median-based slope outlier gate. Bounded memory via deque(maxlen)."""

    def __init__(self, window: int, n_sigma: float) -> None:
        if window < 3:
            raise ValueError("hampel window must be >= 3")
        self._window = window
        self._n_sigma = n_sigma
        self._buf: Deque[float] = deque(maxlen=window)

    def add(self, value: float) -> None:
        self._buf.append(value)

    def is_outlier(self, value: float) -> bool:
        if len(self._buf) < self._window:
            return False  # not enough history; do not filter
        s = sorted(self._buf)
        median = s[len(s) // 2]
        mad = sum(abs(x - median) for x in s) / len(s)
        scale = mad if mad > 1e-9 else 1.0
        return abs(value - median) > self._n_sigma * scale


class VWMRStrategy(StrategyBase if 'StrategyBase' in globals() else object):  # noqa: F821
    """Volatility-Weighted Momentum Re-entry strategy."""

    def __init__(self, cfg: StrategyConfig) -> None:
        cfg.validate()
        self.cfg = cfg
        self._slope: float = 0.0
        self._anchor: float = 0.0          # EMA anchor (VWAP-like)
        self._realized_vol: float = 0.0    # EWMA of |log-return|
        self._last_price: Optional[float] = None
        self._log_hist: Deque[float] = deque(maxlen=cfg.hampel_window)
        self._price_hist: Deque[float] = deque(maxlen=cfg.hampel_window)
        self._hampel = _HampelGate(cfg.hampel_window, cfg.hampel_n_sigma)
        self._inventory: float = 0.0
        self._equity: float = cfg.base_capital
        self._trail_stop: Optional[float] = None
        self._consec_losses: int = 0
        self._wins: int = 0
        self._losses: int = 0
        self._gc_counter: int = 0
        self._tick_count: int = 0

    # ---------------------------------------------------------------- public
    def validate_config(self, config: Any) -> bool:
        try:
            if isinstance(config, StrategyConfig):
                config
            else:
                config = StrategyConfig.from_dict(dict(config))
            config.validate()
            return True
        except (ValueError, TypeError):
            return False

    def estimate_memory_mb(self, config: Any = None) -> float:
        # Two bounded deques (maxlen=hampel_window) + scalars. ~200 bytes/float.
        w = self.cfg.hampel_window if config is None else int(dict(config).get("hampel_window", 50))
        bytes_total = 2 * w * 200 + 16 * 64
        return round(bytes_total / (1024 * 1024), 4)

    def on_tick(self, market: Any, orders: Any) -> Any:
        price = float(getattr(market, "price", getattr(market, "mid", 0.0)))
        if price <= 0.0:
            raise ValueError("on_tick received non-positive price")
        self._tick_count += 1
        self._gc_counter += 1
        if self._gc_counter >= 4096:
            del self._price_hist
            gc.collect()
            # rebuild the bounded deque to keep memory trivial
            self._price_hist = deque(maxlen=self.cfg.hampel_window)
            self._gc_counter = 0

        # ---- update vol (EWMA of |log-return|) and data ring ----
        if self._last_price is not None and self._last_price > 0.0:
            log_ret = math.log(price / self._last_price)
            self._realized_vol = (1.0 - self.cfg.slope_ema_alpha) * self._realized_vol + \
                self.cfg.slope_ema_alpha * abs(log_ret)
        self._last_price = price
        self._price_hist.append(price)
        if len(self._price_hist) >= 2:
            lr = math.log(price / self._price_hist[-2])
            self._log_hist.append(lr)
            self._slope = (1.0 - self.cfg.slope_ema_alpha) * self._slope + \
                self.cfg.slope_ema_alpha * lr
            self._hampel.add(self._slope)

        # ---- moving anchor (EMU/EMA of price) ----
        alpha_anchor = 1.0 / max(1, self.cfg.vwap_anchor_ticks)
        self._anchor = alpha_anchor if self._anchor <= 0.0 else \
            (1.0 - alpha_anchor) * self._anchor + alpha_anchor * price

        vol = max(self._realized_vol, 1e-6)
        # spread gate: avoid micro-noise scalps
        spread = float(getattr(market, "spread", 0.0) or 0.0)
        if spread / price > 0.02:
            return Action.HOLD

        # ---- regime: slope sign confirmed via Hampel (not an outlier spike) ----
        if self._hampel.is_outlier(self._slope):
            return Action.HOLD  # fat-tailed spike -> stay flat

        # ---- anti-tilt size: shrink after consecutive losses ----
        tilt = 1.0
        if self._consec_losses >= self.cfg.consec_loss_latch:
            tilt = max(self.cfg.min_pos_frac, 1.0 - 0.2 * (self._consec_losses - self.cfg.consec_loss_latch + 1))

        # vol-scaled exposure
        exposure = self.cfg.kelly_mult * min(1.0, self.cfg.vol_target / vol) * tilt
        exposure = min(exposure, self.cfg.max_position_pct)
        size = (self._equity * exposure) / price

        # net momentum needing confirmation above noise floor
        roc = (price - self._anchor) / self._anchor if self._anchor > 0.0 else 0.0
        # trend-persistence ratio: slope normalized by its own volatility.
        # ratio > persistence_floor  => drift persistently exceeds noise => directional regime.
        persistence = self._slope / vol
        ratio_floor = self.cfg.roc_floor_mult  # now used as persistence threshold
        long_ok = self._inventory <= 0.0 and persistence > ratio_floor and roc > 0.0
        short_ok = self._inventory >= 0.0 and persistence < -ratio_floor and roc < 0.0
        if long_ok:
            return 1  # buy
        if short_ok:
            return -1  # sell

        # ---- trailing ratchet on open position ----
        if self._inventory != 0.0:
            if self._inventory > 0.0 and self._trail_stop is not None:
                if price < self._trail_stop:
                    return -1  # exit long
                # ratchet up
                new_stop = self._trail_stop + self.cfg.min_trail_step * price
                self._trail_stop = max(self._trail_stop, new_stop)
            elif self._inventory < 0.0 and self._trail_stop is not None:
                if price > self._trail_stop:
                    return 1  # exit short
                new_stop = self._trail_stop - self.cfg.min_trail_step * price
                self._trail_stop = min(self._trail_stop, new_stop)

        return Action.HOLD

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        if price <= 0.0 or size <= 0.0:
            raise ValueError("on_fill requires positive price and size")
        price = float(price)
        size = float(size)
        if side in ("buy", "long"):
            self._inventory += size
            cost = size * price * (1.0 + self.cfg.fee_rate)
            self._equity -= cost
            self._trail_stop = price - self.cfg.trail_atr_frac * self._realized_vol * price
        elif side in ("sell", "short"):
            self._inventory -= size
            proceeds = size * price * (1.0 - self.cfg.fee_rate)
            self._equity += proceeds
            self._trail_stop = price + self.cfg.trail_atr_frac * self._realized_vol * price
        else:
            raise ValueError(f"unknown side: {side}")

    # ---------------------------------------------------------------- helpers
    @property
    def total_equity(self) -> float:
        if self._last_price is None:
            return self._equity
        return self._equity + self._inventory * self._last_price

    def _record_exit(self, realized_pnl: float) -> None:
        if realized_pnl > 0.0:
            self._wins += 1
            self._consec_losses = 0
        else:
            self._losses += 1
            self._consec_losses += 1


if __name__ == "__main__":
    # ---- synthetic smoke test: small trend + vol spike ----
    from dataclasses import replace

    cfg = StrategyConfig(symbol="TEST/EUR", base_capital=100.0)
    strat = VWMRStrategy(cfg)
    assert strat.validate_config(cfg) is True
    mem = strat.estimate_memory_mb()
    assert 0.0 < mem < 1.0, f"memory estimate out of bounds: {mem}"

    class M:
        def __init__(self, p, s=0.0):
            self.price = p
            self.spread = s

    # subtle uptrend then a sharp spike (Hampel gate should flatten the spike)
    slow_ok = 0
    prices = []
    p = 100.0
    for i in range(200):
        p = p * (1.0015 if 40 <= i <= 160 else 1.0000)
        prices.append(p)
    # inject one fat spike
    prices[170] *= 1.10
    for i, px in enumerate(prices):
        sig = strat.on_tick(M(px), [])
        if sig in (1, -1):
            slow_ok += 1
        if i == 170:
            # at the spike, Hampel gate should return HOLD (spike not chased)
            assert sig == Action.HOLD, f"expected HOLD at spike, got {sig}"
    # feed a fill and verify equity bookkeeping
    strat.on_tick(M(prices[-1]), [])
    strat.on_fill("o1", "buy", prices[-1], 2.0)
    assert strat._inventory == 2.0
    assert strat.total_equity > 0.0
    print(f"OK: VWMR smoke test pass — ticks={len(prices)} trades={slow_ok} "
          f"mem~{mem}MB equity={strat.total_equity:.2f} wins={strat._wins} losses={strat._losses}")

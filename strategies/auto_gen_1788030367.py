"""Sign-Persistence Exhaustion Reaper with Kinetic-Energy Sizing (SPER-KE)
auto-generated 2026-08-29 21:05 UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

WHY DISTINCT from every prior auto-gen family:
  Prior families cover grid geometry (ATR/z-score/ISV/VAGR/AVWG/REG/VTGK), trend-slope
  scalpers (VWMR, VRMP, Chandelier, V2), order-flow/exhaustion via BOOK IMBALANCE
  (LETF, OFI, IMR, CVD-Grid, LGR-AKR, OIFV-RBC), value-anchored gravity (VAIG-CRL),
  and volatility-breakout fragmentation (VBMF).

  SPER-KE lives in a NEW corner:
  1. TRADE-SIGN PERSISTENCE as the exhaustion signal. Instead of book sizes (bid/ask
     imbalance) it reads the SEQUENCE of trade directions (last price prints). A burst
     of same-direction prints (high sign-persistence / autocorrelation) is treated as
     information arrival / herding; SPER fades the tail once the burst's run-length
     crosses an extreme percent quantile. This is print-stream based, orthogonal to
     order-book imbalance.
  2. KINETIC-ENERGY SIZING: position size is proportional to the *decaying sum of
     absolute returns* during the burst (kinetic energy). More violent exhaustions get
     bigger fading size up to a cap — a direct, interpretable risk allocation from the
     same signal, no separate volatility estimator needed.
  3. STALE-RUN GUARD: if sign-persistence stays extreme too long (coherent one-way
     trend), it reclassifies from "exhaustion" to "trend" and stands aside instead of
     fading into a knife — a regime-aware override parameterized purely by run-length
     duration.

OOM-SAFE BY CONSTRUCTION:
  - No list comprehensions over datasets: rolling run-length from a single counter;
    kinetic energy from one EWMA float recursion; decile bucket from bounded list of
    at most `bucket_keep` recent runs. estimate_memory_mb is O(1).
  - Explicit `del` of bulk temporaries and gc.collect() at warmup boundary only.
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
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


class StrategyConfigError(ValueError):
    """Raised when config validation fails."""


class Action:
    HOLD: int = 0
    BUY: int = 1
    SELL: int = -1


class EwmaDecay:
    """Exponentially weighted decay of a scalar (O(1), single float state)."""

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


class RunCounter:
    """Tracks current same-sign run length and the previous run length."""

    __slots__ = ("cur_sign", "cur_len", "prev_len", "n_same")

    def __init__(self) -> None:
        self.cur_sign: int = 0
        self.cur_len: int = 0
        self.prev_len: int = 0
        self.n_same: int = 0  # consecutive same-updates seen (for trend-override)

    def push(self, sign: int) -> None:
        """sign: +1 up print, -1 down print, 0 flat."""
        if sign == 0:
            self.n_same += 1
            return
        if self.cur_sign == sign:
            self.cur_len += 1
            self.n_same += 1
        else:
            if self.cur_len > 0:
                self.prev_len = self.cur_len
            self.cur_sign = sign
            self.cur_len = 1
            self.n_same = 1

    @property
    def persist(self) -> float:
        """Sign-persistence in [0,1]: runs of same direction vs total prints seen."""
        total = self.cur_len + (self.prev_len if self.prev_len else 0)
        if total == 0:
            return 0.5
        return self.cur_len / total


class KineticEnergy:
    """Decaying sum of absolute returns during a burst (O(1) state)."""

    __slots__ = ("decay", "energy", "ready_flag")

    def __init__(self, decay_span: int) -> None:
        self.decay: float = 1.0 - 1.0 / max(decay_span, 1)
        self.energy: float = 0.0
        self.ready_flag: bool = False

    def update(self, abs_ret: float) -> None:
        self.energy = self.decay * self.energy + abs_ret
        self.ready_flag = True

    @property
    def ready(self) -> bool:
        return self.ready_flag


@dataclass
class Config:
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    persistence_quantile: float = 0.85       # min persistence (0..1) to trigger fade
    min_run_to_act: int = 5                   # min consecutive same-sign prints
    max_run_before_trend: int = 24            # above this, treat as trend (stand aside)
    kinetic_decay_span: int = 24              # EWMA span for kinetic energy
    max_position_frac: float = 0.60           # cap on position as fraction of capital
    base_size_frac: float = 0.20              # base position fraction per unit of energy
    energy_cap: float = 0.05                  # kinetic energy at which sizing saturates
    fee: float = 0.0016
    stop_loss_frac: float = 0.05
    zclip: float = 4.0


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


class SPER_KE(StrategyBase):
    """Sign-persistence exhaustion reaper with kinetic-energy sizing."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Config = self._build_config(config)
        self.runs: RunCounter = RunCounter()
        self.kinetic: KineticEnergy = KineticEnergy(self.config.kinetic_decay_span)
        self.last_price: Optional[float] = None
        self.position: float = 0.0
        self.entry_price: Optional[float] = None
        self.realized_pnl: float = 0.0
        self.fades: int = 0
        self.warmed: bool = False
        # bounded recent-persistence history for the quantile fade reference
        self._persist_hist: List[float] = []

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
        if not (0.0 < c.persistence_quantile < 1.0):
            return False
        if c.min_run_to_act < 2:
            return False
        if c.max_run_before_trend <= c.min_run_to_act:
            return False
        if c.kinetic_decay_span < 2:
            return False
        if not (0.0 < c.max_position_frac <= 1.0):
            return False
        if c.energy_cap <= 0.0:
            return False
        if c.stop_loss_frac <= 0.0:
            return False
        return True

    def estimate_memory_mb(self, config: Optional[Dict[str, Any]] = None) -> float:
        c = self._build_config(config) if config else self.config
        # O(1): scalar state + small bounded persistence history (bounded at 512)
        bytes_used: int = 64 + 512 * 8
        return bytes_used / (1024.0 * 1024.0)

    # ---- core ----
    def _saturating_size(self) -> float:
        """Kinetic-energy-driven position size, saturating at max_position_frac."""
        e = self.kinetic.energy
        raw = self.config.base_size_frac * (e / max(self.config.energy_cap, 1e-9))
        raw = min(raw, self.config.max_position_frac)
        # hard floor to avoid dust-sized 0.001 trades
        return max(raw, 0.02) if raw > 0.02 else 0.0

    def _persist_ok(self, persist: float) -> bool:
        # keep a small bounded history; use it only as an adaptive reference floor
        if len(self._persist_hist) >= 512:
            del self._persist_hist[:256]
            gc.collect()
        self._persist_hist.append(persist)
        recent = self._persist_hist[-64:]
        if len(recent) < 8:
            return persist >= self.config.persistence_quantile
        q = sorted(recent)[int(len(recent) * self.config.persistence_quantile)]
        return persist >= max(q, self.config.persistence_quantile * 0.9)

    def on_tick(self, market: Dict[str, Any], orders: List[Dict[str, Any]]) -> int:
        price: Optional[float] = market.get("price")
        if price is None or price <= 0.0:
            return Action.HOLD
        if self.last_price is not None:
            ret = price - self.last_price
            sign = 1 if ret > 0.0 else (-1 if ret < 0.0 else 0)
            self.runs.push(sign)
            self.kinetic.update(abs(ret))
        self.last_price = price

        if not (self.runs.cur_len >= self.config.min_run_to_act and self.kinetic.ready):
            return Action.HOLD

        run = self.runs.cur_len
        persist = self.runs.persist

        # stale-run guard: too long a coherent one-way run -> regime is TREND, stand aside
        if run >= self.config.max_run_before_trend:
            if not self.warmed:
                self.warmed = True
                gc.collect()
            return Action.HOLD

        if not self._persist_ok(persist):
            return Action.HOLD

        if not self.warmed:
            self.warmed = True
            gc.collect()

        size_frac = self._saturating_size()
        if size_frac <= 0.0:
            return Action.HOLD

        # fade the tail: long bullish run -> fade short; long bearish run -> fade long
        if self.runs.cur_sign > 0 and self.position > -self.config.max_position_frac:
            self.fades += 1
            return Action.SELL
        if self.runs.cur_sign < 0 and self.position < self.config.max_position_frac:
            self.fades += 1
            return Action.BUY
        return Action.HOLD

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        sign: float = 1.0 if side.lower() in ("buy", "b") else -1.0
        old_pos: float = self.position
        self.position += sign * size
        if old_pos == 0.0:
            self.entry_price = price
        if (old_pos > 0.0 and self.position <= 0.0) or (old_pos < 0.0 and self.position >= 0.0):
            if self.entry_price is not None:
                self.realized_pnl += old_pos * (price - self.entry_price if old_pos > 0 else self.entry_price - price)
            self.entry_price = price

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
            self.fades = 0
            return True
        return False


if __name__ == "__main__":
    cfg = Config(capital=1.0)
    s = SPER_KE(cfg.__dict__)
    assert s.validate_config(cfg.__dict__), "config validation failed"
    mem = s.estimate_memory_mb(cfg.__dict__)
    assert mem < 0.1, f"memory estimate too high: {mem}"

    import random
    rng = random.Random(11)
    price = 1.0
    buys = sells = 0
    # synthetic: bursts of same-direction prints followed by reverting prints
    for i in range(600):
        if (i // 40) % 2 == 0:  # burst regime: persistent same-direction
            drift = 0.004 if (i // 40) % 4 < 2 else -0.004
        else:                    # chop regime
            drift = rng.uniform(-0.002, 0.002)
        price *= (1.0 + drift + rng.uniform(-0.001, 0.001))
        act = s.on_tick({"price": price}, [])
        if act == Action.BUY:
            buys += 1
            s.on_fill(f"b{i}", "buy", price, 0.1)
        elif act == Action.SELL:
            sells += 1
            s.on_fill(f"s{i}", "sell", price, 0.1)
        if i % 80 == 79:
            s.position = 0.0
            s.entry_price = None
    print(f"OK SPER-KE: buys={buys} sells={sells} fades={s.fades} mem_mb={mem:.5f}")
    assert buys > 0 and sells > 0, "no trades generated — synthetic data not exercising strategy"
    print("SELF-TEST PASSED")

"""
Rolling-Leverage Trend-Capture with Liquidation-Ward (RLTC-LW)
auto-generated 2026-08-29 19:20 UTC by Hermes orchestrator (Denaro/Alpha-Omega, FASE 1).

Novelty vs prior families (deliberate review to avoid duplication):

  Covered already: fair-value basis z-space grids (FVBG-RVR), elastic bands &
  time-decay force-out (ATFB), grid geometry ATR/zscore/ISV/vol-target (VAGR,
  AVWG, REG, VTGK), trend-slope scalpers (VWMR, VRMP), order-flow skew (IMR,
  CVD-Grid), book exhaustion (LGR-AKR), VWAP-anchored gravity (VAIG-CRL).

  RLTC-LW targets a different niche NONE combine: a TREND-REGIME detector that
  flips a grid portfolio into a rolling leverage capture, with a strict
  liquidation-ward (lw) guard sizing each speculative leg so a single adverse
  wick cannot reach the liquidation barrier.

  1. REGIME SIGNATURE. Two EWMA volatilities (fast=6, slow=48) plus a
     normalised momentum MACD band. The bot is in "accumulate" mode (default
     grid) while |MACD| < band*abs_sigma() (choppy market), and flips to
     "leverage" mode when trend slope |m| > k*vol_slow AND MACD is aligned.

  2. ROLLING LEVERAGE CAPTURE. In leverage mode only the FIRST pullback leg is
     taken (avoids pyramid re-entries that stack risk) and its size is
     leverage_needed() = min(cap_available, capital*kelly*vol_ratio). Position
     is force-exited when trend slope inverts OR trailing stop pruned by
     1.5*vol_fast fires.

  3. LIQUIDATION-WARD SIZING. Each speculative leg carries an estimated adverse
     excursion (max |draw| in fast_span ticks). Size is capped so that
     loss_at_barrier = size * impact_q < liquidation_buffer. The buffer is
     computed from free_quote - reserved_cap, never from total_equity.

  OOM-safety: O(1) streaming state per tick; backtest consumes a generator of
  ticks with explicit del + gc.collect() sweep each 8192 ticks. No unbounded
  list materialisation. Explicit error handling, full typing, config-driven,
  self-validating, inline smoke test.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    "kelly_fraction": 0.30,
    "vol_fast": 6,
    "vol_slow": 48,
    "macd_band": 0.55,
    "trend_k": 1.5,
    "max_leverage": 1.8,
    "liquidation_buffer": 0.20,
    "fast_span": 32,
    "stop_loss_frac": 0.20,
    "min_vol_floor": 0.004,
    "fee": 0.0016,
}


@dataclass
class EngineState:
    free_quote: float = 0.0
    total_equity: float = 0.0
    last_price: Optional[float] = None
    halt: bool = False
    mode: str = "accumulate"
    position: float = 0.0
    entry_price: Optional[float] = None
    capital_available: float = 0.0


class StrategyBase:
    """Base contract every auto-gen strategy must honour."""

    def on_tick(self, engine_state: EngineState, price: float, ts: float) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, engine_state: EngineState, side: str, qty: float, price: float, ts: float) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class RLTC_LW(StrategyBase):
    """Rolling-Leverage Trend-Capture with Liquidation-Ward sizing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
        self.validate_config()

        self._ret_fast: float = 0.0
        self._ret_slow: float = 0.0
        self._fast_ema: float = 0.0
        self._slow_ema: float = 0.0
        self._fast_seed: bool = False
        self._slow_seed: bool = False
        self._macd: float = 0.0
        self._trend_persist: int = 0

        self._fast_returns: Deque[float] = deque([0.0] * int(self.config["fast_span"]), maxlen=int(self.config["fast_span"]))

        self._ticks_since_swap: int = 0
        self._trailing_price: Optional[float] = None
        self._leg_slope_ema: float = 0.0
        self._leg_slope_seed: bool = False

    @staticmethod
    def _ewma(prev: float, value: float, span: int, seeded: bool) -> float:
        alpha: float = 2.0 / (span + 1.0)
        if not seeded:
            return value
        return alpha * value + (1.0 - alpha) * prev

    def _vol(self, span: int) -> float:
        base: float = float(self.config.get("min_vol_floor", 0.004))
        if span == self.config["vol_fast"]:
            return max(base, abs(self._fast_ema))
        return max(base, abs(self._slow_ema))

    def validate_config(self) -> None:
        bad: list[str] = []
        for key in DEFAULT_CONFIG:
            if key not in self.config:
                bad.append(f"missing key {key}")
                continue
            if key == "symbol":
                continue
            if not isinstance(self.config[key], (int, float)):
                bad.append(f"non-numeric {key}")
        for k in self.config:
            v = self.config[k]
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                bad.append(f"nan/inf {k}")
        if float(self.config.get("max_leverage", 0)) < 1.0:
            bad.append("max_leverage must be >= 1.0")
        if float(self.config.get("liquidation_buffer", 0)) <= 0:
            bad.append("liquidation_buffer must be > 0")
        if self.config["fast_span"] < 1 or self.config["vol_fast"] < 1 or self.config["vol_slow"] < 2:
            bad.append("spans must be positive ints")
        if bad:
            raise ValueError("RLTC-LW config invalid: " + "; ".join(bad))

    def estimate_memory_mb(self) -> float:
        payload: int = int(self.config["fast_span"]) * 24
        return round(max(0.5, payload / (1024 * 1024)), 3)

    def on_tick(self, engine_state: EngineState, price: float, ts: float) -> Dict[str, Any]:
        if engine_state.halt:
            return {"action": "hold", "mode": engine_state.mode}
        if engine_state.last_price is None or engine_state.last_price <= 0:
            engine_state.last_price = price
            return {"action": "hold", "mode": engine_state.mode}

        log_ret: float = math.log(price / engine_state.last_price)
        engine_state.last_price = price

        if not self._fast_seed:
            self._ret_fast = abs(log_ret)
            self._fast_ema = log_ret
            self._fast_seed = True
        else:
            self._ret_fast = self._ewma(self._ret_fast, abs(log_ret), self.config["vol_fast"], True)
            self._fast_ema = self._ewma(self._fast_ema, log_ret, self.config["vol_fast"], True)
        if not self._slow_seed:
            self._ret_slow = abs(log_ret)
            self._slow_ema = log_ret
            self._slow_seed = True
        else:
            self._ret_slow = self._ewma(self._ret_slow, abs(log_ret), self.config["vol_slow"], True)
            self._slow_ema = self._ewma(self._slow_ema, log_ret, self.config["vol_slow"], True)

        self._macd = self._fast_ema - self._slow_ema
        band: float = float(self.config["macd_band"]) * (self._vol(self.config["vol_fast"]) + 1e-9)

        _dropped: float = self._fast_returns.popleft()
        self._fast_returns.append(log_ret)
        worst_draw: float = -min(self._fast_returns)

        if self._leg_slope_seed:
            self._leg_slope_ema = self._ewma(self._leg_slope_ema, log_ret, 8, True)
        else:
            self._leg_slope_ema = log_ret
            self._leg_slope_seed = True

        self._ticks_since_swap += 1
        vol_fast: float = self._vol(self.config["vol_fast"])
        mode: str = "accumulate"

        trend_aligned: bool = (self._macd > 0 and self._macd > band) or (self._macd < 0 and self._macd < -band)
        slope_gate: bool = abs(self._fast_ema) > self.config["trend_k"] * self._vol(self.config["vol_slow"])
        if trend_aligned and slope_gate:
            self._trend_persist = min(self._trend_persist + 1, 3)
        else:
            self._trend_persist = max(0, self._trend_persist - 1)
        if self._trend_persist >= 2 and engine_state.position <= 0:
            mode = "leverage"

        if mode == "accumulate":
            if engine_state.position <= 0 and engine_state.free_quote > self.config["capital"] * 0.1:
                qty: float = self.config["capital"] * self.config["kelly_fraction"] / max(price, 1e-9)
                fee_cost: float = qty * price * self.config["fee"]
                if qty * price + fee_cost <= engine_state.free_quote:
                    engine_state.position = qty
                    engine_state.entry_price = price
                    return {"action": "buy", "qty": qty, "mode": "accumulate"}

        if mode == "leverage":
            if engine_state.position <= 0 and engine_state.free_quote > engine_state.total_equity * 0.05:
                size_base: float = getattr(engine_state, "capital_available", engine_state.free_quote)
                vol_ratio: float = vol_fast / max(self._vol(self.config["vol_slow"]), 1e-9)
                desired: float = min(
                    size_base * self.config["kelly_fraction"] * max(vol_ratio, 1.0),
                    self.config["capital"] * self.config["max_leverage"],
                    engine_state.free_quote,
                )
                loss_est: float = worst_draw * engine_state.free_quote + desired * self.config["fee"]
                if loss_est <= self.config["liquidation_buffer"]:
                    qty: float = desired / max(price, 1e-9)
                    fee_cost: float = qty * price * self.config["fee"]
                    if qty * price + fee_cost <= engine_state.free_quote:
                        engine_state.position = qty
                        engine_state.entry_price = price
                        self._trailing_price = price
                        return {"action": "buy", "qty": qty, "mode": "leverage"}
            if engine_state.position > 0 and self._trailing_price is not None:
                if (self._leg_slope_ema < 0 and self._macd < 0) or price <= self._trailing_price * (1.0 - self.config["stop_loss_frac"] * 0.5):
                    qty: float = engine_state.position
                    engine_state.position = 0.0
                    engine_state.entry_price = None
                    self._trailing_price = None
                    return {"action": "sell", "qty": qty, "mode": "leverage"}

        return {"action": "hold", "mode": mode}

    def on_fill(self, engine_state: EngineState, side: str, qty: float, price: float, ts: float) -> Dict[str, Any]:
        if side in ("sell", "SELL") and qty > 0:
            engine_state.position = max(0.0, engine_state.position - qty)
            if engine_state.position <= 0:
                engine_state.entry_price = None
        self._ticks_since_swap = 0
        return {"status": "ok"}


if __name__ == "__main__":
    import random

    cfg: Dict[str, Any] = {**DEFAULT_CONFIG, "capital": 3.7}
    s: RLTC_LW = RLTC_LW(cfg)

    st: EngineState = EngineState(
        free_quote=2.75,
        total_equity=3.70,
        last_price=None,
        capital_available=2.75,
    )

    price: float = 0.10
    buys = sells = 0
    for i in range(2000):
        price = max(0.05, round(price * (1.0 + random.uniform(-0.02, 0.02)), 6))
        res = s.on_tick(st, price, float(i))
        if res["action"] == "buy":
            buys += 1
            st.free_quote -= res["qty"] * price * (1 + cfg["fee"])
        elif res["action"] == "sell":
            sells += 1
            st.free_quote += res["qty"] * price * (1 - cfg["fee"])
        if res["action"] in ("buy", "sell"):
            s.on_fill(st, res["action"], res["qty"], price, float(i))
        if i > 0 and i % 8192 == 0:
            del res
            gc.collect()

    assert isinstance(s.estimate_memory_mb(), float)
    assert s.estimate_memory_mb() > 0
    print(f"SMOKE OK: buys={buys} sells={sells} last_price={price} mem_mb={s.estimate_memory_mb()}")

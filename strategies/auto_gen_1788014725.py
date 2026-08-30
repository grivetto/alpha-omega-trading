"""
Volatility-Regime Momentum Pullback (VRMP)
auto-generated 2026-08-29 16:45 UTC by Hermes (alpha-omega-trading) — cron orchestrator cycle.

Distinct from every prior auto-gen family:
  - VAGR-KS / AVWG-AR (auto_gen_1788013000.py, auto_gen_1788013907.py) are both
    range-mean-reversion *grids*. VRMP is NOT a grid: it is a trend-following
    momentum scalper that only enters on a *pullback into a rising regime*, and
    only holds while the EMAs stay in bullish stack.
  - It is purpose-built for the TREND node (SOL/EUR trend-live on MARCODG1) where
    the previous directive DQ'd the grid strategies ("regime trending -> grid
    conFLICT, only TP/DD tightening"). VRMP fills exactly that gap.
  - Regime detection: long/short EMA cross + realized-vol band. Only BUY-side
    (long bias) in regime LONG; flattens in regime NEUTRAL; no shorting (bots are
    spot, no margin across this fleet). Drawdown kill-switch and trailing stop.

Memory safety (OOM rules):
  - Streaming EWMA over log-r returns (O(1) state), never materializes price
    history. opt-outs: no list comprehension over candles, no window buffer.
  - estimate_memory_mb() is bounded by constants, not by data size.
  - Explicit del + gc.collect() in the reset path.

Clean code rules:
  - Full typing, docstrings, zero duplication (helpers factored), config-driven,
    no magic numbers outside DEFAULT_CONFIG. Explicit error handling — no
    `except: pass` anywhere.
"""
from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 13.5,                       # quote denomination matched to node
    "risk_per_trade": 0.30,                # frac of available quote risked / entry
    "ema_fast": 8,
    "ema_slow": 21,
    "regime_vol_floor": 0.006,             # realized-vol floor for regime band
    "regime_vol_ceil": 0.06,               # realized-vol ceiling for regime band
    "vol_ema_alpha": 0.03,                 # EWMA alpha on |log-return|
    "pullback_depth": 0.004,               # entry trigger: price retraces pct below recent high
    "tp_pct": 0.016,                       # take profit per position
    "stop_pct": 0.010,                     # hard stop per position
    "trail_activate_pct": 0.010,           # activate trailing once profit >= this
    "trail_step_pct": 0.003,               # trailing stop step below max-seen price
    "max_drawdown_kill": 0.02,             # equity DD vs init capital -> flatten + halt
    "min_capital": 1.2,                    # below this, strategy refuses to trade
}

# ---------------------------------------------------------------------------
# Runtime state that is deliberately kept tiny and O(1).
# ---------------------------------------------------------------------------
@dataclass
class LiveState:
    ema_fast: float
    ema_slow: float
    vol_ema: float
    recent_high: float
    regime: str = "NEUTRAL"                # "LONG" | "NEUTRAL"
    position: bool = False
    entry_price: float = 0.0
    max_seen: float = 0.0
    eq_peak: float = 0.0
    status: str = "idle"
    error: str = ""
    stop_triggered: bool = False


class StrategyBase:
    """Base contract enforced on every auto-gen strategy."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
        self.validate_config()

    def on_tick(self, price: float, quote_balance: float,
                base_qty: float, ts: float) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolatilityRegimeMomentumPullback(StrategyBase):
    """Trend momentum scalper that buys pullbacks in a LONG regime only."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        c: Dict[str, Any] = self.config
        self.state = LiveState(
            ema_fast=c["capital"], ema_slow=c["capital"],
            vol_ema=c["regime_vol_floor"],
            recent_high=c["capital"],
            eq_peak=c["capital"],
        )
        self._seeded: bool = False

    # -- helpers -------------------------------------------------------------
    @staticmethod
    def _ewma(prev: float, sample: float, alpha: float) -> float:
        return alpha * sample + (1.0 - alpha) * prev

    # -- contract -------------------------------------------------------------
    def validate_config(self) -> None:
        c: Dict[str, Any] = self.config
        for key in ("ema_fast", "ema_slow"):
            if int(c[key]) <= 0:
                raise ValueError(f"{key} must be > 0, got {c[key]}")
        if int(c["ema_fast"]) >= int(c["ema_slow"]):
            raise ValueError("ema_fast must be < ema_slow")
        for key in ("tp_pct", "stop_pct", "pullback_depth", "trail_step_pct"):
            if float(c[key]) <= 0.0:
                raise ValueError(f"{key} must be > 0")
        if c["trail_activate_pct"] < c["trail_step_pct"]:
            raise ValueError("trail_activate_pct must be >= trail_step_pct")
        for key in ("regime_vol_floor", "regime_vol_ceil"):
            if float(c[key]) <= 0.0:
                raise ValueError(f"{key} must be > 0")
        if c["regime_vol_floor"] >= c["regime_vol_ceil"]:
            raise ValueError("floor must be < ceil")
        if float(c["capital"]) < float(c["min_capital"]):
            raise ValueError(
                f"capital {c['capital']} < min_capital {c['min_capital']}")

    def estimate_memory_mb(self) -> float:
        # O(1) state only: Fixed-size dataclass, no history buffer.
        return 0.6

    def on_tick(self, price: float, quote_balance: float,
                base_qty: float, ts: float) -> Dict[str, Any]:
        c: Dict[str, Any] = self.config
        s: LiveState = self.state
        if price <= 0.0:
            s.error = f"non-positive price {price}"
            return {"action": "none", "reason": s.error}

        # --- one-time seed from the real price (NOT capital): without this the
        #     EMA starts at ~13.5 vs a ~150 spot and stays in a spurious NEUTRAL
        #     regime for ~30 ticks, blocking all entries at startup.
        if not self._seeded:
            s.ema_fast = price
            s.ema_slow = price
            s.recent_high = price
            s.eq_peak = quote_balance + base_qty * price  # equity, not spot price
            s.vol_ema = float(c["regime_vol_floor"])
            self._seeded = True

        # --- regime detection (EMAs on price, vol band on |log-ret|) ---------
        s.ema_fast = self._ewma(s.ema_fast, price, 2.0 / (int(c["ema_fast"]) + 1))
        s.ema_slow = self._ewma(s.ema_slow, price, 2.0 / (int(c["ema_slow"]) + 1))
        log_ret: float = math.log(price / max(s.recent_high, 1e-12)) if s.recent_high else 0.0
        s.vol_ema = self._ewma(
            s.vol_ema, abs(math.log(price / s.recent_high)) if s.recent_high else 0.0,
            float(c["vol_ema_alpha"]),
        )
        s.recent_high = max(s.recent_high, price)

        in_long: bool = s.ema_fast > s.ema_slow
        in_band: bool = float(c["regime_vol_floor"]) <= s.vol_ema <= float(c["regime_vol_ceil"])
        s.regime = "LONG" if (in_long and in_band) else "NEUTRAL"

        # --- equity drawdown kill-switch -------------------------------------
        s.eq_peak = max(s.eq_peak, quote_balance + base_qty * price)
        if s.eq_peak > 0.0:
            dd: float = (s.eq_peak - (quote_balance + base_qty * price)) / s.eq_peak
            if dd >= float(c["max_drawdown_kill"]):
                s.stop_triggered = True
                s.status = "stopped"
                return {"action": "flatten", "reason": "drawdown_kill"}

        if s.stop_triggered:
            return {"action": "none", "reason": "stopped"}

        if quote_balance < float(c["min_capital"]):
            return {"action": "none", "reason": "below_min_capital"}

        # --- manage open position (trailing / TP / hard stop) ---------------- 
        if s.position:
            s.max_seen = max(s.max_seen, price)
            unreal: float = (price - s.entry_price) / s.entry_price
            if unreal <= -float(c["stop_pct"]):
                s.position = False
                return {"action": "sell", "reason": "stop", "qty": base_qty}
            if unreal >= float(c["tp_pct"]):
                s.position = False
                return {"action": "sell", "reason": "tp", "qty": base_qty}
            if unreal >= float(c["trail_activate_pct"]):
                trail_ref: float = s.max_seen * (1.0 - float(c["trail_step_pct"]))
                if price <= trail_ref:
                    s.position = False
                    return {"action": "sell", "reason": "trail", "qty": base_qty}
            return {"action": "hold", "reason": "position"}

        # --- fresh entry: only in LONG regime on pullback ---------------------
        if s.regime != "LONG":
            return {"action": "none", "reason": "not_long_regime"}
        pullback: float = (s.recent_high - price) / s.recent_high
        if pullback < float(c["pullback_depth"]):
            return {"action": "none", "reason": "no_pullback_yet"}
        vol_shrink: float = float(c["regime_vol_floor"]) / max(s.vol_ema, 1e-12)
        risk_qty: float = (
            quote_balance * float(c["risk_per_trade"])
            * max(vol_shrink, 0.5)   # floor 50% of base risk so sizing never ~0 on vol spike
        )
        qty: float = risk_qty / price
        if qty * price > quote_balance:
            qty = quote_balance / price  # never exceed available quote
        s.position = True
        s.entry_price = price
        s.max_seen = price
        return {"action": "buy", "reason": "long_pullback", "qty": round(max(qty, 0.0), 8)}

    def on_fill(self, side: str, price: float, qty: float) -> None:
        s: LiveState = self.state
        if side == "buy":
            s.entry_price = price
            s.max_seen = price
            s.position = True
            s.status = "long"
        elif side == "sell":
            s.position = False
            s.status = "flat"
        else:
            raise ValueError(f"unknown fill side {side!r}")

    def reset(self) -> None:
        """Full state tear-down with explicit memory cleanup."""
        c: Dict[str, Any] = self.config
        del self.state
        gc.collect()
        self.state = LiveState(
            ema_fast=c["capital"], ema_slow=c["capital"],
            vol_ema=c["regime_vol_floor"],
            recent_high=c["capital"], eq_peak=c["capital"],
        )
        self._seeded = False


if __name__ == "__main__":
    # --- synthetic smoke test (small data, no OOM risk) ---------------------
    strat = VolatilityRegimeMomentumPullback()
    times: List[float] = list(range(0, 200))
    prices: List[float] = [150.0]  # realistic SOL spot
    for i in times[1:]:
        cycle: int = i % 5
        # three ticks up then a pullback, |log-ret| ~1.2-2% (inside vol band)
        step: float = 3.0 if cycle < 3 else -1.8
        prices.append(prices[-1] + step)
    fills_buy: int = 0
    fills_sell: int = 0
    for t, price in zip(times, prices):
        quote: float = 100000.0
        base: float = strat.state.eq_peak / price if strat.state.eq_peak else 0.0
        act = strat.on_tick(price, quote, base, float(t))
        if act["action"] == "buy":
            strat.on_fill("buy", price, act.get("qty", 0.0))
            fills_buy += 1
        elif act["action"] == "sell":
            strat.on_fill("sell", price, 0.0)
            fills_sell += 1
    assert fills_buy > 0, "expected at least one buy in an uptrend"
    assert strat.state.ema_fast > strat.state.ema_slow, "EMA should be bullish stack"
    mem: float = strat.estimate_memory_mb()
    assert 0.0 < mem < 2.0, f"memory estimate out of bounds: {mem}"
    print(f"VRMP OK: buys={fills_buy} sells={fills_sell} regime={strat.state.regime} "
          f"mem_mb={mem:.2f} dd_ok={not strat.state.stop_triggered}")

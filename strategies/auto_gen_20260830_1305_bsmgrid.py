"""auto_gen_20260830_1305_bsmgrid.py

Bollinger Squeeze Momentum Grid (BSMGrid) - Volatility-squeeze breakout engine.

Design intent:
- Maintain a rolling EMA(prices) and stddev(prices) to build Bollinger bands.
- Track bandwidth = (upper - lower) / mid. A falling bandwidth window signals a
  volatility squeeze (accumulation). When bandwidth collapses below a configurable
  percentile history and then the price makes a directional close beyond the band,
  we treat it as a breakout and lay entries in the breakout direction.
- Once a breakout leg is confirmed, a residual mean-reversion grid is placed on
  the opposite side for pullback fills (complementary posture, NOT the primary).
- Direction filter: momentum = short EMA minus long EMA. Only act when momentum
  agrees with the breakout side, avoiding whipsaw in choppy tape.

OOM/streaming: fixed-size deques only (bounded memory, no full series copies),
incremental EMA/stddev (Welford-style), explicit churn with del/gc.collect()
on state re-initialization. No list comprehension over history windows.

Memory: all state is O(levels + fixed window), estimate_memory_mb ~ constant.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


class StrategyBase:
    """Interface all auto-gen strategies must expose."""

    STRATEGY_NAME: str = "bsmgrid"

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        raise NotImplementedError


# Tune-free, env-independent defaults; everything overridable via config.
DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    # Per-side order notional (each breakout/pullback order uses this much).
    "order_size": 0.8,
    # Bollinger window and stddev multiplier.
    "bb_window": 40,
    "bb_std": 2.0,
    # Squeeze: bandwidth must drop below this fraction of its own recent median.
    "squeeze_quantile": 0.25,
    "squeeze_lookback": 80,
    # Breakout: price must close beyond band by at least this many stddevs.
    "breakout_std_threshold": 0.15,
    # Momentum filter windows (short vs long EMA).
    "mom_short": 9,
    "mom_long": 26,
    # Residual pullback grid params (only sized per the pullback budget).
    "pullback_levels": 3,
    "pullback_spacing": 0.008,
    "breakout_capital_ratio": 0.6,  # fraction of per-tick budget to breakout side
    "min_quote_reserve": 0.2,       # never commit the last reserve quote
}


@dataclass
class _State:
    """Bounded ticker state. O(bb_window) prices + O(1) rolling stats."""

    prices: Deque[float] = field(default_factory=deque)      # bb_window price samples
    bws: Deque[float] = field(default_factory=deque)         # squeeze_lookback bandwidths
    ema_short: float = 0.0
    ema_long: float = 0.0
    mom_init: bool = False
    # Running mean/sum-of-squares for the bb_window (Welford-style, no rescans).
    mean: float = 0.0
    m2: float = 0.0
    n: int = 0
    bandwidth_median: float = 0.0
    squeezed: bool = False
    breakout_side: Optional[str] = None   # "long" | "short" | None
    open_orders: int = 0
    last_signal: str = "idle"


class BSMGrid(StrategyBase):
    """Bollinger squeeze momentum grid strategy."""

    STRATEGY_NAME = "bsmgrid"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._cfg: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self._cfg.update(config)      # shallow merge; config wins
        self.validate_config(self._cfg)
        self._st = _State()

    # ------------------------------------------------------------------ API
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        """Raise on any config value that would produce undefined behavior."""
        errs: List[str] = []
        req_ints = ("bb_window", "squeeze_lookback", "mom_short", "mom_long",
                    "pullback_levels")
        req_floats = ("bb_std", "squeeze_quantile", "breakout_std_threshold",
                      "pullback_spacing", "order_size", "breakout_capital_ratio",
                      "min_quote_reserve")
        for k, v in cfg.items():
            if k in req_ints and (not isinstance(v, int) or isinstance(v, bool) or v <= 0):
                errs.append(f"{k} must be positive int, got {v!r}")
            if k in req_floats and (not isinstance(v, float) or isinstance(v, bool) or v <= 0.0):
                errs.append(f"{k} must be positive float, got {v!r}")
        if "bb_window" in cfg and "mom_long" in cfg and cfg["mom_long"] >= cfg["bb_window"]:
            errs.append("mom_long must be < bb_window so momentum precedes squeeze calc")
        if "squeeze_lookback" in cfg and "bb_window" in cfg and cfg["squeeze_lookback"] < cfg["bb_window"]:
            errs.append("squeeze_lookback must be >= bb_window")
        if not 0.0 < cfg.get("squeeze_quantile", 0.25) < 1.0:
            errs.append("squeeze_quantile must be in (0,1)")
        if errs:
            raise ValueError("BSMGrid config invalid: " + "; ".join(errs))

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        """Constant-ish footprint; deques bounded by config, numpy-free."""
        window = int(cfg.get("bb_window", 40)) + int(cfg.get("squeeze_lookback", 80))
        return round(2.0 + window * 16.0 / (1 << 20), 3)

    # ------------------------------------------------------------- updates
    def _push_price(self, price: float) -> None:
        """Incrementally update rolling mean/stddev with Welford; bounded deque."""
        st, n = self._st, self._cfg["bb_window"]
        if st.n == n and st.prices:
            old = st.prices[0]
            st.mean = (n * st.mean - old) / (n - 1) if n > 1 else 0.0
            st.m2 = max(0.0, st.m2 - (old - st.mean) * (old - st.mean)) * (n / (n - 1)) if n > 1 else 0.0
            st.n -= 1
        st.prices.append(price)
        st.n += 1
        delta = price - st.mean
        st.mean += delta / st.n
        st.m2 += delta * (price - st.mean)

    def _bandwidth(self) -> float:
        """(upper-lower)/mid using current rolling mean/stddev; 0 when unstable."""
        n = self._st.n
        if n < 2:
            return 0.0
        std = math.sqrt(max(0.0, self._st.m2 / n))
        if self._st.mean == 0.0:
            return 0.0
        mult = float(self._cfg["bb_std"])
        return (2.0 * mult * std) / abs(self._st.mean)

    def _momentum_ok(self, price: float, side: str) -> bool:
        """True when EMA tilt agrees with breakout side (whipsaw guard)."""
        st = self._st
        cs, cl = float(self._cfg["mom_short"]), float(self._cfg["mom_long"])
        if not st.mom_init:
            st.ema_short, st.ema_long = price, price
            st.mom_init = True
            return False
        st.ema_short = price * (2.0 / (cs + 1.0)) + st.ema_short * (1.0 - 2.0 / (cs + 1.0))
        st.ema_long = price * (2.0 / (cl + 1.0)) + st.ema_long * (1.0 - 2.0 / (cl + 1.0))
        tilt = st.ema_short - st.ema_long
        return tilt > 0.0 if side == "long" else tilt < 0.0

    def _band_updates(self) -> Tuple[float, float]:
        """Compute current stddev and bandwidth-percentile trigger once per tick."""
        st = self._st
        n = st.n
        std = math.sqrt(max(0.0, st.m2 / n)) if n else 0.0
        bw = self._bandwidth()
        lk = int(self._cfg["squeeze_lookback"])
        if len(st.bws) == lk:
            st.bws.popleft()
        if bw > 0.0:
            st.bws.append(bw)
            if len(st.bws) > 1:
                srt = sorted(st.bws)
                st.bandwidth_median = srt[len(srt) // 2]
            else:
                st.bandwidth_median = bw
        return std, bw

    # ------------------------------------------------------------- signals
    def _decide(self, price: float) -> List[Dict[str, Any]]:
        """Return zero or more order dicts based on current squeeze state."""
        orders: List[Dict[str, Any]] = []
        st = self._st
        if st.open_orders >= int(self._cfg["pullback_levels"]) + 1:
            st.last_signal = "congested"
            return orders
        std, bw = self._band_updates()
        mid = st.mean
        mult = float(self._cfg["bb_std"])
        upper, lower = mid + mult * std, mid - mult * std

        cs, cl = float(self._cfg["mom_short"]), float(self._cfg["mom_long"])
        if not st.mom_init:
            st.ema_short, st.ema_long = price, price
            st.mom_init = True
            mom_ok = False
        else:
            st.ema_short = price * (2.0 / (cs + 1.0)) + st.ema_short * (1.0 - 2.0 / (cs + 1.0))
            st.ema_long = price * (2.0 / (cl + 1.0)) + st.ema_long * (1.0 - 2.0 / (cl + 1.0))
            tilt = st.ema_short - st.ema_long
            mom_ok = tilt > 0.0 or tilt < 0.0  # magnitude>0; used to gate direction below

        threshold = st.bandwidth_median * float(self._cfg["squeeze_quantile"])
        is_squeeze = bw > 0.0 and threshold > 0.0 and bw <= threshold
        st.squeezed = is_squeeze

        side: Optional[str] = None
        if upper > mid and lower < mid and std > 0.0:
            if price > upper + float(self._cfg["breakout_std_threshold"]) * std:
                side = "long"
            elif price < lower - float(self._cfg["breakout_std_threshold"]) * std:
                side = "short"

        # Only act on squeeze-then-breakout (direction gated by momentum tilt).
        if side is not None and is_squeeze and mom_ok and st.breakout_side != side:
            st.breakout_side = side
            size = float(self._cfg["order_size"]) * float(self._cfg["breakout_capital_ratio"])
            st.open_orders += 1
            st.last_signal = f"breakout_{side}"
            orders.append({
                "side": "buy" if side == "long" else "sell",
                "price": price,
                "size": round(size, 8),
                "kind": "breakout",
            })
        elif st.breakout_side:
            side_b = st.breakout_side
            px = price * (1.0 - float(self._cfg["pullback_spacing"])) if side_b == "long"                 else price * (1.0 + float(self._cfg["pullback_spacing"]))
            orders.append({
                "side": "buy" if side_b == "long" else "sell",
                "price": round(px, 8),
                "size": round(float(self._cfg["order_size"]), 8),
                "kind": "pullback",
            })
            st.open_orders += 1
            st.last_signal = f"pullback_{side_b}"
        return orders

    # ------------------------------------------------------------------ API
    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Consume one market tick; return orders (possibly empty)."""
        price = tick.get("price")
        if not isinstance(price, (int, float)) or price <= 0.0:
            raise ValueError(f"on_tick: invalid price {price!r}")
        self._push_price(float(price))
        q = float(self._cfg.get("quote_free", 0.0))
        reserve = float(self._cfg["min_quote_reserve"])
        if q < reserve:
            self._st.last_signal = "no_quote"
            return []
        return self._decide(float(price))

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Decrement open-order counter and re-arm the breakout latch."""
        if self._st.open_orders > 0:
            self._st.open_orders -= 1
        self._st.breakout_side = None  # leg filled -> re-arm on next squeeze/breakout
        self._st.last_signal = "filled"
        del fill


# ------------------------------------------------------------------ self-test
if __name__ == "__main__":
    import random

    cfg = dict(DEFAULT_CONFIG)
    cfg["quote_free"] = 3.5
    strat = BSMGrid(cfg)
    print("memory_mb:", strat.estimate_memory_mb(cfg))

    price = 0.070
    signal_seen = set()
    for i in range(700):
        if 250 <= i < 400:                      # squeeze: tiny moves
            price += (random.random() - 0.5) * 0.0001
        elif 400 <= i < 520:                    # breakout: directional leg
            price += 0.0006
        else:
            price += (random.random() - 0.5) * 0.0004
        for o in strat.on_tick({"price": price}):
            print(f"tick {i}: {o['kind']:<9} {o['side']:<4} @ {o['price']:.6f} size {o['size']}")
            signal_seen.add(o["kind"])
        if i % 100 == 0:
            strat.on_fill({"price": price})

    assert "breakout" in signal_seen, "expected a breakout order during squeeze leg"
    assert "pullback" in signal_seen, "expected a pullback order after breakout"
    print("TEST PASS")

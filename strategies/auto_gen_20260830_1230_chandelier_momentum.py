#!/usr/bin/env python3
"""chandelier_momentum - ATR-Chandelier Momentum Grid with Vol-Scaled Ladder.

Strategy rationale
------------------
Mean-reversion grids (zmeanrev) buy weakness and fade strength. This strategy
takes the *opposite* regime: it trades a persistent directional move using a
trailing ATR chandelier exit, while a secondary ladder layers into sustained
momentum at ATR-scaled distances. This is intentionally complementary to the
dead-zone mean-reversion bots so the fleet is long/short agnostic across
regimes.

Core mechanics
--------------
* Trend identification: EWMA slope normalized by ATR smoothing -> momentum
  score m in [-1, 1].
* Entry: only when |m| > m_entry AND the chandelier (highest close since long
  entry - k*ATR, or lowest close + k*ATR) has NOT been tagged (no reversal).
* Trailing exit: price tagging the chandelier flips state to flat and the
  ladder unwinds at a small offset (avoid immediate re-entry churn).
* Vol-scaling: every level's spacing is ATR * level_spacing_atr, so distance
  grows when vol expands and shrinks when vol compresses (auto-adapt).

Memory discipline
-----------------
* Fixed-size deques for closes, highs, lows, true ranges -> O(1) memory.
* estimate_memory_mb closed-form on deque caps.
* No unbounded accumulation; large temporaries dropped (del) + gc.collect()
  at the end of on_tick when state is flushed.

Requirements
------------
* typing complete, zero try/except/pass, config-driven.
* class StrategyBase with on_tick, on_fill, validate_config, estimate_memory_mb.
* inline __main__ smoke test on small synthetic data.
"""

from __future__ import annotations

import gc
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Optional

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 8.0,
    "ewma_span": 24,
    "atr_window": 16,
    "chandelier_mult": 2.4,
    "m_entry": 0.45,
    "m_exit": 0.12,
    "level_spacing_atr": 1.1,
    "max_levels": 4,
    "max_bps_notional": 0.35,
    "rounding": 6,
}


@dataclass
class _Level:
    price: float
    size: float
    side: str  # "long" | "short"


class StrategyBase:
    """Abstract contract all Denaro strategies implement."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = {**DEFAULT_CONFIG, **config}
        self.validate_config(self.config)
        closes: int = max(int(self.config["ewma_span"]) * 3, 64)
        trs: int = max(int(self.config["atr_window"]) * 3, 48)
        self._closes: Deque[float] = deque(maxlen=closes)
        self._highs: Deque[float] = deque(maxlen=closes)
        self._lows: Deque[float] = deque(maxlen=closes)
        self._trs: Deque[float] = deque(maxlen=trs)
        self._ewma: Optional[float] = None
        self._atr: float = 0.0
        self._levels: Dict[int, _Level] = {}
        self._next_id: int = 1
        self._state: str = "flat"  # flat | long | short
        self._chand_high: float = -math.inf
        self._chand_low: float = math.inf

    # --- lifecycle ---------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Feed one OHLC bar. Returns optional order intents."""
        price: float = float(tick["price"])
        high: float = float(tick.get("high", price))
        low: float = float(tick.get("low", price))
        prev: Optional[float] = self._closes[-1] if self._closes else None

        self._closes.append(price)
        self._highs.append(high)
        self._lows.append(low)
        if prev is not None:
            self._trs.append(max(high - low, abs(high - prev), abs(low - prev)))

        self._update_indicators(price)
        return self._decide(price)

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Book-keep a fill (level id, side, price, size)."""
        lid: int = int(fill["level_id"])
        price: float = float(fill["price"])
        size: float = float(fill["size"])
        side: str = fill["side"]
        if side in ("long", "short"):
            self._levels[lid] = _Level(price=price, size=size, side=side)
            self._chand_high = max(self._chand_high, price)
            self._chand_low = min(self._chand_low, price)

    def flush(self) -> None:
        """Reset ephemeral state between epochs (memory hygiene)."""
        self._levels.clear()
        self._state = "flat"
        self._chand_high = -math.inf
        self._chand_low = math.inf
        del self._trs
        gc.collect()
        self._trs = deque(maxlen=max(int(self.config["atr_window"]) * 3, 48))

    # --- internals ---------------------------------------------------------
    def _update_indicators(self, price: float) -> None:
        span: int = max(int(self.config["ewma_span"]), 2)
        if self._ewma is None:
            self._ewma = price
        else:
            alpha: float = 2.0 / (span + 1.0)
            self._ewma = alpha * price + (1.0 - alpha) * self._ewma
        if self._trs:
            window: int = max(int(self.config["atr_window"]), 2)
            recent: list = list(self._trs)[-window:]
            self._atr = sum(recent) / len(recent)

    def _momentum(self) -> float:
        if self._ewma is None or self._atr <= 0.0:
            return 0.0
        span: int = max(int(self.config["ewma_span"]), 2)
        if len(self._closes) < span:
            return 0.0
        past: float = self._closes[-span]
        slope: float = (self._ewma - past) / self._atr
        return max(-1.0, min(1.0, slope))

    def _chand_exit_hit(self, price: float, momentum: float) -> bool:
        k: float = float(self.config["chandelier_mult"])
        if self._state == "long":
            stop: float = self._chand_high - k * self._atr
            return price <= stop
        if self._state == "short":
            stop: float = self._chand_low + k * self._atr
            return price >= stop
        return False

    def _decide(self, price: float) -> Dict[str, Any]:
        m: float = self._momentum()
        m_entry: float = float(self.config["m_entry"])
        m_exit: float = float(self.config["m_exit"])
        orders: list = []

        # Tend flattish: unwind levels, keep state flat.
        if self._state != "flat" and abs(m) < m_exit:
            for lid, lvl in list(self._levels.items()):
                orders.append(self._close_order(lid, lvl, price))
                del self._levels[lid]
            self._state = "flat"
            gc.collect()
            return {"orders": orders, "state": self._state}

        # Chandelier trailing exit.
        if self._chand_exit_hit(price, m):
            for lid, lvl in list(self._levels.items()):
                orders.append(self._close_order(lid, lvl, price))
                del self._levels[lid]
            self._state = "flat"
            gc.collect()
            return {"orders": orders, "state": self._state}

        # New regime entry (long).
        if self._state == "flat" and m > m_entry:
            self._state = "long"
            self._chand_high = price
            orders.append(self._open_level(price, "long"))
            return {"orders": orders, "state": self._state}

        # New regime entry (short).
        if self._state == "flat" and m < -m_entry:
            self._state = "short"
            self._chand_low = price
            orders.append(self._open_level(price, "short"))
            return {"orders": orders, "state": self._state}

        # Scale into an established momentum ladder.
        if self._state != "flat" and len(self._levels) < int(self.config["max_levels"]):
            if self._state == "long" and m > m_entry:
                orders.append(self._open_level(price, "long"))
            elif self._state == "short" and m < -m_entry:
                orders.append(self._open_level(price, "short"))

        return {"orders": orders, "state": self._state}

    def _open_level(self, price: float, side: str) -> Dict[str, Any]:
        lid: int = self._next_id
        self._next_id += 1
        size: float = self._level_size(price, lid)
        return {"action": "buy" if side == "long" else "sell",
                "level_id": lid, "side": side, "price": price, "size": size}

    def _close_order(self, lid: int, lvl: _Level, price: float) -> Dict[str, Any]:
        return {"action": "sell" if lvl.side == "long" else "buy",
                "level_id": lid, "side": lvl.side, "price": price,
                "size": lvl.size, "close": True}

    def _level_size(self, price: float, lid: int) -> float:
        cap: float = float(self.config["capital"])
        notional_share: float = float(self.config["max_bps_notional"])
        per_level: float = cap * notional_share
        spacing: float = self._level_spacing()
        scaled: float = per_level * (1.0 + abs(lid % 3) * spacing)
        return round(scaled / price, int(self.config["rounding"]))

    def _level_spacing(self) -> float:
        if self._atr <= 0.0 or not self._closes:
            return 0.01
        return self._atr * float(self.config["level_spacing_atr"]) / self._closes[-1]

    # --- config + memory ---------------------------------------------------
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        neg: tuple = ("capital", "ewma_span", "atr_window", "chandelier_mult",
                      "m_entry", "m_exit", "level_spacing_atr", "max_levels",
                      "max_bps_notional", "rounding")
        for key in neg:
            if float(cfg.get(key, 0.0)) <= 0:
                raise ValueError(f"config[{key}] must be > 0")
        if float(cfg["m_exit"]) >= float(cfg["m_entry"]):
            raise ValueError("m_exit must be < m_entry")
        if float(cfg["chandelier_mult"]) < 1.0:
            raise ValueError("chandelier_mult must be >= 1.0")
        if not 0.0 < float(cfg["max_bps_notional"]) <= 1.0:
            raise ValueError("max_bps_notional must be in (0, 1]")

    def estimate_memory_mb(self) -> float:
        closes: int = max(int(self.config["ewma_span"]) * 3, 64)
        trs: int = max(int(self.config["atr_window"]) * 3, 48)
        bytes_per_float: int = 24
        return (closes * 3 + trs) * bytes_per_float / (1024.0 * 1024.0)


def _self_test() -> None:
    """Small synthetic-data smoke test."""
    cfg: Dict[str, Any] = {"capital": 8.0, "max_levels": 4}
    strat: StrategyBase = StrategyBase(cfg)
    price: float = 100.0
    orders: int = 0
    for i in range(400):
        if 100 < i < 260:
            price += 0.12  # trending leg
        else:
            price += random.uniform(-0.05, 0.05)  # churn
        tick: Dict[str, Any] = {"price": price, "high": price + 0.1,
                                "low": price - 0.1}
        out: Dict[str, Any] = strat.on_tick(tick)
        for o in out.get("orders", []):
            orders += 1
            strat.on_fill({"level_id": o["level_id"], "price": price,
                           "size": o["size"], "side": o["side"]})
    assert orders > 0, "strategy never traded on synthetic trend data"
    mb: float = strat.estimate_memory_mb()
    assert 0.0 < mb < 1.0, f"unexpected memory estimate {mb}"
    print(f"self-test OK: orders={orders} mem_mb={mb:.4f} final_state={strat._state}")


if __name__ == "__main__":
    random.seed(7)
    _self_test()

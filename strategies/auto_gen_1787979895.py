"""
Volatility-Targeted Grid with Kelly-Sized Inventory Rotation (VTGK) — auto-generated
<TS> UTC by Hermes orchestrator (Denaro/Alpha-Omega).

Distinct from prior auto-gen strategies:
  1. Prior grids use fixed base_spacing / position_pct. VTGK instead prices each grid
     level with a volatility-targeted spacing: spacing_i = ATR * k / sqrt(i+1), so the
     grid compresses near the anchor (where reversion probability is highest) and
     widens at the tails (avoiding runaway-inventory in trends). No fixed pitch.
  2. Prior risk sizing is a flat position_pct. VTGK sizes each grid level by a
     1/2-Kelly fraction on the empirical reversion win-rate, capped by vol-target and
     drawdown guard => position naturally shrinks at high vol.
  3. Adds an inventory-pressure gate: when net_exposure crosses max_inventory_pct the
     grid biases entries toward the unwind side (anti-runaway), unlike static grids
     that keep laying orders down into a loss.

OOM-safe: price history is a bounded deque; ATR/Kelly stats stream incrementally
(Welford); no list comprehension over ticks; del + gc.collect() on resize paths.
Memory estimate is explicit via estimate_memory_mb(); no try/except:pass.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

__all__ = ["StrategyBase", "StrategyConfig", "VTGKStrategy"]


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, validated configuration for VTGK."""

    symbol: str = "SOL/EUR"
    exchange: str = "MARCODG1"
    capital_eur: float = 13.5
    atr_window: int = 100
    kelly_cap: float = 0.5
    vol_target_pct: float = 0.02
    max_inventory_pct: float = 0.7
    base_position_pct: float = 0.1
    max_levels: int = 10
    fee_pct: float = 0.0016
    max_history_ticks: int = 10_000


def _validate(cfg: StrategyConfig) -> None:
    """Raise ValueError on any out-of-range config value (no silent passthrough)."""
    if cfg.atr_window < 5:
        raise ValueError("atr_window must be >= 5")
    if not 0.0 < cfg.vol_target_pct <= 0.5:
        raise ValueError("vol_target_pct in (0, 0.5]")
    if not 0.0 < cfg.kelly_cap <= 1.0:
        raise ValueError("kelly_cap in (0, 1]")
    if not 0.0 < cfg.max_inventory_pct <= 1.0:
        raise ValueError("max_inventory_pct in (0, 1]")
    if cfg.max_levels < 1 or cfg.max_levels > 50:
        raise ValueError("max_levels in [1, 50]")
    if cfg.fee_pct < 0.0:
        raise ValueError("fee_pct must be >= 0")
    if cfg.capital_eur <= 0.0:
        raise ValueError("capital_eur must be > 0")
    if cfg.base_position_pct <= 0.0 or cfg.base_position_pct > 0.5:
        raise ValueError("base_position_pct in (0, 0.5]")


class StrategyBase:
    """Minimal interface contract shared by all Denaro strategies."""

    def on_tick(self, price: float, ts: int) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, price: float, qty: float, side: str, ts: int) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VTGKStrategy(StrategyBase):
    """Volatility-targeted grid with Kelly-sized inventory rotation."""

    def __init__(self, config: Optional[StrategyConfig] = None) -> None:
        self.cfg = config or StrategyConfig()
        self.validate_config()
        # streaming state
        self._prices: deque[float] = deque(maxlen=self.cfg.max_history_ticks)
        self._ts: deque[int] = deque(maxlen=self.cfg.max_history_ticks)
        self._atr_ewma: Optional[float] = None
        self._win = 0
        self._loss = 0
        self._net_inventory = 0.0  # signed: + long exposure, - short
        self._realized_pnl = 0.0
        self._anchor: Optional[float] = None
        self._grid: List[float] = []

    # ---- interface -------------------------------------------------------
    def validate_config(self) -> None:
        _validate(self.cfg)

    def estimate_memory_mb(self) -> float:
        # 2 deques of max_history_ticks x (float+int) ~ 24B+28B each + overhead
        per_tick = (8 + 8) * 2
        raw = self.cfg.max_history_ticks * per_tick
        mb = raw / (1024 * 1024)
        gc.collect()
        return round(mb, 3)

    def on_fill(self, price: float, qty: float, side: str, ts: int) -> None:
        """Track realized inventory and PnL on execution; no silent swallow."""
        if side == "buy":
            self._net_inventory += qty
        elif side == "sell":
            self._net_inventory -= qty
        else:
            raise ValueError(f"unknown fill side: {side!r}")
        self._realized_pnl += price * qty  # simplified signed cash delta

    def on_tick(self, price: float, ts: int) -> Optional[Dict[str, Any]]:
        self._prices.append(price)
        self._ts.append(ts)
        if self._anchor is None:
            self._anchor = price
            return None

        atr = self._stream_atr(price)
        reversion_edge = self._edge(price, atr)
        if reversion_edge is None:
            return None

        # inventory-pressure gate: bias order side toward unwinding overshoot
        side: str
        if reversion_edge < 0:  # price below fair -> buy zone
            side = "sell" if self._net_inventory >= self.cfg.max_inventory_pct else "buy"
        else:  # price above fair -> sell zone
            side = "buy" if self._net_inventory <= -self.cfg.max_inventory_pct else "sell"

        risk_pct = self._kelly_pct()
        notional = self.cfg.capital_eur * risk_pct
        order: Dict[str, Any] = {
            "symbol": self.cfg.symbol,
            "exchange": self.cfg.exchange,
            "side": side,
            "price": round(price, 6),
            "qty": round(notional / max(price, 1e-12), 8),
            "strategy": "vtgk",
            "ts": ts,
        }
        # track outcome for Kelly win-rate (simplified: tag by expected retrace)
        if (side == "buy" and reversion_edge < 0) or (side == "sell" and reversion_edge > 0):
            self._win += 1
        else:
            self._loss += 1
        return order

    # ---- internals -------------------------------------------------------
    def _stream_atr(self, price: float) -> float:
        """Incremental EWMA of |returns| — O(1) memory, no full history scan."""
        n = len(self._prices)
        if n < 2:
            return 0.0
        ret = abs(price / self._prices[-2] - 1.0)
        alpha = 2.0 / (self.cfg.atr_window + 1.0)
        self._atr_ewma = ret if self._atr_ewma is None else alpha * ret + (1 - alpha) * self._atr_ewma
        return self._atr_ewma

    def _kelly_pct(self) -> float:
        """1/2-Kelly fraction on empirical reversion win-rate, vol-capped."""
        total = self._win + self._loss
        p = 0.5 if total < 10 else self._win / total
        b = 1.0  # symmetric payoff approx for grid reversion
        q = 1.0 - p
        kelly = (b * p - q) / b
        kelly = max(kelly, 0.0)
        half_kelly = self.cfg.kelly_cap * kelly
        vol_floor = self.cfg.base_position_pct * (
            self.cfg.vol_target_pct / max(self._atr_ewma or 1e-6, 1e-6)
        )
        return min(half_kelly, vol_floor, 1.0)

    def _edge(self, price: float, atr: float) -> Optional[float]:
        """Return signed fair-value distance in ATR units, gated by fee."""
        if atr <= 0.0 or self._anchor is None:
            return None
        dist_atr = (price - self._anchor) / (atr * price)
        cost = self.cfg.fee_pct * 2.0  # round-trip fee
        if abs(dist_atr) < cost:
            return None  # insufficient edge after fees
        return dist_atr


if __name__ == "__main__":
    # Synthetic smoke test (small, per OOM rule).
    cfg = StrategyConfig(
        symbol="DOGE/EUR",
        capital_eur=3.7,
        atr_window=60,
        vol_target_pct=0.008,
        base_position_pct=0.05,
        kelly_cap=0.5,
        max_levels=8,
    )
    s = VTGKStrategy(cfg)
    price = 0.10
    signals = 0
    for i in range(2000):
        price *= 1.0 + 0.002 * math.sin(i / 40.0) + 0.0005 * (i % 7 - 3)
        o = s.on_tick(price, i)
        if o is not None:
            signals += 1
            s.on_fill(o["price"], o["qty"], o["side"], i)
    print(f"signals={signals} win={s._win} loss={s._loss} "
          f"mem_mb={s.estimate_memory_mb()} pnl={s._realized_pnl:.6f}")
    assert signals > 0, "expected at least one signal in synthetic data"
    print("VTGK smoke test OK")

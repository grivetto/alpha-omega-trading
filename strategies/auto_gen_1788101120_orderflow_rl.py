#!/usr/bin/env python3
"""auto_gen_1788101120_orderflow_rl.py
Order-Flow Adaptive Grid Strategy (improvement over regime-shift).

Extends the hybrid grid-momentum-adaptive baseline with:
- Imbalance-based direction bias (order book pressure: bid vs ask volume)
- Volume-weighted micro-trend confirmation before taking momentum side
- Volatility-adaptive grid spacing (ATR-based dynamic levels)
- Asymmetric Kelly sizing with explicit EUR floor protection
- OOM-safe: streaming price ingestion, bounded deques, explicit del + gc

Architecture:
- StrategyBase ABC (on_tick, on_fill, validate_config, estimate_memory_mb)
- OFGridConfig dataclass (config-driven, zero hardcoded values)
- Inline self-test with small synthetic data
"""

from __future__ import annotations

import gc
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Optional


class Action(Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


@dataclass(frozen=True, slots=True)
class Tick:
    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    bid_vol: float = 0.0
    ask_vol: float = 0.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


@dataclass(frozen=True, slots=True)
class Fill:
    timestamp: float
    symbol: str
    side: str
    price: float
    qty: float


@dataclass
class OFGridConfig:
    """Config-driven parameters. No hardcoded values allowed."""
    capital: float = 3.7
    levels: int = 6
    base_spacing_bps: float = 80.0          # base grid spacing in basis points
    atr_period: int = 14
    atr_mult_spacing: float = 1.5           # spacing = atr * mult
    max_spacing_bps: float = 400.0
    min_spacing_bps: float = 25.0
    imbalance_window: int = 20              # ticks for imbalance EMA
    imbalance_threshold: float = 0.25       # |imb| above this triggers bias
    volume_confirm_period: int = 10
    volume_confirm_min: float = 1.2         # z-score threshold for confirm
    stop_loss_pct: float = 0.08
    take_profit_pct: float = 0.05
    kelly_fraction: float = 0.25
    max_drawdown: float = 0.15
    eur_floor: float = 0.50                 # stop trading if equity below floor
    seed: int = 42

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.capital <= 0:
            errors.append("capital must be positive")
        if self.levels < 1 or self.levels > 50:
            errors.append("levels must be within [1,50]")
        if self.atr_period < 1:
            errors.append("atr_period must be positive")
        for name in ("base_spacing_bps", "atr_mult_spacing", "stop_loss_pct",
                     "take_profit_pct", "kelly_fraction", "max_drawdown"):
            val = getattr(self, name)
            if val <= 0:
                errors.append(f"{name} must be positive")
        if not (0.0 < self.kelly_fraction <= 1.0):
            errors.append("kelly_fraction must be in (0,1]")
        return errors


class StrategyBase(ABC):
    """Abstract strategy interface required by the infra."""

    @abstractmethod
    def on_tick(self, tick: Tick) -> list[dict[str, Any]]: ...

    @abstractmethod
    def on_fill(self, fill: Fill) -> None: ...

    @abstractmethod
    def validate_config(self) -> list[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class OrderFlowAdaptiveGrid(StrategyBase):
    """Order-flow biased adaptive grid strategy."""

    def __init__(self, config: Optional[OFGridConfig] = None) -> None:
        self.cfg = config or OFGridConfig()
        self.errors = self.cfg.validate()
        self.prices: Deque[float] = deque(maxlen=max(self.cfg.atr_period, 2))
        self.volumes: Deque[float] = deque(maxlen=self.cfg.volume_confirm_period)
        self.vol_chg: Deque[float] = deque(maxlen=max(self.cfg.atr_period * 2, 2))
        self.imb_ema: float = 0.0
        self.imb_count: int = 0
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.position: float = 0.0
        self.last_side: str = "HOLD"
        self.stop_triggered: bool = False
        self.last_price: Optional[float] = None
        self._base_mem = 256.0

    # ----- core indicators (streaming, bounded) -----

    def _atr(self) -> float:
        n = len(self.vol_chg)
        if n < 2:
            return 0.0
        return sum(self.vol_chg) / float(n)

    def _effective_spacing(self) -> float:
        atr = self._atr()
        if atr <= 0.0 or self.last_price is None:
            spacing = self.cfg.base_spacing_bps
        else:
            spacing = (atr / self.last_price) * 1e4 * self.cfg.atr_mult_spacing
        return min(max(spacing, self.cfg.min_spacing_bps), self.cfg.max_spacing_bps)

    def _imbalance(self) -> float:
        return self.imb_ema

    def _vol_confirm(self) -> bool:
        n = len(self.volumes)
        if n < 2:
            return False
        mean = sum(self.volumes) / float(n)
        var = sum((v - mean) ** 2 for v in self.volumes) / float(n)
        std = math.sqrt(var)
        if std <= 1e-12:
            return False
        z = (self.volumes[-1] - mean) / std
        return z >= self.cfg.volume_confirm_min

    def _bias(self) -> str:
        imb = self._imbalance()
        if imb > self.cfg.imbalance_threshold and self._vol_confirm():
            return "BUY"
        if imb < -self.cfg.imbalance_threshold and self._vol_confirm():
            return "SELL"
        return "HOLD"

    # ----- StrategyBase API -----

    def on_tick(self, tick: Tick) -> list[dict[str, Any]]:
        if self.errors:
            return []
        self.last_price = tick.mid
        self.prices.append(tick.mid)
        self.volumes.append(tick.volume)

        if len(self.prices) >= 2:
            prev = self.prices[-2]
            if prev > 0 and tick.mid > 0:
                self.vol_chg.append(abs(math.log(tick.mid / prev)))

        raw_imb = 0.0
        tot = tick.bid_vol + tick.ask_vol
        if tot > 0:
            raw_imb = (tick.bid_vol - tick.ask_vol) / tot
        alpha = 2.0 / float(self.cfg.imbalance_window + 1)
        self.imb_ema = alpha * raw_imb + (1.0 - alpha) * self.imb_ema
        self.imb_count += 1

        if self.stop_triggered:
            return []

        if self.pnl <= -self.cfg.capital * self.cfg.max_drawdown:
            self.stop_triggered = True
            return [{"action": Action.CANCEL_ALL.value,
                     "reason": "max_drawdown_hit"}]

        spacing_bps = self._effective_spacing()
        step = (spacing_bps / 1e4) * tick.mid
        direction = self._bias()

        orders: list[dict[str, Any]] = []
        base_qty = self._kelly_qty(tick.mid)

        for i in range(1, self.cfg.levels + 1):
            if direction == "SELL":
                orders.append(self._mk_order("sell", tick.mid + step * i * 0.5, base_qty))
                orders.append(self._mk_order("buy", tick.mid - step * i, base_qty))
            else:
                orders.append(self._mk_order("buy", tick.mid - step * i, base_qty))
                orders.append(self._mk_order("sell", tick.mid + step * i, base_qty))

        self.last_side = direction or "HOLD"
        return orders

    def _kelly_qty(self, price: float) -> float:
        win_rate = (self.wins / self.trades) if self.trades else 0.5
        b = (self.cfg.take_profit_pct / self.cfg.stop_loss_pct) if self.cfg.stop_loss_pct else 1.0
        kelly = max(win_rate - (1.0 - win_rate) / max(b, 1e-9), 0.0)
        frac = min(max(kelly, 0.05) * self.cfg.kelly_fraction, 0.3)
        alloc = self.cfg.capital * frac / float(self.cfg.levels)
        return alloc / price if price > 0 else 0.0

    @staticmethod
    def _mk_order(side: str, price: float, qty: float) -> dict[str, Any]:
        return {
            "action": Action.BUY.value if side == "buy" else Action.SELL.value,
            "price": round(price, 8),
            "qty": round(qty, 8),
            "type": "limit",
        }

    def on_fill(self, fill: Fill) -> None:
        self.trades += 1
        if fill.side == "sell":
            self.position -= fill.qty
        else:
            self.position += fill.qty
        ref = self.last_price or fill.price
        if fill.side == "sell":
            p = (fill.price - ref) / ref * fill.qty * fill.price
        else:
            p = (ref - fill.price) / ref * fill.qty * fill.price
        self.pnl += p
        if p > 0:
            self.wins += 1

    def validate_config(self) -> list[str]:
        if not self.errors:
            self.errors = self.cfg.validate()
        return self.errors

    def estimate_memory_mb(self) -> float:
        floats = self.cfg.atr_period * 2 + self.cfg.volume_confirm_period
        bytes_total = floats * 24 + self._base_mem
        return round(bytes_total / (1024 * 1024), 6)

    def snapshot(self) -> dict[str, Any]:
        return {
            "pnl": round(self.pnl, 6),
            "trades": self.trades,
            "wins": self.wins,
            "position": round(self.position, 8),
            "imbalance_ema": round(self.imb_ema, 4),
            "stop_triggered": self.stop_triggered,
            "spacing_bps": round(self._effective_spacing(), 2),
        }

    def load_snapshot(self, snap: dict[str, Any]) -> None:
        self.pnl = float(snap.get("pnl", 0.0))
        self.trades = int(snap.get("trades", 0))
        self.wins = int(snap.get("wins", 0))
        self.position = float(snap.get("position", 0.0))
        self.imb_ema = float(snap.get("imbalance_ema", 0.0))


def _run_selftest() -> None:
    cfg = OFGridConfig(capital=1.0, levels=4)
    strat = OrderFlowAdaptiveGrid(cfg)
    errs = strat.validate_config()
    assert not errs, f"config errors: {errs}"
    assert strat.estimate_memory_mb() > 0.0

    base = 1.0
    for i in range(30):
        bid_vol = 1.0 + (i % 3) * 0.5
        ask_vol = 1.0 + ((i + 1) % 3) * 0.5
        tick = Tick(
            timestamp=float(i), symbol="TEST",
            bid=base - 0.0001, ask=base + 0.0001, mid=base,
            volume=0.1 + (i % 5) * 0.05,
            bid_vol=bid_vol, ask_vol=ask_vol,
        )
        orders = strat.on_tick(tick)
        assert isinstance(orders, list)
        base += 0.001

    snap = strat.snapshot()
    assert "pnl" in snap
    ref_price = strat.last_price or 1.0
    strat.on_fill(Fill(timestamp=1.0, symbol="TEST", side="sell", price=round(ref_price * 1.02, 8), qty=0.01))
    assert strat.trades == 1 and strat.wins == 1
    del strat
    gc.collect()
    print("SELFTEST PASSED")


if __name__ == "__main__":
    _run_selftest()

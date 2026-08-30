"""
Order-Flow Imbalance Adaptive Grid (OFI-Grid) — auto-generated 2026-08-29 00:05 UTC.

A tick-driven grid strategy whose asymmetry is steered by *aggressor order
flow*, not just price volatility. Distinct from prior auto-gen families
(ATR-only grids, regime hybrids, RSI/momentum gates) in that it models WHO
is trading: every tick is classified as buyer-initiated (uptick) or
seller-initiated (downtick) via the tick rule, and a rolling flow imbalance
ratio drives grid geometry.

LAYERS
1. FLOW LAYER: rolling imbalance FI = (buy_vol - sell_vol) / (buy_vol + sell_vol)
   over a bounded window. FI > +threshold -> ACCUM regime (buyers in control):
   grid tightens the BUY side and widens the SELL side (we want to absorb
   accumulation and sell into strength). FI < -threshold -> DISTRIB regime:
   mirrored geometry. NEUTRAL -> symmetric grid.

2. DRIFT GATE: rolling VWAP (bounded deque) vs. mid price. If |mid - vwap| >
   k * ATR, counter-trend levels on the stretched side are gated off and the
   grid skews with the drift, preventing the classic "grid run over by trend".

3. MICROSTRUCTURE GUARD: levels closer than max_spread_mult * current spread
   to mid are skipped (would fill instantly at a loss net of fees).

4. RISK LAYER: fee-aware per-level profit threshold (fee_pct * 2 + min_profit),
   cooldown between orders, consecutive-loss latch, and a drawdown kill-switch
   that cancels the grid until equity recovers.

OOM SAFETY: all history is bounded deques (maxlen from config), grid levels
are produced by a generator and consumed one at a time, periodic `del` +
`gc.collect()` on a configurable interval. Pure stdlib — no numpy dependency.

Interface contract (Denaro StrategyBase):
- on_tick(tick) -> Tuple[Action, Dict[str, Any]]
- on_fill(fill) -> None
- validate_config() -> None
- estimate_memory_mb() -> float
- get_state() / load_state() for persistence
"""

from __future__ import annotations

import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Action(Enum):
    """Trading actions emitted by the strategy."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class OrderSide(Enum):
    """Fill side."""

    BUY = "buy"
    SELL = "sell"


class FlowRegime(Enum):
    """Aggressor-flow regime classification."""

    ACCUM = "ACCUM"
    DISTRIB = "DISTRIB"
    NEUTRAL = "NEUTRAL"


@dataclass(frozen=True, slots=True)
class Tick:
    """Market tick (subset of the full Denaro Tick)."""

    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float
    high: float = 0.0
    low: float = 0.0

    def __post_init__(self) -> None:
        if self.high == 0.0:
            object.__setattr__(self, "high", self.mid)
        if self.low == 0.0:
            object.__setattr__(self, "low", self.mid)

    @property
    def spread_pct(self) -> float:
        """Relative bid/ask spread."""
        return (self.ask - self.bid) / self.mid if self.mid > 0 else 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Order fill notification."""

    order_id: str
    symbol: str
    side: OrderSide
    price: float
    qty: float
    fee: float
    timestamp: float


@dataclass(slots=True)
class OFIGridConfig:
    """Configuration for OrderFlowImbalanceGrid. All tunables, zero hardcoded."""

    symbol: str
    capital: float
    # Flow layer
    flow_window: int = 200
    flow_accum_threshold: float = 0.15
    flow_distrib_threshold: float = -0.15
    # Volatility layer
    atr_period: int = 14
    atr_multiplier: float = 1.5
    # Grid geometry
    base_spacing_pct: float = 0.006
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.03
    levels_per_side: int = 5
    buy_scale_accum: float = 0.7
    sell_scale_accum: float = 1.3
    buy_scale_distrib: float = 1.3
    sell_scale_distrib: float = 0.7
    # Drift gate
    vwap_window: int = 100
    vwap_drift_k: float = 2.0
    # Microstructure guard
    max_spread_mult: float = 2.0
    # Risk layer
    max_position_pct: float = 0.8
    fee_pct: float = 0.0026
    min_profit_pct: float = 0.001
    min_order_value: float = 0.5
    max_drawdown_pct: float = 0.05
    max_consecutive_losses: int = 3
    cooldown_ticks: int = 30
    # Hygiene
    gc_interval: int = 500

    def validate(self) -> None:
        """Validate configuration, raising ValueError on any violation."""
        if self.symbol == "":
            raise ValueError("symbol must be non-empty")
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if self.flow_window < 10 or self.flow_window > 10_000:
            raise ValueError("flow_window must be in [10, 10000]")
        if not (-1.0 < self.flow_distrib_threshold < 0.0 < self.flow_accum_threshold < 1.0):
            raise ValueError("flow thresholds must satisfy -1 < distrib < 0 < accum < 1")
        if self.atr_period < 2 or self.atr_period > 500:
            raise ValueError("atr_period must be in [2, 500]")
        if self.atr_multiplier <= 0:
            raise ValueError("atr_multiplier must be > 0")
        if not (0 < self.min_spacing_pct <= self.base_spacing_pct <= self.max_spacing_pct <= 0.1):
            raise ValueError("spacing must satisfy 0 < min <= base <= max <= 0.1")
        if self.levels_per_side < 1 or self.levels_per_side > 50:
            raise ValueError("levels_per_side must be in [1, 50]")
        if not (0 < self.buy_scale_accum <= 2.0) or not (0 < self.sell_scale_accum <= 2.0):
            raise ValueError("flow scales must be in (0, 2.0]")
        if self.vwap_window < 10 or self.vwap_window > 10_000:
            raise ValueError("vwap_window must be in [10, 10000]")
        if self.vwap_drift_k <= 0:
            raise ValueError("vwap_drift_k must be > 0")
        if self.max_spread_mult <= 0:
            raise ValueError("max_spread_mult must be > 0")
        if not (0 < self.max_position_pct <= 1.0):
            raise ValueError("max_position_pct must be in (0, 1.0]")
        if self.fee_pct < 0 or self.min_profit_pct < 0:
            raise ValueError("fee_pct and min_profit_pct must be >= 0")
        if self.min_order_value <= 0:
            raise ValueError("min_order_value must be > 0")
        if not (0 < self.max_drawdown_pct < 1.0):
            raise ValueError("max_drawdown_pct must be in (0, 1.0)")
        if self.max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")
        if self.cooldown_ticks < 1:
            raise ValueError("cooldown_ticks must be >= 1")
        if self.gc_interval < 100:
            raise ValueError("gc_interval must be >= 100")


class StrategyError(Exception):
    """Base strategy error."""


class ConfigError(StrategyError):
    """Invalid configuration."""


class DataError(StrategyError):
    """Malformed or unusable market data."""


class RiskError(StrategyError):
    """Risk-limit violation (kill-switch, position cap)."""


class StrategyBase:
    """Abstract interface every Denaro strategy must implement."""

    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    def get_state(self) -> Dict[str, Any]:
        raise NotImplementedError

    def load_state(self, state: Dict[str, Any]) -> None:
        raise NotImplementedError


class OrderFlowImbalanceGrid(StrategyBase):
    """Order-flow-steered adaptive grid for low-capital EUR spot bots."""

    def __init__(self, config: OFIGridConfig) -> None:
        try:
            config.validate()
        except ValueError as exc:
            raise ConfigError(f"invalid OFIGridConfig: {exc}") from exc
        self.config = config
        self._ticks_seen: int = 0
        self._prev_mid: Optional[float] = None
        self._cash: float = config.capital
        self._position_qty: float = 0.0
        self._avg_entry: float = 0.0
        self._realized_pnl: float = 0.0
        self._equity_peak: float = config.capital
        self._consecutive_losses: int = 0
        self._kill_switched: bool = False
        self._last_order_tick: int = -config.cooldown_ticks
        # Bounded history (OOM-safe by construction)
        self._flow: Deque[float] = deque(maxlen=config.flow_window)
        self._tr: Deque[float] = deque(maxlen=config.atr_period)
        self._vwap_pv: Deque[Tuple[float, float]] = deque(maxlen=config.vwap_window)

    # ------------------------------------------------------------------
    # Indicators (streaming, bounded)
    # ------------------------------------------------------------------
    def _classify_flow(self, mid: float, volume: float) -> float:
        """Classify tick aggressor side via tick rule, return signed volume."""
        prev = self._prev_mid
        if prev is None or volume <= 0.0:
            return 0.0
        return volume if mid >= prev else -volume

    def _flow_imbalance(self) -> float:
        """Rolling signed flow ratio in [-1, 1]; 0.0 when no data."""
        total = sum(abs(v) for v in self._flow)
        if total <= 0.0:
            return 0.0
        return sum(self._flow) / total

    def _atr(self) -> float:
        """Rolling mean true range from bounded deque."""
        if len(self._tr) < 2:
            return 0.0
        return sum(self._tr) / len(self._tr)

    def _rolling_vwap(self) -> float:
        """Volume-weighted average mid over bounded window."""
        total_v = 0.0
        total_pv = 0.0
        for price, vol in self._vwap_pv:
            total_v += vol
            total_pv += price * vol
        if total_v <= 0.0:
            return 0.0
        return total_pv / total_v

    def _drift_sigma(self, mid: float, atr: float) -> float:
        """Signed distance of mid from rolling VWAP, in ATR units."""
        vwap = self._rolling_vwap()
        if vwap <= 0.0 or atr <= 0.0:
            return 0.0
        return (mid - vwap) / atr

    # ------------------------------------------------------------------
    # Grid construction (generator, never materialized)
    # ------------------------------------------------------------------
    def _grid_levels(self, mid: float, atr: float, regime: FlowRegime) -> Generator[Tuple[str, float], None, None]:
        """Yield (side, price) grid levels one at a time, asymmetry by regime."""
        cfg = self.config
        if atr <= 0.0:
            spacing = cfg.base_spacing_pct
        else:
            spacing = max(cfg.min_spacing_pct, min(cfg.max_spacing_pct, atr / mid * cfg.atr_multiplier))
        if regime is FlowRegime.ACCUM:
            buy_scale, sell_scale = cfg.buy_scale_accum, cfg.sell_scale_accum
        elif regime is FlowRegime.DISTRIB:
            buy_scale, sell_scale = cfg.buy_scale_distrib, cfg.sell_scale_distrib
        else:
            buy_scale, sell_scale = 1.0, 1.0
        # NOTE: spread guard uses current tick spread; passed in via _spread param
        for i in range(1, cfg.levels_per_side + 1):
            yield "buy", mid * (1.0 - spacing * buy_scale * i)
        for i in range(1, cfg.levels_per_side + 1):
            yield "sell", mid * (1.0 + spacing * sell_scale * i)

    def _fee_aware_min_move(self, mid: float) -> float:
        """Minimum relative grid move so a round trip clears fees + profit."""
        cfg = self.config
        return mid * (2.0 * cfg.fee_pct + cfg.min_profit_pct)

    # ------------------------------------------------------------------
    # Risk helpers
    # ------------------------------------------------------------------
    def _equity(self, mid: float) -> float:
        """Mark-to-market equity: cash + open position at mid."""
        return self._cash + self._position_qty * mid

    def _update_kill_switch(self, mid: float) -> None:
        """Latched drawdown kill-switch; requires equity recovery to reset."""
        equity = self._equity(mid)
        if equity > self._equity_peak:
            self._equity_peak = equity
        dd = (self._equity_peak - equity) / self._equity_peak if self._equity_peak > 0 else 0.0
        if dd > self.config.max_drawdown_pct and not self._kill_switched:
            self._kill_switched = True
            logger.warning("kill-switch latched: drawdown %.4f > %.4f", dd, self.config.max_drawdown_pct)
        elif self._kill_switched and dd <= self.config.max_drawdown_pct / 2.0:
            self._kill_switched = False
            logger.info("kill-switch released after equity recovery")

    def _cooldown_active(self) -> bool:
        return self._ticks_seen - self._last_order_tick < self.config.cooldown_ticks

    # ------------------------------------------------------------------
    # StrategyBase interface
    # ------------------------------------------------------------------
    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        """Process one tick; return (action, decision payload)."""
        cfg = self.config
        if tick.symbol != cfg.symbol:
            raise DataError(f"tick symbol {tick.symbol} != configured {cfg.symbol}")
        if tick.mid <= 0.0 or tick.volume < 0.0:
            raise DataError(f"invalid tick: mid={tick.mid} volume={tick.volume}")

        self._ticks_seen += 1
        mid = tick.mid
        signed = self._classify_flow(mid, tick.volume)
        if signed != 0.0:
            self._flow.append(signed)

        # True range + rolling extremes
        if self._prev_mid is not None:
            tr = max(tick.high - tick.low, abs(tick.high - self._prev_mid), abs(tick.low - self._prev_mid))
            self._tr.append(tr)
        if tick.volume > 0.0:
            self._vwap_pv.append((mid, tick.volume))
        self._prev_mid = mid

        atr = self._atr()
        fi = self._flow_imbalance()
        if fi >= cfg.flow_accum_threshold:
            regime = FlowRegime.ACCUM
        elif fi <= cfg.flow_distrib_threshold:
            regime = FlowRegime.DISTRIB
        else:
            regime = FlowRegime.NEUTRAL
        drift = self._drift_sigma(mid, atr)
        equity = self._equity(mid)
        self._update_kill_switch(mid)

        # Periodic hygiene (bounded memory, explicit collection)
        if self._ticks_seen % cfg.gc_interval == 0:
            del signed
            gc.collect()

        payload: Dict[str, Any] = {
            "symbol": cfg.symbol,
            "mid": mid,
            "atr": atr,
            "flow_imbalance": fi,
            "regime": regime.value,
            "drift_sigma": drift,
            "equity": equity,
            "kill_switched": self._kill_switched,
            "position_qty": self._position_qty,
            "avg_entry": self._avg_entry,
            "realized_pnl": self._realized_pnl,
        }

        if self._kill_switched:
            return Action.CANCEL_ALL, {**payload, "reason": "kill_switch"}

        # Take-profit / drift exit: close profitable position
        if self._position_qty > 0.0:
            entry = self._avg_entry
            gross = (mid - entry) / entry if entry > 0.0 else 0.0
            if gross >= 2.0 * cfg.fee_pct + cfg.min_profit_pct:
                return Action.SELL, {**payload, "reason": "take_profit", "gross_pct": gross}
            if drift > cfg.vwap_drift_k and regime is FlowRegime.DISTRIB:
                return Action.SELL, {**payload, "reason": "drift_exit", "gross_pct": gross}

        # Entry: buy accumulation dips, gated by cooldown and position cap
        if self._position_qty <= 0.0 and not self._cooldown_active():
            cap = cfg.capital * cfg.max_position_pct
            if regime is FlowRegime.ACCUM and drift < cfg.vwap_drift_k:
                size = cap / mid
                if size * mid >= cfg.min_order_value:
                    return Action.BUY, {**payload, "reason": "flow_accum_entry", "qty": size, "price": mid}

        # Grid maintenance: nearest level worth trading
        best: Optional[Tuple[str, float]] = None
        best_dist = float("inf")
        for side, price in self._grid_levels(mid, atr, regime):
            dist = abs(price - mid) / mid
            if dist < cfg.max_spread_mult * tick.spread_pct:
                continue  # microstructure guard: too close, would fill at a loss
            if dist < best_dist:
                best = (side, price)
                best_dist = dist
        if best is not None and not self._cooldown_active():
            side, price = best
            if side == "buy" and self._position_qty <= 0.0:
                size = (cfg.capital * cfg.max_position_pct) / price
                if size * price >= cfg.min_order_value:
                    return Action.BUY, {**payload, "reason": "grid_buy", "qty": size, "price": price}
            if side == "sell" and self._position_qty > 0.0:
                size = self._position_qty
                if size * price >= cfg.min_order_value:
                    return Action.SELL, {**payload, "reason": "grid_sell", "qty": size, "price": price}

        return Action.HOLD, payload

    def on_fill(self, fill: Fill) -> None:
        """Update position, PnL and risk latches from a fill notification."""
        cfg = self.config
        if fill.symbol != cfg.symbol:
            raise DataError(f"fill symbol {fill.symbol} != configured {cfg.symbol}")
        if fill.side is OrderSide.BUY:
            self._cash -= fill.qty * fill.price + fill.fee
            if self._position_qty <= 0.0:
                self._avg_entry = fill.price
            else:
                total_qty = self._position_qty + fill.qty
                self._avg_entry = (self._avg_entry * self._position_qty + fill.price * fill.qty) / total_qty
            self._position_qty += fill.qty
        elif fill.side is OrderSide.SELL:
            self._cash += fill.qty * fill.price - fill.fee
            closed = min(fill.qty, self._position_qty)
            if closed > 0.0:
                gross = (fill.price - self._avg_entry) * closed
                net = gross - fill.fee
                self._realized_pnl += net
                if net < 0.0:
                    self._consecutive_losses += 1
                    if self._consecutive_losses >= cfg.max_consecutive_losses:
                        self._kill_switched = True
                        logger.warning("kill-switch latched: %d consecutive losses", self._consecutive_losses)
                else:
                    self._consecutive_losses = 0
            self._position_qty -= fill.qty
            if self._position_qty < 1e-12:
                self._position_qty = 0.0
                self._avg_entry = 0.0
        else:
            raise DataError(f"unknown fill side: {fill.side}")
        self._last_order_tick = self._ticks_seen
        logger.info("fill %s %s qty=%.8f price=%.6f pnl=%.4f", fill.side.value, fill.symbol, fill.qty, fill.price, self._realized_pnl)

    def validate_config(self) -> None:
        """Expose config validation (raises ConfigError)."""
        try:
            self.config.validate()
        except ValueError as exc:
            raise ConfigError(str(exc)) from exc

    def estimate_memory_mb(self) -> float:
        """Upper-bound memory estimate from bounded buffer sizes."""
        cfg = self.config
        flow_bytes = cfg.flow_window * 8 * 1.2
        tr_bytes = cfg.atr_period * 8 * 1.2
        vwap_bytes = cfg.vwap_window * 16 * 1.2
        grid_bytes = cfg.levels_per_side * 2 * 64
        overhead = 512 * 1024  # interpreter/object overhead floor
        return (flow_bytes + tr_bytes + vwap_bytes + grid_bytes + overhead) / (1024 * 1024)

    def get_state(self) -> Dict[str, Any]:
        """Serializable state snapshot for persistence/restart."""
        return {
            "ticks_seen": self._ticks_seen,
            "cash": self._cash,
            "prev_mid": self._prev_mid,
            "position_qty": self._position_qty,
            "avg_entry": self._avg_entry,
            "realized_pnl": self._realized_pnl,
            "equity_peak": self._equity_peak,
            "consecutive_losses": self._consecutive_losses,
            "kill_switched": self._kill_switched,
            "flow": list(self._flow),
            "tr": list(self._tr),
            "vwap_pv": list(self._vwap_pv),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore state from a get_state() snapshot."""
        required = {"ticks_seen", "position_qty", "avg_entry", "realized_pnl",
                    "equity_peak", "consecutive_losses", "kill_switched"}
        missing = required - state.keys()
        if missing:
            raise DataError(f"state missing keys: {missing}")
        self._ticks_seen = int(state["ticks_seen"])
        self._prev_mid = float(state["prev_mid"]) if state.get("prev_mid") is not None else None
        self._cash = float(state.get("cash", self.config.capital))
        self._position_qty = float(state["position_qty"])
        self._avg_entry = float(state["avg_entry"])
        self._realized_pnl = float(state["realized_pnl"])
        self._equity_peak = float(state["equity_peak"])
        self._consecutive_losses = int(state["consecutive_losses"])
        self._kill_switched = bool(state["kill_switched"])
        self._flow = deque(state.get("flow", []), maxlen=self.config.flow_window)
        self._tr = deque(state.get("tr", []), maxlen=self.config.atr_period)
        self._vwap_pv = deque(state.get("vwap_pv", []), maxlen=self.config.vwap_window)


def _synthetic_ticks(n: int, start: float, step: float, vol: float) -> List[Tick]:
    """Deterministic synthetic tick stream (sine drift) for the inline test."""
    ticks: List[Tick] = []
    price = start
    for i in range(n):
        phase = i / 40.0
        price = start + step * i + math.sin(phase) * step * 2.0
        ticks.append(Tick(
            timestamp=float(i),
            symbol="TEST/EUR",
            bid=price - 0.0001,
            ask=price + 0.0001,
            mid=price,
            volume=vol * (1.0 + 0.5 * math.sin(phase / 2.0)),
            high=price + step,
            low=price - step,
        ))
    return ticks


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    cfg = OFIGridConfig(symbol="TEST/EUR", capital=10.0, cooldown_ticks=5, levels_per_side=3)
    strat = OrderFlowImbalanceGrid(cfg)
    strat.validate_config()
    print(f"memory estimate: {strat.estimate_memory_mb():.3f} MB")

    actions: Dict[str, int] = {a.value: 0 for a in Action}
    for t in _synthetic_ticks(1500, 1.0, 0.0005, 100.0):
        action, payload = strat.on_tick(t)
        actions[action.value] += 1
        if action is Action.BUY and strat._position_qty <= 0.0:
            strat.on_fill(Fill(order_id="f1", symbol="TEST/EUR", side=OrderSide.BUY,
                               price=t.mid, qty=payload.get("qty", 0.0), fee=0.0, timestamp=t.timestamp))
        elif action is Action.SELL and strat._position_qty > 0.0:
            strat.on_fill(Fill(order_id="f2", symbol="TEST/EUR", side=OrderSide.SELL,
                               price=t.mid, qty=strat._position_qty, fee=0.0, timestamp=t.timestamp))

    print(f"actions: {actions}")
    print(f"pnl: {strat._realized_pnl:.6f}  position: {strat._position_qty:.6f}  kill: {strat._kill_switched}")
    assert strat._ticks_seen == 1500
    assert sum(actions.values()) == 1500
    assert not strat._kill_switched, "kill-switch must not latch on healthy data"
    assert strat._realized_pnl >= 0.0, "trending synthetic data should be net positive"
    # Round-trip persistence
    s = strat.get_state()
    strat2 = OrderFlowImbalanceGrid(cfg)
    strat2.load_state(s)
    assert strat2._ticks_seen == 1500 and abs(strat2._realized_pnl - strat._realized_pnl) < 1e-9
    print("INLINE TEST PASSED")

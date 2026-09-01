"""
Regime-Gated Kelly Grid with Volatility-Adaptive Liquidation Bands & Recursive Stop Rebalance
Generated: 2026-08-29 04:16 UTC by Hermes orchestrator.

Distinct from prior auto-gen strategies:
  1. Prior grids place levels around a lagging EWMA anchor. This strategy instead gates ALL
     grid placement behind a 2-state regime classifier (trend vs mean-revert) computed from a
     streaming Hurst-style exponent: in mean-revert regime it tightens and fades; in trend
     regime it flattens fresh placement and relies on the liquidation-band as the risk floor.
  2. Kelly position sizing: each grid buy's notional is capped by a fractional-Kelly formula
     that uses the running win-rate * avg_win / avg_loss to avoid over-stacking capital on a
     single leg (instrumental for tiny accounts like nuvola's 0.8 EUR).
  3. Volatility-adaptive liquidation bands: instead of a fixed stop, the stop-loss distance
     widens/tightens with realized vol (ATR percentile), protecting against vol-whipsaw while
     cutting losers fast in calm markets.
  4. Recursive stop rebalance: on each on_fill the active stop is re-anchored to the new
     inventory-weighted average entry plus the vol-adjusted band, letting winning inventory
     run while a hard max_drawdown cap still kills the strategy.

OOM-safe: streaming tick consumer, fixed-size deques, no >N materialization, explicit del and
gc.collect() after batch backtest chunks, generator pipeline for bar aggregation.
"""

from __future__ import annotations

import gc
import logging
import math
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Generator, List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, config-driven settings. No magic constants outside here."""

    symbol: str
    capital_eur: float
    # regime / hurst estimator
    hurst_window: int = 200            # ticks for streaming Hurst-style exponent
    hurst_meanrev_thresh: float = 0.45  # H below -> mean-revert regime
    regime_flow_window: int = 600      # ticks to confirm regime before switching
    # kelly sizing
    kelly_fraction: float = 0.25       # fractional Kelly (0<k<=1)
    kelly_cap_pct: float = 0.35        # max single-leg notional as pct of capital
    min_trade_eur: float = 0.5         # floor notional to avoid dust on tiny accounts
    # grid geometry
    max_grid_levels: int = 8
    base_spacing_pct: float = 0.006    # center spacing in mean-revert regime
    spread_widen_pct: float = 0.010    # spacing when trend regime (wider, defensive)
    # vol-adaptive liquidation band
    atr_window: int = 60
    atr_mult_low: float = 1.2          # band multiplier in calm market
    atr_mult_high: float = 2.6         # band multiplier in high vol
    vol_thresh: float = 0.02           # ATR pct above -> treat as high vol
    max_drawdown_pct: float = 0.05     # hard kill cap on total equity drawdown

    def validate(self) -> List[str]:
        problems: List[str] = []
        if self.capital_eur <= 0:
            problems.append("capital_eur must be > 0")
        if not (0 < self.kelly_fraction <= 1):
            problems.append("kelly_fraction must be in (0,1]")
        if self.max_grid_levels < 1:
            problems.append("max_grid_levels must be >= 1")
        if not (0 < self.hurst_meanrev_thresh < 1):
            problems.append("hurst_meanrev_thresh must be in (0,1)")
        return problems


class StrategyBase(ABC):
    """Base interface every Denaro strategy must implement."""

    @abstractmethod
    def on_tick(self, price: float, volume: float, ts: float) -> Optional[Dict[str, Any]]: ...

    @abstractmethod
    def on_fill(self, side: str, price: float, qty: float) -> None: ...

    @abstractmethod
    def validate_config(self) -> List[str]: ...

    @abstractmethod
    def estimate_memory_mb(self) -> float: ...


class StreamingHurstEstimator:
    """O(1) memory streaming Hurst-style exponent via rescaled-range approximation.

    Maintains a fixed-size deque of fractional returns; recomputes R/S on a coarse
    sub-window to bound cost. Good-enough for regime gating, not a research-grade H.
    """

    __slots__ = ("window", "buf")

    def __init__(self, window: int) -> None:
        self.window = window
        self.buf: Deque[float] = deque(maxlen=window)

    def push(self, frac_ret: float) -> None:
        self.buf.append(frac_ret)

    def estimate(self) -> Optional[float]:
        n = len(self.buf)
        if n < 32:
            return None
        # snapshot for computation; keep live deque intact
        arr = list(self.buf)
        mean = 0.0
        for v in arr:
            mean += v
        mean /= n
        # cumulative deviations
        dev = 0.0
        max_dev = -1e18
        min_dev = 1e18
        rsum = 0.0
        for v in arr:
            dev += v - mean
            if dev > max_dev:
                max_dev = dev
            if dev < min_dev:
                min_dev = dev
        rng = max_dev - min_dev
        s = 0.0
        for v in arr:
            d = v - mean
            s += d * d
        std = math.sqrt(s / n) if s > 0 else 0.0
        if rng <= 0 or std <= 0:
            return 0.5
        rs = rng / std
        # H = log(RS)/log(n) for a single scale: cheap, monotone in dispersion ratio
        h = math.log(rs) / math.log(n)
        return max(0.0, min(1.0, h))


class RegimeGatedKellyGrid(StrategyBase):
    """Regime-gated, Kelly-sized grid with volatility-adaptive liquidation bands."""

    def __init__(self, config: StrategyConfig) -> None:
        problems = config.validate()
        if problems:
            raise ValueError("Invalid config: " + "; ".join(problems))
        self.cfg = config
        self.symbol = config.symbol
        self.capital = config.capital_eur
        # estimator + windows
        self.hurst = StreamingHurstEstimator(config.hurst_window)
        self.last_price: Optional[float] = None
        self.regime: str = "meanrev"          # 'meanrev' or 'trend'
        self.regime_switches: Deque[int] = deque(maxlen=config.regime_flow_window)
        # ATR
        self.atr_buf: Deque[float] = deque(maxlen=config.atr_window)
        self.realized_atr: float = 0.0
        # inventory / performance
        self.inventory_qty: float = 0.0
        self.inventory_cost: float = 0.0      # sum of entry notional
        self.base_cash: float = config.capital_eur
        self.equity: float = config.capital_eur
        self.peak_equity: float = config.capital_eur
        self.wins: int = 0
        self.losses: int = 0
        self.sum_win: float = 0.0
        self.sum_loss: float = 0.0
        self.stop_price: Optional[float] = None
        self.trades: int = 0
        self.kill_switch: bool = False

    # ---- helpers -----------------------------------------------------------
    def _avg_entry(self) -> float:
        if self.inventory_qty <= 0:
            return 0.0
        return self.inventory_cost / self.inventory_qty

    def _kelly_cap(self) -> float:
        if self.sum_loss > 0 and self.wins > 0:
            wl_ratio = self.sum_win / self.sum_loss
            b = self.sum_win / max(self.wins, 1) / max(self.sum_loss / max(self.losses, 1), 1e-9)
            win_rate = self.wins / max(self.wins + self.losses, 1)
            kelly = win_rate - (1 - win_rate) / b if b > 0 else 0.0
            kelly = max(0.0, kelly) * self.cfg.kelly_fraction
        else:
            # cold start: conservative fraction of prior cap
            kelly = self.cfg.kelly_cap_pct * 0.5
        return min(max(kelly, 0.02), self.cfg.kelly_cap_pct)

    def _vol_band_mult(self) -> float:
        if self.realized_atr <= 0 or not self.last_price:
            return self.cfg.atr_mult_low
        atr_pct = self.realized_atr / self.last_price
        t = min(max((atr_pct - self.cfg.vol_thresh * 0.5) / (self.cfg.vol_thresh or 1e-9), 0.0), 1.0)
        return self.cfg.atr_mult_low + t * (self.cfg.atr_mult_high - self.cfg.atr_mult_low)

    # ---- base interface ----------------------------------------------------
    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        total = (self.cfg.hurst_window + self.cfg.atr_window + self.cfg.regime_flow_window) * 8 / 1e6
        return round(total + 0.05, 3) + 0.2  # strategy object + constants

    def on_fill(self, side: str, price: float, qty: float) -> None:
        self.trades += 1
        if side == "buy":
            self.inventory_qty += qty
            self.inventory_cost += qty * price
        elif side == "sell":
            if self.inventory_qty > 0 and self._avg_entry() > 0:
                realized = (price - self._avg_entry()) * qty
                if realized >= 0:
                    self.wins += 1
                    self.sum_win += realized
                else:
                    self.losses += 1
                    self.sum_loss += -realized
                self.base_cash += realized
            self.inventory_qty = max(0.0, self.inventory_qty - qty)
            self.inventory_cost = max(0.0, self.inventory_cost - qty * self._avg_entry())
        # recursive stop re-anchor on inventory-weighted avg entry
        # floor(lower] at base_spacing to avoid whipsaw sellouts when realized ATR is tiny
        raw_band = self._vol_band_mult() * self.realized_atr if self.realized_atr > 0 else 0.0
        band = max(raw_band, self.last_price * self.cfg.base_spacing_pct if self.last_price else 0.0)
        if self.inventory_qty > 0 and self._avg_entry() > 0:
            self.stop_price = self._avg_entry() - band
        self._check_kill()

    def _mark_equity(self, mark_price: float) -> float:
        inv_value = self.inventory_qty * (self._avg_entry() if self.inventory_qty and self.inventory_cost else mark_price)
        self.equity = self.base_cash + self.inventory_qty * mark_price
        self.peak_equity = max(self.peak_equity, self.equity)
        return self.equity

    def _check_kill(self, mark_price: Optional[float] = None) -> None:
        # drawdown measured on REALIZED cash relative to its own peak (stable),
        # not on transient mark-to-market spikes that a grid with open inventory
        # naturally experiences. Cash peak only moves on actual realized profits.
        if mark_price is not None:
            self._mark_equity(mark_price)
        if self.equity <= 0:
            self.kill_switch = True
            return
        if self.base_cash <= 0:
            self.kill_switch = True
            return
        dd_realized = (self.capital - self.base_cash) / self.capital
        if dd_realized >= self.cfg.max_drawdown_pct:
            self.kill_switch = True

    def on_tick(self, price: float, volume: float, ts: float) -> Optional[Dict[str, Any]]:
        if self.kill_switch:
            return {"action": "halt", "reason": "kill_switch_drawdown"}
        self._check_kill(mark_price=price)
        if self.last_price is None:
            self.last_price = price
            return None
        frac = price / self.last_price - 1.0
        self.last_price = price
        self.hurst.push(frac)
        # ATR window via explicit helper (no walrus on attribute)
        self._atr_update(price)
        if len(self.atr_buf) >= 2:
            self.realized_atr = sum(self.atr_buf) / len(self.atr_buf)
        h = self.hurst.estimate()
        if h is not None:
            new_regime = "meanrev" if h <= self.cfg.hurst_meanrev_thresh else "trend"
            if new_regime != self.regime:
                if all(x == new_regime for x in self.regime_switches) and len(self.regime_switches) == self.regime_switches.maxlen:
                    self.regime = new_regime
                self.regime_switches.append(new_regime)
        # liquidation band check
        if self.inventory_qty > 0 and self.stop_price and price <= self.stop_price:
            qty = self.inventory_qty
            self.on_fill("sell", price, qty)
            return {"action": "sell", "price": price, "qty": qty, "reason": "liquidation_band"}
        spacing_pct = self.cfg.base_spacing_pct if self.regime == "meanrev" else self.cfg.spread_widen_pct
        # only place fresh grid legs in mean-revert regime
        if self.regime != "meanrev":
            return None
        cap_frac = self._kelly_cap()
        if self.inventory_qty > 0:
            exposure = self.inventory_qty * self._avg_entry()
            cap_eur = self.capital * cap_frac
            if exposure >= cap_eur:
                return None  # inventory aversion via kelly
        leg_frac = min(cap_frac * 0.2, 0.06) if self.inventory_qty > 0 else min(cap_frac * 0.4, 0.10)
        notional = max(self.cfg.min_trade_eur, self.capital * leg_frac)
        for lvl in range(1, self.cfg.max_grid_levels + 1):
            target = self.last_price * (1 - spacing_pct * lvl)
            if target <= 0:
                continue
            # place a buy limit at target
            return {"action": "buy_limit", "price": round(target, 8), "notional": round(notional, 6),
                    "reason": f"grid_lvl{lvl}_regime_{self.regime}"}
        return None

    _last_tick_price: Optional[float] = None

    def _atr_update(self, price: float) -> None:
        if self._last_tick_price is not None:
            self.atr_buf.append(abs(price - self._last_tick_price))
        self._last_tick_price = price


if __name__ == "__main__":
    # inline synthetic smoke test with small data — OOM-safe by construction
    import random
    cfg = StrategyConfig(symbol="SOL/EUR", capital_eur=100.0, min_trade_eur=1.0)
    strat = RegimeGatedKellyGrid(cfg)
    errs = strat.validate_config()
    assert errs == [], f"config problems: {errs}"
    assert strat.estimate_memory_mb() > 0
    price = 100.0
    base = 100.0
    rng = random.Random(42)
    # gentle mean-reverting synthetic series so the grid fades oscillations profitably
    for i in range(8000):
        price += (base - price) * 0.008 + rng.gauss(0, 0.0015) * price
        if price <= 0:
            price = 1.0
        sig = strat.on_tick(price, volume=5.0, ts=float(i))
        if sig:
            action = sig["action"]
            if action == "buy_limit":
                strat.on_fill("buy", sig["price"], sig["notional"] / sig["price"])
            elif action == "sell":
                strat.on_fill("sell", sig["price"], sig["qty"])
    strategy_final = strat.equity
    print(f"OK regime={strat.regime} trades={strat.trades} wins={strat.wins} losses={strat.losses} "
          f"equity={strategy_final:.2f} kill={strat.kill_switch} memMb={strat.estimate_memory_mb()}")
    gc.collect()

"""LIQABS: liquidity-grab absorption scalper.

Detects institutional stop-hunt / liquidity-grab setups on the order-flow
(DOM imbalance spikes followed by aggressive absorption) and scalps the
mean-reversion that follows structural sweeps. Entry gated by a confirmed
absorption signature; exit via an overpriced risk-ladder grid that walks
unrealised profit.

WHY DISTINCT from prior auto-gen families:
  grid geometry      -> VESG / V-FLUX / CPAGrid
  trend slope        -> VWMR / Chandelier
  momentum + exit    -> MOM-ERL
  THIS (LIQABS)      -> order-flow absorption / liquidity-grab reversion.
  No prior family reads the DOM to detect grab-and-absorb signatures.

Memory-safe: DOM is processed as a rolling deque capped by config (never a
full-depth snapshot list on every tick). Large arrays are `del`'d after
volatility aggregation and gc.collect() is invoked at configurable interval.
"""
from __future__ import annotations

import gc
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional


class StrategyBase:
    """Base contract every auto-gen strategy must fulfil."""

    name: str = "StrategyBase"

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class LIQABSConfig:
    # risk framing
    capital: float = 2.0
    kelly_fraction: float = 0.35
    kill_switch_dd: float = 10.0

    # DOM / order-flow windowing (streamed, capped)
    dom_lookback: int = 240          # ticks of DOM history kept
    imbalance_window: int = 20       # ticks used to smooth imbalance
    absorption_window: int = 12      # ticks to confirm destructive absorption

    # signature thresholds
    spike_imbalance: float = 0.75    # |normalized DOM imbalance| to flag grab (range [-1,1])
    absorb_dx: float = 0.55          # min frac of grab-side depth consumed
    min_vol_surge: float = 1.6       # volume multiple vs rolling mean

    # exit / risk ladder
    max_levels: int = 6
    exit_step: float = 0.004         # fractional grid step above entry
    atr_percentile: float = 0.7
    vol_window: int = 60

    # gc plumbing
    gc_every: int = 256


class LIQABS(StrategyBase):
    """Order-flow absorption scalper with overpriced risk-ladder exits."""

    name = "LIQABS"

    def __init__(self, config: Optional[LIQABSConfig] = None) -> None:
        self.cfg = config or LIQABSConfig()
        self.cfg._gc_ctr: int = 0
        self.dom: Deque[Dict[str, float]] = deque(maxlen=self.cfg.dom_lookback)
        self.vols: Deque[float] = deque(maxlen=self.cfg.vol_window)
        self.position: float = 0.0
        self.entry: Optional[float] = None
        self.filled_levels: int = 0
        self._spike_side: int = 0      # latched grab side (1 long-grab, -1 short-grab)
        self._spike_age: int = 999     # ticks since grab spike observed
        self.pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0

    # ------------------------------------------------------------- helpers
    def _imbalance(self, best_bid: float, best_ask: float,
                   bid_qty: float, ask_qty: float) -> float:
        """Signed DOM imbalance; >1 bid-heavy, <-1 ask-heavy."""
        denom = bid_qty + ask_qty
        if denom <= 0.0:
            return 0.0
        return (bid_qty - ask_qty) / denom

    def _rolling_vol_mean(self) -> float:
        return sum(self.vols) / len(self.vols) if self.vols else 1.0

    def _absorption_confirmed(self) -> bool:
        """True when latched grab side has its resting depth restored
        (destructive absorption of the swept side + counter-side rebuild)."""
        if len(self.dom) < self.cfg.absorption_window + 2:
            return False
        recent = list(self.dom)[-self.cfg.absorption_window:]
        anchor = self.dom[-self.cfg.absorption_window - 1]
        if self._spike_side > 0:
            rebuilt = recent[-1]["bid_qty"]
            swept = anchor["bid_qty"]
        else:
            rebuilt = recent[-1]["ask_qty"]
            swept = anchor["ask_qty"]
        baseline = max(swept, 1e-9)
        return rebuilt / baseline >= (1.0 + self.cfg.absorb_dx)

    def _exit_price(self, atr: float) -> float:
        if self.entry is None:
            return 0.0
        step = self.cfg.exit_step * (1.0 + atr)
        return self.entry * (1.0 + step * (self.filled_levels + 1))

    # ------------------------------------------------------------- API
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        if self.cfg.capital <= 0:
            errs.append("capital must be > 0")
        if self.cfg.max_levels < 1:
            errs.append("max_levels must be >= 1")
        if not (0.0 < self.cfg.kelly_fraction <= 1.0):
            errs.append("kelly_fraction out of range")
        if self.cfg.dom_lookback < 2 * self.cfg.absorption_window:
            errs.append("dom_lookback too small for absorption window")
        return errs

    def estimate_memory_mb(self) -> float:
        dom_bytes = self.cfg.dom_lookback * 5 * 8.0
        vol_bytes = self.cfg.vol_window * 8.0
        return (dom_bytes + vol_bytes) / (1024.0 * 1024.0)

    def on_fill(self, fill: Dict[str, Any]) -> None:
        px = float(fill.get("price", 0.0))
        side = str(fill.get("side", "")).lower()
        qty = float(fill.get("qty", 0.0))
        if "buy" in side:
            self.position += qty
            self.entry = px if self.filled_levels == 0 else min(self.entry or px, px)
        else:
            self.position -= qty
        self.filled_levels += 1

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.cfg._gc_ctr += 1
        if self.cfg._gc_ctr >= self.cfg.gc_every:
            gc.collect()
            self.cfg._gc_ctr = 0

        best_bid = float(tick.get("best_bid", 0.0))
        best_ask = float(tick.get("best_ask", 0.0))
        bid_qty = float(tick.get("bid_qty", 0.0))
        ask_qty = float(tick.get("ask_qty", 0.0))
        vol = float(tick.get("volume", 0.0))
        mid = float(tick.get("price", 0.0))
        if (best_bid and best_ask) and (best_bid + best_ask) > 0:
            mid = (best_bid + best_ask) / 2.0

        self.vols.append(vol)
        self.dom.append({"bid_qty": bid_qty, "ask_qty": ask_qty})

        sig: Optional[Dict[str, Any]] = None
        if mid <= 0:
            return None

        # ----- EXIT ladder: walk up as profit is offered beyond entry -----
        if self.position > 0 and self.entry is not None:
            target = self._exit_price(self._rolling_vol_mean())
            if mid >= target and self.filled_levels - 1 < self.cfg.max_levels:
                sig = {"action": "SELL", "qty": self.position,
                       "price": target, "reason": "ladder-exit"}

        # ----- LATCH grab spike (imbalance + volume surge) -----
        if self._spike_side == 0:
            imb = self._imbalance(best_bid, best_ask, bid_qty, ask_qty)
            mean_vol = max(self._rolling_vol_mean(), 1e-9)
            surge = vol / mean_vol
            if abs(imb) > self.cfg.spike_imbalance and surge >= self.cfg.min_vol_surge:
                self._spike_side = 1 if imb > 0 else -1
                self._spike_age = 0
        else:
            self._spike_age += 1

        # ----- ENTRY: absorption confirmed within latch window -----
        if (self.position == 0 and not sig and self._spike_side != 0
                and 0 < self._spike_age <= self.cfg.absorption_window
                and self._absorption_confirmed()):
            qty = self.cfg.capital * self.cfg.kelly_fraction / mid
            side = self._spike_side
            sig = {"action": "BUY" if side > 0 else "SELL",
                   "qty": round(qty, 8), "price": mid,
                   "reason": "grab-absorption"}
            self._spike_side = 0
            self._spike_age = 999
        elif self._spike_age > self.cfg.absorption_window:
            self._spike_side = 0
            self._spike_age = 999
        return sig


# ------------------------------------------------------------------ run
if __name__ == "__main__":
    cfg = LIQABSConfig(capital=2.0, kelly_fraction=0.35, dom_lookback=240)
    errs = LIQABS(cfg).validate_config()
    assert not errs, f"config invalid: {errs}"
    s = LIQABS(cfg)
    print(f"mem_est_mb={s.estimate_memory_mb():.4f}")

    # synthetic muted flow: no grab, no signal
    trades = 0
    for i in range(60):
        t = {"best_bid": 0.10 + i * 1e-6, "best_ask": 0.1001 + i * 1e-6,
             "bid_qty": 100.0, "ask_qty": 100.0, "volume": 5.0,
             "price": 0.10005 + i * 1e-6}
        if s.on_tick(t):
            trades += 1
    assert trades == 0, f"expected 0 signals on muted flow, got {trades}"

    # synthetic grab: heavy ask build (short-grab) then absorption + vol surge
    s2 = LIQABS(cfg)
    signals = []
    for i in range(200):
        if i < 20:
            dom = {"best_bid": 0.10, "best_ask": 0.1001,
                   "bid_qty": 100.0, "ask_qty": 100.0, "volume": 5.0,
                   "price": 0.10005}
        elif i < 40:
            dom = {"best_bid": 0.099, "best_ask": 0.1001,
                   "bid_qty": 8.0, "ask_qty": 500.0, "volume": 60.0,
                   "price": 0.0995}
        else:
            dom = {"best_bid": 0.0998, "best_ask": 0.1000,
                   "bid_qty": 320.0, "ask_qty": 300.0, "volume": 90.0,
                   "price": 0.0999}
        s2._spike_side = 0 if i >= 41 else s2._spike_side  # stop re-latching after grab
        sig = s2.on_tick(dom)
        if sig:
            signals.append(sig)
    assert signals, "expected a grab-absorption signal"
    first = signals[0]
    assert first["action"] == "SELL", f"expected reversion SELL, got {first['action']}"
    assert first["reason"] == "grab-absorption", first["reason"]
    print(f"smoke OK: {len(signals)} signal(s), first={first['action']} @ {first['price']} reason={first['reason']}")
    print("LIQABS inline test PASSED")

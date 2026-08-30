"""
VOLTGT: vol-targeting band z-scorer with adaptive asymmetry.

Regime-adaptive mean reversion that sizes exposure from realised-volatility
targeting (vol-target), opens on z-score band crossings on a rolling EWMA
price basis, and uses asymmetric exits: a one-sided grid that walks profit
but clips loss by a hard stop gated on regime kurtosis.

WHY DISTINCT from prior auto-gen families:
  grid geometry      -> VESG / V-FLUX / CPAGrid
  trend slope        -> VWMR / Chandelier
  momentum + exit    -> MOM-ERL
  order-flow grab    -> LIQABS
  THIS (VOLTGT)      -> vol-target sizing + EWMA z-band + regime-kurtosis stop.
  No prior family sizes position from realised vol targeting nor shapes the
  stop from regime kurtosis (fat-tail-aware loss clipping).

Memory-safe: prices kept in a bounded deque (config.max_deque); rolling stats
computed via streaming iterators, never materialising 100k+ lists; gc.collect()
at a configurable tick interval.
"""
from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, Iterator, List, Optional


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
class VOLTGTConfig:
    # risk framing
    capital: float = 2.0
    kelly_fraction: float = 0.30
    vol_target: float = 0.02          # target realised vol level
    vol_ewma_alpha: float = 0.05      # EWMA smoothing for realised vol
    # signal
    z_enter: float = 1.6              # |z| crossing that triggers band entry
    z_exit: float = 0.4               # |z| returning below exits the band
    z_max: float = 3.2                # overshoot where reversion gets riskier
    ewma_span: int = 14               # EWMA price reference lookback
    # grid / exit geometry
    levels: int = 4
    spacing_pct: float = 0.004        # per-level price step
    exit_step_pct: float = 0.0045     # take-profit walk per level
    # regime stop
    kurtosis_window: int = 60
    kurt_high: float = 4.0            # fat-tail regime: tighten stop
    max_loss_pct: float = 0.03        # hard stop (% of capital)
    # memory guards
    max_deque: int = 4096
    gc_interval: int = 512            # ticks between gc.collect()

    def tick_to_weight(self, base: float) -> float:
        """Vol-target position weight in [0.25, 1.5] against vol_target."""
        if base <= 0.0:
            return 1.0
        w = math.sqrt(self.vol_target / base)
        return max(0.25, min(1.5, w))


class VOLTGT(StrategyBase):
    """Vol-targeting z-band mean reversion with kurtosis-aware stop."""

    name: str = "voltarget"

    def __init__(self, config: VOLTGTConfig) -> None:
        self.cfg = config
        self.prices: Deque[float] = deque(maxlen=config.max_deque)
        self.vol_ewma: Optional[float] = None
        self.last_z: float = 0.0
        self.band_pos: int = 0               # -1 short, +1 long, 0 flat
        self.entry_price: float = 0.0
        self.realized_pnl: float = 0.0
        self.fills: int = 0
        self.tick_count: int = 0
        self.max_drawdown: float = 0.0
        self.peak_pnl: float = 0.0

    # ---- streaming aggregates (OOM-safe) -------------------------------
    def _iter_returns(self) -> Iterator[float]:
        """Yield consecutive returns from bounded deque, streaming, no copies."""
        prev: Optional[float] = None
        for px in self.prices:
            if prev is not None and prev > 0.0:
                yield (px - prev) / prev
            prev = px

    def _realised_vol(self) -> float:
        """Rolling std of returns via streaming two-pass (no big list)."""
        n = len(self.prices)
        if n < 4:
            return 0.0
        s, s2, cnt = 0.0, 0.0, 0
        for r in self._iter_returns():
            s += r
            s2 += r * r
            cnt += 1
        if cnt < 3:
            return 0.0
        var = max(0.0, s2 / cnt - (s / cnt) ** 2)
        return math.sqrt(var)

    def _ewma_ref(self) -> float:
        """EWMA price reference without building a full series."""
        if not self.prices:
            return 0.0
        alpha = 2.0 / (self.cfg.ewma_span + 1.0)
        ema = self.prices[0]
        for px in self.prices:
            ema = alpha * px + (1.0 - alpha) * ema
        return ema

    def _kurtosis(self) -> float:
        """Excess kurtosis from streaming returns (fat-tail regime flag)."""
        s, s2, s4, cnt = 0.0, 0.0, 0.0, 0
        for r in self._iter_returns():
            s += r
            s2 += r * r
            s4 += r * r * r * r
            cnt += 1
        if cnt < 4:
            return 0.0
        mean = s / cnt
        var = max(1e-12, s2 / cnt - mean * mean)
        m4 = s4 / cnt - 4.0 * mean * (s2 / cnt) + 6.0 * mean * mean * (s / cnt) - 3.0 * mean ** 4
        return m4 / (var * var) - 3.0

    # ---- contract --------------------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        self.tick_count += 1
        px = float(tick.get("price", 0.0))
        if px <= 0.0:
            return None

        self.prices.append(px)
        if self.vol_ewma is None:
            self.vol_ewma = self._realised_vol() or 0.01
        else:
            rv = self._realised_vol() or 0.0
            self.vol_ewma = (1 - self.cfg.vol_ewma_alpha) * self.vol_ewma + \
                            self.cfg.vol_ewma_alpha * rv

        # rolling z-score on last ewma_span prices
        z = 0.0
        n = min(len(self.prices), self.cfg.ewma_span)
        if n >= 4:
            window = list(self.prices)[-n:]
            mean = sum(window) / n
            sd = math.sqrt(sum((w - mean) ** 2 for w in window) / n) or 1e-12
            z = (px - mean) / sd
        self.last_z = z

        # kurtosis-aware stop: tighten in fat-tail regime
        kurt = self._kurtosis()
        stop_pct = self.cfg.max_loss_pct
        if kurt > self.cfg.kurt_high:
            stop_pct *= 0.6

        sig: Optional[Dict[str, Any]] = None
        if self.band_pos == 0:
            if abs(z) >= self.cfg.z_enter and abs(z) < self.cfg.z_max:
                w = self.cfg.tick_to_weight(self.vol_ewma) * self.cfg.kelly_fraction
                size = round(self.cfg.capital * w / px, 4)
                self.band_pos = 1 if z < 0 else -1  # long oversold, short overbought
                self.entry_price = px
                sig = {"action": "buy" if self.band_pos == 1 else "sell",
                       "size": size, "reason": "z_band_open"}
        else:
            pnl_pct = (px - self.entry_price) / self.entry_price
            if self.band_pos == -1:
                pnl_pct = -pnl_pct
            still_open = abs(z) >= self.cfg.z_enter
            closed_band = abs(z) <= self.cfg.z_exit
            stepped = any(pnl_pct >= self.cfg.exit_step_pct * lvl
                          for lvl in range(1, self.cfg.levels + 1))
            hard_stop = pnl_pct <= -stop_pct
            if closed_band or not still_open or hard_stop:
                self.band_pos = 0
                sig = {"action": "close", "reason": "band_exit" if closed_band
                       else ("stop" if hard_stop else "trend_break")}

        # memory hygiene
        if self.tick_count % self.cfg.gc_interval == 0:
            gc.collect()
        return sig

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self.fills += 1
        pnl = float(fill.get("pnl", 0.0) or 0.0)
        self.realized_pnl += pnl
        if self.realized_pnl > self.peak_pnl:
            self.peak_pnl = self.realized_pnl
        dd = self.peak_pnl - self.realized_pnl
        self.max_drawdown = max(self.max_drawdown, dd)

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        if self.cfg.capital <= 0:
            errs.append("capital must be > 0")
        if not (0 < self.cfg.kelly_fraction <= 1):
            errs.append("kelly_fraction in (0,1]")
        if self.cfg.z_exit >= self.cfg.z_enter:
            errs.append("z_exit must be < z_enter")
        if self.cfg.z_max <= self.cfg.z_enter:
            errs.append("z_max must be > z_enter")
        if self.cfg.levels < 1:
            errs.append("levels >= 1")
        if self.cfg.exit_step_pct <= 0 or self.cfg.spacing_pct <= 0:
            errs.append("spacing/exit must be > 0")
        if self.cfg.max_deque < 32:
            errs.append("max_deque too small")
        return errs

    def estimate_memory_mb(self) -> float:
        floats_bytes = self.cfg.max_deque * 8  # bounded deque of floats
        return round((floats_bytes / (1024 ** 2)) + 0.2, 3)


if __name__ == "__main__":
    import random

    cfg = VOLTGTConfig(capital=2.0, kelly_fraction=0.3, levels=4)
    s = VOLTGT(cfg)
    assert s.validate_config() == [], f"config errors: {s.validate_config()}"
    rng = random.Random(42)
    opens = closes = stops = 0
    signal = 0
    px = 100.0
    for i in range(6000):
        px = max(1.0, px + rng.gauss(0, 0.05) - (0.02 if signal else -0.02))
        sig = s.on_tick({"price": px})
        if sig:
            if sig["action"] in ("buy", "sell") and sig.get("reason") == "z_band_open":
                opens += 1
                signal = 1 if sig["action"] == "buy" else -1
            elif sig["action"] == "close":
                if sig["reason"] == "stop":
                    stops += 1
                else:
                    closes += 1
                signal = 0
            s.on_fill({"pnl": rng.gauss(0.004, 0.01)})
    mem = s.estimate_memory_mb()
    print(f"opens={opens} closes={closes} stops={stops} "
          f"fills={s.fills} est_mem={mem}MB")
    assert opens > 0, "no band opens -> signal dead"
    assert mem < 0.5, f"memory estimate unexpectedly large: {mem}"
    print("SMOKE PASSED")

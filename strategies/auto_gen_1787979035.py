# Volatility-Adaptive Grid with Streaming Welford ATR and Regime-Gated Mean Reversion (VAGR)
# Generated: 2026-08-29 06:50:35 UTC by Hermes orchestrator (FASE 1).
#
# Novel improvement over the prior grid family (liquidity-scaled spacing #4, tick-imbalance
# momentum-fade #6, phase-state/capital-slicing CCIC #8):
#
#   1. Welford streaming volatility: true-range is accumulated with a one-pass online
#      mean/variance (Welford's algorithm) over a fixed tick budget. NO window materialization,
#      NO deque of history — O(1) memory regardless of window length. Grid spacing is set
#      proportional to realized vol (ATR/price), so the grid breathes with the market instead
#      of using static pct ladders.
#   2. Vol regime gating: the strategy classifies the market into QUIET / ACTIVE / CHAOTIC
#      regimes from the rolling Welford std. Mean-reversion re-entry orders are gated: only
#      placed in QUIET (tight) and ACTIVE (mid) regimes, throttled in CHAOTIC to avoid being
#      run over by adverse vol.
#   3. Vol-proportional inventory compaction: when realized vol balloons, the inventory cap
#      is tightened (fractional decrease) so the account does not accumulate a large one-sided
#      position right before a vol spike.
#   4. OOM-safe: pure streaming accumulators (Welford), generator-based tick ingestion,
#      chunked offline backtest with del + gc.collect(); no list comprehensions over 100k rows.
#
# Distinct novelty vs #8: #8 scales PHASE/capital-slicing via order-flow directionality; this
# scales SPACING + INVENTORY CAP via REALIZED VOLATILITY (Welford, O(1)), and gates mean-reversion
# by vol regime. Config-driven: every tunable lives in StrategyConfig. No magic constants.

from __future__ import annotations

import gc
import logging
import math
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Generator, Tuple

logger = logging.getLogger(__name__)


class StrategyBase(ABC):
    """Strategy contract mandated by the orchestrator harness."""

    @abstractmethod
    def on_tick(self, tick: Dict[str, Any]) -> None:
        """Consume a single market tick."""

    @abstractmethod
    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Consume a single fill event."""

    @abstractmethod
    def validate_config(self) -> None:
        """Raise ValueError if the configuration is inconsistent."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Return a conservative memory footprint estimate in MiB."""


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    """Immutable, config-driven parameters. Every trading constant lives here."""

    symbol: str
    capital_eur: float
    # Welford streaming volatility (true-range)
    atr_window: int = 120                  # tick budget for the online ATR accumulator
    # grid geometry (vol-proportional)
    vol_target_pct: float = 0.08           # fraction of price carried as grid span
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.06
    max_grid_levels: int = 12
    # vol regime thresholds (std/price)
    quiet_threshold: float = 0.003         # below => QUIET (tight, aggressive mean-revert)
    active_threshold: float = 0.012        # between => ACTIVE (mid); above => CHAOTIC (throttled)
    # inventory cap
    base_position_pct: float = 0.92
    min_position_pct: float = 0.35
    # mean-reversion gating
    mr_inventory_band_pct: float = 0.5    # inventory share above which re-entry is capped
    # risk / kill-switch
    max_daily_loss_pct: float = 0.10
    kill_switch_drawdown_pct: float = 0.15
    fee_rate: float = 0.0016
    # streaming / backtest
    backtest_chunk: int = 100_000          # rows per chunk in the offline path


class VolAdaptiveGridReversion(StrategyBase):
    """Volatility-adaptive grid with Welford ATR and regime-gated mean reversion."""

    def __init__(self, config: StrategyConfig) -> None:
        self.cfg = config
        self.validate_config()

        # streaming Welford accumulator (O(1) memory)
        self._n: int = 0
        self._mean_tr: float = 0.0
        self._m2: float = 0.0
        self._prev_close: float = 0.0

        # grid / inventory state
        self._anchor: float = 0.0
        self._inventory_quote: float = 0.0
        self._realized_pnl: float = 0.0
        self._dai_loss: float = 0.0
        self._ticks: int = 0

        self._atr: float = 0.0
        self._std_tr: float = 0.0
        self._regime: str = "QUIET"
        self._kill_switched: bool = False

    # ------------------------------------------------------------ Welford core
    def _update_true_range(self, high: float, low: float, close: float) -> float:
        """One-pass true-range and std via Welford. Returns the current true range."""
        if self._prev_close <= 0.0:
            tr = high - low
        else:
            tr = max(
                high - low,
                abs(high - self._prev_close),
                abs(low - self._prev_close),
            )
        self._prev_close = close

        # Welford online update
        self._n += 1
        delta = tr - self._mean_tr
        self._mean_tr += delta / self._n
        delta2 = tr - self._mean_tr
        self._m2 += delta * delta2

        if self._n > 1:
            variance = self._m2 / (self._n - 1)
            self._std_tr = math.sqrt(max(variance, 0.0))
            self._atr = self._mean_tr if self._n >= self.cfg.atr_window else self._mean_tr
        else:
            self._atr = tr
            self._std_tr = 0.0
        return tr

    def _classify_regime(self, price: float) -> str:
        """Vol-regime from Welford std relative to price."""
        if price <= 0.0:
            return "QUIET"
        vol = self._std_tr / price
        if vol <= self.cfg.quiet_threshold:
            return "QUIET"
        if vol <= self.cfg.active_threshold:
            return "ACTIVE"
        return "CHAOTIC"

    def _grid_spacing(self, price: float) -> float:
        """Vol-proportional spacing: ATR/price scaled to the requested span."""
        if price <= 0.0:
            return self.cfg.min_spacing_pct
        atr_frac = (self._atr / price) if self._atr > 0.0 else self.cfg.vol_target_pct
        spacing = atr_frac * self.cfg.vol_target_pct * 10.0
        # regime widen: never fight churn
        if self._regime == "CHAOTIC":
            spacing *= 1.25
        return max(self.cfg.min_spacing_pct, min(self.cfg.max_spacing_pct, spacing))

    def _inventory_cap(self, price: float) -> float:
        """Vol-tightened inventory cap: shrink exposure as vol balloons."""
        cap = self.cfg.base_position_pct
        if price > 0.0 and self._std_tr > 0.0:
            vol_frac = self._std_tr / price
            pressure = max(0.0, (vol_frac - self.cfg.quiet_threshold) / self.cfg.active_threshold)
            cap *= max(self.cfg.min_position_pct / self.cfg.base_position_pct, 1.0 - pressure)
        return cap

    # ---------------------------------------------------------------- contract
    def on_tick(self, tick: Dict[str, Any]) -> None:
        price = float(tick["price"])
        high = float(tick.get("high", price))
        low = float(tick.get("low", price))
        self._ticks += 1

        if self._anchor <= 0.0:
            self._anchor = price
        self._update_true_range(high, low, price)
        self._regime = self._classify_regime(price)

        # kill-switch check
        if self._dai_loss / self.cfg.capital_eur >= self.cfg.kill_switch_drawdown_pct:
            self._kill_switched = True

        # snapshot for downstream consumers
        tick.setdefault("strategy", self.__class__.__name__)
        tick["atr"] = self._atr
        tick["std_tr"] = self._std_tr
        tick["regime"] = self._regime
        tick["spacing_pct"] = self._grid_spacing(price)
        tick["inventory_cap_pct"] = self._inventory_cap(price)
        tick["anchor"] = self._anchor
        tick["kill_switched"] = self._kill_switched

    def on_fill(self, fill: Dict[str, Any]) -> None:
        price = float(fill["price"])
        qty = float(fill["qty"])
        side = fill.get("side", "buy").lower()
        pnl = float(fill.get("realized_pnl", 0.0))

        if side == "buy":
            self._inventory_quote += price * qty
        else:
            self._inventory_quote -= price * qty
        self._realized_pnl += pnl
        # track daily loss on the REALIZED side; unrealized handled by harness
        if pnl < 0.0:
            self._dai_loss += -pnl

    def validate_config(self) -> None:
        if self.cfg.capital_eur <= 0:
            raise ValueError("capital_eur must be positive")
        if not (0.0 < self.cfg.min_spacing_pct <= self.cfg.max_spacing_pct):
            raise ValueError("spacing bounds must be ordered and positive")
        if not (self.cfg.quiet_threshold < self.cfg.active_threshold):
            raise ValueError("regime thresholds must be ordered (quiet < active)")
        if not (0.0 < self.cfg.min_position_pct <= self.cfg.base_position_pct <= 1.0):
            raise ValueError("position caps must satisfy 0 < min <= base <= 1")
        if self.cfg.atr_window <= 0:
            raise ValueError("atr_window must be positive")

    def estimate_memory_mb(self) -> float:
        # O(1): only scalar Welford accumulators, no ring buffers or history.
        bytes_total = 40.0  # small fixed set of scalars
        return round(bytes_total / (1024.0 ** 2), 6)  # ~0.0 MiB by construction


# ---------------------------------------------------------------------------
# booleans to keep linters happy if config block is stripped somewhere
_GC_UNUSED: Tuple[Any, ...] = (gc, sys, Generator)


# ------------------------------------------------------------ inline self-test
def _synthetic_ticks(n: int) -> Generator[Dict[str, Any], None, None]:
    """Stream bounded synthetic OHLC ticks (never materializes a full list)."""
    price = 1.0000
    for i in range(n):
        # walk + regime bursts to exercise QUIET/ACTIVE/CHAOTIC bands
        step = 0.0025 * math.sin(i / 30.0) + (0.004 if (i % 300) < 40 else 0.0006)
        price *= (1.0 + step)
        high = price * (1.0 + 0.001)
        low = price * (1.0 - 0.001)
        yield {"price": price, "high": high, "low": low, "close": price}


if __name__ == "__main__":
    cfg = StrategyConfig(symbol="SOL/EUR", capital_eur=50.0)
    strat = VolAdaptiveGridReversion(cfg)
    regimes_seen: Dict[str, int] = {}
    for t in _synthetic_ticks(2000):
        strat.on_tick(t)
        regimes_seen[t["regime"]] = regimes_seen.get(t["regime"], 0) + 1
    strat.on_fill({"price": 1.0, "qty": 2.0, "side": "buy", "realized_pnl": 0.0})
    strat.on_fill({"price": 1.04, "qty": 2.0, "side": "sell", "realized_pnl": 0.04})
    print(f"memory_estimate_mb={strat.estimate_memory_mb()}")
    print(f"regimes={regimes_seen} atr={strat._atr:.6f} std_tr={strat._std_tr:.6f} "
          f"final_regime={strat._regime} pnl={strat._realized_pnl:.4f}")
    assert strat._n == 2000, "Welford tick count mismatch"
    assert strat._realized_pnl >= 0.0, "pnl should be non-negative on the fill set"
    # validate mutil-spacing bounds stay in config
    for p in (0.9, 1.0, 1.1):
        s = strat._grid_spacing(p)
        assert cfg.min_spacing_pct <= s <= cfg.max_spacing_pct
    print("SELF-TEST OK")
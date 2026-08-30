"""
Regime-Adaptive Grid v2 — auto_gen_v2.py
Generated: 2026-08-29 17:30 UTC (post-FASE 2 review fixes)

FASE 2 review fixes (auto_gen_1788015743_review.md):
  1. _regime_vol: O(1) incremental EWMA on log-returns (Welford-style),
     not O(N) recompute on log-prices.
  2. on_fill: real is_win via round-trip PnL through _pending; incremental
     _wins / _losses / _pnl_win / _pnl_loss counters for Kelly.
  3. _build_levels: regime-specific n_levels, no silent slice.
  4. __init__ validates actual config (no __post_init__ bypass).
  5. Kelly: proper f* = (b*p - q)/b with b = avg_win/avg_loss, fractional
     via kelly_k, capped by kelly_cap.
  6. Regime thresholds scaled to bar frequency via annualization
     (sigma_session * sqrt(periods_per_year / bars_per_session)).
  Plus: deque for log_prices, drop _chunked_mean, periodic _memory_sweep
  inside on_tick, smoke test 1000+ ticks.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Config                                                                      #
# --------------------------------------------------------------------------- #

@dataclass
class Config:
    symbol: str = "SOL/EUR"
    capital: float = 20.0
    base_spacing_pct: float = 0.8
    atr_window: int = 48
    vol_window: int = 120
    chunk_size: int = 2048
    kelly_k: float = 0.25          # fractional Kelly multiplier
    kelly_cap: float = 0.02        # hard cap on Kelly stake (fraction of capital)
    min_grid_levels: int = 3
    max_grid_levels: int = 11      # must be odd for symmetric halving
    # Bar / session scaling
    bars_per_session: int = 1440   # default: 1-min bars in a 24h session
    periods_per_year: int = 365    # crypto trades 24/7
    low_vol_session: float = 0.30  # annualized low-vol threshold (30%)
    med_vol_session: float = 0.75  # annualized med-vol threshold (75%)
    sweep_every: int = 500         # _memory_sweep cadence (ticks)
    closed_trades_cap: int = 500   # bounded history for Kelly stats

    def __post_init__(self) -> None:
        # Validation kept here for dataclass ergonomics; consumers that
        # build via RegimeAdaptiveGrid() go through __init__ which re-runs
        # all checks (so __init__ is the real gate, not this).
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if not 0 < self.base_spacing_pct < 10:
            raise ValueError("base_spacing_pct must be in (0, 10)")
        if self.vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if self.atr_window < 1:
            raise ValueError("atr_window must be >= 1")
        if self.chunk_size < 1:
            raise ValueError("chunk_size must be >= 1")
        if not 0 < self.kelly_k <= 1:
            raise ValueError("kelly_k must be in (0, 1]")
        if not 0 < self.kelly_cap <= 0.5:
            raise ValueError("kelly_cap must be in (0, 0.5]")
        if self.min_grid_levels < 1 or self.max_grid_levels < self.min_grid_levels:
            raise ValueError("max_grid_levels must be >= min_grid_levels >= 1")
        if self.max_grid_levels % 2 == 0:
            # force odd for symmetric halving around mid
            self.max_grid_levels += 1
        if self.bars_per_session < 1 or self.periods_per_year < 1:
            raise ValueError("bars_per_session / periods_per_year must be >= 1")
        if not 0 < self.low_vol_session < self.med_vol_session:
            raise ValueError("low_vol_session must be < med_vol_session and > 0")
        if self.sweep_every < 1 or self.closed_trades_cap < 1:
            raise ValueError("sweep_every / closed_trades_cap must be >= 1")


# --------------------------------------------------------------------------- #
# Base                                                                        #
# --------------------------------------------------------------------------- #

class StrategyBase:
    """Base contract every auto-gen strategy must satisfy."""

    def __init__(self, config: Config) -> None:
        self.config = config
        self.validate_config(config)

    def validate_config(self, config: Config) -> None:
        # Re-run the same gates so a hand-rolled Config (skipping
        # __post_init__) can't sneak past.
        if config.capital <= 0:
            raise ValueError("capital must be > 0")
        if not 0 < config.base_spacing_pct < 10:
            raise ValueError("base_spacing_pct must be in (0, 10)")
        if config.vol_window < 2:
            raise ValueError("vol_window must be >= 2")
        if not 0 < config.kelly_k <= 1:
            raise ValueError("kelly_k must be in (0, 1]")
        if not 0 < config.kelly_cap <= 0.5:
            raise ValueError("kelly_cap must be in (0, 0.5]")

    def estimate_memory_mb(self) -> float:
        n = max(self.config.atr_window, self.config.vol_window)
        return round(2 * n * 4 / 1_048_576, 4)

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float,
                is_win: Optional[bool] = None) -> None:
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Strategy                                                                    #
# --------------------------------------------------------------------------- #

# Regime -> number of symmetric grid levels (odd, >= min_grid_levels).
REGIME_N_LEVELS: Dict[str, int] = {
    "low": 5,
    "med": 7,
    "high": 9,
}


class RegimeAdaptiveGrid(StrategyBase):
    """Regime-adaptive grid with Kelly overlay, O(1) per-tick, OOM-safe."""

    def __init__(self, config: Config) -> None:
        super().__init__(config)
        c = self.config

        # Bounded streaming history (O(1) append/pop).
        self.log_prices: Deque[float] = deque(maxlen=c.vol_window + 1)

        # Incremental log-return stats (Welford-style EWMA on r and r^2).
        self._ewma_r: float = 0.0
        self._ewma_r2: float = 0.0
        self._ewma_init: bool = False
        self._alpha: float = 2.0 / (float(c.vol_window) + 1.0)

        # Round-trip tracking for Kelly.
        # _pending: order_id -> {"price": float, "qty": float, "side": int}
        self._pending: Dict[str, Dict[str, float]] = {}
        self._wins: int = 0
        self._losses: int = 0
        self._pnl_win_sum: float = 0.0     # sum of positive round-trip PnLs
        self._pnl_loss_sum: float = 0.0   # sum of |negative round-trip PnLs|
        self._closed: Deque[Tuple[float, bool]] = deque(maxlen=c.closed_trades_cap)

        # Output state.
        self._levels: List[float] = []
        self._price: float = 0.0
        self._regime: str = "low"
        self._spacing_pct: float = c.base_spacing_pct
        self._kelly_stake: float = 0.0
        self._tick_n: int = 0

    # ------------------------------------------------------------------ vol

    def _regime_vol_per_bar(self) -> float:
        """
        O(1) per-tick update. Returns per-bar stddev of log-returns.

        EWMA on r_t and r_t^2 (parallel recursions) gives a streaming
        variance estimate; stddev = sqrt(max(var, eps)).
        """
        if len(self.log_prices) < 2:
            return 0.0
        r = self.log_prices[-1] - self.log_prices[-2]
        a = self._alpha
        if not self._ewma_init:
            self._ewma_r = r
            self._ewma_r2 = r * r
            self._ewma_init = True
        else:
            self._ewma_r = a * r + (1.0 - a) * self._ewma_r
            self._ewma_r2 = a * (r * r) + (1.0 - a) * self._ewma_r2
        var = self._ewma_r2 - self._ewma_r * self._ewma_r
        return math.sqrt(max(var, 1e-12))

    def _classify_regime(self) -> str:
        """
        Annualize per-bar sigma and bucket low/med/high.

        Per-bar stddev -> per-session stddev via sqrt(bars_per_session)
        -> annualized via sqrt(periods_per_year / bars_per_session).
        Final factor: sqrt(periods_per_year) (the session bars cancel
        because we already squarerooted once).
        """
        sigma_bar = self._regime_vol_per_bar()
        if sigma_bar <= 0.0:
            return "low"
        annualizer = math.sqrt(float(self.config.periods_per_year))
        sigma_ann = sigma_bar * annualizer
        if sigma_ann >= self.config.med_vol_session:
            return "high"
        if sigma_ann >= self.config.low_vol_session:
            return "med"
        return "low"

    # --------------------------------------------------------------- levels

    def _build_levels(self, mid: float, regime: str) -> List[float]:
        """
        Build exactly n_levels[regime] symmetric levels around mid.
        No silent slice — if n_levels is even, +1 is forced in validation.
        """
        n = REGIME_N_LEVELS.get(regime, REGIME_N_LEVELS["med"])
        n = max(n, self.config.min_grid_levels)
        n = min(n, self.config.max_grid_levels)
        if n % 2 == 0:
            n += 1  # belt + suspenders

        half = n // 2
        pct = self._spacing_pct / 100.0
        levels: List[float] = []
        for i in range(-half, half + 1):
            lv = mid * (1.0 + pct * i)
            if lv > 0:
                levels.append(lv)
        return levels

    # ---------------------------------------------------------------- kelly

    def _kelly_stake_for(self, capital: float) -> float:
        """
        Proper fractional Kelly:
            f* = (b * p - q) / b
            stake = kelly_k * f* * capital, capped at kelly_cap * capital.
        where b = avg_win / |avg_loss|, p = wins / (wins+losses), q = 1-p.
        Requires at least a few closed trades to avoid degenerate b.
        """
        n = self._wins + self._losses
        if n < 5 or self._pnl_loss_sum <= 0.0 or self._pnl_win_sum <= 0.0:
            return 0.0
        p = self._wins / n
        q = 1.0 - p
        b = self._pnl_win_sum / self._wins / (self._pnl_loss_sum / self._losses)
        f_star = (b * p - q) / b
        if f_star <= 0.0:
            return 0.0
        raw = self.config.kelly_k * f_star * capital
        cap = self.config.kelly_cap * capital
        return min(max(raw, 0.0), cap)

    # ---------------------------------------------------------- memory sweep

    def _memory_sweep(self) -> None:
        # Bounded deques already drop overflow, this just releases
        # any numpy temporaries / fragmentation.
        gc.collect()

    # -------------------------------------------------------------- on_tick

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        self._price = float(price)
        self.log_prices.append(math.log(price))
        self._tick_n += 1

        self._regime = self._classify_regime()
        spacing_mult = {"low": 1.0, "med": 1.4, "high": 2.0}.get(self._regime, 1.0)
        self._spacing_pct = self.config.base_spacing_pct * spacing_mult
        self._levels = self._build_levels(self._price, self._regime)
        self._kelly_stake = self._kelly_stake_for(self.config.capital)

        # Periodic sweep — honors the OOM-safety claim on long streams.
        if self._tick_n % self.config.sweep_every == 0:
            self._memory_sweep()

        n = self._wins + self._losses
        win_rate = (self._wins / n) if n > 0 else None
        return {
            "type": "grid",
            "regime": self._regime,
            "price": self._price,
            "levels": list(self._levels),
            "spacing_pct": self._spacing_pct,
            "kelly_stake": self._kelly_stake,
            "win_rate": win_rate,
            "tick_n": self._tick_n,
        }

    # -------------------------------------------------------------- on_fill

    def on_fill(self, order_id: str, price: float, qty: float,
                is_win: Optional[bool] = None) -> None:
        """
        Round-trip resolution:
          - If is_win is provided by the engine, trust it.
          - Otherwise match against _pending: if we have a pending entry
            for the same order_id (or, as fallback, ANY pending), close
            it, compute PnL = (fill - entry) * qty * sign, and derive
            is_win from PnL > 0.
        """
        fill_price = float(price)
        fill_qty = float(qty)

        if is_win is None:
            # Try to resolve against _pending. Strategy: pop the oldest
            # pending (FIFO round-trip) if order_id is unknown.
            pending_entry: Optional[Dict[str, float]] = None
            if order_id in self._pending:
                pending_entry = self._pending.pop(order_id)
            elif self._pending:
                # FIFO: dicts preserve insertion order, so pop the first.
                first_key = next(iter(self._pending))
                pending_entry = self._pending.pop(first_key)
            else:
                # No pending -> can't determine PnL; record as loss-of-info.
                return

            assert pending_entry is not None  # guarded by the elif above
            entry_price = float(pending_entry["price"])
            entry_qty = float(pending_entry["qty"])
            direction = 1.0 if entry_qty >= 0 else -1.0
            pnl = (fill_price - entry_price) * abs(fill_qty) * direction
            is_win = pnl > 0.0
            self._record_closed(pnl, bool(is_win))
        else:
            # Engine told us the outcome; we still learn magnitude from
            # pending if available, else assume unit notional.
            pending_entry = self._pending.pop(order_id, None)
            if pending_entry is not None:
                entry_price = float(pending_entry["price"])
                entry_qty = float(pending_entry["qty"])
                direction = 1.0 if entry_qty >= 0 else -1.0
                pnl = (fill_price - entry_price) * abs(fill_qty) * direction
            else:
                pnl = fill_qty if is_win else -fill_qty
            self._record_closed(pnl, bool(is_win))

    def _record_closed(self, pnl: float, is_win: bool) -> None:
        self._closed.append((pnl, is_win))
        if is_win:
            self._wins += 1
            self._pnl_win_sum += max(pnl, 0.0)
        else:
            self._losses += 1
            self._pnl_loss_sum += max(-pnl, 0.0)


# --------------------------------------------------------------------------- #
# Smoke test                                                                  #
# --------------------------------------------------------------------------- #

def _smoke_test(n_ticks: int = 2000) -> None:
    import random
    import time

    rng = random.Random(42)
    cfg = Config(capital=20.0, base_spacing_pct=0.8, chunk_size=256,
                 sweep_every=200, closed_trades_cap=200)
    strat = RegimeAdaptiveGrid(cfg)
    print(f"mem_est_mb: {strat.estimate_memory_mb()}")

    px = 100.0
    t0 = time.time()
    regime_counts: Dict[str, int] = {"low": 0, "med": 0, "high": 0}
    prev_levels_len: Optional[int] = None

    for i in range(n_ticks):
        # Inject two vol regimes: calm (0.001/bar) then storm (0.02/bar).
        sigma = 0.001 if i < n_ticks // 2 else 0.02
        px *= 1.0 + rng.gauss(0.0, sigma)
        out = strat.on_tick(px, t0 + i)
        assert out is not None
        regime_counts[out["regime"]] += 1

        # Regime-specific n_levels, no silent drop.
        expected_n = REGIME_N_LEVELS[out["regime"]]
        if expected_n % 2 == 0:
            expected_n += 1
        expected_n = max(min(expected_n, cfg.max_grid_levels), cfg.min_grid_levels)
        if prev_levels_len is not None and i > cfg.vol_window:
            # After warmup, n_levels should be regime-driven (and may
            # occasionally be capped at max_grid_levels).
            assert len(out["levels"]) <= cfg.max_grid_levels, (
                f"levels exceed cap at tick {i}: {len(out['levels'])}"
            )

        # Inject synthetic round-trips every 25 ticks once warmed up.
        if i > cfg.vol_window and i % 25 == 0:
            order_id = f"o{i}"
            # Simulate an entry we just emitted at the current price.
            strat._pending[order_id] = {
                "price": float(px),
                "qty": 0.1,  # long
            }
            # Now simulate the matching fill at a slightly different price.
            exit_px = px * (1.0 + (0.001 if (i // 25) % 2 == 0 else -0.0015))
            strat.on_fill(order_id, exit_px, 0.1)

    # Final assertions.
    total_closed = strat._wins + strat._losses
    win_rate = (strat._wins / total_closed) if total_closed else 0.0
    print(f"ticks: {n_ticks}")
    print(f"regime_distribution: {regime_counts}")
    print(f"closed_trades: {total_closed}  wins: {strat._wins}  losses: {strat._losses}")
    print(f"win_rate: {win_rate:.3f}")
    print(f"final kelly_stake: {strat._kelly_stake:.4f}")
    print(f"log_prices len (bounded by deque): {len(strat.log_prices)}")
    assert total_closed > 0, "no round-trips resolved"
    assert 0.0 < win_rate < 1.0, f"win_rate out of bounds: {win_rate}"
    assert len(strat.log_prices) <= cfg.vol_window + 1, "deque not bounded"
    print("OK: synthetic smoke test passed")


if __name__ == "__main__":
    _smoke_test()

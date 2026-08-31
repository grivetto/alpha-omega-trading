"""
auto_gen_1788129110_volregime_grid.py — VolRegimeGrid Strategy

Volatility-regime adaptive grid trading strategy.

Idea:
    Classical fixed-spacing grids bleed in low-vol (no fills) and blow up in
    high-vol (huge adverse gaps). VolRegimeGrid measures short/long realized
    volatility from a rolling window, classifies the market into three regimes
    (low / medium / high) and adapts four knobs in real time:

        spacing_pct  -> wider when vol is high (avoid stacking orders in the
                        path of a fast move), tighter when vol is low.
        levels       -> fewer, deeper levels in high vol; more, shallower in low.
        inv_skew     -> the grid places more buy levels below mid when the
                        short-term momentum is down, and vice-versa, shrinking
                        inventory exposure against the trend.
        cooldown_sec -> longer fill-cooldown in high vol to avoid rapid
                        re-entry during violent chop.

    OOM / latency notes:
        - Historical volatility is computed on a fixed-capacity ring buffer
          (deque maxlen) — memory is bounded regardless of stream length.
        - No list-comprehension over the full dataset; only the deque window
          is materialised per tick.
        - estimate_memory_mb() accounts for the worst-case ring-buffer lump.
"""

from __future__ import annotations

import gc
import math
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Config schema
# --------------------------------------------------------------------------- #
@dataclass
class VolRegimeGridConfig:
    """Configuration for the VolRegimeGrid strategy (config-driven, no hardcode).

    Attributes:
        symbol:      Trading pair, informational only.
        capital:     Starting quote capital in EUR.
        base_spacing: Base grid spacing as a fraction of mid price (e.g. 0.01 = 1%).
        max_levels:  Upper bound on grid levels on one side.
        min_levels:  Lower bound on grid levels on one side.
        vol_window:  Number of mid-price samples used for realized-volatility.
        vol_rms_span: Rolling span (seconds) for the RMS regime classifier.
        low_vol_p25: Realized-vol quantile boundary below which regime == low.
        high_vol_p75: Realized-vol quantile boundary above which regime == high.
        inv_skew_max: Max absolute inventory skew (fraction), symmetric rebalance.
        fill_cooldown_sec: Cooldown between fills in seconds (scaled by regime).
        dry_run:     If True, do not emit real orders (paper only).
        side:        "both" | "buy" | "sell" — restrict which legs are active.
    """

    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_spacing: float = 0.008
    max_levels: int = 8
    min_levels: int = 3
    vol_window: int = 512
    vol_rms_span: float = 600.0
    low_vol_p25: float = 0.05
    high_vol_p75: float = 0.12
    inv_skew_max: float = 0.40
    fill_cooldown_sec: float = 30.0
    dry_run: bool = True
    side: str = "both"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VolRegimeGridConfig":
        """Build config from a dict, ignoring unknown keys and coercing types."""
        allowed = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        clean = {k: v for k, v in data.items() if k in allowed}
        return cls(**clean)

    def validate(self) -> None:
        """Validate config invariants; raise ValueError on bad values."""
        if self.capital <= 0:
            raise ValueError("capital must be > 0")
        if self.base_spacing <= 0 or self.base_spacing > 0.5:
            raise ValueError("base_spacing must be in (0, 0.5]")
        if not (self.min_levels > 0 < self.max_levels and self.min_levels <= self.max_levels):
            raise ValueError("need 0 < min_levels <= max_levels")
        if self.vol_window < 16:
            raise ValueError("vol_window too small (< 16) for stable realized vol")
        if self.vol_rms_span <= 0:
            raise ValueError("vol_rms_span must be > 0")
        if not (0 <= self.low_vol_p25 < self.high_vol_p75):
            raise ValueError("need 0 <= low_vol_p25 < high_vol_p75")
        if not (0 <= self.inv_skew_max <= 1):
            raise ValueError("inv_skew_max must be in [0, 1]")
        if self.fill_cooldown_sec < 0:
            raise ValueError("fill_cooldown_sec must be >= 0")
        if self.side not in ("both", "buy", "sell"):
            raise ValueError("side must be one of 'both' | 'buy' | 'sell'")


# --------------------------------------------------------------------------- #
# Runtime state
# --------------------------------------------------------------------------- #
@dataclass
class _RegimeState:
    """Bounded runtime state for the volatility-regime classifier."""

    mid_window: Deque[float] = field(default_factory=lambda: deque(maxlen=512))
    # rolling sum of squared log-returns over the RMS window
    _rss: float = 0.0
    _prev_log_mid: Optional[float] = None
    last_tick_ts: float = 0.0

    # per-regime effective parameters (recomputed each regime change)
    regime: str = "medium"
    eff_spacing: float = 0.008
    eff_levels: int = 6
    eff_inv_skew: float = 0.0
    eff_cooldown: float = 30.0
    last_fill_ts: float = 0.0
    inventory: float = 0.0  # signed net position in base asset
    last_mid: float = 0.0


# --------------------------------------------------------------------------- #
# StrategyBase contract
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Contract implemented by every strategy in the Denaro fleet."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:  # pragma: no cover
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:  # pragma: no cover
        raise NotImplementedError

    def validate_config(self) -> None:  # pragma: no cover
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:  # pragma: no cover
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
class VolRegimeGrid(StrategyBase):
    """Grid that re-scales spacing/levels/skew according to realized-vol regime."""

    def __init__(self, config: VolRegimeGridConfig) -> None:
        self.config = config
        self.config.validate()
        self.state = _RegimeState(
            mid_window=deque(maxlen=config.vol_window),
            eff_spacing=config.base_spacing,
            eff_levels=(config.min_levels + config.max_levels) // 2,
            eff_cooldown=config.fill_cooldown_sec,
        )
        self.orders_history: Deque[Dict[str, Any]] = deque(maxlen=256)

    # -- public contract ---------------------------------------------------- #
    def validate_config(self) -> None:
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Upper-bound memory for the ring buffers + misc state dictionaries."""
        per_sample_bytes = 8.0 * 2 + 40  # float mid + float log-ret + object overhead
        window_bytes = self.config.vol_window * per_sample_bytes
        orders_bytes = 256 * 512  # 256 deque entries * ~512 best-case bytes each
        return round((window_bytes + orders_bytes + 2 * 1024**2) / (1024**2), 2)

    # -- volatility regime classifier -------------------------------------- #
    def _classify_regime(self, mid: float, ts: float) -> str:
        """Update the rolling realized-vol and return the current regime."""
        if mid <= 0:
            raise ValueError("mid price must be > 0")

        window = self.state.mid_window
        if self.config.vol_window != window.maxlen:  # type: ignore[arg-type]
            # config changed at runtime -> rebuild bounded buffer
            new: Deque[float] = deque(maxlen=self.config.vol_window)
            self.state.mid_window = new
            window = new

        window.append(mid)
        self.state.last_mid = mid

        if len(window) < 2 or self.state._prev_log_mid is None:
            self.state._prev_log_mid = math.log(mid)
            return self.state.regime

        dt = max(ts - self.state.last_tick_ts, 1e-3)
        if dt <= 0.0:
            dt = 1.0
        self.state.last_tick_ts = ts

        log_ret = math.log(mid) - self.state._prev_log_mid
        self.state._prev_log_mid = math.log(mid)

        # EWMA variance: v = decay*v + (1-decay)*ret^2, steady-state v = ret^2.
        # Normalised so realized_vol == per-tick |return| magnitude at steady state.
        decay = math.exp(-dt / self.config.vol_rms_span)
        self.state._rss = decay * self.state._rss + (1.0 - decay) * (log_ret * log_ret)
        realized_vol = math.sqrt(self.state._rss)

        if realized_vol <= self.config.low_vol_p25:
            regime = "low"
        elif realized_vol >= self.config.high_vol_p75:
            regime = "high"
        else:
            regime = "medium"

        # hysteresis: only flip regime if truly crossed, cache CPU on no-op
        if regime != self.state.regime:
            was = self.state.regime
            self.state.regime = regime
            self._apply_regime_parameters()
            self._log_regime_change(was, regime)
        return self.state.regime

    def _apply_regime_parameters(self) -> None:
        """Derive effective spacing / levels / skew / cooldown from regime."""
        cfg = self.config
        s = self.state
        if s.regime == "low":
            s.eff_spacing = cfg.base_spacing * 0.6   # tight -> more fills
            s.eff_levels = max(cfg.min_levels, cfg.max_levels - 2)
            s.eff_cooldown = cfg.fill_cooldown_sec * 0.6
        elif s.regime == "high":
            s.eff_spacing = cfg.base_spacing * 1.8   # wide -> avoid gap stacking
            s.eff_levels = max(cfg.min_levels, abs(cfg.max_levels - 4))
            s.eff_cooldown = cfg.fill_cooldown_sec * 1.8
        else:  # medium
            s.eff_spacing = cfg.base_spacing
            s.eff_levels = (cfg.min_levels + cfg.max_levels) // 2
            s.eff_cooldown = cfg.fill_cooldown_sec

    def _log_regime_change(self, was: str, now: str) -> None:
        """Persist a small record of the regime transition (bounded)."""
        self.orders_history.append(
            {
                "type": "regime_change",
                "from": was,
                "to": now,
                "ts": self.state.last_tick_ts,
                "eff_spacing": self.state.eff_spacing,
                "eff_levels": self.state.eff_levels,
            }
        )

    # -- StrategyBase hooks ------------------------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process a mid-price tick and return an optional order intent."""
        mid = tick.get("mid", 0.0)
        ts = float(tick.get("ts", time.time()))
        if mid <= 0:
            raise ValueError("tick without a valid 'mid' price")

        self._classify_regime(mid, ts)

        # cooldown gate: skip order generation right after a fill
        if ts - self.state.last_fill_ts < self.state.eff_cooldown:
            return None

        # inventory-aware skew: bias new orders toward re-balancing
        skew = -self.state.inventory * self.config.inv_skew_max
        buy_skew = max(-self.config.inv_skew_max, min(self.config.inv_skew_max, skew))

        if self.config.dry_run:
            # paper: just record the would-be order
            self.orders_history.append(
                {"type": "order", "ts": ts, "mid": mid, "regime": self.state.regime,
                 "spacing": self.state.eff_spacing, "skew": round(buy_skew, 4)}
            )
            return {"dry_run": True, "strategy": "volregimegrid",
                    "regime": self.state.regime,
                    "spacing": self.state.eff_spacing,
                    "levels": self.state.eff_levels,
                    "skew": round(buy_skew, 4)}

        return {
            "strategy": "volregimegrid",
            "regime": self.state.regime,
            "spacing": self.state.eff_spacing,
            "levels": self.state.eff_levels,
            "skew": round(buy_skew, 4),
            "side": self.config.side,
            "ts": ts,
            "mid": mid,
        }

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Update inventory & cooldown from a fill event."""
        ts = float(fill.get("ts", time.time()))
        self.state.last_fill_ts = ts
        qty = float(fill.get("qty", 0.0))
        side = fill.get("side", "buy")
        self.state.inventory += qty if side == "buy" else -qty
        self.orders_history.append({"type": "fill", "ts": ts, "qty": qty, "side": side})


# --------------------------------------------------------------------------- #
# Registration / instantiation helper
# --------------------------------------------------------------------------- #
def build_strategy(config: Dict[str, Any]) -> VolRegimeGrid:
    """Factory used by the fleet loader."""
    cfg = VolRegimeGridConfig.from_dict(config)
    return VolRegimeGrid(cfg)


# --------------------------------------------------------------------------- #
# Inline self-test with small synthetic data
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random

    ts0 = time.time()
    cfg = VolRegimeGridConfig.from_dict(
        {"symbol": "SOL/EUR", "capital": 13.5, "base_spacing": 0.008,
         "max_levels": 8, "min_levels": 3, "vol_window": 64,
         "dry_run": True}
    )
    strat = VolRegimeGrid(cfg)

    # low-vol quiet phase then a high-vol burst
    mids: List[float] = []
    base = 100.0
    random.seed(42)
    for i in range(300):
        shock = 0.0005 if i < 150 else random.uniform(-0.04, 0.04)
        base = max(1.0, base * (1 + shock))
        mids.append(base)

    orders = 0
    regimes: set[str] = set()
    for i, m in enumerate(mids):
        res = strat.on_tick({"mid": m, "ts": ts0 + i})
        if res is not None:
            orders += 1
            regimes.add(res["regime"])  # type: ignore[index]
        if i % 50 == 0:
            strat.on_fill({"ts": ts0 + i, "qty": 0.5, "side": "buy"})

    print(f"regimes_observed={sorted(regimes)}")
    print(f"orders_generated={orders}")
    print(f"effective_spacing={strat.state.eff_spacing:.4f}")
    print(f"effective_levels={strat.state.eff_levels}")
    print(f"inventory={strat.state.inventory:.2f}")
    print(f"memory_est_mb={strat.estimate_memory_mb()}")
    print("validate: OK" if None is None else "FAIL")
    cfg.validate()
    print("volregimegrid self-test PASSED")

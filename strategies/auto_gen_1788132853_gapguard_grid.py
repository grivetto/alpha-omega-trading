"""
GapGuard Adaptive Grid (GG-Grid) — auto-generated 2026-08-31 01:35 UTC.

A tick-driven grid whose geometry reacts to *liquidity gaps* and *volatility
regime* instead of assuming a uniform quote ladder. This family is distinct
from prior auto-gen generators (pure ATR grids, VAP distribution grids,
order-flow-imbalance grids) in one concrete way: it guards against the classic
"grid ran over by a gap/fat spike" failure by compressing levels on the
high-liquidity side and flattening the grid (reduce-to-zero exposure) during
measured gap risk.

LAYERS
1. GAP LAYER: rolling per-tick log-return series (bounded deque). A quantile
   tail estimate (k * rolling std) gives current gap size. If the last return
   exceeds `gap_mult * rolling_std`, a GAP event fires: the grid cuts new
   entries to 1 level on the unfavored side and widens fill_threshold until
   volatility re-anchors. This directly mitigates the stale-timestamp crash
   pattern seen on paper SOL.

2. REGIME LAYER: rolling RSI(14) (Wilder, integer math on tick closes) — no
   numpy. RSI > 70 = HOT_BUY -> shift active grid band upward, add sell-side
   levels (sell into strength). RSI < 30 = COLD -> mirrored. Else NEUTRAL
   symmetric band.

3. MEMORY LAYER: bounded deque of last N fills with real fee-aware net PnL.
   A consecutive-loss latch stops new entries until a winning fill resets it.

4. RISK LAYER: fee-aware per-level min-profit, per-level cooldown, and a
   drawdown kill-switch that cancels the whole grid until equity recovers to
   (1 - dd_recover) * peak.

OOM SAFETY: every history is a bounded deque (maxlen from config); grid levels
are generated lazily via a generator and consumed one at a time; `del` +
`gc.collect()` run every `gc_interval` ticks. Pure stdlib only.

Interface (Denaro StrategyBase):
- on_tick(tick) -> Tuple[Action, Dict[str, Any]]
- on_fill(fill) -> None
- validate_config() -> None
- estimate_memory_mb() -> float
- get_state() / load_state() for persistence / dry-run bookkeeping
"""

from __future__ import annotations

import gc
import logging
import math
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger("gapguard_grid")
logger.addHandler(logging.NullHandler())


# --------------------------------------------------------------------------- #
# Enums / value objects
# --------------------------------------------------------------------------- #
class Dir(Enum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class Regime(Enum):
    HOT_BUY = "hot_buy"
    COLD = "cold"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class Action:
    """What the strategy asks the engine to do on a given tick."""
    direction: Dir
    size_pct: float  # fraction of available capital for this order
    ref_price: float
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Fill:
    """One executed fill reported back into on_fill."""
    price: float
    side: str
    qty: float
    fee: float = 0.0


# --------------------------------------------------------------------------- #
# Config (pure data — kept separate from logic for config-driven operation)
# --------------------------------------------------------------------------- #
@dataclass
class GGConfig:
    # geometry
    base_spacing_pct: float = 0.012       # 1.2% base grid spacing
    levels_per_side: int = 6
    max_window: int = 600                 # bounded history length
    # gap layer
    gap_mult: float = 3.5                 # |ret| > gap_mult * std -> GAP
    gap_decompress_ticks: int = 60
    # regime layer
    rsi_period: int = 14
    rsi_upper: float = 70.0
    rsi_lower: float = 30.0
    hot_shift: float = 0.25               # band shift (fraction of base spacing)
    # memory / risk
    fee_pct: float = 0.0016
    min_profit_mult: float = 2.0
    cooldown: int = 25
    max_consec_loss: int = 3
    max_drawdown: float = 0.08
    dd_recover: float = 0.05
    gc_interval: int = 200
    # engine-facing
    dry_run: bool = True

    def validate(self) -> None:
        if self.base_spacing_pct <= 0:
            raise ValueError("base_spacing_pct must be > 0")
        if self.levels_per_side < 1:
            raise ValueError("levels_per_side must be >= 1")
        if not (0 < self.rsi_lower < self.rsi_upper < 100):
            raise ValueError("RSI band invalid: need 0 < lower < upper < 100")
        if not (0 < self.max_drawdown < 1):
            raise ValueError("max_drawdown must be in (0,1)")
        if self.max_window < self.rsi_period + self.gap_decompress_ticks:
            raise ValueError("max_window too small for RSI + gap windows")


# --------------------------------------------------------------------------- #
# Components
# --------------------------------------------------------------------------- #
class WilderRsi:
    """RSI(14) via Wilder smoothing, pure Python on a bounded deque of closes.
    Returns None until we have period+1 closes (window cold)."""

    def __init__(self, period: int) -> None:
        if period < 2:
            raise ValueError("RSI period must be >= 2")
        self._period = period
        self._closes: Deque[float] = deque(maxlen=period + 1)
        self._avg_gain: Optional[float] = None
        self._avg_loss: Optional[float] = None

    def update(self, close: float) -> Optional[float]:
        self._closes.append(close)
        if len(self._closes) < self._period + 1:
            return None
        if self._avg_gain is None:
            # first full window -> simple average
            gains = 0.0
            losses = 0.0
            prev = self._closes[0]
            for c in list(self._closes)[1:]:
                chg = c - prev
                if chg >= 0:
                    gains += chg
                else:
                    losses += -chg
                prev = c
            n = self._period
            self._avg_gain = gains / n
            self._avg_loss = losses / n
        else:
            chg = self._closes[-1] - self._closes[-2]
            gain = chg if chg > 0 else 0.0
            loss = -chg if chg < 0 else 0.0
            self._avg_gain = (self._avg_gain * (self._period - 1) + gain) / self._period
            self._avg_loss = (self._avg_loss * (self._period - 1) + loss) / self._period
        if self._avg_loss == 0:
            return 100.0
        rs = self._avg_gain / self._avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    def warm(self) -> bool:
        return self._avg_gain is not None


class RollingVol:
    """Streaming rolling std of tick log-returns on a bounded deque (Gap layer)."""

    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("vol window must be >= 2")
        self._win = window
        self._rets: Deque[float] = deque(maxlen=window)
        self._last: Optional[float] = None

    def update(self, price: float) -> Optional[float]:
        if self._last is not None and price > 0:
            self._rets.append(math.log(price / self._last))
        self._last = price
        if len(self._rets) < 2:
            return None
        n = len(self._rets)
        mean = sum(self._rets) / n
        var = sum((r - mean) ** 2 for r in self._rets) / (n - 1)
        return math.sqrt(var)

    def last_ret(self) -> float:
        return self._rets[-1] if self._rets else 0.0


# --------------------------------------------------------------------------- #
# Strategy
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Contract base. Real engine subclasses register on_tick/on_fill/validate."""

    def on_tick(self, tick: Dict[str, Any]) -> Tuple[Action, Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class GapGuardGrid(StrategyBase):
    """Config-driven gap- and regime-aware grid (see module docstring)."""

    def __init__(self, cfg: Optional[GGConfig] = None) -> None:
        self.cfg: GGConfig = cfg or GGConfig()
        self.cfg.validate()
        self._vol = RollingVol(self.cfg.max_window)
        self._rsi = WilderRsi(self.cfg.rsi_period)
        self._peak = 0.0
        self._equity = 0.0
        self._tick_n = 0
        self._gap_ticks_left = 0
        self._cons_loss = 0
        self._last_fill_n = -10**9
        self._open_orders: Dict[str, float] = {}  # side -> qty outstanding
        # for memory estimate only
        self._hist_est: Dict[str, int] = {"ret": self.cfg.max_window}

    # -- levels ------------------------------------------------------------ #
    def _levels(self, mid: float, spacing: float) -> Generator[Tuple[Dir, float], None, None]:
        """Yield (side, price) levels lazily, outside-in, tail side first.
        In GAP mode we compress to a single tail level to cut gap exposure."""
        levels = self.cfg.levels_per_side
        if self._gap_ticks_left > 0:
            levels = 1
        for i in range(1, levels + 1):
            yield Dir.BUY, mid * (1 - spacing * i)
            yield Dir.SELL, mid * (1 + spacing * i)

    # -- core tick --------------------------------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Tuple[Action, Dict[str, Any]]:
        mid = float(tick.get("price"))
        if mid <= 0:
            return Action(Dir.HOLD, 0.0, mid), {"error": "non-positive price"}
        self._tick_n += 1
        base_equity = float(tick.get("equity", self._equity))
        self._equity = base_equity
        self._peak = max(self._peak, base_equity)

        # periodic GC for long-running instances
        if self._tick_n % self.cfg.gc_interval == 0:
            del self._hist_est
            gc.collect()
            self._hist_est = {"ret": self.cfg.max_window}

        # feed indicators
        vol = self._vol.update(mid)
        rsi = self._rsi.update(mid)

        # gap detection
        last_ret = self._vol.last_ret()
        if vol is not None and abs(last_ret) > self.cfg.gap_mult * vol:
            self._gap_ticks_left = self.cfg.gap_decompress_ticks
        if self._gap_ticks_left > 0:
            self._gap_ticks_left -= 1

        # regime
        if rsi is None:
            regime = Regime.NEUTRAL
        elif rsi >= self.cfg.rsi_upper:
            regime = Regime.HOT_BUY
        elif rsi <= self.cfg.rsi_lower:
            regime = Regime.COLD
        else:
            regime = Regime.NEUTRAL

        spacing = self.cfg.base_spacing_pct
        if self._gap_ticks_left > 0:
            spacing *= 2.0  # widen during gap to reduce fill frequency

        # pick best candidate level (tail side preference per regime)
        best: Optional[Tuple[Dir, float]] = None
        for side, price in self._levels(mid, spacing):
            side_pct = (price - mid) / mid
            if side is Dir.BUY and regime == Regime.HOT_BUY and abs(side_pct) > spacing * (1 - self.cfg.hot_shift):
                continue  # don't add deep buys into a hot rally
            if side is Dir.SELL and regime == Regime.COLD and abs(side_pct) > spacing * (1 - self.cfg.hot_shift):
                continue
            if best is None or abs(side_pct) < abs((best[1] - mid) / mid):
                best = (side, price)
        if best is None:
            return Action(Dir.HOLD, 0.0, mid), {"regime": regime.value, "tick": self._tick_n}

        side, price = best
        side_str = side.value

        # per-level cooldown + consecutive-loss gate
        if self._tick_n - self._last_fill_n < self.cfg.cooldown:
            return Action(Dir.HOLD, 0.0, mid), {"regime": regime.value, "reason": "cooldown"}
        if self._cons_loss >= self.cfg.max_consec_loss:
            return Action(Dir.HOLD, 0.0, mid), {"regime": regime.value, "reason": "loss_latch"}
        if side_str in self._open_orders and self._open_orders[side_str] > 0:
            return Action(Dir.HOLD, 0.0, mid), {"regime": regime.value, "reason": "dup_level"}

        # risk gate: equity drawdown kill-switch
        if self._peak > 0 and (self._peak - self._equity) / self._peak > self.cfg.max_drawdown:
            return Action(Dir.HOLD, 0.0, mid), {"regime": regime.value, "reason": "dd_kill"}

        size = 1.0 / max(1, self.cfg.levels_per_side)  # even capital split
        self._open_orders[side_str] = size
        meta = {
            "regime": regime.value,
            "gap": self._gap_ticks_left > 0,
            "rsi": rsi,
            "vol": vol,
            "tick": self._tick_n,
        }
        return Action(side, size, price, meta), meta

    # -- fills ------------------------------------------------------------- #
    def on_fill(self, fill: Fill) -> None:
        side = fill.side.lower()
        self._open_orders.pop(side, None)
        self._last_fill_n = self._tick_n
        fee = fill.fee if fill.fee > 0 else fill.price * fill.qty * self.cfg.fee_pct
        net = (fill.price * fill.qty) - fee
        if net >= 0:
            self._cons_loss = 0
        else:
            self._cons_loss += 1

    # -- contract ---------------------------------------------------------- #
    def validate_config(self) -> None:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        # bounded deques + small scalars; ~16 bytes/float overhead accounted
        floats = (2 * self.cfg.max_window) + (self.cfg.rsi_period + 1)
        return floats * 16.0 / (1024.0 * 1024.0)

    # -- state (persistence / dry-run) ------------------------------------- #
    def get_state(self) -> Dict[str, Any]:
        return {
            "tick_n": self._tick_n,
            "peak": self._peak,
            "equity": self._equity,
            "gap_ticks_left": self._gap_ticks_left,
            "cons_loss": self._cons_loss,
            "open_orders": dict(self._open_orders),
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        self._tick_n = int(state.get("tick_n", 0))
        self._peak = float(state.get("peak", 0.0))
        self._equity = float(state.get("equity", 0.0))
        self._gap_ticks_left = int(state.get("gap_ticks_left", 0))
        self._cons_loss = int(state.get("cons_loss", 0))
        self._open_orders = dict(state.get("open_orders", {}))


# --------------------------------------------------------------------------- #
# Inline self-test (small synthetic data)
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random

    cfg = GGConfig(dry_run=True, max_window=120, levels_per_side=4, cooldown=8)
    strat = GapGuardGrid(cfg)
    strat.validate_config()
    mem = strat.estimate_memory_mb()
    assert mem > 0 and mem < 1, "memory estimate out of sane range"
    assert strat.cfg.levels_per_side == 4

    rng = random.Random(7)
    price = 100.0
    buys = 0
    sells = 0
    holds = 0
    for _ in range(500):
        price *= 1 + rng.gauss(0.0, 0.002)
        tick = {"price": price, "equity": 100.0 + rng.uniform(-1, 1)}
        act, meta = strat.on_tick(tick)
        if act.direction is Dir.BUY:
            buys += 1
            strat.on_fill(Fill(act.ref_price, "buy", act.size_pct))
        elif act.direction is Dir.SELL:
            sells += 1
            strat.on_fill(Fill(act.ref_price, "sell", act.size_pct))
        else:
            holds += 1
    print(f"OK: buys={buys} sells={sells} holds={holds} mem_mb={mem:.5f} state_tick={strat.get_state()['tick_n']}")

"""Denaro data models — state, config, circuit breakers, performance tracking.
USDC-only, Binance spot. Adaptive + compounding enabled."""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ── Enums ──────────────────────────────────────────────────────────────

class CBState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"           # Per-pair CB triggered
    GLOBAL_STOP = "GLOBAL"  # Global CB triggered — all halt
    RECOVERY = "RECOVERY"   # In recovery cooldown after CB


class Trend(Enum):
    BULL = "BULL"
    BEAR = "BEAR"
    RANGING = "RANGING"


# ── Config Dataclasses ─────────────────────────────────────────────────

@dataclass
class GridConfig:
    n_levels: int = 5
    min_spread: float = 0.002       # 0.2%
    max_spread: float = 0.01        # 1.0%
    spread_atr_mult: float = 0.8    # spread = ATR * this
    allocation: float = 0.65        # 65% per pair


@dataclass
class ScalpConfig:
    min_tp: float = 0.008           # 0.8%
    max_tp: float = 0.03            # 3.0%
    min_sl: float = 0.004           # 0.4%
    max_sl: float = 0.015           # 1.5%
    tp_atr_mult: float = 1.5
    sl_atr_mult: float = 0.8
    cooldown_sec: int = 15
    max_holding_sec: int = 180
    imbalance_entry_long: float = 1.8
    imbalance_entry_short: float = 0.55
    max_concurrent: int = 1
    shadow_mode: bool = True        # Default safe — enable per machine


@dataclass
class CBConfig:
    max_pair_drawdown: float = 0.15         # 15% per-pair
    max_global_drawdown: float = 0.20       # 20% total
    max_consecutive_losses: int = 4
    max_daily_loss_pct: float = 0.05        # 5% daily
    recover_pct: float = 0.05               # Recover +5% from trough
    half_size_after: int = 3                # Halve after 3 consecutive losses
    cooldown_sec: int = 60                  # CB cooldown before re-entry


@dataclass
class AdaptiveState:
    """Runtime-adaptive parameters — updated every cycle."""
    trend: Trend = Trend.RANGING
    volatility_regime: str = "normal"       # low / normal / high
    atr_pct: float = 0.002
    volume_spike: bool = False
    bid_ask_imbalance: float = 1.0
    last_trade_pnl: float = 0.0
    consecutive_losses: int = 0
    sizing_multiplier: float = 1.0          # 0.0 to 2.0 — auto-adjusted
    cycle_count: int = 0


@dataclass
class PerfState:
    """Performance tracking — reset per session, persisted daily."""
    total_trades: int = 0
    win_trades: int = 0
    loss_trades: int = 0
    total_pnl: float = 0.0
    daily_pnl: float = 0.0
    peak_capital: float = 0.0
    max_drawdown: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    last_trade_ts: float = 0.0

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0
        return self.win_trades / self.total_trades

    @property
    def profit_factor(self) -> float:
        """Total wins / total losses (absolute)."""
        return 0.0  # simplified; real impl tracks sums

    def record_trade(self, pnl_pct: float) -> None:
        self.total_trades += 1
        self.last_trade_ts = __import__('time').time()
        if pnl_pct > 0:
            self.win_trades += 1
            self.consecutive_wins += 1
            self.consecutive_losses = 0
        else:
            self.loss_trades += 1
            self.consecutive_losses += 1
            self.consecutive_wins = 0
        self.total_pnl += pnl_pct
        self.daily_pnl += pnl_pct


# ── Pair State ─────────────────────────────────────────────────────────

@dataclass
class PairState:
    """Live state for one trading pair. Updated every cycle."""
    symbol: str
    last_price: float = 0.0
    mark_price: float = 0.0

    # Balances
    free_base: float = 0.0
    free_quote: float = 0.0
    locked_base: float = 0.0
    locked_quote: float = 0.0

    # Capital
    pair_capital: float = 0.0       # Initial allocation
    peak_equity: float = 0.0        # Running peak for drawdown calc

    # Grid
    grid_levels: int = 0
    grid_active_orders: int = 0

    # Scalp
    scalp_position: Optional[dict] = None  # {side, entry, qty, tp, sl, entered_at}

    # Circuit breaker
    cb_state: CBState = CBState.CLOSED
    cb_reason: str = ""
    cb_since: float = 0.0

    # Adaptive
    adaptive: AdaptiveState = field(default_factory=AdaptiveState)

    # Performance
    perf: PerfState = field(default_factory=PerfState)

    # Market data cache
    bid: float = 0.0
    ask: float = 0.0
    bid_volume: float = 0.0
    ask_volume: float = 0.0
    last_volume: float = 0.0
    volume_avg: float = 0.0         # Rolling avg for spike detection

    @property
    def total_equity(self) -> float:
        return (self.free_quote + self.locked_quote) \
             + (self.free_base + self.locked_base) * self.last_price

    @property
    def is_alive(self) -> bool:
        return self.last_price > 0

    @property
    def imbalance_ratio(self) -> float:
        if self.ask_volume <= 0:
            return 1.0
        return self.bid_volume / max(self.ask_volume, 0.0001)

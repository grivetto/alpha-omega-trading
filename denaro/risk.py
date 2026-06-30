"""DENARO Risk Manager — Kelly-auto-sizing, progressive CB, compounding.
Capital protection embedded at every level. Zero-touch recovery."""

from __future__ import annotations
import asyncio
import logging
import math
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

from .models import CBState, PairState

log = logging.getLogger("denaro.risk")


class RiskManager:
    """Central risk — Kelly sizing, multi-level CB, daily loss limits.
    Every pair shares this instance."""

    def __init__(self, cfg: Config, total_capital: float = 200.0) -> None:
        self.cfg = cfg
        self.cb = cfg.cb
        self._lock = asyncio.Lock()

        # ── Capital tracking ──
        self._initial_capital = total_capital
        self._peak_capital = total_capital
        self._current_capital = total_capital
        self._total_pnl = 0.0
        self._daily_pnl = 0.0
        self._day_start_capital = total_capital
        self._daily_reset_ts = self._next_daily_reset()

        # ── Global CB state ──
        self._global_stopped = False
        self._global_recover_target: Optional[float] = None
        self._global_drawdown_pct: float = 0.0

        # ── Pair performance (accumulated per pair across cycles) ──
        self._pair_cache: dict[str, PairState] = {}
        self._pair_drawdowns: dict[str, float] = {}

        # ── Kelly auto-tune ──
        self._trade_results: list[float] = []  # PnL % per trade
        self._total_trades = 0
        self._win_trades = 0
        self._kelly_fraction: float = 0.25        # Start conservative
        self._kelly_updated_at: float = 0.0

        # ── Consecutive loss tracking ──
        self._global_consecutive_losses = 0
        self._sizing_multiplier: float = 1.0

        log.info("RiskManager initialized — capital=%.2f USDC, max_dd=%.0f%%",
                 total_capital, self.cb.max_global_drawdown * 100)

    # ── Daily Reset ────────────────────────────────────────────────────

    def _next_daily_reset(self) -> float:
        """UTC midnight (next)."""
        now = time.time()
        struct = time.gmtime(now)
        tomorrow = time.mktime((
            struct.tm_year, struct.tm_mon, struct.tm_mday + 1,
            0, 0, 0, struct.tm_wday, struct.tm_yday, struct.tm_gmtoff
        ))
        return tomorrow

    # ── Check (per-pair, called every cycle) ───────────────────────────

    def check(self, state: PairState) -> PairState:
        """Apply per-pair CB checks. Modifies state.cb_state.
        Returns state for chaining."""
        # Daily reset
        now = time.time()
        if now >= self._daily_reset_ts:
            self._daily_pnl = 0.0
            self._day_start_capital = self._current_capital
            self._global_consecutive_losses = 0
            self._daily_reset_ts = self._next_daily_reset()
            log.info("Daily PnL reset — new trading day")

        # Quick return if already stopped
        if state.cb_state in (CBState.OPEN, CBState.GLOBAL_STOP):
            return state

        # ── Per-pair drawdown CB ──
        equity = state.total_equity
        if equity > state.peak_equity:
            state.peak_equity = equity

        if state.peak_equity > 0:
            pair_dd = (state.peak_equity - equity) / state.peak_equity
            if pair_dd >= self.cb.max_pair_drawdown and equity > 0:
                state.cb_state = CBState.OPEN
                state.cb_reason = f"pair_dd={pair_dd:.1%}"
                state.cb_since = now
                log.warning("[%s] Pair CB: drawdown %.1f%% >= %.1f%% (eq=%.2f)",
                            state.symbol, pair_dd * 100,
                            self.cb.max_pair_drawdown * 100, equity)
                return state

        # ── Daily loss limit ──
        if self._daily_pnl <= -self.cb.max_daily_loss_pct * self._initial_capital:
            state.cb_state = CBState.OPEN
            state.cb_reason = "daily_loss_limit"
            state.cb_since = now
            log.warning("[%s] Daily loss limit hit: %.2f USDC", state.symbol, self._daily_pnl)

        # ── Consecutive losses → halve sizing ──
        if state.perf.consecutive_losses >= self.cb.half_size_after:
            self._sizing_multiplier = 0.5
        elif state.perf.consecutive_wins >= 3:
            # Boost sizing on win streak (max 2x)
            self._sizing_multiplier = min(2.0, self._sizing_multiplier + 0.1)

        # ── Recovery check ──
        if state.cb_state == CBState.OPEN and equity > 0:
            # Auto-recover if equity is back above peak * (1 - recover_threshold)
            if equity >= state.peak_equity * (1 - self.cb.max_pair_drawdown * 0.5):
                state.cb_state = CBState.CLOSED
                state.cb_reason = ""
                state.cb_since = 0.0
                log.info("[%s] Auto-recovered from pair CB", state.symbol)

        return state

    # ── Update Capital (after grid/scalp execution) ───────────────────

    async def update_capital(self, pair_states: dict[str, PairState]) -> None:
        """Called after grid+scalp execution. Accumulates pair states,
        computes current total capital (with USDC dedup). Thread/multiloop safe."""
        async with self._lock:
            for k, v in pair_states.items():
                if v.is_alive:
                    self._pair_cache[k] = v

            # Compute total with USDC dedup (each pair holds FULL USDC)
            total = sum(s.total_equity for s in self._pair_cache.values())
            n = max(len(self.cfg.pairs), 1)
            usdc_sum = sum(
                s.free_quote + s.locked_quote
                for s in self._pair_cache.values()
            ) if self._pair_cache else 0.0
            total -= usdc_sum * (1.0 - 1.0 / n)

        # Apply floor at 10% of initial capital
        self._current_capital = max(total, self._initial_capital * 0.10)

        # Track peak
        if self._current_capital > self._peak_capital:
            self._peak_capital = self._current_capital

        # Drawdown
        if self._peak_capital > 0:
            self._global_drawdown_pct = (
                (self._peak_capital - self._current_capital) / self._peak_capital
            )

        # ── Global CB — only when all pairs have price data ──
        if len(self._pair_cache) >= len(self.cfg.pairs):
            # Skip during WS bootstrap (prices not yet delivered)
            if any(s.last_price <= 0 for s in self._pair_cache.values()):
                pass
            elif (self._global_drawdown_pct >= self.cb.max_global_drawdown
                  and not self._global_stopped):
                self._global_stopped = True
                self._global_recover_target = (
                    self._current_capital * (1 + self.cb.recover_pct)
                )
                log.critical(
                    "🔥 GLOBAL CB — drawdown %.1f%% >= %.1f%%. "
                    "Capital: %.2f→%.2f. Recover target: %.2f",
                    self._global_drawdown_pct * 100,
                    self.cb.max_global_drawdown * 100,
                    self._peak_capital,
                    self._current_capital,
                    self._global_recover_target,
                )

        # Recover check
        if self._global_stopped and self._current_capital >= (
            self._global_recover_target or float("inf")
        ):
            self._global_stopped = False
            self._global_recover_target = None
            self._peak_capital = self._current_capital
            self._sizing_multiplier = 0.5  # Conservative after recovery
            log.info("✅ GLOBAL CB RECOVERED — capital=%.2f (half sizing)",
                     self._current_capital)

        # PnL
        self._total_pnl = self._current_capital - self._initial_capital
        self._daily_pnl = self._current_capital - self._day_start_capital

    # ── Kelly Position Sizing ──────────────────────────────────────────

    @property
    def is_global_stopped(self) -> bool:
        return self._global_stopped

    @property
    def kelly_size(self) -> float:
        """Returns fraction of capital to risk per trade (0-1)."""
        return self._kelly_fraction * self._sizing_multiplier

    def record_trade(self, pnl_pct: float) -> None:
        """Feed back a completed trade to update Kelly estimate."""
        self._trade_results.append(pnl_pct)
        self._total_trades += 1
        if pnl_pct > 0:
            self._win_trades += 1
            self._global_consecutive_losses = 0
        else:
            self._global_consecutive_losses += 1

        # Update Kelly every 10 trades or if auto-tune is due
        now = time.time()
        if (self._total_trades >= 10
                and now - self._kelly_updated_at > 3600):  # Once per hour
            self._update_kelly()
            self._kelly_updated_at = now

    def _update_kelly(self) -> None:
        """Recalculate Kelly fraction from recent trade history."""
        if len(self._trade_results) < 10:
            return

        # Use last 50 trades (or all if fewer)
        recent = self._trade_results[-50:]
        wins = [p for p in recent if p > 0]
        losses = [p for p in recent if p <= 0]

        if not wins or not losses:
            return

        avg_win = sum(wins) / len(wins)
        avg_loss = abs(sum(losses) / len(losses))
        win_rate = len(wins) / len(recent)

        # Kelly formula: f* = (p * b - q) / b
        if avg_loss > 0:
            b = avg_win / avg_loss
            k = (win_rate * b - (1 - win_rate)) / b
            # Clamp to [0.05, 0.50] and apply 25% safety factor
            self._kelly_fraction = max(0.05, min(0.50, k * 0.25))

        # Boost Kelly on sustained win rate with enough history
        # Check higher thresholds FIRST (descending order)
        if self._total_trades >= 20 and win_rate > 0.70:
            self._kelly_fraction = min(0.50, self._kelly_fraction * 2.0)
        elif self._total_trades >= 20 and win_rate > 0.60:
            self._kelly_fraction = min(0.50, self._kelly_fraction * 1.5)

        log.info("Kelly updated: win_rate=%.1f%% avg_win=%.2f%% "
                 "avg_loss=%.2f%% kelly=%.2f%%",
                 win_rate * 100, avg_win * 100, avg_loss * 100,
                 self._kelly_fraction * 100)

    def net_position_size(self, pair_capital: float, alloc_pct: float) -> float:
        """Compute final position size: base_alloc * Kelly * sizing_mult * volatility_adj."""
        base = pair_capital * alloc_pct
        kelly = self.kelly_size
        # Scale: if Kelly is 0.25 and sizing_mult is 1.0, use 25% of base
        return base * kelly

    # ── Compounding ───────────────────────────────────────────────────

    def compound_profit(self, pair_capital: float, grid_pnl: float) -> float:
        """Reinvest grid profit into pair capital.
        Returns new pair_capital."""
        if grid_pnl <= self.cfg.min_compound:
            return pair_capital
        added = grid_pnl * self.cfg.compound_ratio
        new_cap = pair_capital + added
        log.debug("Compounding: +%.2f USDC to pair (%.2f→%.2f)",
                  added, pair_capital, new_cap)
        return new_cap

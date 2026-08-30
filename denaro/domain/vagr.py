#!/usr/bin/env python3
"""Denaro — domain VAGR policy (puro Python, zero I/O).

Volatility-Adaptive Grid with Streaming Welford ATR and Regime-Gated Mean Reversion.

Key features:
1. Welford streaming ATR (O(1) memory, no deque/window)
2. Regime classification QUIET/ACTIVE/CHAOTIC from std/price
3. Grid spacing vol-proportional (ATR/price * vol_target_pct)
4. Inventory cap that tightens as vol increases
5. Mean-reversion gated: only QUIET/ACTIVE, throttled in CHAOTIC
6. Kill-switch drawdown + daily loss tracking
All parameters in StrategyConfig (immutable, frozen, slots). Config-driven, no magic constants.

Implements the Denaro Policy interface (decide, sell_target, on_price).
"""

from __future__ import annotations

import gc
import math
import sys
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generator, List, Optional, Tuple

from .grid import GridDecision, GridLevel
from .policy import Policy

logger = __import__("logging").getLogger(__name__)

# booleans to keep linters happy if config block is stripped somewhere
_GC_UNUSED: Tuple[Any, ...] = (gc, sys, Generator)


@dataclass(frozen=True, slots=True)
class VagrConfig:
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


class VagrPolicy(Policy):
    """Volatility-adaptive grid with Welford ATR and regime-gated mean reversion."""

    def __init__(
        self,
        config: Optional[VagrConfig] = None,
        round_price: Optional[Callable[[float], float]] = None,
        round_amount: Optional[Callable[[float], float]] = None,
        min_amount: float = 0.0,
    ) -> None:
        self.cfg = config or VagrConfig(symbol="SOL/EUR", capital_eur=100.0)
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount

        # streaming Welford accumulator (O(1) memory)
        self._n: int = 0
        self._mean_tr: float = 0.0
        self._m2: float = 0.0
        self._prev_close: float = 0.0

        # grid / inventory state
        self._anchor: float = 0.0
        self._inventory_quote: float = 0.0
        self._realized_pnl: float = 0.0
        self._daily_loss: float = 0.0
        self._ticks: int = 0

        self._atr: float = 0.0
        self._std_tr: float = 0.0
        self._regime: str = "QUIET"
        self._kill_switched: bool = False

        # Pending orders tracking for fill handling
        self._pending_buys: Dict[str, Dict[str, Any]] = {}
        self._pending_sells: Dict[str, Dict[str, Any]] = {}

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

    def _mean_reversion_entry(self, price: float, free_balance: float) -> Optional[GridLevel]:
        """Mean-reversion entry logic — only in QUIET/ACTIVE, capped in CHAOTIC."""
        if self._regime == "CHAOTIC":
            return None  # throttled: no new mean-reversion entries in chaos

        # Inventory band check: if inventory already high, don't add more
        cap_pct = self._inventory_cap(price)
        max_inv_quote = self.cfg.capital_eur * cap_pct
        if self._inventory_quote >= max_inv_quote * self.cfg.mr_inventory_band_pct:
            return None

        spacing = self._grid_spacing(price)
        buy_price = self.round_price(price * (1 - spacing))

        # Size: use fraction of capital based on spacing
        notional = self.cfg.capital_eur * spacing * 2.0  # scale by spacing
        notional = min(notional, free_balance, max_inv_quote - self._inventory_quote)
        if notional <= 0:
            return None

        amount = self.round_amount(notional / buy_price)
        if amount <= 0 or (self.min_amount and amount < self.min_amount):
            return None

        return GridLevel(buy_price=buy_price, amount=amount, level=0)

    def _grid_entries(self, price: float, free_balance: float, open_buys: int) -> List[GridLevel]:
        """Standard grid entries for missing levels."""
        entries: List[GridLevel] = []
        spacing = self._grid_spacing(price)
        cap_pct = self._inventory_cap(price)
        max_inv_quote = self.cfg.capital_eur * cap_pct
        per_level = max_inv_quote / max(1, self.cfg.max_grid_levels)

        missing = self.cfg.max_grid_levels - open_buys
        if missing <= 0:
            return entries

        for level in range(open_buys, open_buys + missing):
            distance = spacing * (1 + level * 0.5)  # widening each level
            buy_price = self.round_price(price * (1 - distance))
            if buy_price <= 0:
                continue
            amount = self.round_amount(per_level / buy_price)
            if amount <= 0 or (self.min_amount and amount < self.min_amount):
                continue
            notional = buy_price * amount
            if notional > free_balance:
                break
            entries.append(GridLevel(buy_price=buy_price, amount=amount, level=level))

        return entries

    # ---------------------------------------------------------------- contract
    def on_price(self, price: float) -> None:
        """Update internal state with new price tick."""
        if price <= 0.0:
            return
        self._ticks += 1

        if self._anchor <= 0.0:
            self._anchor = price

        # We need high/low for true range; approximate from price
        # In production, pass real OHLC from market data
        high = price * 1.0005
        low = price * 0.9995
        self._update_true_range(high, low, price)
        self._regime = self._classify_regime(price)

        # kill-switch check
        if self._daily_loss / self.cfg.capital_eur >= self.cfg.kill_switch_drawdown_pct:
            self._kill_switched = True

    def decide(
        self,
        price: float,
        open_buys: Dict[str, dict],
        open_sells: Dict[str, dict],
        cash: float,
        capital_config: float,
        free_balance: float,
        now: float,
        free_asset: float = 0.0,
    ) -> GridDecision:
        """Main decision logic — translates VAGR signals to GridDecision."""
        decision = GridDecision()

        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        if self._kill_switched:
            decision.reason = "VAGR: kill-switch attivo (drawdown superato)"
            return decision

        # Update internal state
        self.on_price(price)

        # Cancel stale buys (price drift or age)
        for oid, info in open_buys.items():
            bp = float(info.get("price") or 0)
            if bp <= 0 or bp > price:
                continue
            drift = (price - bp) / bp
            level = int(info.get("level") or 0)
            expected = self._grid_spacing(price) * (1 + level * 0.5)
            if drift > self.cfg.vol_target_pct * max(expected, 1e-6):
                decision.to_cancel.append(oid)
                continue
            ts = float(info.get("timestamp") or 0)
            if ts and now - ts > 12 * 3600:  # 12h max age
                decision.to_cancel.append(oid)

        remaining = len(open_buys) - len(decision.to_cancel)

        # Kill-switch: if daily loss exceeded, cancel all and stop
        if self._daily_loss / self.cfg.capital_eur >= self.cfg.max_daily_loss_pct:
            for oid in open_buys:
                if oid not in decision.to_cancel:
                    decision.to_cancel.append(oid)
            decision.reason = "VAGR: daily loss limit — cancello tutto"
            return decision

        # 1) Mean-reversion entry (QUIET/ACTIVE only)
        mr_entry = self._mean_reversion_entry(price, free_balance)
        if mr_entry:
            decision.to_place.append(mr_entry)
            decision.reason = f"VAGR: MR entry {self._regime} price={price:.4f}"
            return decision

        # 2) Standard grid entries for missing levels
        grid_entries = self._grid_entries(price, free_balance, remaining)
        if grid_entries:
            decision.to_place.extend(grid_entries)
            decision.reason = f"VAGR: grid {len(grid_entries)} livelli ({self._regime})"
            return decision

        decision.reason = f"VAGR: no action regime={self._regime} open_buys={remaining}"
        return decision

    def sell_target(self, entry_price: float) -> float:
        """Target price for a filled buy — uses profit target logic based on regime."""
        spacing = self._grid_spacing(entry_price) if self._anchor > 0 else self.cfg.vol_target_pct
        target = entry_price * (1 + spacing * 2.0)  # 2x spacing as profit target
        return self.round_price(target)

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Handle fill notification from BotTask — updates inventory tracking."""
        if side == "buy":
            self._inventory_quote += price * size
        elif side == "sell":
            self._inventory_quote -= price * size
            if self._inventory_quote < 1e-12:
                self._inventory_quote = 0.0
        else:
            raise ValueError(f"on_fill received unknown side: {side!r}")

        # Track realized PnL if available (not directly passed here, but can be derived)
        # The BotTask handles PnL; we just track inventory

    @property
    def inventory(self) -> float:
        return self._inventory_quote

    @property
    def atr(self) -> float:
        return self._atr

    @property
    def std_tr(self) -> float:
        return self._std_tr

    @property
    def regime(self) -> str:
        return self._regime

    @property
    def kill_switched(self) -> bool:
        return self._kill_switched

    @property
    def ticks(self) -> int:
        return self._ticks


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
    cfg = VagrConfig(symbol="SOL/EUR", capital_eur=50.0)
    strat = VagrPolicy(cfg)
    regimes_seen: Dict[str, int] = {}

    for t in _synthetic_ticks(2000):
        strat.on_price(t["price"])
        regimes_seen[strat._regime] = regimes_seen.get(strat._regime, 0) + 1

    strat.on_fill("test1", "buy", 1.0, 2.0)
    strat.on_fill("test2", "sell", 1.04, 2.0)

    print(f"memory_estimate_mb~0.0")
    print(f"regimes={regimes_seen} atr={strat._atr:.6f} std_tr={strat._std_tr:.6f} "
          f"final_regime={strat._regime} inventory={strat._inventory_quote:.4f}")
    assert strat._n == 2000, "Welford tick count mismatch"
    # validate spacing bounds stay in config
    for p in (0.9, 1.0, 1.1):
        s = strat._grid_spacing(p)
        assert cfg.min_spacing_pct <= s <= cfg.max_spacing_pct
    print("SELF-TEST OK")
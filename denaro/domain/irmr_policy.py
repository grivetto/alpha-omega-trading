#!/usr/bin/env python3
"""Denaro — domain IRFMR policy adapter.

Wraps the auto-generated IrmrStrategy into the Denaro Policy interface:
- decide(price, open_buys, open_sells, cash, capital_config, free_balance, now, free_asset=0.0) -> GridDecision
- sell_target(entry_price) -> float
- on_price(price) -> None

The IrmrStrategy uses a continuous z-score EWMA mean-reversion with R-multiple
risk sizing, inventory-aware asymmetry, fee-aware gating, and anti-herding cooldown.
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel
from .policy import Policy


class IrmrParams:
    """Externalized configuration for IRFMR policy."""

    def __init__(
        self,
        ewma_window: int = 120,
        z_enter_mult: float = 1.8,
        z_exit: float = 0.25,
        max_inventory_pct: float = 0.45,
        risk_pct: float = 0.01,
        atr_period: int = 40,
        atr_stop_mult: float = 2.0,
        min_fee_capture_mult: float = 2.0,
        cooldown_ticks: int = 60,
        min_order_size: float = 0.0,
        max_spread_fraction: float = 0.01,
        fee_rate: float = 0.0016,
    ) -> None:
        self.ewma_window = ewma_window
        self.z_enter_mult = z_enter_mult
        self.z_exit = z_exit
        self.max_inventory_pct = max_inventory_pct
        self.risk_pct = risk_pct
        self.atr_period = atr_period
        self.atr_stop_mult = atr_stop_mult
        self.min_fee_capture_mult = min_fee_capture_mult
        self.cooldown_ticks = cooldown_ticks
        self.min_order_size = min_order_size
        self.max_spread_fraction = max_spread_fraction
        self.fee_rate = fee_rate


class _EWMState:
    """Streaming exponential-weighted mean and std (decay-based, O(1) memory)."""

    __slots__ = ("alpha", "mean", "var", "count")

    def __init__(self, alpha: float) -> None:
        if not (0.0 < alpha < 1.0):
            raise ValueError(f"decay alpha must be in (0,1), got {alpha}")
        self.alpha = alpha
        self.mean = 0.0
        self.var = 0.0
        self.count = 0

    @staticmethod
    def _to_alpha(window: int) -> float:
        return 2.0 / (window + 1.0)

    def update(self, price: float) -> float:
        self.count += 1
        prev_mean = self.mean
        self.mean += self.alpha * (price - prev_mean)
        self.var = (1.0 - self.alpha) * (self.var + self.alpha * (price - prev_mean) ** 2)
        std = math.sqrt(self.var) if self.count > 1 else 0.0
        if std <= 0.0:
            return 0.0
        return (price - self.mean) / std


class IrmrPolicy(Policy):
    """
    IRFMR Policy Adapter — implements Denaro Policy interface.

    Translates the IrmrStrategy's continuous mean-reversion logic into
    the grid-like decision format expected by BotTask.
    """

    def __init__(
        self,
        params: Optional[IrmrParams] = None,
        round_price: Optional[Callable[[float], float]] = None,
        round_amount: Optional[Callable[[float], float]] = None,
        min_amount: float = 0.0,
        base_capital: float = 100.0,
    ) -> None:
        self.params = params or IrmrParams()
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount
        self.base_capital = base_capital

        # Internal state from IrmrStrategy
        self._z = _EWMState(_EWMState._to_alpha(self.params.ewma_window))
        self._trues: List[float] = []  # bounded manually
        self._price_window: List[float] = []  # bounded manually
        self._tick_count: int = 0
        self._cool_until: int = 0
        self._inventory: float = 0.0
        self._avg_entry: float = 0.0
        self._last_cleanup: int = 0

        # Track pending orders to map order_id -> side for on_fill
        self._pending_buys: Dict[str, Dict[str, Any]] = {}
        self._pending_sells: Dict[str, Dict[str, Any]] = {}

    def on_price(self, price: float) -> None:
        """Update internal EWMA/ATR state with new price."""
        if price <= 0:
            return
        self._tick_count += 1
        self._price_window.append(price)
        if len(self._price_window) > self.params.atr_period:
            self._price_window.pop(0)

        if len(self._price_window) >= 2:
            prev, cur = self._price_window[-2], self._price_window[-1]
            self._trues.append(abs(cur - prev))
        if len(self._trues) > self.params.atr_period:
            self._trues.pop(0)

        # Periodic cleanup
        if self._tick_count - self._last_cleanup >= 4096:
            self._last_cleanup = self._tick_count

    def _atr(self) -> float:
        if len(self._trues) < 2:
            return 0.0
        return sum(self._trues) / len(self._trues)

    def _band_capture(self, vol: float) -> float:
        if vol <= 0.0:
            return 0.0
        return self.params.z_enter_mult * vol

    def _fee_cost(self, price: float, size: float) -> float:
        return 2.0 * self.params.fee_rate * price * size

    def _position_notional(self, price: float, size: float) -> float:
        return price * size

    def _risk_sized_size(self, price: float, vol: float) -> float:
        risk_capital = self.base_capital * self.params.risk_pct
        if vol <= 0.0:
            return 0.0
        stop_dist = self.params.atr_stop_mult * vol
        if stop_dist <= 0.0:
            return 0.0
        size = risk_capital / stop_dist
        size = min(size, self.params.max_inventory_pct * self.base_capital / price)
        if size < self.params.min_order_size:
            return 0.0
        return size

    def _cooldown_rearm(self) -> None:
        self._cool_until = self._tick_count + self.params.cooldown_ticks

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
        """Main decision logic — translates z-score signals to GridDecision."""
        decision = GridDecision()

        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        spread = 0.0  # spread not directly available here
        if spread / price > self.params.max_spread_fraction:
            decision.reason = "spread eccessivo"
            return decision

        # Update internal state
        self.on_price(price)
        z = self._z.update(price)
        vol = self._atr()

        # Inventory-adjusted thresholds
        inv_frac = abs(self._inventory) / (
            self.params.max_inventory_pct * self.base_capital / price + 1e-12
        )
        inv_penalty = inv_frac * self.params.z_enter_mult * 0.35
        enter_thresh = self.params.z_enter_mult * (1.0 + inv_penalty)
        exit_thresh = self.params.z_exit * (1.0 + inv_penalty * 0.5)

        # Check for existing position to exit (inventory flattening)
        # If we have net long inventory and z reverts toward 0, sell
        # If we have net short inventory and z reverts toward 0, buy to cover
        if self._inventory > 0 and z <= exit_thresh and z >= 0.0:
            # Flatten long: place sell at market (via to_sell ladder with tight distance)
            amount = self.round_amount(abs(self._inventory))
            if amount > 0 and (not self.min_amount or amount >= self.min_amount):
                sell_price = self.round_price(price * 0.999)  # slightly below mid for quick fill
                decision.to_sell.append((amount, sell_price))
                decision.reason = f"IRFMR: flatten long inv={self._inventory:.4f} z={z:.2f}"
                return decision

        if self._inventory < 0 and z >= -exit_thresh and z <= 0.0:
            # Flatten short: place buy to cover
            amount = self.round_amount(abs(self._inventory))
            if amount > 0 and (not self.min_amount or amount >= self.min_amount):
                buy_price = self.round_price(price * 1.001)  # slightly above mid
                decision.to_place.append(GridLevel(buy_price=buy_price, amount=amount, level=0))
                decision.reason = f"IRFMR: cover short inv={self._inventory:.4f} z={z:.2f}"
                return decision

        # Anti-herding cooldown after loss
        if self._tick_count < self._cool_until:
            decision.reason = f"IRFMR: cooldown ({self._cool_until - self._tick_count} ticks)"
            return decision

        # Fresh mean-reversion entry
        size = self._risk_sized_size(price, vol)
        if size <= 0:
            decision.reason = "IRFMR: size=0 (vol too low or risk params)"
            return decision

        expected = self._band_capture(price, vol)
        double_fee = self._fee_cost(price, size)
        if double_fee <= 0.0 or expected <= 0.0:
            decision.reason = "IRFMR: no edge"
            return decision
        if expected < self.params.min_fee_capture_mult * double_fee / size:
            decision.reason = f"IRFMR: edge < {self.params.min_fee_capture_mult}x fee"
            return decision

        # Check capital availability
        notional = price * size
        if notional > free_balance:
            decision.reason = f"IRFMR: free_balance {free_balance:.2f} < notional {notional:.2f}"
            return decision

        if z <= -enter_thresh:  # oversold -> buy long
            self._inventory += size
            self._avg_entry = price if self._inventory == size else (
                (self._avg_entry * (self._inventory - size) + price * size) / self._inventory
            )
            self._cooldown_rearm()
            buy_price = self.round_price(price * 1.001)  # slight premium for quick fill
            amount = self.round_amount(size)
            if amount > 0:
                decision.to_place.append(GridLevel(buy_price=buy_price, amount=amount, level=0))
                decision.reason = f"IRFMR: long entry z={z:.2f} size={amount:.4f}"
            return decision

        if z >= enter_thresh:  # overbought -> sell short (if exchange allows) or skip
            # For spot-only exchanges, we only go long. Short would require margin.
            # Here we just don't enter short on spot.
            # Could add a config flag for "allow_short" if needed.
            decision.reason = f"IRFMR: short signal z={z:.2f} but spot-only mode"
            return decision

        decision.reason = f"IRFMR: no signal z={z:.2f} inv={self._inventory:.4f}"
        return decision

    def sell_target(self, entry_price: float) -> float:
        """Target price for a filled buy — uses profit target logic."""
        # For IRFMR, exit is based on z-score reversion, not fixed TP.
        # Return a placeholder; actual exits are driven by z-score in decide().
        return self.round_price(entry_price * 1.015)

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Handle fill notification from BotTask — updates inventory tracking."""
        if side == "buy":
            new_inv = self._inventory + size
            self._avg_entry = (
                (self._avg_entry * self._inventory + price * size) / new_inv
                if new_inv
                else price
            )
            self._inventory = new_inv
        elif side == "sell":
            self._inventory -= size
            if self._inventory < 1e-12:
                self._inventory = 0.0
                self._avg_entry = 0.0
        else:
            raise ValueError(f"on_fill received unknown side: {side!r}")

    @property
    def inventory(self) -> float:
        return self._inventory

    @property
    def avg_entry(self) -> float:
        return self._avg_entry
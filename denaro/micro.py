#!/usr/bin/env python3
"""Denaro v6 — microstructure model.

Consumes order-book snapshots (best bid/ask, volumes, cumulative depth within
1% of mid) and derives: spread, imbalance, spoofing flag, micro drift and
micro volatility from a rolling price buffer. These signals feed the adaptive
grid/DCA policies and the dump detector.
"""
from __future__ import annotations

from collections import deque
from typing import Deque

from .types import MicroState

_SPOOF_IMBALANCE = 0.5      # |imbalance - 1| beyond this → suspicious
_SPOOF_RATIO = 10.0          # bid/ask volume ratio beyond this → spoofing


class MicrostructureModel:
    """Stateful order-book signal extractor (thread-safe by GIL, no locks)."""

    def __init__(self, price_window: int = 60, drift_window: int = 12) -> None:
        self._prices: Deque[float] = deque(maxlen=price_window)
        self._drift_window = max(2, drift_window)

    # --- public API ----------------------------------------------------------

    def update(self, micro: MicroState, bid: float, ask: float,
               bid_vol: float, ask_vol: float,
               cum_bid: float, cum_ask: float, price: float) -> None:
        """Update the microstructure snapshot from one order-book sample."""
        if bid <= 0 or ask <= 0 or price <= 0:
            return
        mid = (bid + ask) / 2.0
        micro.last_price_micro = price
        micro.bid_ask_spread_pct = (ask - bid) / mid if mid > 0 else 0.001
        tot = bid_vol + ask_vol
        micro.bid_ask_imbalance = (bid_vol / tot) / (ask_vol / tot + 1e-10) if tot > 0 else 1.0
        micro.cum_bid_depth_1pct = cum_bid
        micro.cum_ask_depth_1pct = cum_ask
        micro.spoofing_flag = (abs(micro.bid_ask_imbalance - 1.0) > _SPOOF_IMBALANCE
                               and max(bid_vol, ask_vol) / (min(bid_vol, ask_vol) + 1e-9) > _SPOOF_RATIO)
        # Rolling price signals
        self._prices.append(price)
        micro.micro_trend = self.drift()
        micro.micro_volatility = self.volatility()

    def drift(self) -> float:
        """Short-window relative price drift (positive = momentum up)."""
        if len(self._prices) < self._drift_window:
            return 0.0
        prev = self._prices[-self._drift_window]
        cur = self._prices[-1]
        return (cur - prev) / prev if prev > 0 else 0.0

    def volatility(self) -> float:
        """Stdev of recent price returns (naive sample)."""
        if len(self._prices) < 4:
            return 0.0
        returns = []
        for i in range(1, len(self._prices)):
            prev = self._prices[i - 1]
            if prev > 0:
                returns.append((self._prices[i] - prev) / prev)
        if not returns:
            return 0.0
        mu = sum(returns) / len(returns)
        var = sum((r - mu) ** 2 for r in returns) / len(returns)
        return var ** 0.5

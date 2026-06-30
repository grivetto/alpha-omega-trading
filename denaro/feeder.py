"""DENARO Feeder — consumes WSClient data, updates PairState indicators.
No direct WS connection — reads from centralized WSClient cache."""

from __future__ import annotations
import logging
import time
from typing import Optional

from .exchange import WSClient
from .models import PairState, Trend

log = logging.getLogger("denaro.feeder")


class Feeder:
    """Feeds WS data into PairState. Computes ATR, imbalance, trend."""

    def __init__(self, ws: WSClient, state: PairState) -> None:
        self.ws = ws
        self.state = state
        self.symbol = state.symbol
        self._norm = state.symbol.replace("/", "").upper()

        # Price history for ATR computation (last 20)
        self._price_history: list[float] = []
        self._volume_history: list[float] = []

    def update(self) -> PairState:
        """Pull latest WS data → update state. Call every cycle."""
        state = self.state

        # 1. Price
        price = self.ws.get_price(self.symbol)
        if price > 0:
            state.last_price = price
            self._price_history.append(price)
            if len(self._price_history) > 20:
                self._price_history = self._price_history[-20:]

        if state.last_price <= 0:
            return state

        # 2. Bid/ask + imbalance
        bid, ask = self.ws.get_bid_ask(self.symbol)
        if bid > 0:
            state.bid = bid
        if ask > 0:
            state.ask = ask

        # 3. Imbalance ratio from depth
        imbalance = self.ws.get_imbalance(self.symbol)
        state.bid_volume = imbalance  # We approximate
        state.ask_volume = 1.0 / max(imbalance, 0.01) if imbalance > 0 else 1.0

        # 4. Recent trades + volume
        trades = self.ws.get_recent_trades(self.symbol)
        if trades:
            self._volume_history.extend(trades)
            if len(self._volume_history) > 100:
                self._volume_history = self._volume_history[-100:]

        # 5. Indicator computation
        self._compute_indicators()

        # 6. WS data freshness check for state
        state.adaptive.cycle_count += 1

        return state

    def _compute_indicators(self) -> None:
        """Compute ATR, trend, volume spike, and update state.adaptive."""
        state = self.state
        prices = self._price_history

        if len(prices) < 2:
            return

        # ── ATR approximation ──
        high = max(prices[-10:]) if len(prices) >= 10 else max(prices)
        low = min(prices[-10:]) if len(prices) >= 10 else min(prices)
        atr_abs = (high - low) / 2.0
        state.adaptive.atr_pct = max(atr_abs / prices[-1], 0.0005)

        # ── Trend (from 10-period direction) ──
        if len(prices) >= 10:
            change_10 = (prices[-1] - prices[0]) / prices[0]
            if change_10 > 0.005:
                state.adaptive.trend = Trend.BULL
            elif change_10 < -0.005:
                state.adaptive.trend = Trend.BEAR
            else:
                state.adaptive.trend = Trend.RANGING

        # ── Volatility regime ──
        if state.adaptive.atr_pct > 0.03:
            state.adaptive.volatility_regime = "high"
        elif state.adaptive.atr_pct < 0.005:
            state.adaptive.volatility_regime = "low"
        else:
            state.adaptive.volatility_regime = "normal"

        # ── Volume spike ──
        vols = self._volume_history
        if len(vols) >= 20:
            recent = vols[-5:]
            old = vols[-20:-5]
            avg_recent = sum(recent) / max(len(recent), 1)
            avg_old = sum(old) / max(len(old), 1)
            state.adaptive.volume_spike = (
                avg_old > 0 and avg_recent > avg_old * 1.5
            )
            state.last_volume = avg_recent
            state.volume_avg = avg_old

        # ── Imbalance ratio ──
        imbalance = self.ws.get_imbalance(self.symbol)
        state.adaptive.bid_ask_imbalance = imbalance

"""DENARO Adaptive Grid Engine — volatility-aware, compounding, zero-touch.

Key features:
- Spread adapts to ATR × multiplier (wider in high vol, tighter in low vol)
- Grid levels auto-adjust count based on available capital
- Uses AVAILABLE USDC (free_quote) for sizing — not base asset value
- Resilient: handles -2010 (insufficient balance) gracefully
- Anti-spam: min 500ms between order placements"""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .config import Config

from .exchange import Exchange, OrderSide
from .models import CBState, PairState, GridConfig

log = logging.getLogger("denaro.grid")

MIN_ORDER_INTERVAL = 0.5


class GridEngine:
    """Manages grid levels for one pair."""

    def __init__(self, exchange: Exchange, cfg: GridConfig, pair_cfg: "Config") -> None:
        self.exchange = exchange
        self.cfg = cfg
        self.pair_cfg = pair_cfg
        self._last_order_ts: float = 0.0

    async def sync(self, state: PairState) -> PairState:
        if state.cb_state in (CBState.OPEN, CBState.GLOBAL_STOP):
            return state

        symbol = state.symbol
        price = state.last_price
        if price <= 0:
            return state

        atr_pct = state.adaptive.atr_pct
        spread = self.pair_cfg.grid_spread(atr_pct)

        # ── Capital base = FREE USDC only (not base asset value) ──
        available_usdc = state.free_quote + state.locked_quote
        if available_usdc <= 0:
            return state

        n_levels = self._optimal_levels(state, available_usdc)
        min_not = self.exchange.markets.min_notional(symbol)

        # Grid allocation fraction of available USDC
        grid_alloc = available_usdc * self.pair_cfg.grid_alloc
        if grid_alloc < min_not * 2:
            log.warning("[%s] Capital too low for grid: %.2f USDC (need %.2f)",
                        symbol, available_usdc, min_not * 2 * (n_levels * 2))
            return state

        # ── Convert USDC per level → BASE qty per order ──
        usdc_per_order = grid_alloc / (n_levels * 2)
        base_per_order = self.exchange.round_amount(symbol, usdc_per_order / price)

        # Validate per-order min notional
        if base_per_order * price < min_not:
            log.warning("[%s] Grid too small — %.6f %s × %.4f = %.2f < %.2f min notional",
                        symbol, base_per_order, symbol.split("/")[0],
                        price, base_per_order * price, min_not)
            return state

        # ── Check existing orders ──
        try:
            open_ords = await self.exchange.open_orders(symbol)
        except Exception:
            return state
        state.grid_active_orders = len(open_ords)

        # If more than half the grid still alive, skip
        if len(open_ords) >= n_levels * 0.5:
            return state

        if len(open_ords) > 0:
            log.info("[%s] %.0f%% grid filled — re-deploying",
                     symbol, (1 - len(open_ords) / (n_levels * 2)) * 100)

        # Cancel existing grid orders only (skip scalp positions)
        if state.scalp_position:
            # Cancel only orders matching expected grid size
            grid_order_ids = [o["orderId"] for o in open_ords
                            if float(o.get("price", 0)) < price * 0.99
                            or float(o.get("price", 0)) > price * 1.01]
            for oid in grid_order_ids:
                await self.exchange.cancel_order(symbol, oid)
                await asyncio.sleep(0.05)
        else:
            await self.exchange.cancel_all_orders(symbol)

        # ── Generate levels ──
        buy_levels = [price * (1 - spread * (i + 1)) for i in range(n_levels)]
        sell_levels = [price * (1 + spread * (i + 1)) for i in range(n_levels)]
        buy_levels = [max(b, price * 0.5) for b in buy_levels]

        # ── Place BUY orders ──
        buy_placed = 0
        for bp in buy_levels:
            bpr = self.exchange.round_price(symbol, bp)
            if bpr <= 0 or bpr >= price:
                continue
            await self._throttle()
            result = await self.exchange.place_limit_order(symbol, OrderSide.BUY, bpr, base_per_order)
            if result:
                buy_placed += 1
                self._last_order_ts = time.time()
            await asyncio.sleep(0.05)

        # ── Place SELL orders (only if we have base asset) ──
        sell_placed = 0
        if state.free_base + state.locked_base > base_per_order * 0.5:
            for sp in sell_levels:
                spr = self.exchange.round_price(symbol, sp)
                if spr <= price or spr <= 0:
                    continue
                await self._throttle()
                result = await self.exchange.place_limit_order(symbol, OrderSide.SELL, spr, base_per_order)
                if result:
                    sell_placed += 1
                    self._last_order_ts = time.time()
                await asyncio.sleep(0.05)

        state.grid_levels = n_levels
        state.grid_active_orders = buy_placed + sell_placed

        if buy_placed or sell_placed:
            log.info("[%s] Grid deployed: %d BUY + %d SELL at spread %.2f%% "
                     "(%.1f USDC, %.6f base/order)",
                     symbol, buy_placed, sell_placed, spread * 100,
                     usdc_per_order, base_per_order)

        return state

    async def _throttle(self) -> None:
        """Ensure min gap between orders."""
        wait = MIN_ORDER_INTERVAL - (time.time() - self._last_order_ts)
        if wait > 0:
            await asyncio.sleep(wait)

    def _optimal_levels(self, state: PairState, available_usdc: float) -> int:
        """Scale levels to available USDC."""
        base = self.cfg.n_levels
        min_not = self.exchange.markets.min_notional(state.symbol)
        price = state.last_price
        if price <= 0:
            return base
        for n in range(base, 0, -1):
            usdc_per = available_usdc * self.pair_cfg.grid_alloc / (n * 2)
            base_per = usdc_per / price
            if base_per * price >= min_not * 1.2:
                return n
        return 0  # Not enough for even 1 level

    def _calc_sizes(self, available_usdc: float, atr_pct: float) -> tuple[float, float]:
        grid_alloc = available_usdc * self.pair_cfg.grid_alloc
        scalp_alloc = available_usdc * self.pair_cfg.scalp_alloc
        if atr_pct > 0.04:
            grid_alloc *= 0.7
        elif atr_pct < 0.005:
            grid_alloc *= 0.8
        return (grid_alloc, scalp_alloc)

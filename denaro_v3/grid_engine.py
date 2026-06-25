"""Denaro v3 Grid Engine – core grid logic with robust rounding and zero‑price guards.

Fixes applied:
- Guard against zero or negative prices before placing orders.
- Unified rounding using exchange precision.
- Simplified level calculation ensuring at least one level.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from loguru import logger

from config import GridConfig
from data_feeder import DataFeeder
from circuit_breaker import CircuitBreaker, TradeRecord


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class GridLevel:
    side: Side
    price: float
    amount: float
    order_id: Optional[str] = None
    filled: bool = False


class GridEngine:
    def __init__(self, cfg: GridConfig, feeder: DataFeeder, breaker: CircuitBreaker):
        self._cfg = cfg
        self._feeder = feeder
        self._breaker = breaker
        self._levels: List[GridLevel] = []
        self._buy_fills: List[GridLevel] = []

    # ── Grid calculation ───────────────────────────────────────
    def calculate_levels(self) -> List[GridLevel]:
        ticker = self._feeder.get_ticker(self._cfg.symbol)
        mid = ticker.get("last", 0)
        if mid <= 0:
            logger.error("Invalid mid price for grid calculation")
            return []
        spacing = self._cfg.spacing_pct
        # ATR‑based dynamic spacing (fallback to static)
        try:
            ohlcv = self._feeder.get_ohlcv(self._cfg.symbol, "1h", self._cfg.atr_period + 1)
            if len(ohlcv) >= self._cfg.atr_period:
                atr = self._compute_atr(ohlcv)
                if atr > 0:
                    spacing = max(self._cfg.spacing_pct * 0.5,
                                   min((atr / mid) * 100 * self._cfg.atr_spacing_factor,
                                       self._cfg.spacing_pct * 3))
        except Exception:
            pass
        n = max(2, self._cfg.levels)  # ensure at least one buy and one sell
        half = n // 2
        levels: List[GridLevel] = []
        for i in range(half):
            price = self._round_price(mid * (1 - spacing / 100 * (i + 1)))
            if price <= 0:
                continue
            amt = self._calc_amount(price, Side.BUY)
            levels.append(GridLevel(Side.BUY, price, amt))
        for i in range(n - half):
            price = self._round_price(mid * (1 + spacing / 100 * (i + 1)))
            if price <= 0:
                continue
            amt = self._calc_amount(price, Side.SELL)
            levels.append(GridLevel(Side.SELL, price, amt))
        logger.info(f"Grid calculated {len(levels)} levels | mid={mid:.4f} spacing={spacing:.2f}%")
        return levels

    def _compute_atr(self, ohlcv: List[List[float]]) -> float:
        if len(ohlcv) < 2:
            return 0.0
        tr_sum = 0.0
        for i in range(1, min(len(ohlcv), self._cfg.atr_period + 1)):
            high, low = ohlcv[i][2], ohlcv[i][3]
            prev_close = ohlcv[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_sum += tr
        return tr_sum / min(len(ohlcv) - 1, self._cfg.atr_period)

    def _calc_amount(self, price: float, side: Side) -> float:
        if side == Side.BUY:
            balance = self._feeder.get_free_balance(self._cfg.quote_asset)
        else:
            balance = self._feeder.get_free_balance(self._cfg.base_asset) * price
        per_lvl = max(self._cfg.min_order_usdc, min(balance / (self._cfg.levels + 1), self._cfg.max_order_usdc))
        amount = per_lvl / price
        return self._round_amount(amount)

    def _round_price(self, price: float) -> float:
        try:
            market = self._feeder.exchange.market(self._cfg.symbol)
            step = market.get("precision", {}).get("price")
            if step is None:
                self._feeder.exchange.load_markets()
                step = market.get("precision", {}).get("price")
            if step is not None:
                if step < 1:
                    return round(price / step) * step
                return round(price, int(step))
        except Exception:
            pass
        return round(price, 4)

    def _round_amount(self, amount: float) -> float:
        try:
            market = self._feeder.exchange.market(self._cfg.symbol)
            limits = market.get("limits", {}).get("amount", {})
            min_amt = limits.get("min", 0.001)
            step = market.get("precision", {}).get("amount")
            if step is not None:
                if step < 1:
                    amount = math.floor(amount / step) * step
                else:
                    amount = round(amount, int(step))
            else:
                info = market.get("info", {})
                step = float(info.get("stepSize", "0.001"))
                amount = math.floor(amount / step) * step
            return max(min_amt, amount)
        except Exception:
            return round(amount, 6)

    # ── Order management ───────────────────────────────────────
    def sync_orders(self):
        open_orders = self._feeder.get_open_orders(self._cfg.symbol)
        open_ids = {o["id"] for o in open_orders}
        # Detect fills
        for lvl in self._levels:
            if lvl.order_id and not lvl.filled and lvl.order_id not in open_ids:
                lvl.filled = True
                logger.info(f"Fill detected {lvl.side.name} {lvl.amount:.4f}@{lvl.price:.4f}")
                if lvl.side == Side.BUY:
                    self._buy_fills.append(lvl)
                else:
                    if self._buy_fills:
                        buy = self._buy_fills.pop(0)
                        pnl = (lvl.price - buy.price) * lvl.amount
                        fee = (buy.price * buy.amount + lvl.price * lvl.amount) * 0.001
                        self._breaker.record_trade(TradeRecord(time.time(), self._cfg.symbol, "sell", lvl.amount, lvl.price, pnl - fee, fee))
        # Reconcile existing orders
        price_to_order = {o["price"]: o for o in open_orders}
        for lvl in self._levels:
            if lvl.order_id is None and lvl.price in price_to_order:
                lvl.order_id = price_to_order[lvl.price]["id"]
        # Place missing orders
        for lvl in self._levels:
            if lvl.order_id is None and lvl.price not in price_to_order:
                self._place_level(lvl)

    def _place_level(self, lvl: GridLevel):
        if lvl.price <= 0:
            logger.warning("Refusing to place order with non‑positive price")
            return
        # Asset availability checks
        if lvl.side == Side.SELL:
            if self._feeder.get_free_balance(self._cfg.base_asset) < lvl.amount:
                return
        else:
            if self._feeder.get_free_balance(self._cfg.quote_asset) < lvl.amount * lvl.price:
                return
        allowed, reason, max_amount = self._breaker.can_trade(lvl.amount * lvl.price)
        if not allowed:
            logger.warning(f"CB blocks {lvl.side.name} @ {lvl.price:.4f}: {reason}")
            return
        # Apply size reduction if half‑open
        amount = lvl.amount
        if self._breaker.state == CircuitBreaker.STATE_HALF_OPEN:
            amount = min(amount, max_amount / lvl.price)
        if lvl.side == Side.BUY:
            order = self._feeder.create_limit_buy(self._cfg.symbol, amount, lvl.price)
        else:
            order = self._feeder.create_limit_sell(self._cfg.symbol, amount, lvl.price)
        if order:
            lvl.order_id = order["id"]
            logger.info(f"Placed {lvl.side.name} @ {lvl.price:.4f} x {amount:.4f}")
        else:
            logger.error(f"Failed to place {lvl.side.name} @ {lvl.price:.4f}")

    def reset_grid(self):
        logger.info("Resetting grid – canceling all orders")
        try:
            for o in self._feeder.get_open_orders(self._cfg.symbol):
                self._feeder.cancel_order(o["id"], self._cfg.symbol)
        except Exception:
            pass
        self._levels = self.calculate_levels()
        self._buy_fills.clear()
        self.sync_orders()

    def needs_reset(self) -> bool:
        if not self._levels:
            return True
        active = sum(1 for lvl in self._levels if lvl.order_id and not lvl.filled)
        return active == 0

    # ── WS fill handling ───────────────────────────────────────
    def on_ws_fill(self, data: dict):
        symbol = data.get("symbol")
        if symbol != self._cfg.symbol:
            return
        order_id = data.get("order_id")
        for lvl in self._levels:
            if lvl.order_id == order_id:
                lvl.filled = data.get("status") == "FILLED"
                side = Side.BUY if data.get("side") == "buy" else Side.SELL
                if side == Side.BUY:
                    self._buy_fills.append(lvl)
                else:
                    if self._buy_fills:
                        buy = self._buy_fills.pop(0)
                        price = data.get("price")
                        amount = data.get("amount")
                        pnl = (price - buy.price) * amount
                        fee = data.get("fee", 0) or (buy.price * buy.amount + price * amount) * 0.001
                        self._breaker.record_trade(TradeRecord(time.time(), self._cfg.symbol, "sell", amount, price, pnl - fee, fee))
                break

    def summary(self) -> dict:
        active_buys = sum(1 for lvl in self._levels if lvl.side == Side.BUY and lvl.order_id and not lvl.filled)
        active_sells = sum(1 for lvl in self._levels if lvl.side == Side.SELL and lvl.order_id and not lvl.filled)
        pending = len(self._buy_fills)
        return {"levels_total": len(self._levels), "active_buys": active_buys,
                "active_sells": active_sells, "pending_sells": pending}

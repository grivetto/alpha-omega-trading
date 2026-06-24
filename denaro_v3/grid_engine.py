"""Denaro v3 Grid Engine — Pure grid trading logic.

Calculates grid levels, places orders, handles fills.
No LLM. No multi-strategy. No complexity. Just grid.
"""

import math
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

from loguru import logger

from .config import GridConfig
from .data_feeder import DataFeeder
from .circuit_breaker import CircuitBreaker, TradeRecord


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class GridLevel:
    """A single grid level."""
    side: Side
    price: float
    amount: float  # in base asset
    order_id: Optional[str] = None
    filled: bool = False


class GridEngine:
    """Pure grid trading. One pair, configurable levels.

    Flow:
    1. Fetch mid price
    2. Calculate grid levels (symmetrical around mid)
    3. Place missing orders
    4. Detect fills → place opposite order
    5. Track P&L per fill pair
    """

    def __init__(self, config: GridConfig, feeder: DataFeeder, breaker: CircuitBreaker):
        self._config = config
        self._feeder = feeder
        self._breaker = breaker
        self._levels: List[GridLevel] = []
        self._buy_fills: List[GridLevel] = []  # Filled buys waiting for sell

    # ── Grid Calculation ───────────────────────────────────
    def calculate_levels(self) -> List[GridLevel]:
        """Calculate grid levels around current mid price.

        Uses ATR-based dynamic spacing if ATR available, else fixed.
        """
        ticker = self._feeder.get_ticker(self._config.symbol)
        mid = ticker.get("last", 0)
        if mid <= 0:
            logger.error("Invalid mid price — cannot calculate levels")
            return []

        # Try ATR-based spacing
        spacing_pct = self._config.spacing_pct
        try:
            ohlcv = self._feeder.get_ohlcv(self._config.symbol, "1h", self._config.atr_period + 1)
            if ohlcv and len(ohlcv) >= self._config.atr_period:
                atr = self._compute_atr(ohlcv)
                if atr > 0:
                    spacing_pct = (atr / mid) * 100 * self._config.atr_spacing_factor
                    spacing_pct = max(self._config.spacing_pct * 0.5, min(spacing_pct, self._config.spacing_pct * 3))
        except Exception:
            pass  # Fall back to fixed spacing

        levels = []
        n = self._config.levels
        half = n // 2

        for i in range(half):
            # Buy levels below mid
            buy_price = mid * (1 - spacing_pct / 100 * (i + 1))
            buy_amount = self._calculate_amount(buy_price, Side.BUY)
            levels.append(GridLevel(side=Side.BUY, price=self._round_price(buy_price), amount=buy_amount))

        for i in range(n - half):
            # Sell levels above mid
            sell_price = mid * (1 + spacing_pct / 100 * (i + 1))
            sell_amount = self._calculate_amount(sell_price, Side.SELL)
            levels.append(GridLevel(side=Side.SELL, price=self._round_price(sell_price), amount=sell_amount))

        logger.info(
            f"Grid: {len(levels)} levels | mid={mid:.4f} | "
            f"spacing={spacing_pct:.2f}% | "
            f"range=[{levels[0].price:.4f}..{levels[-1].price:.4f}]"
        )
        return levels

    def _compute_atr(self, ohlcv: List[List[float]]) -> float:
        """Compute Average True Range from OHLCV data."""
        if len(ohlcv) < 2:
            return 0.0
        tr_sum = 0.0
        for i in range(1, min(len(ohlcv), self._config.atr_period + 1)):
            high, low = ohlcv[i][2], ohlcv[i][3]
            prev_close = ohlcv[i - 1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            tr_sum += tr
        return tr_sum / min(len(ohlcv) - 1, self._config.atr_period)

    def _calculate_amount(self, price: float, side: Side) -> float:
        """Calculate order amount in base asset.

        BUY: uses free quote balance. SELL: uses free base balance.
        """
        if side == Side.BUY:
            balance = self._feeder.get_free_balance(self._config.quote_asset)
        else:
            balance = self._feeder.get_free_balance(self._config.base_asset)
            balance = balance * price  # Convert base asset to quote value

        capital_per_level = balance / (self._config.levels + 1)  # +1 buffer

        # Clamp between min and max
        capital_per_level = max(self._config.min_order_usdc, min(capital_per_level, self._config.max_order_usdc))
        amount = capital_per_level / price

        # Round to valid lot size (Binance step size)
        return self._round_amount(amount)

    def _round_price(self, price: float) -> float:
        """Round price to exchange tick size."""
        try:
            market = self._feeder.exchange.market(self._config.symbol)
            if not market.get("precision"):
                self._feeder.exchange.load_markets()
                market = self._feeder.exchange.market(self._config.symbol)
            step_size = market["precision"]["price"]
            if step_size is not None:
                if step_size < 1:
                    # Float step size (e.g. 0.01) — use floor/round
                    return round(price / step_size) * step_size
                # Integer decimal places
                return round(price, int(step_size))
            # Fallback
            info = market.get("info", {})
            tick = float(info.get("tickSize", "0.01"))
            return round(price / tick) * tick
        except Exception:
            return round(price, 4)

    def _round_amount(self, amount: float) -> float:
        """Round amount to exchange step size."""
        try:
            market = self._feeder.exchange.market(self._config.symbol)
            if not market.get("precision"):
                self._feeder.exchange.load_markets()
                market = self._feeder.exchange.market(self._config.symbol)
            limits = market.get("limits", {}).get("amount", {})
            min_amt = limits.get("min", 0.001)
            step_size = market["precision"]["amount"]
            if step_size is not None:
                if step_size < 1:
                    # Float step size (e.g. 0.001) — use floor division
                    amount = math.floor(amount / step_size) * step_size
                else:
                    # Integer decimal places (e.g. 3)
                    amount = round(amount, int(step_size))
            else:
                info = market.get("info", {})
                step = float(info.get("stepSize", "0.001"))
                amount = math.floor(amount / step) * step
            return max(min_amt, amount)
        except Exception:
            return round(amount, 6)

    # ── Order Management ───────────────────────────────────
    def sync_orders(self):
        """Reconcile local grid state with exchange orders.

        Called every loop cycle. Detects fills, places missing orders.
        """
        open_orders = self._feeder.get_open_orders(self._config.symbol)
        open_ids = {o["id"] for o in open_orders}

        # Check for fills (order ID not in open orders)
        for level in self._levels:
            if level.order_id and not level.filled:
                if level.order_id not in open_ids:
                    level.filled = True
                    logger.info(f"Grid fill: {level.side.name} {level.amount:.4f} @ {level.price:.4f}")

                    # Record P&L for completed buy-sell cycle
                    if level.side == Side.BUY:
                        self._buy_fills.append(level)
                    elif level.side == Side.SELL:
                        # Find matching buy to calculate P&L
                        if self._buy_fills:
                            buy = self._buy_fills.pop(0)
                            pnl = (level.price - buy.price) * level.amount
                            fee = (buy.price * buy.amount + level.price * level.amount) * 0.001  # 0.1% estimate
                            self._breaker.record_trade(TradeRecord(
                                timestamp=0,  # Will be set by breaker
                                symbol=self._config.symbol,
                                side="sell",
                                amount=level.amount,
                                price=level.price,
                                pnl=pnl - fee,
                                fee=fee,
                            ))
                            logger.info(f"Grid cycle complete: BUY @ {buy.price:.4f} → SELL @ {level.price:.4f} | P&L={pnl:.2f}")

        # Reconcile: assign existing order IDs to levels with matching prices
        price_to_order = {o["price"]: o for o in open_orders}
        for level in self._levels:
            if level.order_id is None and level.price in price_to_order:
                level.order_id = price_to_order[level.price]["id"]
                logger.debug(f"Reconciled {level.side.name} @ {level.price:.4f} → ID={level.order_id}")

        # Place missing orders
        for level in self._levels:
            if level.order_id is None and level.price not in price_to_order:
                self._place_level(level)

    def _place_level(self, level: GridLevel):
        """Place a single grid level order. Pre-checked by CircuitBreaker."""
        # Check if we have the asset to trade
        if level.side == Side.SELL:
            base_balance = self._feeder.get_free_balance(self._config.base_asset)
            if base_balance < level.amount:
                return  # Will retry after a buy fills
        elif level.side == Side.BUY:
            needed = level.amount * level.price
            quote_balance = self._feeder.get_free_balance(self._config.quote_asset)
            if quote_balance < needed:
                return  # Will retry after a sell fills or capital arrives

        result = self._breaker.can_trade(level.amount * level.price)
        if not result[0]:
            logger.warning(f"Circuit breaker blocked {level.side.name} @ {level.price:.4f}: {result[1]}")
            return

        if level.side == Side.BUY:
            order = self._feeder.create_limit_buy(self._config.symbol, level.amount, level.price)
        else:
            order = self._feeder.create_limit_sell(self._config.symbol, level.amount, level.price)

        if order:
            level.order_id = order["id"]
            logger.info(f"Placed {level.side.name} @ {level.price:.4f} x {level.amount:.4f} | ID={level.order_id}")
        else:
            logger.error(f"Failed to place {level.side.name} @ {level.price:.4f}")

    def reset_grid(self):
        """Cancel all open orders and recalculate grid from scratch."""
        logger.info("Resetting grid...")
        for level in self._levels:
            if level.order_id and not level.filled:
                self._feeder.cancel_order(level.order_id, self._config.symbol)
        self._levels = self.calculate_levels()
        self._buy_fills = []
        self.sync_orders()

    def needs_reset(self) -> bool:
        """Check if grid needs recalculation (no active orders)."""
        if not self._levels:
            return True
        active = sum(1 for level in self._levels if level.order_id and not level.filled)
        return active == 0

    # ── Status ─────────────────────────────────────────────
    def summary(self) -> dict:
        """Human-readable grid status."""
        active_buys = sum(1 for level in self._levels if level.side == Side.BUY and level.order_id and not level.filled)
        active_sells = sum(1 for level in self._levels if level.side == Side.SELL and level.order_id and not level.filled)
        pending_buys = len(self._buy_fills)
        return {
            "levels_total": len(self._levels),
            "active_buys": active_buys,
            "active_sells": active_sells,
            "pending_sells": pending_buys,
        }

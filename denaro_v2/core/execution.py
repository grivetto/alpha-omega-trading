#!/usr/bin/env python3
"""
DENARO V2 - Execution Engine
Smart order management with OCO (One-Cancels-Other) support,
iceberg orders, and fill tracking.
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("Denaro.Execution")


class ExecutionEngine:
    """Smart order execution with risk controls."""

    def __init__(self, exchange, risk_manager=None):
        self.exchange = exchange
        self.risk_manager = risk_manager
        self.pending_orders = {}
        self.filled_orders = {}
        self._order_counter = 0

    async def execute_entry(self, symbol: str, side: str, amount: float,
                             price: float, tp_price: float = None,
                             sl_price: float = None) -> Optional[dict]:
        """Execute entry order with optional TP/SL."""
        # Risk check
        if self.risk_manager:
            risk_ok = await self.risk_manager.check_entry(symbol, side, amount, price)
            if not risk_ok:
                logger.warning(f"Entry blocked by risk manager: {symbol} {side}")
                return None

        # Place entry order
        if side == 'buy':
            order = await self.exchange.create_limit_buy(symbol, amount, price)
        else:
            order = await self.exchange.create_limit_sell(symbol, amount, price)

        if not order:
            return None

        order_id = order['id']
        self.pending_orders[order_id] = {
            'symbol': symbol,
            'side': side,
            'amount': amount,
            'entry_price': price,
            'tp_price': tp_price,
            'sl_price': sl_price,
            'timestamp': time.time(),
        }

        logger.info(f"Entry placed: {symbol} {side} {amount} @ {price}")

        # Place TP/SL if specified
        if tp_price and side == 'buy':
            await self._place_tp_sl(symbol, amount, tp_price, sl_price, order_id)

        return order

    async def _place_tp_sl(self, symbol: str, amount: float,
                            tp_price: float, sl_price: float,
                            parent_order_id: str):
        """Place take-profit and stop-loss orders."""
        # Round amount slightly to ensure we can sell
        sell_amount = amount * 0.997  # Account for fees

        # Place TP order
        try:
            tp_order = await self.exchange.create_limit_sell(symbol, sell_amount, tp_price)
            if tp_order:
                self.pending_orders[tp_order['id']] = {
                    'symbol': symbol,
                    'side': 'sell',
                    'type': 'take_profit',
                    'parent_id': parent_order_id,
                    'amount': sell_amount,
                    'price': tp_price,
                    'timestamp': time.time(),
                }
                logger.info(f"TP placed: {symbol} {sell_amount} @ {tp_price}")
        except Exception as e:
            logger.error(f"TP placement failed: {e}")

        # Place SL order
        if sl_price:
            try:
                sl_order = await self.exchange.create_limit_sell(symbol, sell_amount, sl_price)
                if sl_order:
                    self.pending_orders[sl_order['id']] = {
                        'symbol': symbol,
                        'side': 'sell',
                        'type': 'stop_loss',
                        'parent_id': parent_order_id,
                        'amount': sell_amount,
                        'price': sl_price,
                        'timestamp': time.time(),
                    }
                    logger.info(f"SL placed: {symbol} {sell_amount} @ {sl_price}")
            except Exception as e:
                logger.error(f"SL placement failed: {e}")

    async def execute_exit(self, symbol: str, amount: float, price: float = None,
                            market: bool = False) -> Optional[dict]:
        """Execute exit order."""
        if market or not price:
            order = await self.exchange.create_market_sell(symbol, amount)
        else:
            order = await self.exchange.create_limit_sell(symbol, amount, price)

        if order:
            logger.info(f"Exit executed: {symbol} {amount} @ {order.get('price', price)}")
            self._cleanup_related_orders(order.get('id', ''))

        return order

    async def cancel_all_orders(self, symbol: Optional[str] = None) -> int:
        """Cancel all open orders."""
        orders = await self.exchange.fetch_open_orders(symbol)
        cancelled = 0
        for order in orders:
            if await self.exchange.cancel_order(order['id'], order['symbol']):
                cancelled += 1
                self.pending_orders.pop(order['id'], None)
        logger.info(f"Cancelled {cancelled} orders")
        return cancelled

    async def check_fills(self) -> list:
        """Check for filled orders."""
        filled = []
        orders = await self.exchange.fetch_open_orders()
        pending_ids = set(self.pending_orders.keys())

        # Check which pending orders are no longer open (filled or cancelled)
        open_ids = set(o['id'] for o in orders)
        completed_ids = pending_ids - open_ids

        for order_id in completed_ids:
            order_info = self.pending_orders.pop(order_id, None)
            if order_info:
                # Fetch actual order to check status
                actual = await self.exchange.fetch_order(order_id, order_info['symbol'])
                if actual and actual['status'] == 'closed':
                    self.filled_orders[order_id] = actual
                    filled.append(actual)
                    logger.info(f"Order filled: {order_info['symbol']} {order_info['side']} "
                                f"{actual['filled']} @ {actual.get('average', actual['price'])}")

        return filled

    def _cleanup_related_orders(self, filled_order_id: str):
        """Cancel TP/SL orders when parent is filled."""
        to_cancel = []
        for order_id, info in self.pending_orders.items():
            if info.get('parent_id') == filled_order_id:
                to_cancel.append((order_id, info))

        for order_id, info in to_cancel:
            asyncio.create_task(
                self.exchange.cancel_order(order_id, info['symbol'])
            )
            self.pending_orders.pop(order_id, None)

    def get_position_summary(self) -> dict:
        """Get summary of active positions."""
        return {
            'pending': len(self.pending_orders),
            'filled_today': len(self.filled_orders),
            'orders': list(self.pending_orders.values()),
        }

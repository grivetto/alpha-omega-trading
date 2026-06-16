#!/usr/bin/env python3
"""Patch base.py to implement Dynamic Position Sizing and Trailing Stop Guard"""
import os
import asyncio
from typing import Any
from enum import Enum

from loguru import logger

# Constants
MAX_DRAWDOWN = 0.05  # 5 % of total capital
BASE_RISK_PER_TRADE = 0.02  # 2 % base risk per trade


class Side(Enum):
    BUY = 'buy'
    SELL = 'sell'


class Position:
    def __init__(self, symbol, side, amount, entry_price, tp_price, sl_price, signal_source, order_id=None, tp_order_id=None):
        self.symbol = symbol
        self.side = side
        self.amount = amount
        self.entry_price = entry_price
        self.tp_price = tp_price
        self.sl_price = sl_price
        self.signal_source = signal_source
        self.order_id = order_id
        self.tp_order_id = tp_order_id


class Signal:
    def __init__(self, side, symbol, amount, entry_price, tp_price, sl_price, source):
        self.side = side
        self.symbol = symbol
        self.amount = amount
        self.entry_price = entry_price
        self.tp_price = tp_price
        self.sl_price = sl_price
        self.source = source


class BaseStrategy:
    def __init__(self, exchange: Any, db: object, initial_capital: float = 0.0, **kwargs):
        self.exchange = exchange
        self.db = db
        # Accept symbol from kwargs or from exchange if available
        self.symbol = kwargs.get('symbol', getattr(exchange, 'symbol', 'DEFAULT'))
        self.initial_capital = initial_capital
        self.capital = initial_capital
        self.is_paused = False
        self._positions = {}
        self.logger = logger.bind(strategy=self.__class__.__name__)
        self.update_interval = kwargs.get('update_interval', 60)
        self.timeframe = kwargs.get('timeframe', '1h')

    async def get_quote_capital(self):
        """Fetches current quote currency capital (e.g., USDC) from the exchange."""
        try:
            balance = await self.exchange.fetch_balance()
            quote_currency = self.symbol.split('/')[-1]
            return balance.get('free', {}).get(quote_currency, 0.0)
        except Exception as e:
            self.logger.error(f"Error fetching quote capital: {e}")
            return 0.0

    async def _get_dynamic_risk_factor(self, current_capital):
        """Calculates a dynamic risk factor based on drawdown."""
        if self.initial_capital <= 0: return BASE_RISK_PER_TRADE
        drawdown = max(0.0, (self.initial_capital - current_capital) / self.initial_capital)
        factor = max(0.1, 1 - drawdown / MAX_DRAWDOWN)
        return factor

    async def _size(self, entry_price, stop_loss_price, short=False):
        """Calculates order size based on dynamic risk and market limits."""
        current_capital = await self.get_quote_capital()
        risk_factor = await self._get_dynamic_risk_factor(current_capital)
        risk_amount = current_capital * risk_factor

        stop_loss_distance = abs(entry_price - stop_loss_price)
        if stop_loss_distance <= 0: return 0.0

        calculated_size = risk_amount / stop_loss_distance

        try:
            # Try to get market info from exchange
            market = None
            if hasattr(self.exchange, 'market'):
                market = self.exchange.market(self.symbol)
            elif hasattr(self.exchange, '_exchange') and hasattr(self.exchange._exchange, 'market'):
                market = self.exchange._exchange.market(self.symbol)

            if market:
                min_notional = market.get('limits', {}).get('cost', {}).get('min', 5.0)
                min_amount = market.get('limits', {}).get('amount', {}).get('min', 0.0)
                amount_precision = market.get('precision', {}).get('amount', 8)
            else:
                min_notional = 5.0
                min_amount = 0.0
                amount_precision = 8

            if calculated_size < min_amount:
                calculated_size = min_amount
            
            final_size = round(calculated_size, amount_precision)
            
            if final_size * entry_price < min_notional:
                 final_size = round(min_notional / entry_price, amount_precision)
            
            balance = await self.exchange.fetch_balance()
            base_currency, quote_currency = self.symbol.split('/')

            if short:
                available_base = balance.get('free', {}).get(base_currency, 0.0)
                final_size = min(final_size, available_base * 0.98)
            else:
                available_quote = balance.get('free', {}).get(quote_currency, 0.0)
                max_possible_size = available_quote / entry_price
                final_size = min(final_size, max_possible_size * 0.98)

            if final_size < min_amount:
                return 0.0
            
            return round(final_size, amount_precision)

        except Exception as e:
            self.logger.error(f"Error calculating size for {self.symbol}: {e}")
            return 0.0

    async def _place_market(self, side: Side, amount, price):
        """Places a market order for closing a position."""
        try:
            order_type = 'market'
            params = {}
            # Get the actual ccxt exchange id
            exchange_id = 'binance'
            if hasattr(self.exchange, 'id'):
                exchange_id = self.exchange.id
            elif hasattr(self.exchange, '_exchange') and hasattr(self.exchange._exchange, 'id'):
                exchange_id = self.exchange._exchange.id
                
            if exchange_id == 'binance':
                if side == Side.BUY:
                    params['side'] = 'SELL'
                else:
                    params['side'] = 'BUY'

            order = await self.exchange.create_order(self.symbol, order_type, side.value, amount, params=params)
            self.logger.info(f"Market order for closing: {side.value} {amount} {self.symbol} @ {price}. Order ID: {order['id']}")
            return order
        except Exception as e:
            self.logger.error(f"Failed to place market order: {e}")
            return None

    async def _exec_sl(self, oid, pos, side: Side):
        """Executes stop-loss, cancels existing TP order, places market order."""
        try:
            if pos.tp_order_id:
                await self.exchange.cancel_order(pos.tp_order_id, self.symbol)
                self.logger.info(f"Cancelled TP order ID: {pos.tp_order_id}")

            close_order = await self._place_market(side, pos.amount, pos.entry_price)
            if not close_order:
                return

            self.logger.info(f"Stop Loss triggered for order ID {oid}. Position closed.")

            if oid in self._positions:
                del self._positions[oid]

        except Exception as e:
            self.logger.error(f"Error executing stop loss for order ID {oid}: {e}")

    async def on_candle(self, ohlcv):
        raise NotImplementedError

    async def _check_sl(self, current_price):
        """Checks if any active positions have hit their stop loss."""
        positions_to_remove = []
        for oid, pos in self._positions.items():
            if pos.sl_price is None: continue
            if pos.side == Side.BUY and current_price <= pos.sl_price:
                await self._exec_sl(oid, pos, Side.SELL)
                positions_to_remove.append(oid)
            elif pos.side == Side.SELL and current_price >= pos.sl_price:
                await self._exec_sl(oid, pos, Side.BUY)
                positions_to_remove.append(oid)
        for oid in positions_to_remove:
            if oid in self._positions:
                del self._positions[oid]

    async def get_initial_capital(self):
        return self.initial_capital

    async def set_initial_capital(self, capital):
        self.initial_capital = capital
        self.capital = capital

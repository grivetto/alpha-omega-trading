#!/usr/bin/env python3
"""
DENARO V2 - Grid Market Maker Strategy
High-frequency tight grid trading with adaptive spacing,
order book-aware placement, and rapid turnover.
"""
import asyncio
import logging
import time
from typing import Optional

logger = logging.getLogger("Denaro.GridMM")


class GridMarketMaker:
    """High-frequency grid market making strategy."""

    def __init__(self, exchange, execution, risk_manager, config: dict = None):
        self.exchange = exchange
        self.execution = execution
        self.risk = risk_manager
        self.config = config or {}

        self.symbol = self.config.get('symbol', 'SOL/EUR')
        self.grid_levels = self.config.get('grid_levels', 7)
        self.grid_spacing_pct = self.config.get('grid_spacing_pct', 0.005)  # 0.5%
        self.base_order_eur = self.config.get('base_order_eur', 5.0)
        self.max_total_invested = self.config.get('max_total_invested', 50.0)
        self.profit_per_grid = self.config.get('profit_per_grid', 0.004)  # 0.4%

        self.state = {
            'active': False,
            'buy_orders': {},
            'sell_orders': {},
            'total_invested': 0,
            'total_profit': 0,
            'fills': 0,
            'last_rebalance': 0,
            'center_price': 0,
        }

    async def run_cycle(self, price: float, balance: dict) -> bool:
        """Run one cycle of the grid market maker."""
        eur_free = balance.get('EUR', {}).get('free', 0)
        asset = self.symbol.split('/')[0]
        asset_free = balance.get(asset, {}).get('free', 0)

        # Check if we need to initialize or rebalance
        if not self.state['active'] or self._needs_rebalance(price):
            await self._rebuild_grid(price, eur_free, asset_free)
            return True

        # Check for fills
        await self._check_grid_fills(price)

        return False

    def _needs_rebalance(self, price: float) -> bool:
        """Check if grid needs rebalancing."""
        if not self.state['center_price']:
            return True

        dist = abs(price - self.state['center_price']) / self.state['center_price']
        if dist > self.grid_spacing_pct * 2:
            return True

        if time.time() - self.state['last_rebalance'] > 300:  # 5 min max
            return True

        return False

    async def _rebuild_grid(self, price: float, eur_free: float, asset_free: float):
        """Rebuild the entire grid."""
        # Cancel existing orders
        await self.execution.cancel_all_orders(self.symbol)
        self.state['buy_orders'] = {}
        self.state['sell_orders'] = {}
        self.state['total_invested'] = 0
        self.state['center_price'] = price
        self.state['last_rebalance'] = time.time()

        logger.info(f"Grid rebuild @ {price} | EUR={eur_free:.2f} | {self.symbol.split('/')[0]}={asset_free:.4f}")

        # Calculate grid levels
        half_levels = self.grid_levels // 2
        step = self.grid_spacing_pct

        # Get market info for minimums
        market_info = await self.exchange.get_market_info(self.symbol)
        min_cost = 5.0  # Default minimum
        if market_info and 'limits' in market_info:
            min_cost = market_info['limits'].get('cost', {}).get('min', 5.0)

        # Place buy orders below current price
        for i in range(1, half_levels + 1):
            buy_price = price * (1 - i * step)
            order_eur = max(min_cost + 1, self.base_order_eur * (1 + i * 0.1))  # Ensure above minimum

            if self.state['total_invested'] + order_eur > self.max_total_invested:
                break
            if order_eur > eur_free * 0.85:
                break

            amount = order_eur / buy_price
            order = await self.exchange.create_limit_buy(self.symbol, amount, buy_price)
            if order:
                self.state['buy_orders'][order['id']] = {
                    'price': buy_price,
                    'amount': amount,
                    'eur': order_eur,
                    'level': i,
                }
                self.state['total_invested'] += order_eur
                eur_free -= order_eur
                logger.info(f"Buy placed @ {buy_price} ({order_eur:.2f} EUR)")
            else:
                logger.warning(f"Buy failed @ {buy_price}")

        # Place sell orders above current price
        for i in range(1, half_levels + 1):
            sell_price = price * (1 + i * step)
            sell_amount = min(asset_free * 0.3, self.base_order_eur / sell_price)

            # Check minimum notional
            sell_notional = sell_amount * sell_price
            if sell_notional < min_cost:
                continue

            if sell_amount < 0.001:
                break

            order = await self.exchange.create_limit_sell(self.symbol, sell_amount, sell_price)
            if order:
                self.state['sell_orders'][order['id']] = {
                    'price': sell_price,
                    'amount': sell_amount,
                    'level': i,
                }
                asset_free -= sell_amount
                logger.info(f"Sell placed @ {sell_price} ({sell_amount:.4f})")

        self.state['active'] = True
        logger.info(f"Grid set: {len(self.state['buy_orders'])} buys, "
                     f"{len(self.state['sell_orders'])} sells, "
                     f"invested={self.state['total_invested']:.2f}")

    async def _check_grid_fills(self, price: float):
        """Check for filled grid orders and replace them."""
        filled = await self.execution.check_fills()

        for order in filled:
            order_id = order['id']

            # Check if it was a buy order
            if order_id in self.state['buy_orders']:
                buy_info = self.state['buy_orders'].pop(order_id)
                fill_price = order.get('average', order['price'])
                fill_amount = order.get('filled', buy_info['amount'])

                # Place corresponding sell order above
                sell_price = fill_price * (1 + self.profit_per_grid)
                sell_order = await self.exchange.create_limit_sell(
                    self.symbol, fill_amount * 0.997, sell_price
                )
                if sell_order:
                    self.state['sell_orders'][sell_order['id']] = {
                        'price': sell_price,
                        'amount': fill_amount * 0.997,
                        'level': buy_info['level'],
                    }

                self.state['fills'] += 1
                logger.info(f"Buy filled @ {fill_price} → sell placed @ {sell_price}")

            # Check if it was a sell order
            elif order_id in self.state['sell_orders']:
                sell_info = self.state['sell_orders'].pop(order_id)
                fill_price = order.get('average', order['price'])

                # Place new buy order below
                buy_price = fill_price * (1 - self.profit_per_grid)
                buy_eur = self.base_order_eur
                amount = buy_eur / buy_price

                buy_order = await self.exchange.create_limit_buy(self.symbol, amount, buy_price)
                if buy_order:
                    self.state['buy_orders'][buy_order['id']] = {
                        'price': buy_price,
                        'amount': amount,
                        'eur': buy_eur,
                        'level': sell_info['level'],
                    }
                    self.state['total_invested'] += buy_eur

                # Calculate profit
                profit = self.profit_per_grid * buy_eur
                self.state['total_profit'] += profit
                self.state['fills'] += 1

                self.risk.record_trade(self.symbol, profit)
                logger.info(f"Sell filled @ {fill_price} → buy placed @ {buy_price} | profit={profit:.4f}")

    def get_status(self) -> dict:
        """Get grid status."""
        return {
            'symbol': self.symbol,
            'active': self.state['active'],
            'center_price': self.state['center_price'],
            'buy_orders': len(self.state['buy_orders']),
            'sell_orders': len(self.state['sell_orders']),
            'total_invested': self.state['total_invested'],
            'total_profit': self.state['total_profit'],
            'fills': self.state['fills'],
        }

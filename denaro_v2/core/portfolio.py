#!/usr/bin/env python3
"""
DENARO V2 - Portfolio Manager
Auto-rebalancing, profit compounding, and allocation management.
"""
import asyncio
import logging
import time
import json
import os

logger = logging.getLogger("Denaro.Portfolio")


class PortfolioManager:
    """Manages portfolio allocation and auto-compounding."""

    def __init__(self, exchange, config: dict = None):
        self.exchange = exchange
        self.config = config or {}
        self.total_profit = 0
        self.total_trades = 0
        self.win_trades = 0
        self.start_time = time.time()
        self._state_file = self.config.get('state_file', '.tmp/portfolio_state.json')

        # Load persisted state
        self._load_state()

    async def get_portfolio_value(self) -> dict:
        """Get full portfolio valuation."""
        balance = await self.exchange.fetch_balance()
        total_eur = 0
        assets = {}

        for symbol, data in balance.items():
            if symbol == 'EUR':
                total_eur += data['total']
                assets[symbol] = {
                    'amount': data['total'],
                    'value_eur': data['total'],
                }
            elif data['total'] > 0:
                pair = f"{symbol}/EUR"
                try:
                    ticker = await self.exchange.fetch_ticker(pair)
                    price = ticker.get('last', 0)
                    value = data['total'] * price
                    total_eur += value
                    assets[symbol] = {
                        'amount': data['total'],
                        'price': price,
                        'value_eur': value,
                    }
                except Exception:
                    assets[symbol] = {
                        'amount': data['total'],
                        'value_eur': 0,
                    }

        return {
            'total_eur': total_eur,
            'assets': assets,
            'timestamp': time.time(),
        }

    async def rebalance(self, target_allocations: dict) -> bool:
        """Rebalance portfolio to target allocations.

        target_allocations: {'SOL': 0.3, 'ETH': 0.3, 'BTC': 0.2, 'EUR': 0.2}
        """
        portfolio = await self.get_portfolio_value()
        total = portfolio['total_eur']
        if total <= 0:
            return False

        for symbol, target_pct in target_allocations.items():
            if symbol == 'EUR':
                continue

            target_value = total * target_pct
            current = portfolio['assets'].get(symbol, {}).get('value_eur', 0)
            diff = target_value - current

            if abs(diff) > total * 0.05:  # Only rebalance if > 5% off
                pair = f"{symbol}/EUR"
                ticker = await self.exchange.fetch_ticker(pair)
                price = ticker.get('last', 0)

                if diff > 0:
                    # Buy
                    amount = diff / price
                    logger.info(f"Rebalance BUY {symbol}: {amount:.4f} @ {price}")
                    await self.exchange.create_market_buy(pair, amount)
                else:
                    # Sell
                    current_amount = portfolio['assets'].get(symbol, {}).get('amount', 0)
                    sell_amount = min(abs(diff) / price, current_amount * 0.95)
                    logger.info(f"Rebalance SELL {symbol}: {sell_amount:.4f} @ {price}")
                    await self.exchange.create_market_sell(pair, sell_amount)

        return True

    def record_trade(self, pnl: float, won: bool):
        """Record trade for performance tracking."""
        self.total_profit += pnl
        self.total_trades += 1
        if won:
            self.win_trades += 1
        self._save_state()

    def get_performance(self) -> dict:
        """Get performance metrics."""
        win_rate = self.win_trades / self.total_trades * 100 if self.total_trades > 0 else 0
        avg_profit = self.total_profit / self.total_trades if self.total_trades > 0 else 0
        uptime = time.time() - self.start_time

        return {
            'total_profit': self.total_profit,
            'total_trades': self.total_trades,
            'win_rate': win_rate,
            'avg_profit': avg_profit,
            'uptime_hours': uptime / 3600,
        }

    def _load_state(self):
        """Load persisted state."""
        try:
            if os.path.exists(self._state_file):
                with open(self._state_file, 'r') as f:
                    state = json.load(f)
                self.total_profit = state.get('total_profit', 0)
                self.total_trades = state.get('total_trades', 0)
                self.win_trades = state.get('win_trades', 0)
        except Exception as e:
            logger.error(f"Failed to load portfolio state: {e}")

    def _save_state(self):
        """Persist state."""
        try:
            os.makedirs(os.path.dirname(self._state_file), exist_ok=True)
            state = {
                'total_profit': self.total_profit,
                'total_trades': self.total_trades,
                'win_trades': self.win_trades,
                'timestamp': time.time(),
            }
            with open(self._state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save portfolio state: {e}")

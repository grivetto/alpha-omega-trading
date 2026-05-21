#!/usr/bin/env python3
"""
DENARO V2 - Mean Reversion Strategy
Captures price extremes with RSI-based entries and quick exits.
"""
import asyncio
import logging
import time

logger = logging.getLogger("Denaro.MeanRev")


class MeanReversion:
    """Mean reversion trading strategy."""

    def __init__(self, exchange, execution, risk_manager, scanner, signals, config: dict = None):
        self.exchange = exchange
        self.execution = execution
        self.risk = risk_manager
        self.scanner = scanner
        self.signals = signals
        self.config = config or {}

        self.symbol = self.config.get('symbol', 'ETH/EUR')
        self.timeframe = self.config.get('timeframe', '5m')
        self.base_order_eur = self.config.get('base_order_eur', 5.0)
        self.rsi_oversold = self.config.get('rsi_oversold', 25)
        self.rsi_overbought = self.config.get('rsi_overbought', 75)
        self.tp_pct = self.config.get('tp_pct', 0.01)  # 1%
        self.sl_pct = self.config.get('sl_pct', 0.008)  # 0.8%

        self.position = None
        self.entry_time = 0
        self.max_hold_time = 7200  # 2 hours max

    async def run_cycle(self, price: float, balance: dict) -> bool:
        """Run one cycle."""
        eur_free = balance.get('EUR', {}).get('free', 0)
        asset = self.symbol.split('/')[0]
        asset_free = balance.get(asset, {}).get('free', 0)

        if self.position:
            return await self._manage_position(price, balance)

        return await self._look_for_entry(price, eur_free, asset_free)

    async def _manage_position(self, price: float, balance: dict) -> bool:
        """Manage open position."""
        entry_price = self.position['entry_price']
        pnl = (price - entry_price) / entry_price

        # Take profit
        if pnl >= self.tp_pct:
            await self._exit(price, "TP")
            return True

        # Stop loss
        if pnl <= -self.sl_pct:
            await self._exit(price, "SL")
            return True

        # Time stop
        if time.time() - self.entry_time > self.max_hold_time:
            await self._exit(price, "TIME")
            return True

        # RSI-based exit: exit when RSI goes above 50 (mean reverted)
        ohlcv = await self.scanner.fetch_ohlcv(self.symbol, self.timeframe, 20)
        if ohlcv:
            rsi = self.signals._calc_rsi(ohlcv, 14)
            if rsi > 55 and pnl > 0:
                await self._exit(price, "RSI")
                return True

        return False

    async def _look_for_entry(self, price: float, eur_free: float, asset_free: float) -> bool:
        """Look for mean reversion entry."""
        if eur_free < self.base_order_eur:
            return False

        ohlcv = await self.scanner.fetch_ohlcv(self.symbol, self.timeframe, 50)
        if not ohlcv or len(ohlcv) < 20:
            return False

        rsi = self.signals._calc_rsi(ohlcv, 14)

        # Buy when RSI is oversold
        if rsi < self.rsi_oversold:
            amount = self.risk.get_position_size(self.symbol, price, 0.03)
            if amount <= 0:
                return False

            risk_ok = await self.risk.check_entry(self.symbol, 'buy', amount, price)
            if not risk_ok:
                return False

            tp_price = price * (1 + self.tp_pct)
            sl_price = price * (1 - self.sl_pct)

            order = await self.execution.execute_entry(
                self.symbol, 'buy', amount, price,
                tp_price=tp_price, sl_price=sl_price
            )

            if order:
                self.position = {
                    'entry_price': price,
                    'amount': amount,
                    'rsi_entry': rsi,
                }
                self.entry_time = time.time()
                logger.info(f"MeanRev ENTRY {self.symbol} @ {price} | RSI={rsi:.1f} "
                            f"TP={tp_price} SL={sl_price}")
                return True

        return False

    async def _exit(self, price: float, reason: str):
        """Exit position."""
        if not self.position:
            return

        pnl = (price - self.position['entry_price']) / self.position['entry_price']
        pnl_eur = pnl * self.position['entry_price'] * self.position['amount']

        await self.execution.cancel_all_orders(self.symbol)
        await self.execution.execute_exit(
            self.symbol, self.position['amount'] * 0.997, market=True
        )

        self.risk.record_trade(self.symbol, pnl_eur)

        logger.info(f"MeanRev EXIT {self.symbol} @ {price} | "
                     f"reason={reason} pnl={pnl*100:.2f}% ({pnl_eur:.2f})")

        self.position = None

    def get_status(self) -> dict:
        """Get status."""
        if self.position:
            return {
                'symbol': self.symbol,
                'in_position': True,
                'entry_price': self.position['entry_price'],
                'rsi_entry': self.position.get('rsi_entry', 0),
                'hold_time': time.time() - self.entry_time,
            }
        return {'symbol': self.symbol, 'in_position': False}

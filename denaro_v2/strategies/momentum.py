#!/usr/bin/env python3
"""
DENARO V2 - Momentum Scalper Strategy
Fast breakout trading with volume confirmation and tight stops.
"""
import asyncio
import logging
import time

logger = logging.getLogger("Denaro.Momentum")


class MomentumScalper:
    """Momentum breakout scalping strategy."""

    def __init__(self, exchange, execution, risk_manager, scanner, signals, config: dict = None):
        self.exchange = exchange
        self.execution = execution
        self.risk = risk_manager
        self.scanner = scanner
        self.signals = signals
        self.config = config or {}

        self.symbol = self.config.get('symbol', 'SOL/EUR')
        self.timeframe = self.config.get('timeframe', '1m')
        self.base_order_eur = self.config.get('base_order_eur', 5.0)
        self.tp_pct = self.config.get('tp_pct', 0.008)  # 0.8%
        self.sl_pct = self.config.get('sl_pct', 0.005)  # 0.5%
        self.min_vol_ratio = self.config.get('min_vol_ratio', 1.5)
        self.min_score = self.config.get('min_score', 0.3)

        self.position = None
        self.entry_time = 0
        self.max_hold_time = 3600  # 1 hour max

    async def run_cycle(self, price: float, balance: dict) -> bool:
        """Run one cycle of the momentum scalper."""
        eur_free = balance.get('EUR', {}).get('free', 0)

        # If in position, check exit conditions
        if self.position:
            return await self._manage_position(price, balance)

        # Look for entry signals
        return await self._look_for_entry(price, eur_free)

    async def _manage_position(self, price: float, balance: dict) -> bool:
        """Manage open position."""
        entry_price = self.position['entry_price']
        pnl = (price - entry_price) / entry_price

        # Take profit
        if pnl >= self.tp_pct:
            await self._exit_position(price, "TP")
            return True

        # Stop loss
        if pnl <= -self.sl_pct:
            await self._exit_position(price, "SL")
            return True

        # Time stop
        if time.time() - self.entry_time > self.max_hold_time:
            await self._exit_position(price, "TIME")
            return True

        # Signal-based exit
        ohlcv = await self.scanner.fetch_ohlcv(self.symbol, self.timeframe, 20)
        if ohlcv:
            signal = self.signals.analyze(self.symbol, price, ohlcv)
            if signal['signal'] in ('STRONG_SELL', 'SELL') and pnl > 0:
                await self._exit_position(price, "SIGNAL")
                return True

        return False

    async def _look_for_entry(self, price: float, eur_free: float) -> bool:
        """Look for momentum entry signals."""
        if eur_free < self.base_order_eur:
            return False

        # Fetch OHLCV
        ohlcv = await self.scanner.fetch_ohlcv(self.symbol, self.timeframe, 50)
        if not ohlcv or len(ohlcv) < 20:
            return False

        # Get signal
        orderbook = self.scanner.orderbooks.get(self.symbol)
        signal = self.signals.analyze(self.symbol, price, ohlcv, orderbook)

        # Check for strong buy signal with volume confirmation
        if signal['signal'] in ('STRONG_BUY', 'BUY') and signal['score'] >= self.min_score:
            vol_ratio = signal['factors'].get('vol_ratio', 1)
            if vol_ratio < self.min_vol_ratio:
                return False

            # Calculate position size
            atr_pct = signal['factors'].get('atr_pct', 0.02)
            amount = self.risk.get_position_size(self.symbol, price, atr_pct / 100)
            if amount <= 0:
                return False

            # Check risk
            risk_ok = await self.risk.check_entry(self.symbol, 'buy', amount, price)
            if not risk_ok:
                return False

            # Place entry
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
                    'tp_price': tp_price,
                    'sl_price': sl_price,
                    'order_id': order['id'],
                }
                self.entry_time = time.time()
                logger.info(f"Momentum ENTRY {self.symbol} @ {price} | "
                            f"score={signal['score']:.2f} vol={vol_ratio:.1f}x "
                            f"TP={tp_price} SL={sl_price}")
                return True

        return False

    async def _exit_position(self, price: float, reason: str):
        """Exit position."""
        if not self.position:
            return

        pnl = (price - self.position['entry_price']) / self.position['entry_price']
        pnl_eur = pnl * self.position['entry_price'] * self.position['amount']

        # Cancel any pending orders for this position
        await self.execution.cancel_all_orders(self.symbol)

        # Market sell to exit
        await self.execution.execute_exit(
            self.symbol, self.position['amount'] * 0.997,
            market=True
        )

        self.risk.record_trade(self.symbol, pnl_eur)

        logger.info(f"Momentum EXIT {self.symbol} @ {price} | "
                     f"reason={reason} pnl={pnl*100:.2f}% ({pnl_eur:.2f})")

        self.position = None

    def get_status(self) -> dict:
        """Get scalper status."""
        if self.position:
            return {
                'symbol': self.symbol,
                'in_position': True,
                'entry_price': self.position['entry_price'],
                'amount': self.position['amount'],
                'hold_time': time.time() - self.entry_time,
            }
        return {
            'symbol': self.symbol,
            'in_position': False,
        }

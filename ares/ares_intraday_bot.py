"""
ARES INTRADAY TREND BOT — v1.0
Scelta: SMA crossover veloce per trend intraday.
Trading: SOL/EUR con ordini LIMIT e TP/SL.
Budget: max 30€, base order 10€, TP 0.8%, SL 0.4%.
"""
import os, json, asyncio
from collections import deque
from denaro_opportunistico_core import DenaroOpportunisticCore

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class AresIntradayTrendBot(DenaroOpportunisticCore):
    """Trend-following bot using SMA crossover on 1m candles."""

    def __init__(self):
        super().__init__(bot_name="AresIntraday")
        self.load_config("ares_config.json")
        self.symbol = self.config.get("symbol", "SOL/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.base_asset = self.symbol.split("/")[0]

        # Price history for indicators
        self.close_prices = deque(maxlen=40)  # 2x window for safety
        self.current_price = 0.0

        # Position tracking
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0  # in base asset (e.g., SOL)
        self.order_id = None
        self.order_type = None  # 'BUY' or 'SELL'

    # ── Indicator helpers ──────────────────────────────────────
    def _sma(self, period):
        if len(self.close_prices) < period:
            return None
        return sum(list(self.close_prices)[-period:]) / period

    def _generate_signal(self):
        """SMA(10) vs SMA(20) crossover with 0.05% buffer."""
        if len(self.close_prices) < 20:
            return "HOLD"

        price = self.close_prices[-1]
        fast = self._sma(10)
        slow = self._sma(20)
        if fast is None or slow is None:
            return "HOLD"

        prev_fast = self._sma(11)
        prev_slow = self._sma(21)

        # Crossover detection: fast crosses ABOVE slow
        if prev_fast is not None and prev_slow is not None:
            if prev_fast <= prev_slow and fast > slow and price > fast * 1.0003:
                return "BUY"
            if prev_fast >= prev_slow and fast < slow and price < fast * 0.9997:
                return "SELL"
        return "HOLD"

    def _calc_position_size(self, balance_eur):
        """Calculate how much to buy based on config limits."""
        base_amount = self.config.get("base_order_eur", 10.0)
        max_invest = self.config.get("max_investment_eur", 30.0)
        price = self.current_price
        if price <= 0:
            return 0

        # Clamp to available balance and max investment
        amount = min(base_amount, balance_eur, max_invest)
        # Enforce MIN_NOTIONAL (5€ minimum)
        if amount < 5.0:
            return 0
        # Convert EUR amount to asset quantity
        return round(amount / price * 0.999, 6)  # 0.1% buffer for rounding

    def _calc_tp_sl(self, entry_price, side):
        """Calculate TP and SL prices."""
        tp_pct = self.config.get("take_profit_pct", 0.008)   # 0.8%
        sl_pct = self.config.get("stop_loss_pct", 0.004)     # 0.4%
        if side == "BUY":
            return entry_price * (1 + tp_pct), entry_price * (1 - sl_pct)
        return entry_price * (1 - tp_pct), entry_price * (1 + sl_pct)

    # ── Core strategy ──────────────────────────────────────────
    async def run_strategy(self):
        self.logger.info(f"=== Ares cycle: {self.symbol} @ {self.current_price:.2f} ===")

        # 1. Sync state with exchange (check open orders, positions)
        await self._sync_state()

        # 2. Fetch fresh OHLCV
        await self._fetch_ohlcv()

        # 3. Generate signal
        signal = self._generate_signal()
        self.logger.info(f"Signal: {signal} | In position: {self.in_position} | History: {len(self.close_prices)} candles")

        # 4. Execute
        if signal == "BUY" and not self.in_position:
            await self._execute_buy()
        elif signal == "SELL" and self.in_position:
            await self._execute_sell()
        elif self.in_position:
            await self._check_tp_sl()

    async def _fetch_ohlcv(self):
        """Fetch latest OHLCV candles."""
        try:
            ohlcv = await self.exchange.fetch_ohlcv(
                self.symbol, timeframe=self.timeframe, limit=40
            )
            for candle in ohlcv:
                self.close_prices.append(candle[4])  # close
            if ohlcv:
                self.current_price = ohlcv[-1][4]
        except Exception as e:
            self.logger.error(f"OHLCV fetch error: {e}")

    async def _sync_state(self):
        """Sync position state with exchange — check open orders."""
        try:
            open_orders = await self.exchange.fetch_open_orders(self.symbol)
            # Find our TP/SL orders
            buy_orders = [o for o in open_orders if o['side'] == 'buy']
            sell_orders = [o for o in open_orders if o['side'] == 'sell']

            if not self.in_position and sell_orders:
                # We have a position (sell orders exist = we're in a buy)
                self.in_position = True
                # Entry price is somewhere between the buys
                self.logger.info(f"Synced: detected in position via {len(sell_orders)} sell orders")

            if self.in_position and not sell_orders and not buy_orders:
                # Position was closed externally
                self.in_position = False
                self.entry_price = 0.0
                self.entry_amount = 0.0
                self.logger.info("Position closed externally.")

        except Exception as e:
            self.logger.error(f"Sync error: {e}")

    async def _execute_buy(self):
        """Execute buy entry with limit order at current price + buffer."""
        bal = await self.fetch_balance("EUR")
        amount = self._calc_position_size(bal)
        if amount <= 0:
            self.logger.info(f"Buy skipped: insufficient balance ({bal:.2f}€) or <5€")
            return

        # Place limit buy slightly above current price (+0.05%)
        buy_price = round(self.current_price * 1.0005, 2)
        order = await self.create_limit_buy_order(self.symbol, amount, buy_price)
        if order and order.get('id'):
            self.entry_price = buy_price
            self.entry_amount = amount
            self.in_position = True
            self.order_id = order['id']
            self.order_type = 'BUY'

            # Place TP and SL as limit orders
            tp, sl = self._calc_tp_sl(buy_price, "BUY")
            await self.create_limit_sell_order(self.symbol, amount, round(tp, 2))
            await self.create_limit_sell_order(self.symbol, amount, round(sl, 2))
            self.logger.info(f"✅ BUY {amount} @ {buy_price} | TP {tp:.2f} | SL {sl:.2f}")

    async def _execute_sell(self):
        """If SHORT signal — close position with sell order."""
        try:
            # Check balance of base asset
            bal = await self.fetch_balance(self.base_asset)
            if bal <= 0:
                self.logger.info("No asset balance to sell.")
                return

            # Cancel existing TP/SL orders first
            await self._cancel_order_by_side('sell')

            # Place market sell to exit
            order = await self.exchange.create_market_sell_order(
                self.symbol, round(bal * 0.999, 6)
            )
            self.in_position = False
            self.entry_price = 0.0
            self.entry_amount = 0.0
            self.logger.info(f"✅ SELL signal — closed position @ market")
        except Exception as e:
            self.logger.error(f"SELL failed: {e}")

    async def _check_tp_sl(self):
        """Check if TP/SL hit and update state."""
        try:
            orders = await self.exchange.fetch_orders(self.symbol, limit=10)
            # Check for filled orders
            filled = [o for o in orders if o['status'] == 'closed' and o['side'] == 'sell']
            if filled:
                last_fill = filled[-1]
                pnl = ((last_fill['price'] - self.entry_price) / self.entry_price * 100) if self.entry_price != 0 else 0
                self.logger.info(f"📊 TP/SL hit! Filled @ {last_fill['price']:.2f} | PnL: {pnl:.2f}%")
                self.in_position = False
                self.entry_price = 0.0
                self.entry_amount = 0.0
        except Exception as e:
            self.logger.error(f"TP/SL check error: {e}")

    async def _cancel_order_by_side(self, side):
        """Cancel all open orders of given side."""
        try:
            orders = await self.exchange.fetch_open_orders(self.symbol)
            for o in orders:
                if o['side'] == side:
                    await self.exchange.cancel_order(o['id'], self.symbol)
                    self.logger.info(f"Cancelled {side} order {o['id']}")
        except Exception as e:
            self.logger.error(f"Cancel error: {e}")


# ── Entry point ────────────────────────────────────────────────
if __name__ == "__main__":
    async def main():
        bot = AresIntradayTrendBot()
        await bot.start()

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Ares bot stopped.")

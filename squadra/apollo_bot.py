"""
Apollo — Arbitrage Bot (Pair Trading) v3.
Delega la logica di strategia al modulo strategies/apollo_strategy.py.
"""
import asyncio, time
from core import DenaroOpportunisticCore
from strategies import apollo_signal

class ApolloArbitrageBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Apollo", config_file="apollo.json", test_mode=test_mode)
        self.symbol_a = self.config.get("symbol_a", "ETH/EUR")
        self.symbol_b = self.config.get("symbol_b", "BTC/EUR")
        self.timeframe = self.config.get("timeframe", "5m")
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.z_entry = self.config.get("z_entry", 2.0)
        self.z_exit = self.config.get("z_exit", 0.5)
        self.tp_pct = self.config.get("take_profit_pct", 0.006)
        self.sl_pct = self.config.get("stop_loss_pct", 0.004)
        self.ratio_history = []
        self.in_position = False
        self.position_type = None  # "LONG_RATIO" or "SHORT_RATIO"
        self.entry_ratio = 0.0
        self.entry_price_a = 0.0
        self.entry_price_b = 0.0
        self.amount_a = 0.0
        self.amount_b = 0.0

    async def run_strategy(self):
        ohlcv_a = await self.fetch_ohlcv(self.symbol_a, self.timeframe, limit=50)
        ohlcv_b = await self.fetch_ohlcv(self.symbol_b, self.timeframe, limit=50)
        if not ohlcv_a or not ohlcv_b:
            return

        signal = apollo_signal(
            ohlcv_a, ohlcv_b, self.ratio_history,
            z_entry=self.z_entry, z_exit=self.z_exit,
        )
        action = signal["action"]
        z_score = signal["z_score"]
        ratio = signal["ratio"]
        price_a = signal["current_price_a"]
        price_b = signal["current_price_b"]

        # Update history from strategy output
        if "updated_history" in signal:
            self.ratio_history = signal["updated_history"]

        base_a = self.symbol_a.split("/")[0]
        base_b = self.symbol_b.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))

        # TP/SL check (Apollo uses ratio movement for TP/SL, not price)
        if self.in_position and self.entry_ratio > 0:
            ratio_pnl = (ratio - self.entry_ratio) / self.entry_ratio
            if abs(ratio_pnl) >= self.tp_pct:
                await self._close_position(price_a, price_b)
                self.logger.info(f"APOLLO TP: ratio moved {ratio_pnl*100:.2f}%")
                return
            elif abs(ratio_pnl) >= self.sl_pct:
                await self._close_position(price_a, price_b)
                self.logger.info(f"APOLLO SL: ratio moved {ratio_pnl*100:.2f}%")
                return
            # Exit when ratio reverts
            if action == "EXIT":
                await self._close_position(price_a, price_b)
                self.logger.info(f"APOLLO EXIT: ratio reverted (z={z_score:.2f})")
                return

        # Entry: ratio over-extended
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur * 2:
            # Ratio too low -> long ratio -> buy symbol_a (ETH)
            amt_a = (self.base_order_eur / price_a) * 0.997
            if amt_a > 0:
                order = await self.create_limit_buy(self.symbol_a, amt_a, price_a * 1.001)
                if order:
                    self.in_position = True
                    self.position_type = "LONG_RATIO"
                    self.entry_ratio = ratio
                    self.entry_price_a = price_a
                    self.amount_a = amt_a
                    self.logger.info(f"APOLLO ENTRY LONG RATIO (z={z_score:.2f}): bought {self.symbol_a}")
                    self.save_position_to_db()

        elif action == "SELL" and not self.in_position and free_eur >= self.base_order_eur * 2:
            # Ratio too high -> short ratio -> buy symbol_b (BTC)
            amt_b = (self.base_order_eur / price_b) * 0.997
            if amt_b > 0:
                order = await self.create_limit_buy(self.symbol_b, amt_b, price_b * 1.001)
                if order:
                    self.in_position = True
                    self.position_type = "SHORT_RATIO"
                    self.entry_ratio = ratio
                    self.entry_price_b = price_b
                    self.amount_b = amt_b
                    self.logger.info(f"APOLLO ENTRY SHORT RATIO (z={z_score:.2f}): bought {self.symbol_b}")
                    self.save_position_to_db()

        self.logger.info(f"Apollo | Ratio: {ratio:.4f} | Z: {z_score:.2f} | {action} | Pos: {self.in_position} | EUR: {free_eur:.2f}")

    # ── Apollo-specific DB persistence ────────────────────────
    def save_position_to_db(self):
        self.db.save_bot_state(
            bot_name=self.bot_name,
            is_in_position=self.in_position,
            entry_price=self.entry_ratio if self.in_position else 0.0,
            quantity=self.amount_a or self.amount_b or 0.0,
            tp=self.tp_pct,
            sl=self.sl_pct,
            entry_time=time.time(),
            exchange_name='binance',
        )

    def load_position_from_db(self):
        state = self.db.load_bot_state(self.bot_name)
        if state and state.get('is_in_position') and state.get('quantity', 0) > 0:
            self.in_position = True
            self.entry_ratio = state['entry_price']
            self.position_type = "LONG_RATIO"
            self.amount_a = state['quantity']
            self.entry_price_a = 0
            self.logger.info(
                f"♻️ Apollo restored: {self.position_type} with ratio {self.entry_ratio:.4f}, "
                f"qty {self.amount_a:.4f} {self.symbol_a}")
            return True
        return False

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            if self.test_mode:
                self.logger.info(f"🧪 Apollo startup: restored position (test mode, skipping balance check)")
                return
            bal = await self.exchange.fetch_balance()
            eth_bal = float(bal.get(self.symbol_a.split('/')[0], {}).get('free', 0) or 0)
            btc_bal = float(bal.get(self.symbol_b.split('/')[0], {}).get('free', 0) or 0)
            if btc_bal > eth_bal:
                self.position_type = "SHORT_RATIO"
                self.amount_a = 0
                self.amount_b = btc_bal
                self.entry_price_b = 0
                await self.startup_validate_position(self.symbol_b.split('/')[0])
            else:
                self.position_type = "LONG_RATIO"
                self.amount_b = 0
                await self.startup_validate_position(self.symbol_a.split('/')[0])

    async def _close_position(self, price_a, price_b):
        if self.position_type == "LONG_RATIO" and self.amount_a > 0:
            if not await self.validate_balance_before_sell(self.symbol_a.split('/')[0], self.amount_a):
                self.in_position = False
                self.position_type = None
                self.entry_ratio = 0
                self.entry_price_a = 0
                self.entry_price_b = 0
                self.amount_a = 0
                self.amount_b = 0
                self.save_position_to_db()
                return
            amt = self.amount_a * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol_a, amt, price_a * 0.999)
                pnl = (price_a - self.entry_price_a) / self.entry_price_a * 100
                self.logger.info(f"APOLLO CLOSE LONG: {self.symbol_a} PnL={pnl:.2f}%")
        elif self.position_type == "SHORT_RATIO" and self.amount_b > 0:
            if not await self.validate_balance_before_sell(self.symbol_b.split('/')[0], self.amount_b):
                self.in_position = False
                self.position_type = None
                self.entry_ratio = 0
                self.entry_price_a = 0
                self.entry_price_b = 0
                self.amount_a = 0
                self.amount_b = 0
                self.save_position_to_db()
                return
            amt = self.amount_b * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol_b, amt, price_b * 0.999)
                pnl = (price_b - self.entry_price_b) / self.entry_price_b * 100
                self.logger.info(f"APOLLO CLOSE SHORT: {self.symbol_b} PnL={pnl:.2f}%")
        self.in_position = False
        self.position_type = None
        self.entry_ratio = 0
        self.entry_price_a = 0
        self.entry_price_b = 0
        self.amount_a = 0
        self.amount_b = 0
        self.save_position_to_db()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = ApolloArbitrageBot()
    asyncio.run(bot.start())

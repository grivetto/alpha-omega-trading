"""
Ares — Intraday Trend Bot (v3).
Delega la logica di strategia al modulo strategies/ares_strategy.py.
"""
import asyncio
from core import DenaroOpportunisticCore
from strategies import ares_signal

class AresIntradayTrendBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Ares", config_file="ares.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "ETH/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.fast_period = self.config.get("fast_sma", 5)
        self.slow_period = self.config.get("slow_sma", 20)
        self.base_order_eur = self.config.get("base_order_eur", 10.0)
        self.max_investment = self.config.get("max_investment_eur", 30.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.008)
        self.sl_pct = self.config.get("stop_loss_pct", 0.004)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0

    async def run_strategy(self):
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        if not ohlcv:
            return

        signal = ares_signal(ohlcv, fast_period=self.fast_period, slow_period=self.slow_period)
        action = signal["action"]
        current_price = signal["current_price"]
        atr = signal["atr"]

        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))
        free_asset = float(self.balance.get(base, 0))

        # Check TP/SL if in position
        if self.in_position and self.entry_price > 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            if pnl_pct >= self.tp_pct:
                self.logger.info(f"TP hit: {pnl_pct*100:.2f}%")
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return
            elif pnl_pct <= -self.sl_pct:
                self.logger.info(f"SL hit: {pnl_pct*100:.2f}%")
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return

        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            total_invested = self.base_order_eur + (float(self.entry_amount * self.entry_price) if self.in_position else 0)
            if total_invested <= self.max_investment:
                amount = (self.base_order_eur / current_price) * 0.997
                if amount > 0:
                    order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                    if order:
                        self.in_position = True
                        self.entry_price = current_price
                        self.entry_amount = amount
                        self.logger.info(f"ARES ENTRY {self.symbol} @ {current_price:.2f} | reason: {signal['reason']}")
                        self.save_position_to_db()
        elif action == "SELL" and self.in_position:
            if not await self.validate_balance_before_sell(base, self.entry_amount):
                return
            amt = self.entry_amount * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                self.in_position = False
                pnl = (current_price - self.entry_price) / self.entry_price * 100
                self.logger.info(f"ARES EXIT {self.symbol} @ {current_price:.2f} (PnL: {pnl:.2f}%) | reason: {signal['reason']}")
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()

        self.logger.info(f"Ares | {self.symbol} @ {current_price:.2f} | {action} | ATR: {atr:.2f} | Pos: {self.in_position} | EUR: {free_eur:.2f} | {signal['reason']}")

    async def on_startup(self):
        self.logger.info(f"[STARTUP] loading position from DB (bot={self.bot_name})")
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split('/')[0])
        else:
            self.logger.info(f"[STARTUP] No position found in DB, starting fresh.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = AresIntradayTrendBot()
    asyncio.run(bot.start())

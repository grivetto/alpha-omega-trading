"""
Ares — Intraday Trend Bot.
Segue trend con SMA crossover su ETH/EUR.
TP/SL basati su ATR.
"""
import asyncio
from core import DenaroOpportunisticCore

class AresIntradayTrendBot(DenaroOpportunisticCore):
    def __init__(self):
        super().__init__(bot_name="Ares", config_file="ares.json")
        self.symbol = self.config.get("symbol", "ETH/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.fast_period = self.config.get("fast_sma", 5)
        self.slow_period = self.config.get("slow_sma", 20)
        self.base_order_eur = self.config.get("base_order_eur", 10.0)
        self.max_investment = self.config.get("max_investment_eur", 30.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.008)
        self.sl_pct = self.config.get("stop_loss_pct", 0.004)
        self.price_history = []
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self.atr = 0.0

    def _calculate_sma(self, data, period):
        if len(data) < period:
            return None
        return sum(data[-period:]) / period

    def _calculate_atr(self, ohlcv, period=14):
        if len(ohlcv) < period + 1:
            return 0.0
        trs = []
        for i in range(1, len(ohlcv)):
            high, low, prev_close = ohlcv[i][2], ohlcv[i][3], ohlcv[i-1][4]
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            trs.append(tr)
        return sum(trs[-period:]) / period

    def _generate_signal(self):
        if len(self.price_history) < self.slow_period:
            return "HOLD"
        fast_sma = self._calculate_sma(self.price_history, self.fast_period)
        slow_sma = self._calculate_sma(self.price_history, self.slow_period)
        if fast_sma is None or slow_sma is None:
            return "HOLD"
        prev_fast = self._calculate_sma(self.price_history[:-1], self.fast_period)
        prev_slow = self._calculate_sma(self.price_history[:-1], self.slow_period)
        if prev_fast is None or prev_slow is None:
            return "HOLD"
        current_price = self.price_history[-1]
        if prev_fast <= prev_slow and fast_sma > slow_sma and current_price > fast_sma:
            return "BUY"
        elif prev_fast >= prev_slow and fast_sma < slow_sma and current_price < fast_sma:
            return "SELL"
        return "HOLD"

    async def run_strategy(self):
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        if not ohlcv:
            return
        self.price_history = [c[4] for c in ohlcv]  # closing prices
        self.atr = self._calculate_atr(ohlcv)
        current_price = self.price_history[-1]
        signal = self._generate_signal()
        
        base_symbol = self.symbol.replace("/", "")
        free_eur = float(self.balance.get("EUR", 0))
        free_asset = float(self.balance.get(self.symbol.split("/")[0], 0))

        # Check TP/SL if in position
        if self.in_position and self.entry_price > 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            if pnl_pct >= self.tp_pct:
                self.logger.info(f"TP hit: {pnl_pct*100:.2f}%")
                amt = self.entry_amount * 0.997  # lascia 0.3% per fees
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
            elif pnl_pct <= -self.sl_pct:
                self.logger.info(f"SL hit: {pnl_pct*100:.2f}%")
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0

        if signal == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            total_invested = self.base_order_eur + (float(self.entry_amount * self.entry_price) if self.in_position else 0)
            if total_invested <= self.max_investment:
                amount = (self.base_order_eur / current_price) * 0.997
                if amount > 0:
                    order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                    if order:
                        self.in_position = True
                        self.entry_price = current_price
                        self.entry_amount = amount
                        self.logger.info(f"ARES ENTRY {self.symbol} @ {current_price:.2f}")
        elif signal == "SELL" and self.in_position:
            amt = self.entry_amount * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                self.in_position = False
                pnl = (current_price - self.entry_price) / self.entry_price * 100
                self.logger.info(f"ARES EXIT {self.symbol} @ {current_price:.2f} (PnL: {pnl:.2f}%)")
                self.entry_price = 0
                self.entry_amount = 0

        self.logger.info(f"Ares | {self.symbol} @ {current_price:.2f} | Signal: {signal} | Pos: {self.in_position} | EUR: {free_eur:.2f}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = AresIntradayTrendBot()
    asyncio.run(bot.start())

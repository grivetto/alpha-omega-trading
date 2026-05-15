"""
Apollo — Arbitrage Bot (Pair Trading).
Sfrutta la mean reversion del ratio ETH/BTC.
Quando il ratio devia >2σ dalla media, scommette sulla convergenza.
Opera su ETH/EUR e BTC/EUR sulla stesso exchange (no multi-exchange richiesto).
"""
import asyncio, statistics, math
from core import DenaroOpportunisticCore

class ApolloArbitrageBot(DenaroOpportunisticCore):
    def __init__(self):
        super().__init__(bot_name="Apollo", config_file="apollo.json")
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
        closes_a = [c[4] for c in ohlcv_a]
        closes_b = [c[4] for c in ohlcv_b]
        min_len = min(len(closes_a), len(closes_b))
        closes_a, closes_b = closes_a[-min_len:], closes_b[-min_len:]
        
        # Ratio = ETH price / BTC price
        ratio = closes_a[-1] / closes_b[-1] if closes_b[-1] > 0 else 0
        self.ratio_history.append(ratio)
        if len(self.ratio_history) > 100:
            self.ratio_history = self.ratio_history[-100:]
        
        current_price_a = closes_a[-1]
        current_price_b = closes_b[-1]
        
        base_a = self.symbol_a.split("/")[0]
        base_b = self.symbol_b.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))
        free_a = float(self.balance.get(base_a, 0))
        free_b = float(self.balance.get(base_b, 0))

        # Calcola Z-score
        if len(self.ratio_history) < 20:
            self.logger.info(f"Apollo | Ratio: {ratio:.4f} | Building history ({len(self.ratio_history)}/20)")
            return
        
        mean_ratio = statistics.mean(self.ratio_history)
        std_ratio = statistics.stdev(self.ratio_history) if len(self.ratio_history) > 1 else 0.001
        z_score = (ratio - mean_ratio) / std_ratio if std_ratio > 0 else 0

        # TP/SL check
        if self.in_position and self.entry_ratio > 0:
            ratio_pnl = (ratio - self.entry_ratio) / self.entry_ratio
            if abs(ratio_pnl) >= self.tp_pct:
                await self._close_position(current_price_a, current_price_b)
                self.logger.info(f"APOLLO TP: ratio moved {ratio_pnl*100:.2f}%")
                return
            elif abs(ratio_pnl) >= self.sl_pct:
                await self._close_position(current_price_a, current_price_b)
                self.logger.info(f"APOLLO SL: ratio moved {ratio_pnl*100:.2f}%")
                return
            # Exit when ratio reverts
            if abs(z_score) < self.z_exit:
                await self._close_position(current_price_a, current_price_b)
                self.logger.info(f"APOLLO EXIT: ratio reverted (z={z_score:.2f})")
                return

        # Entry: ratio over-extended
        if not self.in_position and free_eur >= self.base_order_eur * 2:
            if z_score > self.z_entry:
                # Ratio troppo alto → ratio scenderà → short ratio (compra B, vendi A)
                # Ma shortare ETH non è possibile su spot → LONG BTC, LONG ETH ma in proporzioni inverse
                # Semplificazione: compra B (BTC) con tutto il budget
                amt_b = (self.base_order_eur / current_price_b) * 0.997
                if amt_b > 0:
                    order = await self.create_limit_buy(self.symbol_b, amt_b, current_price_b * 1.001)
                    if order:
                        self.in_position = True
                        self.position_type = "SHORT_RATIO"
                        self.entry_ratio = ratio
                        self.entry_price_b = current_price_b
                        self.amount_b = amt_b
                        self.logger.info(f"APOLLO ENTRY SHORT RATIO (z={z_score:.2f}): bought {self.symbol_b}")
                        
            elif z_score < -self.z_entry:
                # Ratio troppo basso → ratio salirà → long ratio (compra A)
                amt_a = (self.base_order_eur / current_price_a) * 0.997
                if amt_a > 0:
                    order = await self.create_limit_buy(self.symbol_a, amt_a, current_price_a * 1.001)
                    if order:
                        self.in_position = True
                        self.position_type = "LONG_RATIO"
                        self.entry_ratio = ratio
                        self.entry_price_a = current_price_a
                        self.amount_a = amt_a
                        self.logger.info(f"APOLLO ENTRY LONG RATIO (z={z_score:.2f}): bought {self.symbol_a}")

        self.logger.info(f"Apollo | Ratio: {ratio:.4f} | Z: {z_score:.2f} | Pos: {self.in_position} | EUR: {free_eur:.2f}")

    async def _close_position(self, price_a, price_b):
        """Close existing position"""
        if self.position_type == "LONG_RATIO" and self.amount_a > 0:
            amt = self.amount_a * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol_a, amt, price_a * 0.999)
                pnl = (price_a - self.entry_price_a) / self.entry_price_a * 100
                self.logger.info(f"APOLLO CLOSE LONG: {self.symbol_a} PnL={pnl:.2f}%")
        elif self.position_type == "SHORT_RATIO" and self.amount_b > 0:
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

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = ApolloArbitrageBot()
    asyncio.run(bot.start())

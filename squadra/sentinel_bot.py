"""
SENTINEL v2 — Mean Reversion BNB/EUR
Portato nel framework Denaro v5.1.
Strategy: RSI(5) + EMA(20) distance on 5m candles.
Entry on oversold/overbought extremes → fade the move.
TP 0.5%, SL 0.35%. Max 10€/trade. Kill-switch + circuit breaker integrati.
"""
import asyncio, statistics
from core import DenaroOpportunisticCore


class SentinelMeanRevBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Sentinel", config_file="sentinel.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "BNB/EUR")
        self.timeframe = self.config.get("timeframe", "5m")
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.005)
        self.sl_pct = self.config.get("stop_loss_pct", 0.0035)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0

    def _calc_rsi(self, prices, period=5):
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[-i] - prices[-i - 1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = statistics.mean(gains[:period]) if gains else 0
        avg_loss = statistics.mean(losses[:period]) if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _ema(self, closes, period=20):
        """Simple EMA approximation using weighted average."""
        if len(closes) < period:
            return statistics.mean(closes)
        k = 2 / (period + 1)
        ema = statistics.mean(closes[:period])
        for price in closes[period:]:
            ema = price * k + ema * (1 - k)
        return ema

    def _get_signal(self, ohlcv):
        if len(ohlcv) < 21:
            return "HOLD", 0.0, 50.0, 0.0
        closes = [c[4] for c in ohlcv]
        price = closes[-1]
        r5 = self._calc_rsi(closes, 5)
        ema20 = self._ema(closes, 20)
        ema_dist = (price - ema20) / max(ema20, 0.001) * 100

        # Oversold — buy signal (RSI < 25 → price over-extended down)
        if r5 < 25:
            conf = min(1.0, (25 - r5) / 20)
            return "BUY", conf, r5, ema_dist

        # Overbought — sell signal (RSI > 75 → price over-extended up)
        if r5 > 75:
            conf = min(1.0, (r5 - 75) / 20)
            return "SELL", conf, r5, ema_dist

        # Secondary: extreme EMA deviation
        if ema_dist < -2.0 and r5 < 40:
            return "BUY", 0.5, r5, ema_dist
        if ema_dist > 2.0 and r5 > 60:
            return "SELL", 0.5, r5, ema_dist

        return "HOLD", 0.0, r5, ema_dist

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split("/")[0])
        else:
            self.logger.info("=== SENTINEL STARTUP: no position found ===")

    async def run_strategy(self):
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        if not ohlcv:
            return

        current_price = ohlcv[-1][4]
        action, confidence, rsi, ema_dist = self._get_signal(ohlcv)
        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))

        # ── TP/SL check ──
        if self.in_position and self.entry_price > 0:
            pnl = (current_price - self.entry_price) / self.entry_price
            hit = False
            if pnl >= self.tp_pct:
                if await self.validate_balance_before_sell(base, self.entry_amount):
                    amt = self.entry_amount * 0.997
                    if amt > 0:
                        await self.create_limit_sell(self.symbol, amt,
                                                     current_price * 0.999)
                        self._record_completed_trade(pnl)
                        self.logger.info(
                            f"SENTINEL TP: +{pnl * 100:.2f}% @ {current_price:.2f}")
                        hit = True
            elif pnl <= -self.sl_pct:
                if await self.validate_balance_before_sell(base, self.entry_amount):
                    amt = self.entry_amount * 0.997
                    if amt > 0:
                        self.logger.warning(
                            f"☠️ SENTINEL SL: {pnl * 100:.2f}% — MARKET SELL {self.symbol}")
                        await self.create_market_sell(self.symbol, amt)
                        self._record_completed_trade(pnl)
                        self.logger.info(
                            f"SENTINEL SL: {pnl * 100:.2f}% @ {current_price:.2f}")
                        hit = True
            if hit:
                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()
                return

        # ── ENTRY ──
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            amount = (self.base_order_eur / current_price) * 0.997
            if amount > 0 and self.base_order_eur <= self.max_investment:
                order = await self.create_limit_buy(self.symbol, amount,
                                                    current_price * 1.001)
                if order:
                    self._last_entry_price = current_price
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(
                        f"SENTINEL BUY {self.symbol} @ {current_price:.2f} | "
                        f"size={self.base_order_eur:.2f}€ | RSI={rsi:.1f} "
                        f"| EMA%={ema_dist:.2f}% | conf={confidence:.2f}")
                    self.save_position_to_db()

        elif action == "SELL" and self.in_position:
            if await self.validate_balance_before_sell(base, self.entry_amount):
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt,
                                                 current_price * 0.999)
                    pnl = (current_price - self.entry_price) / self.entry_price
                    self._record_completed_trade(pnl)
                    self.logger.info(
                        f"SENTINEL EXIT (signal): {pnl * 100:.2f}% @ "
                        f"{current_price:.2f} | RSI={rsi:.1f}")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
            return

        self.logger.info(
            f"Sentinel | {self.symbol} @ {current_price:.2f} | "
            f"RSI={rsi:.1f} | EMA%={ema_dist:.2f}% | {action} "
            f"| conf={confidence:.2f} | Pos={self.in_position} "
            f"| EUR={free_eur:.2f}")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s - %(name)s - %(message)s")
    bot = SentinelMeanRevBot()
    asyncio.run(bot.start())

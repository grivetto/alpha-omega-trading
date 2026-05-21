"""
Hermes — Sentiment Bot (self-contained).
Analizza sentiment del mercato tramite RSI, volume spike, VWAP.
v3.2: SELL exit da segnale strategia + SL/TP allargati per SOL.
"""
import asyncio, statistics
from core import DenaroOpportunisticCore

class HermesSentimentBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Hermes", config_file="hermes.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "SOL/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.020)
        self.sl_pct = self.config.get("stop_loss_pct", 0.015)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0

    def _calc_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[-i] - prices[-i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = statistics.mean(gains[:period]) if gains else 0
        avg_loss = statistics.mean(losses[:period]) if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_vwap(self, ohlcv):
        if not ohlcv:
            return None
        tp_vol = sum(((c[1] + c[2] + c[3]) / 3) * c[5] for c in ohlcv)
        vol = sum(c[5] for c in ohlcv)
        return tp_vol / vol if vol > 0 else None

    def _get_signal(self, ohlcv):
        if len(ohlcv) < 20:
            return "HOLD", 0.0, 50.0
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        current_price = closes[-1]
        avg_volume = statistics.mean(volumes[-20:]) if volumes else 1
        rsi = self._calc_rsi(closes)
        vwap = self._calc_vwap(ohlcv)

        score = 0.0

        # Volume spike
        if avg_volume > 0:
            vol_ratio = volumes[-1] / avg_volume
            if vol_ratio > 2.0:
                score += 0.3 if current_price > closes[-5] else -0.3

        # RSI extremes
        if rsi < 25:
            score += 0.4
        elif rsi > 75:
            score -= 0.4
        elif rsi < 35:
            score += 0.2
        elif rsi > 65:
            score -= 0.2

        # VWAP position
        if vwap and vwap > 0:
            dist_pct = (current_price - vwap) / vwap * 100
            if dist_pct < -1.5:
                score += 0.2
            elif dist_pct > 1.5:
                score -= 0.2

        score = max(-1, min(1, score))

        if score >= 0.3:
            action = "BUY"
        elif score <= -0.3:
            action = "SELL"
        else:
            action = "HOLD"

        return action, score, rsi

    async def run_strategy(self):
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        if not ohlcv:
            return

        current_price = ohlcv[-1][4]
        action, score, rsi = self._get_signal(ohlcv)

        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))

        # TP/SL check
        if self.in_position and self.entry_price > 0:
            pnl = (current_price - self.entry_price) / self.entry_price
            if pnl >= self.tp_pct:
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.logger.info(f"HERMES TP: +{pnl*100:.2f}% @ {current_price:.2f}")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return
            elif pnl <= -self.sl_pct:
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.logger.info(f"HERMES SL: {pnl*100:.2f}% @ {current_price:.2f}")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return

        # ENTRY
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            amount = (self.base_order_eur / current_price) * 0.997
            if amount > 0:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(f"HERMES ENTRY {self.symbol} @ {current_price:.2f} | score={score:.2f} | RSI={rsi:.1f}")
                    self.save_position_to_db()

        # SELL exit from strategy
        elif action == "SELL" and self.in_position:
            if not await self.validate_balance_before_sell(base, self.entry_amount):
                return
            amt = self.entry_amount * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                pnl = (current_price - self.entry_price) / self.entry_price * 100
                self.logger.info(f"HERMES EXIT (signal): {pnl:.2f}% @ {current_price:.2f} | score={score:.2f}")
                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()
            return

        self.logger.info(f"Hermes | {self.symbol} @ {current_price:.2f} | score={score:.2f} | RSI={rsi:.1f} | {action} | Pos={self.in_position} | EUR={free_eur:.2f}")

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split("/")[0])
        else:
            self.logger.info("=== HERMES STARTUP: no position found ===")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = HermesSentimentBot()
    asyncio.run(bot.start())

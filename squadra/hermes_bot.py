"""
Hermes — Sentiment Bot.
Analizza il "sentiment" del mercato usando indicatori tecnici come proxy:
  - Volume spike (surge anomalo)
  - RSI estremo (ipercomprato/venduto)
  - Prezzo rispetto a VWAP
Genera segnali BUY su paura estrema (RSI<25, volume alto) e SELL su euforia (RSI>75).
Coppia consigliata: SOL/EUR (alta volatilità).
"""
import asyncio, statistics
from core import DenaroOpportunisticCore

class HermesSentimentBot(DenaroOpportunisticCore):
    def __init__(self):
        super().__init__(bot_name="Hermes", config_file="hermes.json")
        self.symbol = self.config.get("symbol", "SOL/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.012)
        self.sl_pct = self.config.get("stop_loss_pct", 0.005)
        self.price_history = []
        self.volume_history = []
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0

    def _calculate_rsi(self, prices, period=14):
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

    def _calculate_vwap(self, ohlcv):
        if not ohlcv:
            return None
        tp_vol = sum((c[1] + c[2] + c[3]) / 3 * c[5] for c in ohlcv)  # typical price * volume
        vol = sum(c[5] for c in ohlcv)
        return tp_vol / vol if vol > 0 else None

    def _sentiment_score(self, ohlcv):
        """Return -1 (bearish) to +1 (bullish) sentiment score"""
        if len(ohlcv) < 20:
            return 0
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        current_price = closes[-1]
        current_volume = volumes[-1]
        avg_volume = statistics.mean(volumes[-20:]) if volumes else 1
        rsi = self._calculate_rsi(closes)
        vwap = self._calculate_vwap(ohlcv)
        
        score = 0.0
        # Volume spike = sentiment forte (direzione determinata dal prezzo)
        if avg_volume > 0:
            vol_ratio = current_volume / avg_volume
            if vol_ratio > 2.0:
                score += 0.3 if current_price > closes[-5] else -0.3
        
        # RSI extremes
        if rsi < 25:
            score += 0.4  # ipervenduto = bullish (rimbalzo)
        elif rsi > 75:
            score -= 0.4  # ipercomprato = bearish (correzione)
        elif rsi < 35:
            score += 0.2
        elif rsi > 65:
            score -= 0.2
        
        # VWAP position
        if vwap and vwap > 0:
            dist = (current_price - vwap) / vwap * 100
            if dist < -1.5:
                score += 0.2  # sotto VWAP = oversold
            elif dist > 1.5:
                score -= 0.2  # sopra VWAP = overbought
        
        return max(-1, min(1, score))

    def _get_signal(self, score):
        if score >= 0.5:
            return "BUY"
        elif score <= -0.5:
            return "SELL"
        return "HOLD"

    async def run_strategy(self):
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        if not ohlcv:
            return
        self.price_history = [c[4] for c in ohlcv]
        self.volume_history = [c[5] for c in ohlcv]
        current_price = self.price_history[-1]
        score = self._sentiment_score(ohlcv)
        signal = self._get_signal(score)
        rsi = self._calculate_rsi(self.price_history)
        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))
        free_asset = float(self.balance.get(base, 0))

        # TP/SL check
        if self.in_position and self.entry_price > 0:
            pnl = (current_price - self.entry_price) / self.entry_price
            if pnl >= self.tp_pct:
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.logger.info(f"HERMES TP: {pnl*100:.2f}%")
                    self.in_position = False
            elif pnl <= -self.sl_pct:
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self.logger.info(f"HERMES SL: {pnl*100:.2f}%")
                    self.in_position = False

        if signal == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            amount = (self.base_order_eur / current_price) * 0.997
            if amount > 0:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(f"HERMES ENTRY {self.symbol} @ {current_price:.2f} (sentiment={score:.2f})")

        self.logger.info(f"Hermes | {self.symbol} @ {current_price:.2f} | Sentiment: {score:.2f} | RSI: {rsi:.1f} | Signal: {signal} | Pos: {self.in_position} | EUR: {free_eur:.2f}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = HermesSentimentBot()
    asyncio.run(bot.start())

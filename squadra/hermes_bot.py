"""
Hermes — Sentiment Bot (v3.2).
Delega la logica di strategia al modulo strategies/hermes_strategy.py.
v3.1: multi-timeframe context (MACD, divergence filter).
v3.2: social sentiment engine (Fear & Greed, X/Twitter, news).
"""
import asyncio
from core import DenaroOpportunisticCore
from strategies import hermes_signal
from utils.indicators import aggregate_timeframes
from utils.sentiment import SentimentEngine

class HermesSentimentBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Hermes", config_file="hermes.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "SOL/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.timeframe_long = self.config.get("timeframe_long", "1h")
        self.long_candles = self.config.get("long_candles", 72)
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.012)
        self.sl_pct = self.config.get("stop_loss_pct", 0.005)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        # Sentiment engine
        sentiment_cfg = self.config.get("sentiment", {})
        self.sentiment_enabled = sentiment_cfg.get("enabled", True)
        self.sentiment_weight = sentiment_cfg.get("weight", 0.15)
        self.sentiment_interval = sentiment_cfg.get("interval_cycles", 10)
        if self.sentiment_enabled:
            self._sentiment_engine = SentimentEngine()
            self._sentiment_cache = None
            self._sentiment_cycle = 0
        self._cycle_count = 0

    async def run_strategy(self):
        self._cycle_count += 1

        # Fetch short timeframe (1m, ~50 candles) + long timeframe (1h, ~72 candles)
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        ohlcv_long = await self.fetch_ohlcv(self.symbol, self.timeframe_long, limit=self.long_candles)
        if not ohlcv:
            return

        # Build multi-timeframe context
        ctx = aggregate_timeframes(ohlcv, ohlcv_long) if ohlcv_long else {}

        # ── Sentiment integration (v3.2) ─────────────────────────
        if self.sentiment_enabled:
            # Refresh sentiment ogni N cicli per non fare troppe chiamate API
            if (self._sentiment_cache is None or
                self._cycle_count % self.sentiment_interval == 0):
                sent = self._sentiment_engine.analyze(self.symbol)
                self._sentiment_cache = sent
            else:
                sent = self._sentiment_cache

            if sent and sent.get("available_sources", 0) > 0:
                ctx["sentiment"] = {
                    "score": sent["overall_score"],
                    "weight": self.sentiment_weight,
                    "sources": sent.get("active_sources", []),
                    "details": sent.get("sources", {}),
                }
                self.logger.info(
                    f"Sentiment {self.symbol}: {sent['overall_score']:.2f} "
                    f"(da {sent['available_sources']} fonti)"
                )

        signal = hermes_signal(ohlcv, ctx=ctx)
        action = signal["action"]
        current_price = signal["current_price"]
        score = signal["score"]
        rsi = signal["rsi"]

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
                    self.logger.info(f"HERMES TP: {pnl*100:.2f}%")
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
                    self.logger.info(f"HERMES SL: {pnl*100:.2f}%")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return

        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            amount = (self.base_order_eur / current_price) * 0.997
            if amount > 0:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(f"HERMES ENTRY {self.symbol} @ {current_price:.2f} | sentiment={score:.2f} | {signal['reason']}")
                    self.save_position_to_db()

        self.logger.info(f"Hermes | {self.symbol} @ {current_price:.2f} | Sentiment: {score:.2f} | RSI: {rsi:.1f} | {action} | Pos: {self.in_position} | EUR: {free_eur:.2f}")

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split('/')[0])
        else:
            self.logger.info(f"=== HERMES STARTUP: no position found ===")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = HermesSentimentBot()
    asyncio.run(bot.start())

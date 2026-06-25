import asyncio
import logging
import time
import re
from typing import Dict, List, Optional
from datetime import datetime, timedelta

from core.engine import DenaroEngine, ExecutionSignal, TradeDirection, Position
from strategies import Strategy


class NewsReactorStrategy(Strategy):
    def __init__(self, config: Dict[str, Any], engine: DenaroEngine):
        super().__init__(config, engine)
        self.config_section = config.get("news_reactor", {})
        self.symbol_keywords = self.config_section.get("symbol_keywords", {})
        self.keyword_weights = self.config_section.get("keyword_weights", {})
        self.sentiment_threshold_bullish = self.config_section.get("sentiment_threshold_bullish", 0.6)
        self.sentiment_threshold_bearish = self.config_section.get("sentiment_threshold_bearish", -0.6)
        self.sentiment_consecutive_readings = self.config_section.get("sentiment_consecutive_readings", 2)
        self.take_profit_bps = self.config_section.get("take_profit_bps", 50)
        self.stop_loss_bps = self.config_section.get("stop_loss_bps", 30)
        self.max_hold_seconds = self.config_section.get("max_hold_seconds", 600)
        self.cooldown_after_trade_seconds = self.config_section.get("cooldown_after_trade_seconds", 300)
        self.max_positions_per_symbol = self.config_section.get("max_positions_per_symbol", 1)
        self.enabled = self.config_section.get("enabled", True)
        self.twitter_check_interval = self.config_section.get("twitter_check_interval_s", 15)
        self.last_twitter_check: float = 0
        self.last_trade_time: float = 0
        self.last_exit_time: float = 0
        self.last_positive_sentiment_time: Dict[str, float] = {}
        self.consecutive_positive: Dict[str, int] = {}
        self.sentiment_history: Dict[str, List[float]] = {}

    def _get_symbol(self) -> str:
        symbols = self.config.get("symbols", ["SOLUSDC", "ADAUSDC", "DOGEUSDC"])
        return symbols[2]

    async def run(self):
        self.running = True
        check_interval = 0.2

        while self.running and not self.engine.shutdown_event.is_set():
            try:
                await self._scan_news()
                await self._manage_positions()

                await asyncio.sleep(check_interval)
                await self.engine.health_monitor.heartbeat(f"strategy_news_{self.symbol}")

            except Exception as e:
                logging.error(f"News reactor strategy error for {self.symbol}: {e}")

    async def _scan_news(self):
        if not self.enabled:
            return

        if time.time() - self.last_exit_time < self.cooldown_after_trade_seconds:
            return

        current_positions = [p for p in self.engine.positions if p.symbol == self.symbol and p.strategy == "news_reactor" and not p.closed]
        if len(current_positions) >= self.max_positions_per_symbol:
            return

        symbol_keywords = self.symbol_keywords.get(self.symbol, [])
        combined_keywords = symbol_keywords + list(self.keyword_weights.keys())

        sentiment = await self._analyze_sentiment(combined_keywords)

        if sentiment > 0 and sentiment >= self.sentiment_threshold_bullish:
            if self.symbol not in self.consecutive_positive:
                self.consecutive_positive[self.symbol] = 0
            self.consecutive_positive[self.symbol] += 1
            self.last_positive_sentiment_time[self.symbol] = time.time()
        elif sentiment < 0 and sentiment <= self.sentiment_threshold_bearish:
            self.consecutive_positive[self.symbol] = 0
        else:
            self.consecutive_positive[self.symbol] = 0

        if self.consecutive_positive.get(self.symbol, 0) >= self.sentiment_consecutive_readings:
            capital = await self.engine._allocate_capital("news_reactor")
            position_size_pct = self.config_section.get("position_size_pct", 0.25)
            capital = capital * position_size_pct

            signal = ExecutionSignal(
                symbol=self.symbol,
                direction=TradeDirection.LONG,
                capital=capital,
                reason=f"News sentiment spike: {sentiment:.3f} (threshold: {self.sentiment_threshold_bullish})",
                strategy="news_reactor",
                priority=1,
                metadata={
                    "price": await self.engine.price_cache.get_latest(self.symbol) or 0,
                    "current_price": await self.engine.price_cache.get_latest(self.symbol) or 0,
                    "sentiment": sentiment,
                    "consecutive_positive": self.consecutive_positive[self.symbol]
                }
            )
            await self.notify_signal(signal)
            self.last_trade_time = time.time()
            self.consecutive_positive[self.symbol] = 0

    async def _analyze_sentiment(self, keywords: List[str]) -> float:
        price = await self.engine.price_cache.get_latest(self.symbol)
        if not price:
            return 0.0

        sentiment = 0.0
        for keyword in keywords:
            weight = self.keyword_weights.get(keyword, 1.0)
            if keyword.lower() in ["elon musk", "moon", "pump"]:
                sentiment += 0.3 * weight
            elif keyword.lower() in ["crash", "dump", "fed", "sec"]:
                sentiment += -0.4 * weight
            elif keyword.lower() in ["cardano", "solana", "dogecoin"]:
                sentiment += 0.1 * weight
        sentiment = min(max(sentiment, -1.0), 1.0)
        return sentiment

    async def _manage_positions(self):
        async with self.lock:
            for position in self.positions[:]:
                if position.symbol == self.symbol and position.strategy == "news_reactor" and not position.closed:
                    await self.check_position(position)

                    if position.exit_time is None:
                        entry_price = position.entry_price
                        price = await self.engine.price_cache.get_latest(self.symbol)
                        if price:
                            duration = time.time() - position.entry_time
                            if duration >= self.max_hold_seconds:
                                position.record_exit(price, "max_hold_exceeded")
                                self.engine.positions.remove(position)
                                logging.info(f"News position {position.id}: max hold time exceeded @ {price:.4f}, PnL ${position.pnl_usdc:.2f}")
                                self.last_exit_time = time.time()
                                continue

                            tp_pct = self.take_profit_bps / 100
                            sl_pct = self.stop_loss_bps / 100

                            if position.direction == TradeDirection.LONG:
                                if price >= entry_price * (1 + tp_pct) or price <= entry_price * (1 - sl_pct):
                                    position.record_exit(price, "news_take_profit_or_stop_loss")
                                    self.engine.positions.remove(position)
                                    logging.info(f"News position {position.id}: exit @ {price:.4f}, PnL ${position.pnl_usdc:.2f}")
                                    self.last_exit_time = time.time()

    async def analyze(self) -> Optional[ExecutionSignal]:
        return None
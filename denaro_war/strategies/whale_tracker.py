import asyncio
import logging
import time
from typing import Dict, List, Optional
from collections import deque

from core.engine import DenaroEngine, ExecutionSignal, TradeDirection, Position
from strategies import Strategy


class WhaleTrackerStrategy(Strategy):
    def __init__(self, config: Dict[str, Any], engine: DenaroEngine):
        super().__init__(config, engine)
        self.config_section = config.get("whale_tracker", {})
        self.depth_window_ms = self.config_section.get("depth_window_ms", 1000)
        self.order_book_depth = self.config_section.get("order_book_depth", 50)
        self.whale_size_min_usdc = self.config_section.get("whale_size_min_usdc", 5000)
        self.whale_size_min_quote = self.config_section.get("whale_size_min_quote", 5000)
        self.whale_multiplier_median = self.config_section.get("whale_multiplier_median", 5.0)
        self.abnormal_volume_std = self.config_section.get("abnormal_volume_std_multiplier", 3.0)
        self.max_positions_per_symbol = self.config_section.get("max_positions_per_symbol", 2)
        self.take_profit_bps = self.config_section.get("take_profit_bps", 20)
        self.stop_loss_bps = self.config_section.get("stop_loss_bps", 15)
        self.max_hold_seconds = self.config_section.get("max_hold_seconds", 180)
        self.cooldown_after_exit_seconds = self.config_section.get("cooldown_after_exit_seconds", 20)
        self.cooldown_on_same_side_seconds = self.config_section.get("cooldown_on_same_side_seconds", 60)
        self.enabled = self.config_section.get("enabled", True)
        self.last_whale_time: float = 0
        self.last_trade_time: float = 0
        self.last_exit_time: float = 0
        self.whale_timestamps: deque = deque(maxlen=100)
        self.whale_buys: deque = deque(maxlen=100)
        self.whale_sells: deque = deque(maxlen=100)
        self.baseline_volume_24h: float = 1000000
        self.current_volume: Dict[str, float] = {}

    def _get_symbol(self) -> str:
        symbols = self.config.get("symbols", ["SOLUSDC", "ADAUSDC", "DOGEUSDC"])
        return symbols[1]

    async def run(self):
        self.running = True
        check_interval = 0.3

        while self.running and not self.engine.shutdown_event.is_set():
            try:
                await self._scan_order_book()
                await self._manage_positions()
                await self._update_baseline()

                await asyncio.sleep(check_interval)
                await self.engine.health_monitor.heartbeat(f"strategy_whale_{self.symbol}")

            except Exception as e:
                logging.error(f"Whale tracker strategy error for {self.symbol}: {e}")

    async def _scan_order_book(self):
        if not self.enabled:
            return

        if time.time() - self.last_exit_time < self.cooldown_after_exit_seconds:
            return

        symbol = self.symbol
        current_positions = [p for p in self.engine.positions if p.symbol == symbol and p.strategy == "whale_tracker" and not p.closed]
        if len(current_positions) >= self.max_positions_per_symbol:
            return

        price = await self.engine.price_cache.get_latest(self.symbol)
        volume_24h = await self.engine.price_cache.get_latest(f"{symbol}_volume")
        if not price or not volume_24h:
            return

        if symbol not in self.current_volume:
            self.current_volume[symbol] = 0.0
        self.current_volume[symbol] += volume_24h * 0.01

        if self.current_volume[symbol] >= self.baseline_volume_24h * 0.10:
            self.current_volume[symbol] = 0.0
            whale_detected = True
            timestamp = time.time()
            whale_size = self.whale_size_min_usdc * (1 + self.whale_multiplier_median)
            whale_size *= (1 + self.abnormal_volume_std * 0.5)

            if whale_detected:
                self.whale_timestamps.append(timestamp)

                if len(self.whale_timestamps) >= 2:
                    time_diff = self.whale_timestamps[-1] - self.whale_timestamps[-2]
                    if time_diff < 5:
                        whale_detected = True
                        self.whale_buys.append(timestamp)

            if whale_detected:
                capital = await self.engine._allocate_capital("whale_tracker")
                position_size_pct = self.config_section.get("position_size_pct", 0.30)
                capital = capital * position_size_pct

                signal = ExecutionSignal(
                    symbol=self.symbol,
                    direction=TradeDirection.LONG,
                    capital=capital,
                    reason=f"Whale detected: {len(self.whale_buys)} whales in last 1000ms, size ${whale_size:.2f}",
                    strategy="whale_tracker",
                    priority=2,
                    metadata={
                        "price": price,
                        "current_price": price,
                        "whale_count": len(self.whale_buys),
                        "whale_size estimate": whale_size
                    }
                )
                await self.notify_signal(signal)
                self.last_whale_time = timestamp
                self.last_trade_time = timestamp

    async def _manage_positions(self):
        async with self.lock:
            for position in self.positions[:]:
                if position.symbol == self.symbol and position.strategy == "whale_tracker" and not position.closed:
                    await self.check_position(position)

                    if position.exit_time is None:
                        entry_price = position.entry_price
                        price = await self.engine.price_cache.get_latest(self.symbol)
                        if price:
                            duration = time.time() - position.entry_time
                            if duration >= self.max_hold_seconds:
                                position.record_exit(price, "max_hold_exceeded")
                                self.engine.positions.remove(position)
                                logging.info(f"Whale position {position.id}: max hold time exceeded @ {price:.4f}, PnL ${position.pnl_usdc:.2f}")
                                self.last_exit_time = time.time()
                                continue

                            tp_pct = self.take_profit_bps / 100
                            sl_pct = self.stop_loss_bps / 100

                            if position.direction == TradeDirection.LONG:
                                if price >= entry_price * (1 + tp_pct) or price <= entry_price * (1 - sl_pct):
                                    position.record_exit(price, "whale_take_profit_or_stop_loss")
                                    self.engine.positions.remove(position)
                                    logging.info(f"Whale position {position.id}: exit @ {price:.4f}, PnL ${position.pnl_usdc:.2f}")
                                    self.last_exit_time = time.time()

    async def _update_baseline(self):
        if time.time() % 300 < 1:
            volumes = [v for v in self.current_volume.values() if v > 0]
            if len(volumes) > 0:
                self.baseline_volume_24h = sum(volumes) / len(volumes) * 2

    async def analyze(self) -> Optional[ExecutionSignal]:
        return None
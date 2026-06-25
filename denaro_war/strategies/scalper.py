import asyncio
import logging
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

from core.engine import DenaroEngine, ExecutionSignal, TradeDirection, Position
from strategies import Strategy


class ScalperStrategy(Strategy):
    def __init__(self, config: Dict[str, Any], engine: DenaroEngine):
        super().__init__(config, engine)
        self.config_section = config.get("scalper", {})
        self.atr_period = self.config_section.get("atr_period", 14)
        self.atr_baseline_periods = self.config_section.get("atr_baseline_periods", 50)
        self.atr_spike_threshold = self.config_section.get("atr_spike_threshold", 3.0)
        self.entry_consecutive_spikes = self.config_section.get("entry_consecutive_spikes", 2)
        self.take_profit_atr = self.config_section.get("take_profit_atr_multiple", 1.5)
        self.stop_loss_atr = self.config_section.get("stop_loss_atr_multiple", 1.0)
        self.max_hold_seconds = self.config_section.get("max_hold_seconds", 120)
        self.min_hold_seconds = self.config_section.get("min_hold_seconds", 10)
        self.min_profit_bps = self.config_section.get("min_profit_bps", 5)
        self.cooldown_after_exit_seconds = self.config_section.get("cooldown_after_exit_seconds", 30)
        self.enabled = self.config_section.get("enabled", True)
        self.last_exit_time: float = 0
        self.consecutive_spikes: Dict[str, int] = {}

    def _get_symbol(self) -> str:
        symbols = self.config.get("symbols", ["SOLUSDC", "ADAUSDC", "DOGEUSDC"])
        return symbols[0]

    async def run(self):
        self.running = True
        check_interval = 0.5

        while self.running and not self.engine.shutdown_event.is_set():
            try:
                await self._scan_opportunities()
                await self._manage_positions()

                await asyncio.sleep(check_interval)
                await self.engine.health_monitor.heartbeat(f"strategy_scalper_{self.symbol}")

            except Exception as e:
                logging.error(f"Scalper strategy error for {self.symbol}: {e}")

    async def _scan_opportunities(self):
        if not self.enabled:
            return

        if time.time() - self.last_exit_time < self.cooldown_after_exit_seconds:
            return

        atr = await self.engine.price_cache.get_atr(self.symbol, self.atr_period)
        if atr <= 0:
            return

        price = await self.engine.price_cache.get_latest(self.symbol)
        if not price:
            return

        prices = await self.engine.price_cache.get_range(self.symbol, self.atr_baseline_periods * 60)
        if len(prices) > self.atr_baseline_periods:
            baseline_atr = atr
        else:
            baseline_atr = atr * 2

        spike_detected = atr >= baseline_atr * self.atr_spike_threshold
        if spike_detected:
            if self.symbol not in self.consecutive_spikes:
                self.consecutive_spikes[self.symbol] = 0
            self.consecutive_spikes[self.symbol] += 1
        else:
            self.consecutive_spikes[self.symbol] = 0

        if self.consecutive_spikes.get(self.symbol, 0) >= self.entry_consecutive_spikes:
            capital = await self.engine._allocate_capital("scalper")
            position_size_pct = self.config_section.get("position_size_pct", 0.20)
            capital = capital * position_size_pct

            signal = ExecutionSignal(
                symbol=self.symbol,
                direction=TradeDirection.LONG,
                capital=capital,
                reason=f"ATR spike detected: {atr:.4f} >= {baseline_atr:.4f} * {self.atr_spike_threshold}",
                strategy="scalper",
                priority=1,
                metadata={
                    "price": price,
                    "atr": atr,
                    "current_price": price
                }
            )
            await self.notify_signal(signal)
            self.last_exit_time = time.time()

    async def _manage_positions(self):
        async with self.lock:
            for position in self.positions[:]:
                if position.symbol == self.symbol and not position.closed:
                    await self.check_position(position)

                    if position.exit_time is None:
                        entry_price = position.entry_price
                        price = await self.engine.price_cache.get_latest(self.symbol)
                        if price:
                            if position.direction == TradeDirection.LONG:
                                current_atr = await self.engine.price_cache.get_atr(self.symbol, self.atr_period)
                                if current_atr > 0:
                                    tp_price = entry_price * (1 + self.take_profit_atr * current_atr / entry_price * 100 / 100)
                                    sl_price = entry_price * (1 - self.stop_loss_atr * current_atr / entry_price * 100 / 100)
                                else:
                                    tp_price = entry_price * 1.02
                                    sl_price = entry_price * 0.98

                                if price >= tp_price or price <= sl_price:
                                    position.record_exit(price, "take_profit_or_stop_loss")
                                    self.engine.positions.remove(position)
                                    logging.info(f"Scalper position {position.id}: exit @ {price:.4f}, PnL ${position.pnl_usdc:.2f}")

                                    if position.pnl_pct < 0:
                                        self.last_exit_time = time.time()

    async def analyze(self) -> Optional[ExecutionSignal]:
        return None
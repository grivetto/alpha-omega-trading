import json
import time
import threading
import random
from typing import Dict
from datetime import datetime
import logging

from engine import BinanceEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class NewsReactor:
    def __init__(
        self,
        symbol: str,
        engine: BinanceEngine,
        capital: float,
        config: Dict,
        risk_config: Dict
    ):
        self.name = "NewsReactor"
        self.symbol = symbol
        self.engine = engine
        self.capital = capital
        self.risk_config = risk_config
        self.active = False
        self.trades = []
        self.start_capital = capital
        self.pnl = 0.0
        self.lock = threading.Lock()

        self.keywords = config.get("keywords", [])
        self.alert_threshold = config.get("alert_threshold_per_minute", 5)
        self.entry_pct = config.get("position_size_pct_of_bucket", 0.1)
        self.tp_pct = config.get("take_profit_pct", 0.015)
        self.sl_pct = config.get("stop_loss_pct", -0.02)
        self.interval = config.get("check_interval_seconds", 60)

        logger.info(f"[{self.name}] Initialized with ${capital:.2f} capital")

    def start(self):
        self.active = True
        self.start_time = datetime.now()
        logger.info(f"[{self.name}] Started")

    def stop(self):
        self.active = False
        self._log_final_stats()
        logger.info(f"[{self.name}] Stopped")

    def _log_final_stats(self):
        total_trades = len([t for t in self.trades if t.get("closed")])
        logger.info(f"[{self.name}] Final Stats: Closed Trades={total_trades}, PnL=${self.pnl:.2f}")

    def _check_daily_loss(self) -> bool:
        daily_loss_pct = (self.start_capital - (self.start_capital + self.pnl)) / self.start_capital
        halt_pct = self.risk_config.get("daily_loss_halt_pct", 0.03)
        return daily_loss_pct >= halt_pct

    def _get_position_size(self, bucket_pct: float) -> float:
        max_trade_pct = self.risk_config.get("max_per_trade_pct", 0.05)
        size = min(self.capital * bucket_pct, self.capital * max_trade_pct)
        return max(size, 0.0)

    def _simulate_news_signal(self) -> int:
        """Simulated news spike counter (replace with real X API/RSS when credentials available)"""
        base = 2
        spike_chance = 0.2
        if random.random() < spike_chance:
            return base + random.randint(3, 10)
        return base + random.randint(0, 2)

    def run(self):
        while self.active:
            if self._check_daily_loss():
                logger.warning(f"[{self.name}] Daily loss limit reached, halting")
                self.stop()
                return

            news_signal = self._simulate_news_signal()
            
            if news_signal > self.alert_threshold and random.random() < 0.7:
                self._execute_entry(news_signal)

            self._manage_positions()
            time.sleep(self.interval)

    def _execute_entry(self, signal_strength: int):
        size = self._get_position_size(self.entry_pct)
        if size < 1.0:
            return

        try:
            current_price = self.engine.price(self.symbol)
            self.engine.market_buy(self.symbol, size)
            entry_price = current_price
            
            with self.lock:
                self.trades.append({
                    "type": "BUY",
                    "symbol": self.symbol,
                    "qty": size,
                    "entry": entry_price,
                    "tp": entry_price * (1 + self.tp_pct),
                    "sl": entry_price * (1 + self.sl_pct),
                    "signal_strength": signal_strength,
                    "timestamp": datetime.now().isoformat()
                })
            logger.info(f"[{self.name}] BUY {self.symbol} @ {entry_price:.2f} | signal={signal_strength}")

        except Exception as e:
            logger.error(f"[{self.name}] Trade error: {e}")

    def _manage_positions(self):
        with self.lock:
            for trade in list(self.trades):
                if trade.get("closed"):
                    continue

                current_price = self.engine.price(self.symbol)
                entry = trade["entry"]
                tp = trade["tp"]
                sl = trade["sl"]

                pnl_pct = (current_price - entry) / entry

                if pnl_pct >= self.tp_pct or pnl_pct <= self.sl_pct:
                    self.engine.market_sell(self.symbol, trade["qty"])
                    trade["closed"] = True
                    trade["exit"] = current_price
                    trade["pnl_pct"] = pnl_pct
                    self.pnl += trade["qty"] * entry * pnl_pct
                    logger.info(f"[{self.name}] Exit {self.symbol} @ {current_price:.2f} | PnL=${self.pnl:.2f}")


if __name__ == "__main__":
    with open("config/war_config.json", "r") as f:
        config = json.load(f)
    
    engine = BinanceEngine()
    strat = NewsReactor(
        "SOLUSDC",
        engine,
        10000 * config["capital_allocation"]["news"],
        config["strategies"]["news_reactor"],
        config["risk"]
    )
    
    import threading
    t = threading.Thread(target=strat.run)
    t.start()
    t.join()
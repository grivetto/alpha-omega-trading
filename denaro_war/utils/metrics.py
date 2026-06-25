import asyncio
import csv
import json
import logging
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional


class MetricsRecorder:
    def __init__(self, filepath: str = "logs/metrics.csv"):
        self.filepath = filepath
        self.metrics_buffer: deque = deque(maxlen=10000)
        self.strategy_performance: Dict[str, Dict[str, List[float]]] = {}
        self.lock = asyncio.Lock()
        self.last_flush_time = 0
        self.flush_interval = 5
        self._ensure_directory()
        self._init_csv()

    def _ensure_directory(self):
        os.makedirs(os.path.dirname(self.filepath), exist_ok=True)

    def _init_csv(self):
        if not os.path.exists(self.filepath):
            with open(self.filepath, "w", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(["timestamp", "metric", "value", "strategy", "symbol", "tags"])

    async def record(self, metric: str, value: float, tags: Dict[str, str] = None, strategy: str = None, symbol: str = None):
        async with self.lock:
            self.metrics_buffer.append({
                "timestamp": time.time(),
                "metric": metric,
                "value": value,
                "strategy": strategy,
                "symbol": symbol,
                "tags": tags or {}
            })

    async def record_pnl(self, pnl_usdc: float, strategy: str, symbol: str, direction: str = "unknown"):
        async with self.lock:
            self.metrics_buffer.append({
                "timestamp": time.time(),
                "metric": "pnl",
                "value": pnl_usdc,
                "strategy": strategy,
                "symbol": symbol,
                "tags": {"direction": direction}
            })

            if strategy not in self.strategy_performance:
                self.strategy_performance[strategy] = {
                    "pnl": [],
                    "wins": [],
                    "losses": [],
                    "positions": []
                }
            self.strategy_performance[strategy]["pnl"].append(pnl_usdc)
            self.strategy_performance[strategy]["positions"].append(time.time())
            if pnl_usdc > 0:
                self.strategy_performance[strategy]["wins"].append(pnl_usdc)
            else:
                self.strategy_performance[strategy]["losses"].append(abs(pnl_usdc))

    async def record_trade(self, symbol: str, direction: str, capital: float, pnl_usdc: float, strategy: str):
        async with self.lock:
            self.metrics_buffer.append({
                "timestamp": time.time(),
                "metric": "trade",
                "value": capital,
                "strategy": strategy,
                "symbol": symbol,
                "tags": {"direction": direction, "pnl_usdc": str(pnl_usdc)}
            })

    async def record_event(self, event: str, value: float = 1.0, tags: Dict[str, str] = None):
        async with self.lock:
            self.metrics_buffer.append({
                "timestamp": time.time(),
                "metric": f"event_{event}",
                "value": value,
                "strategy": None,
                "symbol": None,
                "tags": tags or {}
            })

    async def flush(self):
        async with self.lock:
            try:
                with open(self.filepath, "a", newline="") as f:
                    writer = csv.writer(f)
                    while len(self.metrics_buffer) > 0:
                        m = self.metrics_buffer.popleft()
                        writer.writerow([
                            datetime.fromtimestamp(m["timestamp"], tz=timezone.utc).isoformat(),
                            m["metric"],
                            m["value"],
                            m["strategy"] or "",
                            m["symbol"] or "",
                            json.dumps(m["tags"])
                        ])
                logging.debug("Metrics flushed to CSV")
            except Exception as e:
                logging.error(f"Failed to flush metrics: {e}")

    async def get_strategy_performance(self, window_minutes: int = 60) -> Dict[str, Dict[str, Any]]:
        async with self.lock:
            cutoff = time.time() - (window_minutes * 60)
            result = {}
            for strategy, data in self.strategy_performance.items():
                if strategy not in result:
                    result[strategy] = {"pnl": 0.0, "wins": 0, "losses": 0, "sharpe": 0.0}
                pnl = sum(data["pnl"])
                wins = len(data["wins"])
                losses = len(data["losses"])
                result[strategy] = {
                    "pnl": pnl,
                    "wins": wins,
                    "losses": losses,
                    "sharpe": pnl / (abs(sum(data["losses"])) + 1) if losses > 0 else 0.0
                }
            return result

    async def get_position_count(self, strategy: str = None) -> int:
        async with self.lock:
            return len(self.metrics_buffer)

    async def close(self):
        await self.flush()
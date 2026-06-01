"""denaro-antigravity strategies/base.py – Strategy base class.

Provides common classes and abstractions for all trading strategies.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from loguru import logger

if TYPE_CHECKING:
    from core.engine import ExchangeWrapper

class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"

@dataclass
class Signal:
    side: Side
    symbol: str
    amount: float
    price: float | None = None
    tp_price: float | None = None
    sl_price: float | None = None
    reason: str = ""

    def __str__(self) -> str:
        price_str = f"@ {self.price:.4f}" if self.price else "MARKET"
        return f"{self.side.upper()} {self.amount:.6f} {self.symbol} {price_str} [TP={self.tp_price} SL={self.sl_price}] {self.reason}"

@dataclass
class Position:
    symbol: str
    side: Side
    amount: float
    entry_price: float
    tp_price: float | None = None
    sl_price: float | None = None
    order_id: str = ""
    tp_order_id: str = ""
    sl_order_id: str = ""
    pnl: float = 0.0
    entry_time: float = 0.0

class BaseStrategy(ABC):
    def __init__(self, name: str, exchange: ExchangeWrapper, symbol: str, capital: float):
        self.name = name
        self.exchange = exchange
        self.symbol = symbol
        self.capital = capital
        self.is_paused = False
        self._positions: dict[str, Position] = {}  # order_id -> Position
        self.logger = logger.bind(strategy=name)

    @abstractmethod
    async def on_candle(self, ohlcv: list[list[float]]) -> list[Signal]:
        """Process new candles and return trade signals."""

    @abstractmethod
    async def on_order_update(self, order: dict[str, Any]) -> None:
        """Handle order fills, cancellations, etc."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully cancel open orders and close positions."""

    @property
    def has_open_position(self) -> bool:
        return len(self._positions) > 0

    def pause(self) -> None:
        self.is_paused = True
        self.logger.warning(f"{self.name} paused.")

    def resume(self) -> None:
        self.is_paused = False
        self.logger.info(f"{self.name} resumed.")

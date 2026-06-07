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

    async def get_quote_capital(self) -> float:
        """Dynamically scales capital (denominated in EUR) to the quote asset of the traded symbol."""
        parts = self.symbol.split("/")
        if len(parts) < 2:
            return self.capital
        quote = parts[1].upper()
        if quote == "EUR":
            return self.capital

        scaled_found = None

        # Fetch ticker for quote/EUR (e.g., BTC/EUR)
        try:
            ticker = await self.exchange.fetch_ticker(f"{quote}/EUR")
            rate = float(ticker.get("last") or ticker.get("close") or 0)
            if rate > 0:
                scaled = self.capital / rate
                self.logger.info(f"Scaled capital from {self.capital:.2f} EUR to {scaled:.6f} {quote} using {quote}/EUR rate: {rate:.4f}")
                scaled_found = scaled
        except Exception as e:
            self.logger.debug(f"Failed to fetch {quote}/EUR ticker: {e}. Trying inverse...")

        # Fallback to EUR/quote (e.g. EUR/USDT)
        try:
            ticker = await self.exchange.fetch_ticker(f"EUR/{quote}")
            rate = float(ticker.get("last") or ticker.get("close") or 0)
            if rate > 0:
                scaled = self.capital * rate
                self.logger.info(f"Scaled capital from {self.capital:.2f} EUR to {scaled:.6f} {quote} using EUR/{quote} rate: {rate:.4f}")
                scaled_found = scaled
        except Exception as e:
            self.logger.error(f"Failed to convert capital from EUR to {quote}: {e}")


        # Cap to available quote balance
        try:
            bal = await self.exchange.fetch_balance()
            free_quote = bal.get("free", {}).get(quote, 0)
            if free_quote < scaled:
                self.logger.warning(f"Capping capital to available {quote} balance: {free_quote:.6f} (scaled: {scaled:.6f})")
                scaled = free_quote
                scaled_found = scaled
        except Exception as e:
            self.logger.debug(f"Failed to fetch balance for capping: {e}")
        if scaled_found is not None:
            return scaled_found
        return self.capital  # Safe fallback


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

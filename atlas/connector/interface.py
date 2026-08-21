"""ATLAS Connector Interface - Abstract base for exchange adapters."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator, Optional
from atlas.connector.models import Ticker, OrderBook, Balance
from atlas.execution.models import OrderRequest, OrderResponse, CancelResponse


class ExchangeConnector(ABC):
    """Unified interface for all exchange adapters."""

    @property
    @abstractmethod
    def exchange_id(self) -> str:
        """Exchange identifier (e.g., 'binance', 'okx', 'kraken')."""
        ...

    @abstractmethod
    async def connect(self) -> None:
        """Establish connections (REST + WebSocket)."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close all connections gracefully."""
        ...

    # Market Data
    @abstractmethod
    async def fetch_ticker(self, symbol: str) -> Ticker:
        """Fetch current ticker for symbol."""
        ...

    @abstractmethod
    async def fetch_order_book(self, symbol: str, limit: int = 100) -> OrderBook:
        """Fetch order book snapshot."""
        ...

    @abstractmethod
    async def fetch_balance(self) -> dict[str, Balance]:
        """Fetch account balances."""
        ...

    # Trading
    @abstractmethod
    async def create_order(self, order: OrderRequest) -> OrderResponse:
        """Place a new order."""
        ...

    @abstractmethod
    async def cancel_order(self, order_id: str, symbol: str) -> CancelResponse:
        """Cancel an existing order."""
        ...

    @abstractmethod
    async def fetch_order(self, order_id: str, symbol: str) -> OrderResponse:
        """Fetch order status."""
        ...

    @abstractmethod
    async def fetch_open_orders(self, symbol: str = "") -> list[OrderResponse]:
        """Fetch open orders, optionally filtered by symbol."""
        ...

    # WebSocket Streams
    @abstractmethod
    async def watch_ticker(self, symbol: str) -> AsyncIterator[Ticker]:
        """Stream real-time ticker updates."""
        ...

    @abstractmethod
    async def watch_order_book(self, symbol: str) -> AsyncIterator[OrderBook]:
        """Stream real-time order book updates."""
        ...

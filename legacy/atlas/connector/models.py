"""ATLAS Connector Models - Normalized exchange data structures."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True, frozen=True)
class Ticker:
    """Normalized ticker data."""
    symbol: str
    exchange: str
    bid: float
    ask: float
    last: float
    high: float
    low: float
    open: float
    close: float
    volume: float
    timestamp: int

    @property
    def spread(self) -> float:
        return self.ask - self.bid

    @property
    def spread_pct(self) -> float:
        if self.last > 0:
            return (self.ask - self.bid) / self.last
        return 0.0


@dataclass(slots=True, frozen=True)
class OrderBook:
    """Normalized order book snapshot."""
    symbol: str
    exchange: str
    bids: list[tuple[float, float]]  # [(price, size), ...] sorted descending
    asks: list[tuple[float, float]]  # [(price, size), ...] sorted ascending
    timestamp: int


@dataclass(slots=True, frozen=True)
class Balance:
    """Account balance for a currency."""
    currency: str
    free: float
    used: float
    total: float
    exchange: str

    @property
    def available(self) -> float:
        return self.free

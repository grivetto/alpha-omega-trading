"""ATLAS Core Events - Event definitions for the event bus."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Union
from atlas.connector.models import Ticker, OrderBook
from atlas.execution.models import Fill, OrderResponse, OrderStatus


@dataclass(slots=True, frozen=True)
class TickEvent:
    """Market data tick event."""
    symbol: str
    ticker: Ticker
    order_book: OrderBook
    timestamp: int


@dataclass(slots=True, frozen=True)
class FillEvent:
    """Order fill event."""
    fill: Fill
    order: OrderResponse


@dataclass(slots=True, frozen=True)
class OrderUpdateEvent:
    """Order status update event."""
    order: OrderResponse
    previous_status: OrderStatus


@dataclass(slots=True, frozen=True)
class RiskEvent:
    """Risk management event."""
    event_type: str  # "drawdown_warning", "kill_switch", "daily_loss"
    details: dict
    timestamp: int


# Union type for all events
Event = Union[TickEvent, FillEvent, OrderUpdateEvent, RiskEvent]

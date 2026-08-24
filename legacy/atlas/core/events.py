"""ATLAS Core Events - Event bus and event definitions."""
from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Callable, Union, Dict, List

from atlas.connector.models import Ticker, OrderBook
from atlas.execution.models import Fill, OrderResponse, OrderStatus

logger = logging.getLogger(__name__)


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


class EventBus:
    """Simple async event bus for decoupled component communication."""

    def __init__(self):
        self._subscribers: Dict[type, List[Callable]] = defaultdict(list)
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._task: asyncio.Task | None = None

    def subscribe(self, event_type: type, handler: Callable) -> None:
        """Subscribe to an event type."""
        self._subscribers[event_type].append(handler)

    def unsubscribe(self, event_type: type, handler: Callable) -> None:
        """Unsubscribe from an event type."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)

    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        await self._queue.put(event)

    async def _dispatch_loop(self) -> None:
        """Internal dispatch loop."""
        self._running = True
        while self._running:
            try:
                event = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                event_type = type(event)
                for handler in self._subscribers.get(event_type, []):
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler: {e}", exc_info=True)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in dispatch loop: {e}", exc_info=True)

    async def start(self) -> None:
        """Start the event bus."""
        if self._task is None:
            self._task = asyncio.create_task(self._dispatch_loop())
            logger.info("EventBus started")

    async def stop(self) -> None:
        """Stop the event bus."""
        self._running = False
        if self._task:
            await self._task
            self._task = None
            logger.info("EventBus stopped")
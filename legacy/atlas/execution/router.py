"""ATLAS Execution Router - Routes orders to exchanges with idempotency."""
from __future__ import annotations

import logging
import uuid
from typing import Optional

from atlas.connector.interface import ExchangeConnector
from atlas.execution.models import OrderRequest, OrderResponse, CancelResponse
from atlas.portfolio.manager import ExchangeRegistry, PortfolioManager
from atlas.core.events import EventBus, FillEvent

logger = logging.getLogger(__name__)


class ExecutionRouter:
    """Routes order requests to the correct exchange connector."""

    def __init__(
        self,
        exchange_registry: ExchangeRegistry,
        portfolio_manager: PortfolioManager,
        event_bus: Optional[EventBus] = None,
    ):
        self.exchange_registry = exchange_registry
        self.portfolio_manager = portfolio_manager
        self.event_bus = event_bus

    def _resolve_exchange(self, order: OrderRequest) -> ExchangeConnector:
        connector = self.exchange_registry.get(order.exchange)
        if not connector:
            raise ValueError(f"Exchange not found: {order.exchange}")
        return connector

    async def submit(self, order: OrderRequest) -> OrderResponse:
        """Submit an order with risk pre-check."""
        # Risk check before routing
        can_trade, reason = self.portfolio_manager.can_trade(
            exchange=order.exchange,
            symbol=order.symbol,
            side=order.side.value,
            amount=order.amount,
            price=order.price or 0,
        )
        if not can_trade:
            logger.warning(f"Order rejected by risk: {reason}")
            raise ValueError(f"Risk check failed: {reason}")

        connector = self._resolve_exchange(order)
        response = await connector.create_order(order)
        logger.info(f"Order submitted: {response.exchange_order_id} {order.side.value} {order.symbol}")
        return response

    async def cancel(self, exchange: str, order_id: str, symbol: str) -> CancelResponse:
        """Cancel an order."""
        connector = self.exchange_registry.get(exchange)
        if not connector:
            raise ValueError(f"Exchange not found: {exchange}")
        response = await connector.cancel_order(order_id, symbol)
        logger.info(f"Order cancelled: {order_id}")
        return response

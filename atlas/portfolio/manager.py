"""ATLAS Portfolio Manager - Risk management and position tracking."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, List, Optional

from atlas.connector.models import Balance
from atlas.core.config import RiskConfig
from atlas.connector.interface import ExchangeConnector
from atlas.core.events import EventBus, FillEvent, RiskEvent

logger = logging.getLogger(__name__)


@dataclass
class Position:
    """Current position for a symbol on an exchange."""
    symbol: str
    exchange: str
    base_currency: str
    quote_currency: str
    amount: float = 0.0
    avg_entry_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl: float = 0.0
    updated_at: int = field(default_factory=lambda: int(time.time() * 1000))


class ExchangeRegistry:
    """Registry of connected exchange connectors."""

    def __init__(self):
        self._exchanges: Dict[str, ExchangeConnector] = {}

    def register(self, name: str, connector: ExchangeConnector) -> None:
        self._exchanges[name] = connector
        logger.info(f"Registered exchange: {name}")

    def get(self, name: str) -> Optional[ExchangeConnector]:
        return self._exchanges.get(name)

    def all(self) -> List[ExchangeConnector]:
        return list(self._exchanges.values())

    @property
    def names(self) -> List[str]:
        return list(self._exchanges.keys())


class PortfolioManager:
    """Manages portfolio state, risk limits, and position tracking."""

    def __init__(
        self,
        exchange_registry: ExchangeRegistry,
        risk_config: RiskConfig,
        event_bus: Optional[EventBus] = None,
    ):
        self.exchange_registry = exchange_registry
        self.risk_config = risk_config
        self.event_bus = event_bus

        self._positions: Dict[str, Position] = {}  # key: f"{exchange}:{symbol}"
        self._balances: Dict[str, Dict[str, Balance]] = {}  # exchange -> currency -> Balance
        self._daily_pnl: float = 0.0
        self._peak_equity: float = 0.0
        self._kill_switch_triggered: bool = False
        self._last_balance_update: int = 0

    async def initialize(self) -> None:
        """Initialize by fetching initial balances."""
        await self._update_balances()
        self._calculate_peak_equity()
        logger.info("PortfolioManager initialized")

    def _position_key(self, exchange: str, symbol: str) -> str:
        return f"{exchange}:{symbol}"

    async def _update_balances(self) -> None:
        """Fetch and update balances from all exchanges."""
        for exchange_name, connector in self.exchange_registry._exchanges.items():
            try:
                balances = await connector.fetch_balance()
                self._balances[exchange_name] = balances
                logger.debug(f"Updated balances for {exchange_name}: {list(balances.keys())}")
            except Exception as e:
                logger.error(f"Failed to fetch balance from {exchange_name}: {e}")

        self._last_balance_update = int(time.time() * 1000)

    def _calculate_peak_equity(self) -> None:
        """Calculate peak equity for drawdown tracking."""
        total_equity = 0.0
        for exchange_balances in self._balances.values():
            for balance in exchange_balances.values():
                total_equity += balance.total
        self._peak_equity = max(self._peak_equity, total_equity)

    def get_total_equity(self) -> float:
        """Get total portfolio equity in quote currency (approximation)."""
        total = 0.0
        for exchange_balances in self._balances.values():
            for balance in exchange_balances.values():
                total += balance.total
        return total

    def get_current_drawdown(self) -> float:
        """Calculate current drawdown from peak."""
        if self._peak_equity <= 0:
            return 0.0
        current = self.get_total_equity()
        return (self._peak_equity - current) / self._peak_equity

    def check_risk_limits(self) -> List[str]:
        """Check all risk limits, return list of violations."""
        violations = []

        # Check drawdown (skip if no equity baseline yet)
        drawdown = self.get_current_drawdown()
        if self._peak_equity > 0 and drawdown >= self.risk_config.max_portfolio_drawdown:
            violations.append(f"Max drawdown exceeded: {drawdown:.2%} >= {self.risk_config.max_portfolio_drawdown:.2%}")

        # Check daily loss (skip if no equity baseline yet)
        if self._peak_equity > 0 and abs(self._daily_pnl) >= self.risk_config.max_daily_loss * self._peak_equity:
            violations.append(f"Max daily loss exceeded: {self._daily_pnl:.2f}")

        # Check kill switch
        if self._kill_switch_triggered:
            violations.append("Kill switch active")

        return violations

    def can_trade(self, exchange: str, symbol: str, side: str, amount: float, price: float) -> tuple[bool, str]:
        """Check if a trade is allowed under risk limits."""
        violations = self.check_risk_limits()
        if violations:
            return False, "; ".join(violations)

        # Check position size limit
        position_value = amount * price
        total_equity = self.get_total_equity()
        if total_equity > 0:
            position_pct = position_value / total_equity
            if position_pct > self.risk_config.max_position_size_pct:
                return False, f"Position size {position_pct:.2%} exceeds max {self.risk_config.max_position_size_pct:.2%}"

        return True, "OK"

    def update_position(self, exchange: str, symbol: str, side: str, amount: float, price: float, fee: float = 0.0) -> None:
        """Update position after a fill."""
        key = self._position_key(exchange, symbol)
        pos = self._positions.get(key)

        if pos is None:
            # Parse symbol to get base/quote
            parts = symbol.split("/")
            base = parts[0] if len(parts) > 0 else ""
            quote = parts[1] if len(parts) > 1 else ""
            pos = Position(
                symbol=symbol,
                exchange=exchange,
                base_currency=base,
                quote_currency=quote,
            )
            self._positions[key] = pos

        if side == "buy":
            new_amount = pos.amount + amount
            if pos.amount >= 0:
                pos.avg_entry_price = ((pos.amount * pos.avg_entry_price) + (amount * price)) / new_amount
            else:
                # Closing short
                realized = (pos.avg_entry_price - price) * min(amount, abs(pos.amount))
                pos.realized_pnl += realized
                self._daily_pnl += realized
            pos.amount = new_amount
        else:  # sell
            new_amount = pos.amount - amount
            if pos.amount <= 0:
                pos.avg_entry_price = ((abs(pos.amount) * pos.avg_entry_price) + (amount * price)) / abs(new_amount)
            else:
                # Closing long
                realized = (price - pos.avg_entry_price) * min(amount, pos.amount)
                pos.realized_pnl += realized
                self._daily_pnl += realized
            pos.amount = new_amount

        pos.updated_at = int(time.time() * 1000)
        logger.info(f"Position updated: {key} amount={pos.amount:.6f} avg_price={pos.avg_entry_price:.2f} realized_pnl={pos.realized_pnl:.2f}")

    def trigger_kill_switch(self, reason: str) -> None:
        """Trigger emergency kill switch."""
        self._kill_switch_triggered = True
        logger.critical(f"KILL SWITCH TRIGGERED: {reason}")
        if self.event_bus:
            asyncio.create_task(self.event_bus.publish(RiskEvent(
                event_type="kill_switch",
                details={"reason": reason},
                timestamp=int(time.time() * 1000)
            )))

    async def on_fill(self, fill_event: FillEvent) -> None:
        """Handle fill event from event bus."""
        fill = fill_event.fill
        order = fill_event.order
        self.update_position(
            exchange=order.exchange,
            symbol=order.symbol,
            side=order.side.value,
            amount=fill.amount,
            price=fill.price,
            fee=fill.fee,
        )
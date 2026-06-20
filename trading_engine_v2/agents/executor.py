"""Executor Agent — dynamically calculates entry/exit points and places orders."""
from __future__ import annotations
from datetime import datetime
from decimal import Decimal

from core.config import settings
from core.logger import AgentLogger
from connectors.exchange import ExchangeConnector
from models import (
    ContextState, RiskAssessment, RiskDecision,
    ExecutionSignal, SignalType,
)

log = AgentLogger.get("executor")


class ExecutorAgent:
    """Calculates optimal entry/exit points and executes trades."""

    def __init__(self, exchange: ExchangeConnector):
        self.exchange = exchange
        self._open_orders: dict[str, list[ExecutionSignal]] = {}

    async def compute_signal(
        self,
        context: ContextState,
        risk: RiskAssessment,
    ) -> ExecutionSignal:
        """Compute the optimal execution signal given context and risk.

        Args:
            context: Enriched market state from the Analyst.
            risk: Risk assessment from the Risk Manager.

        Returns:
            An ExecutionSignal with dynamically calculated price and size.
        """
        log.info("Computing signal for %s | risk=%s | size=%.1f%%",
                 context.symbol, risk.decision.value,
                 risk.max_position_size_pct * 100)

        # Respect the risk manager's decision
        if risk.decision == RiskDecision.NO_GO:
            return self._hold_signal(context, "Risk veto: NO_GO")
        if risk.decision == RiskDecision.LIQUIDATE:
            return self._liquidate_signal(context)

        price = context.raw_snapshot.price if context.raw_snapshot else None
        if not price:
            return self._hold_signal(context, "No price data")

        # ---- Dynamic entry calculation ----
        entry_price = self._calc_entry_price(context, risk)
        exit_price = self._calc_exit_price(context, entry_price)
        quantity = self._calc_quantity(context, risk, entry_price)

        if quantity <= 0 or entry_price <= 0:
            return self._hold_signal(context, "Invalid quantity or price")

        # Determine signal type based on regime
        if risk.decision == RiskDecision.REDUCE:
            sig_type = SignalType.REDUCE_POSITION
        elif (
            context.regime.value in ("trending_up", "recovery", "calm")
            and quantity > 0
        ):
            sig_type = SignalType.ENTER_LONG
        else:
            sig_type = SignalType.ENTER_SHORT

        signal = ExecutionSignal(
            symbol=context.symbol,
            signal_type=sig_type,
            price=entry_price,
            quantity=quantity,
            order_type="limit",
            time_in_force="GTC",
            reason=(
                f"{risk.decision.value} | "
                f"regime={context.regime.value} | "
                f"entry={entry_price:.4f} exit={exit_price:.4f}"
            ),
            generated_at=datetime.utcnow(),
            risk_assessment=risk,
        )

        log.info("Signal: %s %s @ %.4f x %.4f = $%.2f",
                 sig_type.value, context.symbol, entry_price, quantity,
                 entry_price * quantity)
        return signal

    def _calc_entry_price(
        self, context: ContextState, risk: RiskAssessment
    ) -> float:
        """Dynamically calculate the best entry price.
        Uses a combination of order book depth, spread, and risk constraints.
        """
        snap = context.raw_snapshot
        if not snap or not snap.price:
            return 0.0

        base = snap.price

        # Tighten entry near the bid for longs, near ask for shorts
        if context.regime.value in ("trending_up", "calm", "recovery"):
            # Enter slightly below current price for a long
            offset = snap.spread_bps / 10000 if snap.spread_bps else 0.001
            return round(base * (1 - offset), 4)
        else:
            # Enter slightly above for a short
            offset = snap.spread_bps / 10000 if snap.spread_bps else 0.001
            return round(base * (1 + offset), 4)

    def _calc_exit_price(self, context: ContextState, entry: float) -> float:
        """Calculate the take-profit exit price dynamically.
        Uses volatility-adjusted targets instead of fixed spacing.
        """
        vol = context.raw_snapshot.volatility_5m if context.raw_snapshot else 0.01
        # Target 2x the 5m volatility as profit, min 0.3%
        target_pct = max(vol * 2, 0.003)

        if context.regime.value in ("trending_up", "calm", "recovery"):
            return round(entry * (1 + target_pct), 4)
        else:
            return round(entry * (1 - target_pct), 4)

    def _calc_quantity(
        self, context: ContextState, risk: RiskAssessment, price: float
    ) -> float:
        """Calculate position size respecting risk limits and available capital.
        """
        if not price:
            return 0.0

        # Use the risk manager's max size percentage
        size_pct = risk.max_position_size_pct
        if size_pct <= 0:
            return 0.0

        # In production, this would fetch actual free balance
        # For now, use config or capital estimate
        mock_capital = 100.0  # TODO: replace with real balance fetch
        position_value = mock_capital * size_pct
        quantity = position_value / price

        # Round to exchange-specific precision
        return round(quantity, 2)

    def _hold_signal(self, context: ContextState, reason: str) -> ExecutionSignal:
        return ExecutionSignal(
            symbol=context.symbol,
            signal_type=SignalType.HOLD,
            reason=reason,
            generated_at=datetime.utcnow(),
        )

    def _liquidate_signal(self, context: ContextState) -> ExecutionSignal:
        return ExecutionSignal(
            symbol=context.symbol,
            signal_type=SignalType.REDUCE_POSITION,
            price=context.raw_snapshot.price if context.raw_snapshot else None,
            reason="Emergency liquidation by Risk Manager",
            order_type="market",
            generated_at=datetime.utcnow(),
        )

"""Risk Manager Agent — evaluates ContextState and returns GO/NO-GO decisions."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Optional

from core.config import settings
from core.exceptions import RiskVetoError
from core.logger import AgentLogger
from connectors.llm_client import LLMClient
from models import (
    ContextState, RiskAssessment, RiskDecision,
    MarketRegime, AgentMessage,
)

log = AgentLogger.get("risk_manager")

RISK_SYSTEM_PROMPT = """You are a risk management officer for an automated trading system.
Your role is to evaluate market conditions and decide whether it is SAFE to
open new positions. You have ABSOLUTE VETO power.

Analyse the following market context and return a JSON decision:

{
  "decision": "go|no_go|reduce|liquidate",
  "confidence": 0.0-1.0,
  "max_position_size_pct": 0-100,
  "max_entry_price": null or float,
  "min_entry_price": null or float,
  "reasoning": "brief explanation of your decision"
}

Rules:
- GO: conditions are favourable, proceed with normal sizing
- NO_GO: block ALL new positions immediately (liquidity crisis, flash crash)
- REDUCE: allow entry but at reduced size (max_position_size_pct)
- LIQUIDATE: close ALL existing positions NOW (extreme conditions)

Be conservative. Protecting capital is priority #1.
"""


class RiskManagerAgent:
    """Evaluates risk based on ContextState and LLM reasoning.
    Has absolute veto power over all executions.
    """

    def __init__(self, llm: LLMClient):
        self.llm = llm
        self._last_assessment: Optional[RiskAssessment] = None
        self._consecutive_vetoes = 0
        self._daily_pnl: float = 0.0
        self._day_start: datetime = datetime.utcnow().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    async def evaluate(self, context: ContextState) -> RiskAssessment:
        """Evaluate risk for a given ContextState and return a decision."""
        log.info("Evaluating risk for %s (regime: %s)...",
                 context.symbol, context.regime.value)

        # 1. Hard rule checks (override LLM)
        hard_stop = self._hard_rule_check(context)
        if hard_stop:
            log.critical("HARD STOP triggered for %s: %s",
                         context.symbol, hard_stop.reason)
            return RiskAssessment(
                symbol=context.symbol,
                decision=RiskDecision.NO_GO,
                confidence=1.0,
                max_position_size_pct=0.0,
                reasoning=hard_stop.reason,
                assessed_at=datetime.utcnow(),
            )

        # 2. LLM risk evaluation
        try:
            llm_assessment = await self._llm_risk_eval(context)
            assessment = self._parse_llm_response(llm_assessment, context)
            log.info("Risk decision: %s (confidence=%.2f, size=%.0f%%)",
                     assessment.decision.value, assessment.confidence,
                     assessment.max_position_size_pct * 100)
        except Exception as e:
            log.warn("LLM risk eval failed, using conservative fallback: %s", e)
            assessment = self._conservative_fallback(context)

        # 3. Track consecutive vetoes
        if assessment.decision == RiskDecision.NO_GO:
            self._consecutive_vetoes += 1
        else:
            self._consecutive_vetoes = 0

        # Escalate after 3 consecutive vetoes
        if self._consecutive_vetoes >= 3:
            log.warn("3+ consecutive vetoes — escalating to LIQUIDATE")
            assessment.decision = RiskDecision.LIQUIDATE

        self._last_assessment = assessment
        return assessment

    def _hard_rule_check(self, context: ContextState) -> Optional[RiskVetoError]:
        """Hard-coded rules that trigger an automatic NO-GO."""
        cfg = settings.risk

        # Flash crash — immediate veto
        if context.regime == MarketRegime.FLASH_CRASH:
            return RiskVetoError(context.symbol, "flash crash detected")

        # Low liquidity — no new positions
        if context.regime == MarketRegime.LOW_LIQUIDITY:
            return RiskVetoError(context.symbol, "low liquidity regime")

        # Daily loss limit exceeded
        if self._daily_pnl <= -cfg.max_daily_loss_pct:
            return RiskVetoError(
                context.symbol,
                f"daily loss limit exceeded: {self._daily_pnl:.1f}%"
            )

        return None

    async def _llm_risk_eval(self, context: ContextState) -> str:
        """Query the LLM for a risk assessment."""
        prompt = self._build_risk_prompt(context)
        return await self.llm.chat(RISK_SYSTEM_PROMPT, prompt)

    def _parse_llm_response(
        self, raw: str, context: ContextState
    ) -> RiskAssessment:
        """Parse the LLM's JSON response into a RiskAssessment."""
        # Extract JSON from the response (handle markdown wrapping)
        json_str = raw.strip()
        if json_str.startswith("```"):
            json_str = json_str.split("\n", 1)[-1]
            if json_str.endswith("```"):
                json_str = json_str[:-3]

        data = json.loads(json_str)

        decision_str = data.get("decision", "no_go")
        try:
            decision = RiskDecision(decision_str)
        except ValueError:
            log.warn("Unknown LLM decision '%s', defaulting to NO_GO", decision_str)
            decision = RiskDecision.NO_GO

        # Apply hard caps from config
        max_size = min(
            data.get("max_position_size_pct", 0) / 100.0,
            settings.risk.max_position_pct / 100.0,
        )

        return RiskAssessment(
            symbol=context.symbol,
            decision=decision,
            confidence=float(data.get("confidence", 0.5)),
            max_position_size_pct=max_size,
            max_entry_price=data.get("max_entry_price"),
            min_entry_price=data.get("min_entry_price"),
            reasoning=data.get("reasoning", "LLM assessment"),
            llm_raw_response=raw,
            assessed_at=datetime.utcnow(),
        )

    def _conservative_fallback(self, context: ContextState) -> RiskAssessment:
        """Fallback when LLM is unreachable: always NO_GO with reduced sizing."""
        if context.regime in (MarketRegime.FLASH_CRASH, MarketRegime.LOW_LIQUIDITY):
            decision = RiskDecision.NO_GO
        elif context.regime in (MarketRegime.HIGH_VOLATILITY,):
            decision = RiskDecision.REDUCE
        else:
            decision = RiskDecision.GO

        return RiskAssessment(
            symbol=context.symbol,
            decision=decision,
            confidence=0.4,
            max_position_size_pct=settings.risk.max_position_pct / 200.0,
            reasoning="Fallback: LLM unavailable, conservative defaults applied",
            assessed_at=datetime.utcnow(),
        )

    def _build_risk_prompt(self, context: ContextState) -> str:
        """Build the risk evaluation prompt for the LLM."""
        return f"""Market Context for {context.symbol}:
Regime: {context.regime.value}
Confidence: {context.confidence:.2f}
Anomalies: {', '.join(context.anomalies_detected) or 'none'}
Summary: {context.analysis_summary}

Current risk settings:
- Max daily loss: {settings.risk.max_daily_loss_pct}%
- Max drawdown: {settings.risk.max_drawdown_pct}%
- Today's P&L: {self._daily_pnl:.2f}%
- Consecutive vetoes: {self._consecutive_vetoes}
"""

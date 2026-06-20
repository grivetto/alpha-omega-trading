"""Context Analyst Agent — converts raw market data into enriched context state."""
from __future__ import annotations
from datetime import datetime
from typing import Optional

from core.config import settings
from core.logger import AgentLogger
from connectors.exchange import ExchangeConnector
from connectors.llm_client import LLMClient
from models import (
    ContextState, MarketSnapshot, MarketRegime,
    AgentMessage,
)

log = AgentLogger.get("analyst")

# System prompt for the LLM analysis
ANALYST_SYSTEM_PROMPT = """You are a senior market microstructure analyst.
Given the following market data, classify the current regime and highlight
any anomalies or notable patterns. Be concise and quantitative.

Output format (JSON):
{
  "regime": "calm|trending_up|trending_down|high_volatility|low_liquidity|flash_crash|recovery",
  "confidence": 0.0-1.0,
  "anomalies": ["list", "of", "observed", "anomalies"],
  "summary": "One-sentence analysis of current conditions"
}
"""


class AnalystAgent:
    """Analyses market data and produces a dynamic ContextState."""

    def __init__(self, exchange: ExchangeConnector, llm: LLMClient):
        self.exchange = exchange
        self.llm = llm
        self._last_state: Optional[ContextState] = None

    async def analyse(self, symbol: str) -> ContextState:
        """Fetch fresh data and produce an enriched ContextState."""
        log.info("Analysing %s...", symbol)

        # 1. Fetch raw data
        snapshot = await self.exchange.fetch_snapshot(symbol)
        imbalance = await self.exchange.fetch_order_book_imbalance(symbol)

        snapshot.order_book_imbalance = imbalance

        # 2. Heuristic regime classification (fast path)
        regime = self._classify_regime(snapshot)
        anomalies = self._detect_anomalies(snapshot)

        # 3. LLM enrichment (slower, but deeper insight)
        llm_insights = ""
        try:
            llm_prompt = self._build_llm_prompt(snapshot)
            llm_response = await self.llm.chat(ANALYST_SYSTEM_PROMPT, llm_prompt)
            llm_insights = llm_response
        except Exception as e:
            log.warn("LLM analysis failed, falling back to heuristics: %s", e)

        state = ContextState(
            symbol=symbol,
            regime=regime,
            confidence=snapshot.volatility_1h if snapshot.volatility_1h else 0.5,
            raw_snapshot=snapshot,
            analysis_summary=f"{regime.value} | vol_5m={snapshot.volatility_5m:.4f} imbalance={imbalance:+.3f}",
            anomalies_detected=anomalies,
            llm_insights=llm_insights,
            generated_at=datetime.utcnow(),
        )

        self._last_state = state
        log.info("Analysis complete: %s | confidence=%.2f",
                 state.regime.value, state.confidence)
        return state

    def _classify_regime(self, s: MarketSnapshot) -> MarketRegime:
        """Heuristic regime classification based on quantitative thresholds."""
        if s.volatility_5m is None:
            return MarketRegime.CALM

        if s.volatility_5m > 0.05:   # 5% move in 5min = flash crash/spike
            return MarketRegime.FLASH_CRASH
        if s.volatility_5m > 0.02:   # 2% = high volatility
            return MarketRegime.HIGH_VOLATILITY
        if s.spread_bps and s.spread_bps > 100:  # 100bp+ spread
            return MarketRegime.LOW_LIQUIDITY
        if s.volume_24h and s.volume_change_pct and s.volume_change_pct > 0.5:
            return MarketRegime.TRENDING_UP
        if s.volume_change_pct and s.volume_change_pct < -0.3:
            return MarketRegime.TRENDING_DOWN

        return MarketRegime.CALM

    def _detect_anomalies(self, s: MarketSnapshot) -> list[str]:
        """Detect specific anomalies in the market data."""
        anomalies = []
        if s.spread_bps and s.spread_bps > 50:
            anomalies.append(f"wide spread: {s.spread_bps:.1f} bps")
        if s.order_book_imbalance and abs(s.order_book_imbalance) > 0.3:
            side = "bid" if s.order_book_imbalance > 0 else "ask"
            anomalies.append(f"order book skewed to {side} side")
        if s.volatility_5m and s.volatility_5m > 0.03:
            anomalies.append(f"high 5m volatility: {s.volatility_5m:.2%}")
        return anomalies

    def _build_llm_prompt(self, s: MarketSnapshot) -> str:
        """Build a structured prompt for the LLM."""
        return f"""Symbol: {s.symbol}
Price: ${s.price:.4f}
Bid: ${s.bid:.4f} | Ask: ${s.ask:.4f}
Spread: {s.spread_bps:.1f} bps
24h Volume: ${s.volume_24h:.2f}
Volatility 5m: {s.volatility_5m:.4%}
Volatility 1h: {s.volatility_1h:.4%}
Order Book Imbalance: {s.order_book_imbalance:+.3f}
"""

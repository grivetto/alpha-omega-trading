"""AgentOrchestrator — async controller managing inter-agent communication."""
from __future__ import annotations
import asyncio
import signal
import sys
from datetime import datetime
from typing import Optional

from core.config import settings
from core.exceptions import AgentCommunicationError, RiskVetoError
from core.logger import AgentLogger
from connectors.exchange import ExchangeConnector
from connectors.llm_client import LLMClient
from agents.analyst import AnalystAgent
from agents.risk_manager import RiskManagerAgent
from agents.executor import ExecutorAgent
from models import (
    ContextState, RiskAssessment, ExecutionSignal,
    AgentMessage, SignalType, RiskDecision,
)

log = AgentLogger.get("orchestrator")


class AgentOrchestrator:
    """Central controller that coordinates the three agents via async message passing.

    The lifecycle for each symbol:
        1. AnalystAgent.analyse()  →  ContextState
        2. RiskManagerAgent.evaluate(context)  →  RiskAssessment
        3. ExecutorAgent.compute_signal(context, risk)  →  ExecutionSignal
        4. If signal is actionable → execute (or log in paper mode)
    """

    def __init__(self):
        self.exchange = ExchangeConnector(settings.exchange.exchange_id)
        self.llm = LLMClient()
        self.analyst = AnalystAgent(self.exchange, self.llm)
        self.risk_manager = RiskManagerAgent(self.llm)
        self.executor = ExecutorAgent(self.exchange)

        self._running = False
        self._tasks: list[asyncio.Task] = []
        self._symbol_states: dict[str, ContextState] = {}
        self._symbol_risks: dict[str, RiskAssessment] = {}

        # Message bus: (source, target, message)
        self._message_queue: asyncio.Queue[AgentMessage] = asyncio.Queue()

    # ------------------------------------------------------------------
    # Public lifecycle
    # ------------------------------------------------------------------

    async def start(self):
        """Start the orchestration loop for all configured symbols."""
        self._running = True
        log.info("Starting AgentOrchestrator for %d symbols: %s",
                 len(settings.orchestrator.symbols),
                 settings.orchestrator.symbols)

        # Connect to exchange once
        await self.exchange.connect()
        log.info("Exchange connected")

        # Spawn one analysis task per symbol
        for symbol in settings.orchestrator.symbols:
            task = asyncio.create_task(
                self._symbol_loop(symbol),
                name=f"symbol-{symbol.replace('/', '_')}",
            )
            self._tasks.append(task)

        # Spawn the message processor
        msg_task = asyncio.create_task(
            self._process_messages(),
            name="message-processor",
        )
        self._tasks.append(msg_task)

        # Set up graceful shutdown
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))
            except NotImplementedError:
                # Windows doesn't support add_signal_handler fully
                pass

        log.info("All tasks started. Waiting for signals...")

        # Wait for all tasks
        results = await asyncio.gather(*self._tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                log.error("Task raised: %s", r)

    async def stop(self):
        """Gracefully shut down all agents."""
        if not self._running:
            return
        self._running = False
        log.info("Shutting down AgentOrchestrator...")

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Close connections
        await self.exchange.close()
        await self.llm.close()
        log.info("Shutdown complete")

    # ------------------------------------------------------------------
    # Per-symbol analysis loop
    # ------------------------------------------------------------------

    async def _symbol_loop(self, symbol: str):
        """Main loop for a single symbol: analyse → assess → execute."""
        while self._running:
            try:
                # ----- Step 1: Analyst analyses the market -----
                log.info("[%s] Step 1: Analysing market context...", symbol)
                context = await self.analyst.analyse(symbol)
                self._symbol_states[symbol] = context

                await self._send_message("analyst", "orchestrator", "context", {
                    "symbol": symbol,
                    "regime": context.regime.value,
                    "confidence": context.confidence,
                })

                # ----- Step 2: Risk Manager evaluates -----
                log.info("[%s] Step 2: Evaluating risk...", symbol)
                risk = await self.risk_manager.evaluate(context)
                self._symbol_risks[symbol] = risk

                await self._send_message("risk_manager", "orchestrator", "risk_assessment", {
                    "symbol": symbol,
                    "decision": risk.decision.value,
                    "confidence": risk.confidence,
                })

                # ----- Step 3: Executor computes signal -----
                log.info("[%s] Step 3: Computing execution signal...", symbol)
                signal = await self.executor.compute_signal(context, risk)

                await self._send_message("executor", "orchestrator", "signal", {
                    "symbol": symbol,
                    "signal_type": signal.signal_type.value,
                    "price": signal.price,
                    "quantity": signal.quantity,
                    "reason": signal.reason,
                })

                # ----- Step 4: Execute or log -----
                await self._execute_signal(signal)

            except asyncio.CancelledError:
                log.info("[%s] Symbol loop cancelled", symbol)
                break
            except Exception as e:
                log.error("[%s] Symbol loop error: %s", symbol, e)
                await self._send_message("orchestrator", "system", "error", {
                    "symbol": symbol,
                    "error": str(e),
                })

            # Interval between analysis cycles
            await asyncio.sleep(settings.orchestrator.analysis_interval)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    async def _execute_signal(self, signal: ExecutionSignal):
        """Execute (or log) the computed signal."""
        if signal.signal_type == SignalType.HOLD:
            log.info("[%s] HOLD — %s", signal.symbol, signal.reason)
            return

        if settings.orchestrator.execution_mode == "paper":
            log.info(
                "[%s] PAPER EXECUTION: %s %.4f @ %.4f | %s",
                signal.symbol,
                signal.signal_type.value,
                signal.quantity,
                signal.price,
                signal.reason,
            )
            return

        # TODO: real exchange execution
        log.info(
            "[%s] LIVE EXECUTION: %s %.4f @ %.4f | %s",
            signal.symbol,
            signal.signal_type.value,
            signal.quantity,
            signal.price,
            signal.reason,
        )

    # ------------------------------------------------------------------
    # Message passing
    # ------------------------------------------------------------------

    async def _send_message(
        self,
        source: str,
        target: str,
        msg_type: str,
        payload: dict,
    ):
        """Send an async message to the internal bus."""
        msg = AgentMessage(
            agent_id=source,
            target=target,
            msg_type=msg_type,
            payload=payload,
        )
        await self._message_queue.put(msg)
        log.debug("Message: %s -> %s [%s]", source, target, msg_type)

    async def _process_messages(self):
        """Process messages from the internal bus (logging / alerting)."""
        while self._running:
            try:
                msg = await asyncio.wait_for(
                    self._message_queue.get(), timeout=1.0
                )

                # Log critical messages
                if msg.msg_type == "error":
                    log.error("Agent error | %s: %s", msg.agent_id, msg.payload)
                elif msg.msg_type == "risk_assessment":
                    decision = msg.payload.get("decision", "?")
                    if decision == "no_go":
                        log.warn("Risk veto for %s", msg.payload.get("symbol"))

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                log.error("Message processor error: %s", e)


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

async def main():
    orchestrator = AgentOrchestrator()
    try:
        await orchestrator.start()
    except KeyboardInterrupt:
        await orchestrator.stop()
    except Exception as e:
        log.critical("Fatal error: %s", e)
        await orchestrator.stop()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

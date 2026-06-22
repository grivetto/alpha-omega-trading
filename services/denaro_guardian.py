"""
Denaro Guardian Integration – Bridge between all enhanced modules and the existing squadra orchestrator.
"""
import asyncio, logging
from typing import Optional

class DenaroGuardian:
    """
    Central hub that wires all enhanced modules together and integrates with the existing squadra orchestrator.
    """

    def __init__(self, orchestrator):
        self.logger = logging.getLogger("DenaroGuardian")
        self.orchestrator = orchestrator
        self.early_warning = None
        self.regime_classifier = None
        self.advanced_risk_manager = None
        self.portfolio_optimizer = None
        self.performance_analytics = None
        self.strategy_evolution = None
        self._defensive_mode = False
        self._loop_running = False

    async def initialize(self):
        """Initialize all enhanced modules."""
        from services.early_warning import EarlyWarningSystem
        from services.portfolio_optimizer import PortfolioOptimizer
        from risk_modules.advanced_risk_manager import AdvancedRiskManager
        from risk_modules.market_regime_classifier import MarketRegimeClassifier
        from risk_modules.performance_analytics import PerformanceAnalytics
        from risk_modules.strategy_evolution import StrategyEvolution

        self.early_warning = EarlyWarningSystem(self.orchestrator)
        self.advanced_risk_manager = AdvancedRiskManager(
            initial_capital=self.orchestrator.initial_capital
        )
        self.regime_classifier = MarketRegimeClassifier(
            self.orchestrator.exchange,
            "SOL/EUR"
        )
        self.portfolio_optimizer = PortfolioOptimizer()
        self.performance_analytics = PerformanceAnalytics()
        self.strategy_evolution = StrategyEvolution()

        self.logger.info("DenaroGuardian: all modules initialized")

    async def activate_defensive_mode(self):
        """Put the whole system in defensive posture."""
        if self._defensive_mode:
            return
        
        self._defensive_mode = True
        self.logger.warning("DenaroGuardian: DEFENSIVE MODE ACTIVATED")

        # Reduce all bot investment limits
        for bot in self.orchestrator.bots:
            if hasattr(bot, 'max_investment'):
                bot.max_investment = min(bot.max_investment, self.orchestrator.max_per_bot_eur * 0.3)
            if hasattr(bot, 'base_order_eur'):
                bot.base_order_eur = min(bot.base_order_eur, 3.0)

    async def deactivate_defensive_mode(self):
        if not self._defensive_mode:
            return
        
        self._defensive_mode = False
        self.logger.info("DenaroGuardian: NORMAL MODE RESTORED")

        # Restore investment limits from orchestrator config
        for bot in self.orchestrator.bots:
            if hasattr(bot, 'max_investment'):
                bot.max_investment = self.orchestrator.max_per_bot_eur

    async def guardian_loop(self):
        """Main guardian loop – runs all modules periodically."""
        await asyncio.sleep(10)
        self._loop_running = True

        while self._loop_running:
            try:
                # 1. Fetch portfolio equity
                total_eur = await self.orchestrator._fetch_total_portfolio()
                self.advanced_risk_manager.update_capital(total_eur)

                # 2. Check early warning
                await self.early_warning.check_market_conditions()

                # 3. Classify market regime
                if self.orchestrator.exchange:
                    await self.regime_classifier.get_current_regime()

                # 4. Run stress test
                if self.orchestrator.exchange and self.orchestrator.bots:
                    sym = self.orchestrator.bots[0].symbol
                    stress = await self.advanced_risk_manager.stress_test(self.orchestrator.exchange, sym)
                    if stress.get("stress", 0) > 0.6:
                        self.logger.warning(f"Guardian: liquidity stress {stress['stress']:.2f} – reducing positions")
                        await self.activate_defensive_mode()

                # 5. Check consecutive losses
                if self.advanced_risk_manager.check_consecutive_losses(4):
                    await self.activate_defensive_mode()

            except Exception as e:
                self.logger.error(f"Guardian loop error: {e}")

            await asyncio.sleep(30)

    def stop(self):
        self._loop_running = False


# Integration hook – to be called from squadra/orchestrator.py:
"""
from services.denaro_guardian import DenaroGuardian

# In SquadraOrchestrator.__init__:
self.guardian = DenaroGuardian(self)

# In SquadraOrchestrator.run:
await self.guardian.initialize()
tasks.append(self.guardian.guardian_loop())

# Override:
async def activate_defensive_mode(self):
    await self.guardian.activate_defensive_mode()
"""
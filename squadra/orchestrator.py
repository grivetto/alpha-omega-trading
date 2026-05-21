"""Squadra Orchestrator — Coordina Ares, Hermes, Apollo e Artemis.
Gestione del rischio centralizzata:
  - Capitale massimo totale allocato
  - No overlapping pairs
  - Kill-switch automatico su drawdown
  - Report unificato
v4.0: + Artemis (BTC Long-Only Trend Follower)
"""
import os, sys, json, logging, asyncio, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core import ENV_PATH, DenaroOpportunisticCore
from ares_bot import AresIntradayTrendBot
from hermes_bot import HermesSentimentBot
from apollo_bot import ApolloPairBot
from artemis_bot import ArtemisTrendBot

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "squadra.json")

class SquadraOrchestrator:
    def __init__(self):
        self.logger = logging.getLogger("Squadra-Orchestrator")
        self.config = self._load_config()
        self.max_total_eur = self.config.get("max_total_eur", 80.0)
        self.max_per_bot_eur = self.config.get("max_per_bot_eur", 30.0)
        self.drawdown_limit = self.config.get("drawdown_limit_pct", 5.0)
        self.initial_capital = self.config.get("initial_capital_eur", 80.0)
        self.test_mode = self.config.get("test_mode", False)
        self.start_time = time.time()
        self.bots = []
        self.metrics = {}
        self.kill_switch = False

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {}

    async def check_risk(self):
        """Check drawdown and total exposure — activate kill-switch if breached."""
        if self.test_mode:
            return True

        current_portfolio = await self._fetch_total_portfolio()

        # Skip risk check if portfolio fetch failed (0 or very low)
        if current_portfolio <= 0:
            self.logger.warning("Portfolio fetch returned 0 — skipping risk check this cycle")
            return True

        # Track peak capital
        if current_portfolio > self.peak_capital:
            self.peak_capital = current_portfolio
            self.logger.info(f"New capital peak: {self.peak_capital:.2f}€")

        # Calcola drawdown reale dal picco
        if self.peak_capital > 0:
            drawdown_pct = (self.peak_capital - current_portfolio) / self.peak_capital * 100
        else:
            drawdown_pct = 0.0

        # Esposizione totale
        total_exposure = 0.0
        for bot in self.bots:
            if hasattr(bot, 'in_position') and bot.in_position:
                order_size = getattr(bot, 'base_order_eur', 0) or getattr(bot, 'last_order_eur', 0)
                total_exposure += order_size

        # Log
        self.logger.info(
            f"Risk | Portfolio={current_portfolio:.2f}€ | Peak={self.peak_capital:.2f} | "
            f"Drawdown={drawdown_pct:.2f}%/{self.drawdown_limit:.1f}% | "
            f"Exposure={total_exposure:.2f}€/{self.max_total_eur:.2f}€ | "
            f"KS={'⚠️ ON' if self.kill_switch else '✅'}"
        )

        # Se drawdown supera il limite → kill-switch
        if drawdown_pct > self.drawdown_limit:
            self.logger.error(
                f"🚨 DRAWDOWN {drawdown_pct:.2f}% > LIMIT {self.drawdown_limit}% — "
                f"ATTIVO KILL-SWITCH!"
            )
            self.kill_switch = True
            return False

        # Se l'esposizione totale è troppo alta
        if total_exposure > self.max_total_eur:
            self.logger.warning(
                f"⚠️ Total exposure {total_exposure:.2f}€ > limit {self.max_total_eur}€"
            )
            return False

        if self.kill_switch:
            self.logger.error("☠️ KILL SWITCH ACTIVE — all bots stopped")
            return False

        return True

    async def report(self):
        """Log unified status report"""
        lines = []
        lines.append("━" * 50)
        mode_tag = "🧪 TEST MODE" if self.test_mode else "🔴 LIVE"
        lines.append(f"SQUADRA DENARO OPPORTUNISTICO — {mode_tag}")
        uptime = (time.time() - self.start_time) / 60
        lines.append(f"Uptime: {uptime:.0f} min | Kill Switch: {'⚠️ ON' if self.kill_switch else '✅ OFF'}")
        lines.append(f"Max allocation: {self.max_total_eur}€")
        
        for bot in self.bots:
            name = bot.bot_name
            pair = bot.config.get("symbol", getattr(bot, 'symbol_a', '?'))
            in_pos = getattr(bot, 'in_position', False)
            lines.append(f"  • {name}: {pair} | {'🔴 IN POSITION' if in_pos else '⚪ WAITING'}")
        
        lines.append("━" * 50)
        self.logger.info("\n".join(lines))

    async def run(self):
        # Instantiate bots with test_mode
        ares = AresIntradayTrendBot(test_mode=self.test_mode)
        hermes = HermesSentimentBot(test_mode=self.test_mode)
        apollo = ApolloPairBot(test_mode=self.test_mode)
        artemis = ArtemisTrendBot(test_mode=self.test_mode)
        
        # Clamp configs
        ares.max_investment = self.max_per_bot_eur
        hermes.max_investment = self.max_per_bot_eur
        apollo.max_investment = self.max_per_bot_eur
        # Artemis ha budget separato (10€), non clampiamo oltre
        
        self.bots = [ares, hermes, apollo, artemis]
        self.logger.info(f"Squadra avviata: {len(self.bots)} bot, budget {self.max_total_eur}€, "
                        f"{'🧪 TEST MODE' if self.test_mode else '🔴 LIVE'}")

        # Run all bots + report concurrently
        async def bot_wrapper(bot):
            try:
                await bot.start()
            except Exception as e:
                self.logger.error(f"Bot {bot.bot_name} stopped: {e}")

        tasks = [bot_wrapper(b) for b in self.bots]
        tasks.append(self._report_loop())
        tasks.append(self._risk_loop())

        await asyncio.gather(*tasks)

    async def _report_loop(self):
        await asyncio.sleep(5)
        while True:
            await self.report()
            await asyncio.sleep(60)  # report ogni minuto

    async def _risk_loop(self):
        await asyncio.sleep(10)
        while True:
            ok = await self.check_risk()
            if not ok:
                self.logger.error("Risk limit breached — stopping all bots!")
                for bot in self.bots:
                    bot.stop()
            await asyncio.sleep(30)

    def stop(self):
        for bot in self.bots:
            bot.stop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), "squadra.log"))
        ]
    )
    orchestrator = SquadraOrchestrator()
    try:
        asyncio.run(orchestrator.run())
    except KeyboardInterrupt:
        orchestrator.stop()
        logging.info("Squadra stopped by user.")

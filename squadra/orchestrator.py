"""Squadra Orchestrator — Coordina Ares, Hermes, Apollo e Artemis.
Gestione del rischio centralizzata (v5.1 - spietato):
  - Kill-switch persistente su file (sopravvive a systemd restart)
  - Capitale massimo totale allocato
  - No overlapping pairs
  - Kill-switch automatico su drawdown globale (5%)
  - Per-bot stop-loss individuale (max_drawdown_eur 12€)
  - Circuit breaker: 3 loss consecutivi bloccano il bot
  - Risk loop ogni 10s (era 60s)
"""
import os, sys, json, logging, asyncio, time, math
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import ENV_PATH, DenaroOpportunisticCore
from dotenv import load_dotenv
import ccxt.async_support as ccxt

from ares_bot import AresIntradayTrendBot
from hermes_bot import HermesSentimentBot
from apollo_bot import ApolloPairBot
from artemis_bot import ArtemisTrendBot
from sentinel_bot import SentinelMeanRevBot
from vulcan_bot import VulcanGridBot
from doge_bot import DogeGridBot

from risk.kill_switch import KillSwitchManager, KS_OFF, KS_BOT_STOPPED, KS_LOCKED

CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config", "squadra.json")

# Stati kill-switch (importati da kill_switch.py)
# KS_OFF=0, KS_BOT_STOPPED=1, KS_LOCKED=2

class SquadraOrchestrator:
    def __init__(self):
        self.logger = logging.getLogger("Squadra-Orchestrator")
        self.config = self._load_config()
        self.max_total_eur = self.config.get("max_total_eur", 80.0)
        self.max_per_bot_eur = self.config.get("max_per_bot_eur", 30.0)
        self.drawdown_limit = self.config.get("drawdown_limit_pct", 5.0)
        self.initial_capital = self.config.get("initial_capital_eur", 125.0)
        self.per_bot_drawdown_limit = self.config.get("per_bot_drawdown_eur", 12.0)
        self.kill_switch_auto_reset = self.config.get("kill_switch_auto_reset", False)
        self.test_mode = self.config.get("test_mode", False)
        self.start_time = time.time()
        self.bots = []
        self.metrics = {}
        # Kill-switch persistente
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "trades.db")
        lock_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "bot_lock.json")
        self.kill_switch = KillSwitchManager(db_path, lock_file)
        self.kill_switch_state = self.kill_switch.get_global_state()
        self.peak_capital = self.initial_capital
        # Per-bot capital tracking (bot_name -> (initial_eur, peak_eur, current_eur))
        self.bot_capitals = {}
        # Exchange connection for balance checking
        self.exchange = None

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {}

    async def _init_exchange(self):
        if self.test_mode:
            return
        load_dotenv(ENV_PATH)
        api_key = os.getenv("BINANCE_API_KEY", "")
        api_secret = os.getenv("BINANCE_API_SECRET", "")
        if api_key and api_secret:
            self.exchange = ccxt.binance({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "warnOnFetchOpenOrdersWithoutSymbol": False},
            })

    async def _fetch_total_portfolio(self) -> float:
        """Fetch TOTAL portfolio value in EUR (EUR free + crypto at market prices)."""
        if self.test_mode:
            return 125.0
        if not self.exchange:
            return self.initial_capital
        try:
            bal = await self.exchange.fetch_balance()
            free = bal.get("free", {})
            total = bal.get("total", {})

            # Prendi il totale reale (free + locked), non solo free
            eur = float(total.get("EUR", 0) or 0)

            # Prezzi per convertire crypto in EUR
            symbols = [f"{a}EUR" for a in total if a not in ("EUR", "USDT", "BNB", "BUSD", "USDC")]
            prices = {}
            for s in symbols:
                try:
                    t = await self.exchange.fetch_ticker(s)
                    prices[s.replace("EUR", "")] = t["last"]
                except:
                    pass

            crypto_value = 0.0
            for asset, qty in total.items():
                if asset == "EUR" or qty <= 0:
                    continue
                if asset in prices:
                    crypto_value += float(qty) * prices[asset]
                elif asset == "USDT":
                    try:
                        t = await self.exchange.fetch_ticker("USDT/EUR")
                        crypto_value += float(qty) * t["last"]
                    except:
                        pass
                elif asset == "BNB":
                    try:
                        t = await self.exchange.fetch_ticker("BNB/EUR")
                        crypto_value += float(qty) * t["last"]
                    except:
                        pass

            total_portfolio = eur + crypto_value
            self.logger.debug(f"Portfolio: EUR={eur:.2f} + Crypto={crypto_value:.2f} = {total_portfolio:.2f}€")
            return round(total_portfolio, 2)
        except Exception as e:
            self.logger.error(f"Portfolio fetch error: {e}")
            # Fallback a EUR free
            try:
                bal2 = await self.exchange.fetch_balance()
                return float(bal2.get("free", {}).get("EUR", 0) or 0)
            except:
                return 0.0

    async def _fetch_per_bot_balances(self) -> dict:
        """
        Prova a stimare quanto EUR possiede ogni bot guardando il saldo EUR totale
        e i saldi dei singoli asset. Se un bot non ha posizioni aperte, il suo capitale
        è tutto EUR libero (pro-rata). I bot in posizione hanno bloccato EUR in crypto.

        Restituisce dict {bot_name: eur_estimate}
        """
        if self.test_mode or not self.exchange:
            return {}
        try:
            bal = await self.exchange.fetch_balance()
            total = bal.get("total", {})
            eur = float(total.get("EUR", 0) or 0)

            # Valuta ogni asset posseduto da ogni bot
            bot_assets = {}
            for bot in self.bots:
                name = bot.bot_name
                sym = getattr(bot, 'symbol', None) or getattr(bot, 'symbol_a', None)
                if sym:
                    bot_assets[name] = sym.split('/')[0]

            # Stima: il capitale di un bot = EUR che era suo + valore della sua crypto
            # Facciamo semplice: dividiamo EUR libero pro-rata tra i bot che non hanno posizioni,
            # e assegniamo valore crypto al bot che ha quel simbolo
            active_bots = [b for b in self.bots if b.bot_name in bot_assets]
            if not active_bots:
                return {}

            # Coarse: report each bot's own tracked P&L from core
            capitals = {}
            for bot in self.bots:
                name = bot.bot_name
                initial = getattr(bot, '_initial_balance_eur', 0)
                pnl = getattr(bot, '_total_pnl_eur', 0)
                peak = getattr(bot, '_peak_balance_eur', 0)
                current = initial + pnl if initial > 0 else 0
                capitals[name] = {
                    'initial': initial,
                    'current': current,
                    'peak': peak,
                    'drawdown_eur': peak - current if peak > 0 else 0,
                }
            return capitals
        except Exception as e:
            self.logger.error(f"Per-bot balance fetch error: {e}")
            return {}

    async def check_risk(self):
        """Check drawdown and total exposure — activate kill-switch if breached.
        Check per-bot drawdown FIRST (individual stop-loss), then global.
        Returns True = OK, False = risk breached.
        """
        if self.test_mode:
            return True

        # --- SE LOCKED, non si torna indietro ---
        if self.kill_switch_state >= KS_LOCKED:
            self.logger.error("🔒 KILL SWITCH LOCKED — no trading allowed. Restart manually.")
            return False

        current_eur = await self._fetch_total_portfolio()

        # Track peak capital
        if current_eur > self.peak_capital:
            self.peak_capital = current_eur
            self.logger.info(f"New capital peak: {self.peak_capital:.2f}€")

        # Calcola drawdown reale dal picco
        if self.peak_capital > 0:
            drawdown_pct = (self.peak_capital - current_eur) / self.peak_capital * 100
        else:
            drawdown_pct = 0.0
        drawdown_eur = self.peak_capital - current_eur

        # --- Per-bot drawdown check ---
        capitals = await self._fetch_per_bot_balances()
        per_bot_breach = False
        for name, cap in capitals.items():
            dd = cap['drawdown_eur']
            if dd > 0 and self.per_bot_drawdown_limit > 0 and dd >= self.per_bot_drawdown_limit:
                self.logger.error(
                    f"☠️ BOT DRAWDOWN LIMIT: {name} — "
                    f"drawdown {dd:.2f}€ >= limit {self.per_bot_drawdown_limit:.1f}€ | "
                    f"initial={cap['initial']:.2f} current={cap['current']:.2f} peak={cap['peak']:.2f}"
                )
                per_bot_breach = True
                # Ferma subito quel bot individualmente, prima del kill-switch globale
                for bot in self.bots:
                    if bot.bot_name == name:
                        self.logger.warning(f"🛑 Stopping {name} due to per-bot drawdown breach")
                        try:
                            await self._emergency_close_single_bot(bot)
                        except Exception as e:
                            self.logger.error(f"❌ Error closing {name}: {e}")
                        bot.stop()
                        break

        # Exposizione totale
        total_exposure = 0.0
        for bot in self.bots:
            if hasattr(bot, 'in_position') and bot.in_position:
                order_size = getattr(bot, 'base_order_eur', 0) or getattr(bot, 'last_order_eur', 0)
                total_exposure += order_size

        # Log
        self.logger.info(
            f"Risk | EUR={current_eur:.2f} | Peak={self.peak_capital:.2f} | "
            f"Drawdown={drawdown_pct:.2f}%/{self.drawdown_limit:.1f}% ({drawdown_eur:.2f}€) | "
            f"Exposure={total_exposure:.2f}€/{self.max_total_eur:.2f}€ | "
            f"KS={'🔒 LOCKED' if self.kill_switch_state >= KS_LOCKED else '🔴 ACTIVE' if self.kill_switch_state != KS_OFF else '✅ OFF'}"
        )

        # Se drawdown supera il limite → kill-switch
        if drawdown_pct > self.drawdown_limit:
            self.logger.error(
                f"🚨 GLOBAL DRAWDOWN {drawdown_pct:.2f}% > LIMIT {self.drawdown_limit}% — "
                f"ATTIVO KILL-SWITCH!"
            )
            self.kill_switch_state = KS_BOT_STOPPED
            self.kill_switch.lock_global()
            return False

        # Se l'exposizione totale è troppo alta
        if total_exposure > self.max_total_eur:
            self.logger.warning(
                f"⚠️ Total exposure {total_exposure:.2f}€ > limit {self.max_total_eur}€"
            )
            return False

        if self.kill_switch_state != KS_OFF:
            self.logger.warning("☠️ KILL SWITCH ACTIVE — all bots stopped")
            return False

        return True

    async def _emergency_close_single_bot(self, bot):
        """Close a single bot's position via market sell + cancel orders."""
        if self.test_mode:
            return

        name = bot.bot_name
        symbol = getattr(bot, 'symbol', getattr(bot, 'symbol_a', None))
        if not symbol:
            return

        base = symbol.split('/')[0]

        # 1. Market sell del saldo disponibile
        try:
            bal = await self.exchange.fetch_balance()
            free_amt = float(bal.get(base, {}).get('free', 0) or 0)
            if free_amt > 0:
                sell_amt = free_amt * 0.997
                # Round down to LOT_SIZE step to avoid precision errors
                LOT_STEPS = {'ADA': 0.1, 'ALGO': 1.0, 'BNB': 0.001, 'BTC': 0.00001, 'CHZ': 1.0, 'DOGE': 1.0, 'DOT': 0.01, 'ETH': 0.0001, 'GALA': 1.0, 'NEAR': 0.1, 'SAND': 1.0, 'SOL': 0.001, 'SUI': 0.1, 'UNI': 0.01, 'VET': 0.01, 'XLM': 1.0, 'XRP': 0.1, 'ZIL': 0.1}
                step = LOT_STEPS.get(base, 0.0001)
                rounded = math.floor(sell_amt / step) * step
                if rounded <= 0:
                    self.logger.warning(f"⚠️ {name}: {symbol} amount {sell_amt:.8f} rounds to 0 after LOT_SIZE={step} — skipping sell")
                else:
                    self.logger.warning(f"🚨 {name}: MARKET SELL {symbol} {rounded:.8f} (free={free_amt:.8f})")
                    await self.exchange.create_market_sell_order(symbol, rounded)
                    self.logger.warning(f"✅ {name}: market sell executed")
            else:
                self.logger.warning(f"⚠️ {name}: no {base} balance to sell")
        except Exception as e:
            self.logger.error(f"❌ {name}: market sell failed: {e}")

        # 2. Cancel open orders
        try:
            orders = await self.exchange.fetch_open_orders(symbol)
            for o in orders:
                try:
                    await self.exchange.cancel_order(o['id'], symbol)
                    self.logger.info(f"🗑️ {name}: cancelled order {o['id']}")
                except Exception as e:
                    self.logger.warning(f"⚠️ {name}: cancel order {o['id']} failed: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ {name}: fetch orders failed: {e}")

        # 3. Reset bot state
        bot.in_position = False
        bot.entry_price = 0
        bot.entry_amount = 0
        if hasattr(bot, 'save_position_to_db'):
            bot.save_position_to_db()

    async def _emergency_close_positions(self):
        """Close ALL positions across ALL bots — market sell, non limit!
        Poi cancella TUTTI gli ordini aperti su tutti i simboli.
        """
        self.logger.error("🚨 EMERGENCY CLOSE ALL — starting full liquidation")

        # Fase 1: market sell per ogni bot in posizione
        for bot in self.bots:
            if not getattr(bot, 'in_position', False):
                continue
            try:
                await self._emergency_close_single_bot(bot)
            except Exception as e:
                self.logger.error(f"❌ {bot.bot_name}: emergency close failed: {e}")

        # Fase 2: kill-switch → LOCKED (persistente)
        self.kill_switch.lock_global()
        self.kill_switch_state = self.kill_switch.get_global_state()
        self.logger.error("🔒 KILL SWITCH LOCKED — no trading will resume until bot_lock.json is manually reset")

    async def report(self):
        """Log unified status report"""
        lines = []
        lines.append("━" * 50)
        mode_tag = "🧪 TEST MODE" if self.test_mode else "🔴 LIVE"
        ks_tag = "🔒 LOCKED" if self.kill_switch_state >= KS_LOCKED else "🔴 ACTIVE" if self.kill_switch_state != KS_OFF else "✅ OFF"
        lines.append(f"SQUADRA DENARO OPPORTUNISTICO — {mode_tag} | KS: {ks_tag}")
        uptime = (time.time() - self.start_time) / 60
        lines.append(f"Uptime: {uptime:.0f} min | Peak: {self.peak_capital:.2f}€")

        for bot in self.bots:
            name = bot.bot_name
            pair = bot.config.get("symbol", getattr(bot, 'symbol_a', getattr(bot, 'symbol', '?')))
            in_pos = getattr(bot, 'in_position', False)
            eur = getattr(bot, 'last_order_eur', 0)
            dd_stopped = getattr(bot, '_drawdown_stopped', False)

            # Grid bot detection
            grid_state = getattr(bot, '_grid_state', None)
            pnl_eur = ""
            if grid_state:
                tot_pnl = grid_state.get('total_pnl_eur', 0)
                cycles = grid_state.get('cycle_count', 0)
                active = grid_state.get('active', False)
                pnl_eur = f" | PnL={tot_pnl:.2f}€ ({cycles} cicli)"
                dd_indicator = "☠️" if dd_stopped else ("🟢" if active else "⚪")
                status_text = "GRID ACTIVE" if active else ("STOP-LOSS" if dd_stopped else "WAITING")
            else:
                dd_indicator = "☠️" if dd_stopped else ("🔴" if in_pos else "⚪")
                status_text = "STOP-LOSS HIT" if dd_stopped else ("IN POS" if in_pos else "WAITING")

            lines.append(f"  • {name}: {pair} | {dd_indicator} {status_text} | order={eur:.1f}€{pnl_eur}")

        lines.append("━" * 50)
        self.logger.info("\n".join(lines))

    async def run(self):
        await self._init_exchange()

        # ── Kill-switch check all'avvio ──
        if self.kill_switch_state >= KS_LOCKED:
            self.logger.error("🔒 KILL SWITCH LOCKED — cannot start squadra. Reset bot_lock.json manually.")
            return

        # Instantiate bots with test_mode
        ares = AresIntradayTrendBot(test_mode=self.test_mode)
        hermes = HermesSentimentBot(test_mode=self.test_mode)
        apollo = ApolloPairBot(test_mode=self.test_mode)
        artemis = ArtemisTrendBot(test_mode=self.test_mode)
        sentinel = SentinelMeanRevBot(test_mode=self.test_mode)
        vulcan = VulcanGridBot(test_mode=self.test_mode)
        doge = DogeGridBot(test_mode=self.test_mode)
        # Clamp configs
        ares.max_investment = self.max_per_bot_eur
        hermes.max_investment = self.max_per_bot_eur
        apollo.max_notional_eur = self.max_per_bot_eur
        sentinel.max_investment = self.max_per_bot_eur

        self.bots = [ares, hermes, apollo, artemis, sentinel, vulcan, doge]
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
            await asyncio.sleep(60)

    async def _risk_loop(self):
        await asyncio.sleep(10)
        while True:
            ok = await self.check_risk()
            if not ok and self.kill_switch_state >= KS_BOT_STOPPED:
                self.logger.error("🚨 KILL SWITCH — closing positions and locking!")
                await self._emergency_close_positions()
                for bot in self.bots:
                    bot.stop()
                self.logger.error("🔒 Squadra fermata. Kill-switch LOCKED — reset bot_lock.json manualmente.")
            elif not ok and self.kill_switch_state >= KS_LOCKED:
                self.logger.warning("🔒 Kill-switch locked — waiting for manual reset")
            await asyncio.sleep(10)  # ogni 10s, non 60s

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

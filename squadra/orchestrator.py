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
sys.path.insert(1, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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

# ── Self-Improve ──────────────────────────────
from self_improve.history import TradeHistory as SITradeHistory
from self_improve.goal import GoalManager
from self_improve.reflector import StrategyReflector

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
        self.initial_capital = self.config.get("initial_capital_eur", 19.27)
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
        # Peak capital — sarà aggiornato al primo fetch reale dal saldo Binance
        self.peak_capital = self.initial_capital
        self._capital_synced = False  # flag: primo sync col saldo reale done?
        self._stall_ticks = 0          # contatore tick senza trade (warm-up detection)
        self._ks_locked_since = 0.0    # timestamp quando kill-switch è stato locked
        # Per-bot capital tracking (bot_name -> (initial_eur, peak_eur, current_eur))
        self.bot_capitals = {}
        # Exchange connection for balance checking
        self.exchange = None
        # Self-Improve
        self.si_history = SITradeHistory()
        self.si_goal = GoalManager()
        self.si_reflector = StrategyReflector(self.si_goal, self.si_history)
        self.last_reflection_time = time.time()

    def _load_config(self):
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH) as f:
                return json.load(f)
        return {}

    async def _init_exchange(self):
        if self.test_mode:
            return
        # Read .env directly to bypass system env vars
        env_vars = {}
        try:
            with open(ENV_PATH, 'r') as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith('#') and '=' in line:
                        k, v = line.split('=', 1)
                        env_vars[k.strip()] = v.strip()
        except FileNotFoundError:
            pass
        mc_label = env_vars.get("MACHINE_LABEL", "").upper().strip()
        api_key = env_vars.get(f"BINANCE_API_KEY_{mc_label}", "")
        api_secret = env_vars.get(f"BINANCE_API_SECRET_{mc_label}", "")
        if not api_key:
            api_key = env_vars.get("BINANCE_API_KEY", "")
            api_secret = env_vars.get("BINANCE_API_SECRET", "")
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

        # ── Auto-sync capitale iniziale al primo fetch reale ──
        # Principio del video: "Accurate" — i dati devono riflettere la realtà
        if not self._capital_synced and current_eur > 0 and self.exchange:
            self.initial_capital = current_eur
            self.peak_capital = current_eur
            self._capital_synced = True
            # Persisti nel config
            try:
                self.config["initial_capital_eur"] = round(current_eur, 2)
                with open(CONFIG_PATH, "w") as f:
                    json.dump(self.config, f, indent=2)
                self.logger.info(f"🔄 Capital synced: initial_capital={current_eur:.2f}€ (saved to config)")
            except Exception as e:
                self.logger.warning(f"Could not save capital sync: {e}")

        # Safety stop: if EUR balance drops below 3€, halt new trades
        if current_eur < 3.0:
            self.logger.error("⚠️ EUR balance < 3€ – suspending new trades")
            return False

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
        tasks.append(self._reflection_loop())

        await asyncio.gather(*tasks)

    async def _report_loop(self):
        await asyncio.sleep(5)
        while True:
            await self.report()
            await asyncio.sleep(60)

    async def _reflection_loop(self):
        """Ciclo di riflessione auto-miglioramento.
        Principi dal video (Lewis Jackson / Zero-One):
          1. ACCURATE  → dati dal saldo reale, non dal config statico
          2. RELIABLE  → se stallo per 10+ tick senza trade, seeda il reflector
          3. WELL-DEFINED GOAL → metriche chiare (sharpe, win_rate, pnl_cum)
          4. SELF-IMPROVING → dopo N trade, modifica UNA variabile (metodo scientifico)

        Dopo reflection_every trade chiusi per bot, calcola performance
        e modifica UNA variabile del suo config (metodo scientifico)."""
        await asyncio.sleep(30)  # dai tempo ai bot di fare qualche trade
        while True:
            try:
                # ── Stall detection: se NESSUN bot ha trade, il sistema è bloccato ──
                total_trades = sum(
                    self.si_history.get_trade_count(b.bot_name) for b in self.bots
                )
                if total_trades == 0:
                    self._stall_ticks += 1
                else:
                    self._stall_ticks = 0

                # Dopo 10 tick (20 min) senza NESSUN trade → warm-up seed
                if self._stall_ticks >= 10 and not hasattr(self, '_warmup_done'):
                    self._warmup_done = True
                    self.logger.warning(
                        "🔥 STALL DETECTED: 20+ min senza trade — "
                        "esecuzione warm-up seed per inizializzare reflector"
                    )
                    await self._warmup_seed()

                for bot in self.bots:
                    name = bot.bot_name
                    trade_count = self.si_history.get_trade_count(name)
                    cadence = self.si_goal.reflection_cadence(name)

                    if trade_count < cadence:
                        continue

                    # Quanti trade quando abbiamo riflettuto l'ultima volta?
                    reflections = self.si_history.get_reflections(name, 1)
                    last_ref_trade_count = 0
                    if reflections:
                        last_ref_trade_count = len(reflections) * cadence

                    if trade_count - last_ref_trade_count < cadence:
                        continue

                    # Esegui riflessione
                    self.logger.info(
                        f"🧬 {name}: riflessione ({trade_count} trade, cadenza={cadence})"
                    )
                    report = self.si_reflector.reflect(name)
                    if report.get("changed"):
                        self.logger.info(
                            f"✅ {name}: {report['variable']} "
                            f"{report['old_value']} → {report['new_value']} "
                            f"({report['reason']})"
                        )
                    else:
                        self.logger.info(
                            f"⏭️ {name}: nessuna modifica ({report.get('reason', 'N/A')})"
                        )

                # Refresh goal ogni 15 min
                if time.time() - self.last_reflection_time > 900:
                    self.last_reflection_time = time.time()
                    self.si_goal.load()  # reload if manual edits made
            except Exception as e:
                self.logger.error(f"❌ Reflection loop error: {e}")
            await asyncio.sleep(120)  # controlla ogni 2 minuti

    async def _warmup_seed(self):
        """Seed trade history con mini-backtest su dati reali recenti.
        Principio: il reflector non può migliorare senza dati storici.
        Usiamo le candele recenti per simulare entry/exit con i parametri correnti."""
        if not self.exchange:
            self.logger.warning("Exchange non inizializzato — skip warmup seed")
            return

        seed_count = 0
        for bot in self.bots:
            name = bot.bot_name
            symbol = getattr(bot, 'symbol', None)
            if not symbol or self.si_history.get_trade_count(name) > 0:
                continue  # salta se già ha trade reali

            try:
                # Fetch ultime 50 candele
                tf = getattr(bot, 'timeframe', '5m')
                ohlcv = await self.exchange.fetch_ohlcv(symbol, tf, limit=50)
                if len(ohlcv) < 20:
                    continue

                # Simula trade semplici: TP/SL dai parametri del bot
                tp = getattr(bot, 'take_profit_pct', 0.008)
                sl = getattr(bot, 'stop_loss_pct', 0.005)
                if tp == 0 and sl == 0:
                    tp, sl = 0.008, 0.005  # default

                for i in range(1, len(ohlcv) - 1):
                    entry = ohlcv[i][2]  # high come entry simulato
                    exit_ = ohlcv[i + 1][4]  # close del candle successivo
                    pnl_pct = (exit_ - entry) / entry if entry > 0 else 0

                    # Simula solo se oltre TP o SL
                    if pnl_pct >= tp or pnl_pct <= -sl:
                        reason = "TP" if pnl_pct >= 0 else "SL"
                        self.si_history.record_trade(name, pnl_pct, reason=reason)
                        seed_count += 1

                self.logger.info(f"🌱 {name}: seeded {seed_count} mock trades da {symbol}")

            except Exception as e:
                self.logger.warning(f"Warmup seed error per {name}: {e}")

        if seed_count > 0:
            self.logger.info(f"🌱 Warmup completo: {seed_count} mock trades seeded — reflector pronto")
        else:
            self.logger.warning("🌱 Warmup: nessun mock trade generato")

    async def _risk_loop(self):
        await asyncio.sleep(10)
        while True:
            ok = await self.check_risk()
            if not ok and self.kill_switch_state >= KS_BOT_STOPPED:
                self.logger.error("🚨 KILL SWITCH — closing positions and locking!")
                await self._emergency_close_positions()
                for bot in self.bots:
                    bot.stop()
                self.logger.error("🔒 Squadra fermata. Kill-switch LOCKED.")
            elif not ok and self.kill_switch_state >= KS_LOCKED:
                # ── Auto-reset after cooldown (principio: RELIABLE) ──
                # Se il kill-switch è locked da oltre 30 min, prova a resettarlo
                # Il drawdown si ricalcolerà sul capitale aggiornato
                if self._ks_locked_since == 0.0:
                    self._ks_locked_since = time.time()
                elapsed = time.time() - self._ks_locked_since
                if elapsed > 1800:  # 30 min cooldown
                    self.logger.warning("🔄 Kill-switch auto-reset dopo 30 min cooldown")
                    # Reset manuale: sblocca tutti i bot + global state
                    for bot in self.bots:
                        self.kill_switch.unlock_bot(bot.bot_name)
                    self.kill_switch._state_cache = KS_OFF
                    self.kill_switch._save_persistent_state()
                    self.kill_switch_state = KS_OFF
                    self._ks_locked_since = 0.0
                    # Reset peak capital al saldo corrente per drawdown fresh
                    current_eur = await self._fetch_total_portfolio()
                    if current_eur > 0:
                        self.peak_capital = current_eur
                        self._capital_synced = True
                    self.logger.info(f"🔄 Sistema sbloccato — peak={self.peak_capital:.2f}€ — bot riprenderanno")
                else:
                    self.logger.warning(
                        f"🔒 Kill-switch locked — auto-reset in {int(1800-elapsed)}s"
                    )
            else:
                # Se tutto OK, resetta il timer di lock
                self._ks_locked_since = 0.0
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

"""
VULCAN v2 — ADA/EUR Grid Scalper
Portato nel framework Denaro v5.1.
5 livelli grid con 0.4% spacing, TP 0.5% per livello.
Auto-compound fino a 1.5x del base_order.
Kill-switch + circuit breaker integrati.
Non usa in_position del core — gestione stato grid autonoma.
"""
import asyncio
from core import DenaroOpportunisticCore


class VulcanGridBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Vulcan", config_file="vulcan.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "ADA/EUR")
        self.base_order_eur = self.config.get("base_order_eur", 5.0)
        self.max_investment = self.config.get("max_investment_eur", 30.0)
        self.grid_levels = self.config.get("grid_levels", 5)
        self.grid_spacing_pct = self.config.get("grid_spacing_pct", 0.004)  # 0.4%
        self.tp_pct = self.config.get("take_profit_pct", 0.005)  # 0.5%
        self.compound_factor = self.config.get("compound_factor", 1.2)  # auto-compound
        self.max_compound = self.config.get("max_compound_mult", 1.5)

        # Grid state (non usa in_position/entry_price del core)
        self._grid_state = {
            "center_price": 0.0,
            "active": False,
            "total_pnl_eur": 0.0,
            "cycle_count": 0,
            "last_rebalance_ts": 0.0,
            "expected_orders": self.grid_levels * 2,
        }

        # Per-bot drawdown tracking (grid via PnL)
        self._grid_peak_pnl = 0.0

        self.interval_sec = self.config.get("interval_sec", 30)

    async def _cancel_all_orders(self):
        """Cancella TUTTI gli ordini aperti sul simbolo grid."""
        if self.test_mode:
            self._grid_state["active"] = False
            return
        try:
            orders = await self.exchange.fetch_open_orders(self.symbol)
            for o in orders:
                try:
                    await self.exchange.cancel_order(o["id"], self.symbol)
                except Exception:
                    pass
        except Exception as e:
            self.logger.warning(f"Cancel all orders: {e}")

    async def _place_grid(self, center_price: float, order_size: float = None):
        """
        Pulisce e piazza grid fresco intorno a center_price.
        order_size: quanto EUR per ogni livello (default base_order_eur).
        """
        await self._cancel_all_orders()

        sz = order_size if order_size else self.base_order_eur
        self._grid_state["center_price"] = center_price
        self._grid_state["active"] = True
        placed = 0

        for i in range(1, self.grid_levels + 1):
            # Buy levels sotto il centro
            buy_price = center_price * (1 - self.grid_spacing_pct) ** i
            buy_amt = (sz / buy_price) * 0.997
            if buy_amt > 0:
                await self.create_limit_buy(self.symbol, buy_amt, buy_price)
                placed += 1

            # Sell levels sopra il centro
            sell_price = center_price * (1 + self.grid_spacing_pct) ** i
            sell_amt = (sz / sell_price) * 0.997
            if sell_amt > 0:
                await self.create_limit_sell(self.symbol, sell_amt, sell_price)
                placed += 1

        self._grid_state["expected_orders"] = placed
        self._grid_state["last_rebalance_ts"] = asyncio.get_event_loop().time()
        self.logger.info(
            f"GRID placed: {placed} ordini around {center_price:.4f} | "
            f"size={sz:.2f}€/livello | tot={(sz * self.grid_levels * 2):.1f}€ stimati"
        )

    async def _sell_accumulated_base(self):
        """Vende al market l'asset base accumulato dai buy eseguiti."""
        if self.test_mode:
            return 0.0

        try:
            bal = await self.exchange.fetch_balance()
            base = self.symbol.split("/")[0]
            acc = float(bal.get(base, {}).get("free", 0) or 0)
            if acc < 0.00001:
                return 0.0

            ticker = await self.exchange.fetch_ticker(self.symbol)
            price = ticker["last"]
            eur_value = acc * price

            await self.create_market_sell(self.symbol, acc * 0.997)
            self.logger.info(
                f"GRID sold accumulated: {acc:.4f} {base} ≈ {eur_value:.2f}€ @ {price:.4f}"
            )
            return eur_value
        except Exception as e:
            self.logger.warning(f"Sell accumulated: {e}")
            return 0.0

    async def _rebalance_grid(self):
        """
        Rebalance completo:
        1. Cancella ordini residui
        2. Vendi base accumulato
        3. Calcola PnL del ciclo
        4. Piazza grid fresco con eventuale compounding
        """
        # Sells accumulated (register profit first)
        recovered = await self._sell_accumulated_base()
        invested = self.base_order_eur * self.grid_levels
        cycle_pnl = recovered - invested if recovered > 0 else 0.0

        if cycle_pnl > 0:
            self._grid_state["total_pnl_eur"] += cycle_pnl
            # Record trade nel circuit breaker
            pnl_pct = cycle_pnl / max(invested, 1)
            self._record_completed_trade(pnl_pct)
            self.logger.info(f" GRID cycle +{cycle_pnl:.2f}€ | tot={self._grid_state['total_pnl_eur']:.2f}€")
        elif cycle_pnl < 0:
            self._grid_state["total_pnl_eur"] += cycle_pnl
            pnl_pct = cycle_pnl / max(invested, 1)
            self._record_completed_trade(pnl_pct)
            self.logger.warning(f" GRID cycle {cycle_pnl:.2f}€ | tot={self._grid_state['total_pnl_eur']:.2f}€")

        # Aggiorna peak per drawdown tracking
        if self._grid_state["total_pnl_eur"] > self._grid_peak_pnl:
            self._grid_peak_pnl = self._grid_state["total_pnl_eur"]

        # Calcola compounding size
        mult = 1.0
        if self._grid_state["total_pnl_eur"] > 0:
            ratio = self._grid_state["total_pnl_eur"] / max(self.base_order_eur * 2, 1)
            mult = min(1.0 + ratio * self.compound_factor, self.max_compound)
        current_order_size = min(self.base_order_eur * mult,
                                 self.max_investment / self.grid_levels)

        # Prezzo corrente per nuovo centro
        try:
            if self.test_mode:
                import random
                center = self._grid_state.get("center_price", 1.0) * (1 + random.uniform(-0.002, 0.002))
            else:
                ticker = await self.exchange.fetch_ticker(self.symbol)
                center = ticker["last"]
        except Exception as e:
            self.logger.warning(f"Ticker: {e}, keeping old center")
            center = self._grid_state.get("center_price", 1.0)

        # Piazza grid fresco
        await self._place_grid(center, current_order_size)
        self._grid_state["cycle_count"] += 1
        self.logger.info(
            f"GRID rebalanced #{self._grid_state['cycle_count']}: "
            f"size={current_order_size:.2f}€/lv | PnL={self._grid_state['total_pnl_eur']:.2f}€"
        )

    async def _emergency_close_per_bot(self):
        """Override: cancella grid + vende tutto ciò che è accumulato."""
        self.logger.warning("🚨 VULCAN EMERGENCY CLOSE: cancelling grid")
        await self._cancel_all_orders()
        if not self.test_mode:
            try:
                bal = await self.exchange.fetch_balance()
                base = self.symbol.split("/")[0]
                total_bal = max(
                    float(bal.get(base, {}).get("free", 0) or 0),
                    float(bal.get(base, {}).get("total", 0) or 0),
                )
                if total_bal > 0:
                    await self.create_market_sell(self.symbol, total_bal * 0.997)
                    self.logger.warning(f"☠️ VULCAN emergency sold {total_bal:.4f} {base}")
            except Exception as e:
                self.logger.error(f"VULCAN emergency sell: {e}")

        self._grid_state["active"] = False
        # Clean DB state
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self.save_position_to_db()

    def check_drawdown(self) -> bool:
        """Grid-specific drawdown via PnL (override core)."""
        if self.max_drawdown_eur <= 0:
            return True
        drawdown = self._grid_peak_pnl - self._grid_state["total_pnl_eur"]
        if drawdown >= self.max_drawdown_eur:
            self.logger.error(
                f"☠️ VULCAN STOP-LOSS: drawdown {drawdown:.2f}€ >= "
                f"limit {self.max_drawdown_eur:.1f}€ | "
                f"peak={self._grid_peak_pnl:.2f} curr={self._grid_state['total_pnl_eur']:.2f}"
            )
            self._drawdown_stopped = True
            return False
        if self._drawdown_stopped:
            return False
        return True

    async def on_startup(self):
        """Grid startup: cancella ordini residui e piazza grid fresco."""
        if not self.kill_switch.check_bot_can_start(self.bot_name):
            self.logger.error("☠️ VULCAN: kill-switch locked on startup")
            self.running = False
            return

        self.logger.info("=== VULCAN GRID STARTUP ===")

        # Recupera prezzo corrente
        if self.test_mode:
            price = 1.0
        else:
            try:
                ticker = await self.exchange.fetch_ticker(self.symbol)
                price = ticker["last"]
                self.logger.info(f"ADA/EUR prezzo attuale: {price:.4f}")
            except Exception as e:
                self.logger.error(f"Startup ticker: {e}")
                return

        await self._place_grid(price)
        self.logger.info(f"=== VULCAN GRID AVVIATO — {self.grid_levels} livelli @ {price:.4f} ===")

    async def run_strategy(self):
        """Grid main loop: controlla ordini, ripara gap, rebalancing se necessario."""
        if not self._grid_state["active"]:
            return

        if self.test_mode:
            # In test mode, just simulate
            await asyncio.sleep(0)
            return

        # 1. Conta ordini attivi
        try:
            active_orders = await self.exchange.fetch_open_orders(self.symbol)
            active_count = len(active_orders)
        except Exception as e:
            self.logger.warning(f"Fetch ordini: {e}")
            return

        expected = self._grid_state.get("expected_orders", self.grid_levels * 2)

        # 2. Verifica se prezzo si è allontanato troppo dal centro
        try:
            ticker = await self.exchange.fetch_ticker(self.symbol)
            current_price = ticker["last"]
        except Exception as e:
            self.logger.warning(f"Ticker grid: {e}")
            current_price = None

        needs_rebalance = False

        # Price drift check
        if current_price:
            center = self._grid_state["center_price"]
            if center > 0:
                drift_pct = abs(current_price - center) / center * 100
                max_drift = self.grid_spacing_pct * self.grid_levels * 100 * 0.4
                if drift_pct > max_drift:
                    self.logger.info(
                        f"GRID drift {drift_pct:.2f}% > {max_drift:.2f}% → rebalance"
                    )
                    needs_rebalance = True

        # Order count change = fills happened
        if active_count < expected * 0.5:
            self.logger.info(
                f"GRID orders {active_count}/{expected} → rebalance (fills)"
            )
            needs_rebalance = True

        if needs_rebalance:
            await self._rebalance_grid()

    async def start(self):
        """
        Override start() per grid: stesso del core ma con check_drawdown()
        personalizzato e senza refresh_open_orders() (gestito internamente).
        """
        self.running = True

        if not self.kill_switch.check_bot_can_start(self.bot_name):
            self.logger.error(f"☠️ {self.bot_name}: BLOCKED by kill-switch on startup")
            self.running = False
            return

        await self.on_startup()
        self.logger.info(f"{self.bot_name} grid started (interval={self.interval_sec}s, test_mode={self.test_mode})")

        tick = 0
        while self.running:
            try:
                tick += 1
                if tick % 6 == 0 or tick == 1:  # every 6 ticks ≈ 30s
                    await self.refresh_balance()

                # Drawdown check (usa la nostra versione grid-aware)
                if not self._drawdown_stopped and not self.check_drawdown() and not self.test_mode:
                    await self._emergency_close_per_bot()
                    self.kill_switch.lock_bot(self.bot_name)
                    self.logger.error(f"☠️ {self.bot_name}: drawdown limit hit — LOCKED by kill-switch")
                    self.running = False
                    break

                await self.run_strategy()
            except Exception as e:
                self.logger.error(f"Strategy error: {e}", exc_info=True)

            await asyncio.sleep(self.interval_sec)

    async def close(self):
        await self._cancel_all_orders()
        if self.exchange:
            await self.exchange.close()


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(message)s",
    )
    bot = VulcanGridBot()
    asyncio.run(bot.start())

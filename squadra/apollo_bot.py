"""
Apollo — Pair Trading Statistico ETH/BTC (MNMR v1.0)
=====================================================
Market-neutral mean reversion basato su cointegrazione Engle-Granger.

Segnale: Z-score dello spread cointegrato ETH/BTC.
- Z > +2.0 (ETH_OVERPRICED)  → short ETH, long BTC
- Z < -2.0 (ETH_UNDERPRICED) → long ETH, short BTC
- |Z| < 0.5 → exit (mean reversion avvenuta)
- |Z| > 3.5 → emergency exit (divergenza)
- >48h in posizione → time-stop exit

Esecuzione dual-order via PairTradeExecutor.
Position sizing: Kelly 5% del capitale disponibile.
Test cointegrazione ricalcolato ogni 24h.
"""

import asyncio
import time
import json
import os

from core import DenaroOpportunisticCore
from utils.analysis import CointegrationEngine, Z_ENTRY, Z_EXIT, Z_EMERGENCY, COINT_P_THRESHOLD, MIN_SAMPLE
from executor import PairTradeExecutor, expected_profit_threshold

# Path to config
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_DIR = os.path.join(SCRIPT_DIR, "config")


class ApolloPairBot(DenaroOpportunisticCore):
    """
    Apollo MNMR — pair trading statistico ETH/BTC su Binance Spot.
    Market-neutral: profitta dalla mean reversion dello spread cointegrato.
    """

    def __init__(self, test_mode=False):
        super().__init__(bot_name="Apollo", config_file="apollo.json", test_mode=test_mode)
        self.timeframe = self.config.get("timeframe", "5m")
        self.lookback = self.config.get("lookback_period", 96)
        self.z_entry = self.config.get("z_entry", Z_ENTRY)
        self.z_exit = self.config.get("z_exit", Z_EXIT)
        self.z_emergency = self.config.get("z_emergency", Z_EMERGENCY)
        self.base_order_eur = self.config.get("base_order_eur", 10.0)
        self.max_notional_eur = self.config.get("max_notional_eur", 25.0)
        self.kelly_fraction = self.config.get("kelly_fraction", 0.05)
        self.time_stop_hours = self.config.get("time_stop_hours", 48)
        self.coint_refresh_hours = self.config.get("coint_refresh_hours", 24)

        # Symbols
        self.symbol_a = self.config.get("symbol_a", "ETH/EUR")
        self.symbol_b = self.config.get("symbol_b", "BTC/EUR")
        self.base_a = self.config.get("base_a", "ETH")
        self.base_b = self.config.get("base_b", "BTC")

        # Cointegration engine
        self.coint_engine = CointegrationEngine(
            p_threshold=self.config.get("coint_p_threshold", COINT_P_THRESHOLD))

        # Pair trade executor
        self.executor = PairTradeExecutor(self)

        # State
        self.in_position = False
        self.entry_price_eth = 0.0
        self.entry_price_btc = 0.0
        self._coint_result = None
        self._last_coint_time = 0
        self._last_log = {}

        self.logger.info(
            f"ApolloPairBot inizializzato | {self.symbol_a}/{self.symbol_b} | "
            f"z_entry={self.z_entry} z_exit={self.z_exit} | "
            f"timeframe={self.timeframe} | Kelly={self.kelly_fraction*100:.1f}% | "
            f"time_stop={self.time_stop_hours}h | "
            f"test_mode={test_mode}"
        )

    # ── CORE LOGIC ─────────────────────────────────────────────

    async def run_strategy(self):
        """Ciclo principale: refresh prezzi → cointegrazione → segnale → esecuzione."""
        now = time.time()

        # Fetch OHLCV per entrambi i simboli
        ohlcv_a = await self.fetch_ohlcv(self.symbol_a, self.timeframe, limit=self.lookback + 10)
        ohlcv_b = await self.fetch_ohlcv(self.symbol_b, self.timeframe, limit=self.lookback + 10)

        if not ohlcv_a or not ohlcv_b:
            self.logger.warning("OHLCV fetch fallito, skipping ciclo")
            return

        prices_a = [c[4] for c in ohlcv_a]
        prices_b = [c[4] for c in ohlcv_b]
        current_price_a = prices_a[-1]
        current_price_b = prices_b[-1]

        # Ricalcolo cointegrazione ogni 24h (o se prima mai fatto)
        needs_refresh = (now - self._last_coint_time) > (self.coint_refresh_hours * 3600)
        if needs_refresh:
            self._coint_result = self.coint_engine.run_cointegration_test(prices_a, prices_b)
            self._last_coint_time = now
            self.logger.info(
                f"Cointegration refresh | "
                f"{'✅' if self._coint_result['is_cointegrated'] else '❌'} | "
                f"p={self._coint_result['p_value']:.4f} | β={self._coint_result['beta']:.4f} | "
                f"n={self._coint_result['sample_size']}"
            )

        # Z-score corrente
        z_score = self.coint_engine.compute_zscore(current_price_a, current_price_b)

        # Stato corrente
        free_eur = float(self.balance.get("EUR", 0))
        entry_age_hours = self.executor.get_entry_age() if self.executor.in_position else 0

        # ── POSITION MANAGEMENT ──
        if self.executor.in_position:
            # 1) Emergency exit: divergenza
            if abs(z_score) > self.z_emergency:
                self.logger.warning(f"🚨 EMERGENCY EXIT: |Z|={abs(z_score):.2f} > {self.z_emergency}")
                await self.executor.execute_close(current_price_a, current_price_b)
                self.in_position = False
                self._reset_position()
                return

            # 2) Time stop
            if entry_age_hours > self.time_stop_hours:
                self.logger.warning(f"⏰ TIME STOP: {entry_age_hours:.1f}h > {self.time_stop_hours}h")
                await self.executor.execute_close(current_price_a, current_price_b)
                self.in_position = False
                self._reset_position()
                return

            # 3) Mean reversion exit: z-score tornato sotto soglia
            if abs(z_score) < self.z_exit:
                self.logger.info(f"✅ EXIT (mean reversion): |Z|={abs(z_score):.2f} < {self.z_exit}")
                await self.executor.execute_close(current_price_a, current_price_b)
                self.in_position = False
                self._reset_position()
                return

        # ── ENTRY SIGNAL (usa z-score, cointegrazione non richiesta per trade) ──
        if not self.executor.in_position and self._coint_result:
            # Logga se c'è cointegrazione o meno
            is_coint = self._coint_result.get('is_cointegrated', False)
            if not is_coint:
                self.logger.debug(f"Z-score trade (no coint): |z|={abs(z_score):.2f}")

            if abs(z_score) > self.z_entry:
                # Determina direzione
                position_type = "ETH_OVERPRICED" if z_score > self.z_entry else "ETH_UNDERPRICED"

                # Kelly position sizing: 5% del free capital
                total_capital = free_eur
                if total_capital < self.base_order_eur:
                    self.logger.debug(f"Capitale insufficiente: {total_capital:.2f}€ < {self.base_order_eur}€")
                    return

                notional_eur = min(
                    total_capital * self.kelly_fraction * 100,  # Kelly: 5% → 5x leverage-like
                    self.max_notional_eur
                )
                notional_eur = max(notional_eur, self.base_order_eur)
                # Cap at available EUR (leave 2% buffer for fees)
                notional_eur = min(notional_eur, free_eur * 0.98)
                if notional_eur < self.base_order_eur:
                    self.logger.debug(f"Available EUR too low: {free_eur:.2f}€ < {self.base_order_eur}€")
                    return

                # Controlla profitto minimo (cost filter base)
                spread_pct = abs(z_score) * self._coint_result.get('spread_std', 0.01)
                if spread_pct > 0:
                    expected_net = spread_pct * 0.5
                    min_profit = expected_profit_threshold()
                    if expected_net < min_profit:
                        self.logger.debug(
                            f"Cost filter: expected {expected_net*100:.3f}% < {min_profit*100:.3f}%"
                        )
                        return

                # ENTRY
                success = await self.executor.execute_entry(
                    position_type, notional_eur,
                    current_price_a, current_price_b
                )
                if success:
                    self.in_position = True
                    self.entry_price_eth = current_price_a
                    self.entry_price_btc = current_price_b
                    self._last_entry_price = current_price_a  # per circuit breaker
                    self.logger.info(
                        f"🚀 ENTRY {position_type} | z={z_score:.2f} | "
                        f"notional={notional_eur:.2f}€ | "
                        f"ETH={current_price_a:.2f} BTC={current_price_b:.2f}"
                    )

        # ── LOG periodico ──
        self._log_status(z_score, current_price_a, current_price_b, free_eur, entry_age_hours)

    # ── HELPERS ────────────────────────────────────────────────

    def _reset_position(self):
        self.in_position = False
        self.entry_price_eth = 0.0
        self.entry_price_btc = 0.0

    def _log_status(self, z_score, price_eth, price_btc, free_eur, age_hours):
        """Log breve ogni ciclo."""
        coint_status = ""
        if self._coint_result:
            coint_status = "COINT" if self._coint_result['is_cointegrated'] else "NOCOINT"

        pos_status = ""
        if self.executor.in_position:
            pos_type = self.executor._position_type or "?"
            pos_status = f"| {pos_type} {age_hours:.1f}h"

        self.logger.info(
            f"Apollo | {self.symbol_a}={price_eth:.2f} {self.symbol_b}={price_btc:.2f} | "
            f"Z={z_score:.2f} | {coint_status}{pos_status} | EUR={free_eur:.2f}"
        )

    # ── DB persistence ─────────────────────────────────────────

    def save_position_to_db(self):
        """Salva stato posizione pair trading su DB."""
        info = self.executor.get_status() if self.executor.in_position else None
        self.db.save_bot_state(
            bot_name=self.bot_name,
            is_in_position=self.in_position,
            entry_price=self.entry_price_eth or 0.0,
            quantity=info.get('notional_eur', 0.0) if info else 0.0,
            tp=self.z_entry,
            sl=self.z_emergency,
            entry_time=time.time(),
            exchange_name='binance_pair',
        )

    def load_position_from_db(self):
        """Ripristina posizione da DB."""
        state = self.db.load_bot_state(self.bot_name)
        if state and state.get('is_in_position') and state.get('quantity', 0) > 0:
            self.in_position = True
            self.entry_price_eth = state['entry_price']
            # Nota: non possiamo ripristinare completamente l'esecuzione
            # senza i dettagli del pair trade. Il bot ripartirà flat.
            self.logger.info(
                f"♻️ Apollo restored from DB: pos @ ETH={self.entry_price_eth:.2f}, "
                f"notional={state['quantity']:.2f}€"
            )
            self.logger.warning(
                "Pair trade position restored as FLAT — ri-esecuzione non "
                "supportata senza full state. Monitorare manualmente."
            )
            self.in_position = False
            self.entry_price_eth = 0.0
            self.entry_price_btc = 0.0
            self.save_position_to_db()
            return False
        return False

    async def on_startup(self):
        """Startup: pulisci posizioni pregresse, parti flat."""
        restored = self.load_position_from_db()
        if restored:
            self.logger.info("Apollo startup: position found (reset to flat)")
        else:
            self.logger.info("Apollo startup: nessuna posizione, partenza flat")

        # Verifica bilanci (senza forzare holding)
        if not self.test_mode:
            await self.refresh_balance()
            self.logger.info(
                f"Balance: ETH={self.balance.get('ETH', 0):.4f} "
                f"BTC={self.balance.get('BTC', 0):.6f} "
                f"EUR={self.balance.get('EUR', 0):.2f}"
            )

    # ── Utility ────────────────────────────────────────────────

    def get_debug_state(self) -> dict:
        """Stato dettagliato per debug/dashboard."""
        return {
            "bot": "ApolloPairBot",
            "in_position": self.in_position,
            "symbol_a": self.symbol_a,
            "symbol_b": self.symbol_b,
            "z_entry": self.z_entry,
            "z_exit": self.z_exit,
            "z_emergency": self.z_emergency,
            "executor": self.executor.get_status(),
            "coint": self.coint_engine.get_status(),
            "balance": dict(self.balance) if self.balance else {},
        }


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(message)s"
    )
    bot = ApolloPairBot(test_mode="--test" in __import__('sys').argv)
    asyncio.run(bot.start())

"""
Artemis — BTC Long-Only Trend Follower Bot (v1.0).
Delega la logica di strategia al modulo strategies/artemis_strategy.py.

Basato sulla strategia del video: long BTC solo in bull trend su timeframe daily.
Trades 3-5 volte all'anno. Set-and-forget.
"""
import asyncio
import time
from core import DenaroOpportunisticCore
from strategies import artemis_signal


class ArtemisTrendBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Artemis", config_file="artemis.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "BTC/EUR")
        self.timeframe = self.config.get("timeframe", "1d")
        self.base_order_eur = self.config.get("base_order_eur", 10.0)
        self.max_investment = self.config.get("max_investment_eur", 10.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.0)   # Nessun TP — usciamo solo su segnale
        self.sl_pct = self.config.get("stop_loss_pct", 0.0)     # Nessuno SL fisso — la strategia è l'exit
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self._last_daily_check = 0  # timestamp dell'ultimo controllo daily

    async def run_strategy(self):
        # Daily timeframe: fetch OHLCV una volta al giorno (o ogni ora tanto)
        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=250)
        if not ohlcv:
            return

        signal = artemis_signal(
            ohlcv,
            in_position=self.in_position,
            entry_price=self.entry_price,
        )
        action = signal["action"]
        current_price = signal["current_price"]
        fast_sma = signal["fast_sma"]
        slow_sma = signal["slow_sma"]
        pnl = signal["pnl_pct"]

        base = self.symbol.split("/")[0]  # BTC
        free_eur = float(self.balance.get("EUR", 0))

        # ── SELL / EXIT ──
        if action == "SELL" and self.in_position:
            if not await self.validate_balance_before_sell(base, self.entry_amount):
                return
            amt = self.entry_amount * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                self.logger.info(
                    f"ARTEMIS EXIT: BTC @ {current_price:.2f} | P&L: {pnl:.2f}% | "
                    f"{signal['reason']}"
                )
                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()
            return

        # ── BUY / ENTRY ──
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            amount = (self.base_order_eur / current_price) * 0.997
            if amount > 0:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(
                        f"ARTEMIS ENTRY {self.symbol} @ {current_price:.2f} | "
                        f"SMA50={fast_sma:.2f} SMA200={slow_sma:.2f} | "
                        f"{signal['reason']}"
                    )
                    self.save_position_to_db()

        # ── Status log ──
        pos_info = f" | P&L: {pnl:.2f}%" if self.in_position else ""
        self.logger.info(
            f"Artemis | {self.symbol} @ {current_price:.2f} | "
            f"SMA50={fast_sma:.2f} SMA200={slow_sma:.2f} | "
            f"{action} | Pos: {self.in_position}{pos_info} | EUR: {free_eur:.2f}"
        )

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split('/')[0])
        else:
            self.logger.info(f"=== ARTEMIS STARTUP: no position found ===")


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = ArtemisTrendBot()
    asyncio.run(bot.start())

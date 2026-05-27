"""
Ares — Intraday Trend Bot (v3.2).
Timeframe: 5m + 1h confirmation. SL/TP dinamici su ATR.
RiskManager integrato per position sizing. Cost filter pre-entry.
"""
import asyncio, statistics, sys
from core import DenaroOpportunisticCore, cost_model, cost_filter, ROUND_TRIP_COST_PCT, RiskManager
from strategies import ares_signal
from utils.indicators import aggregate_timeframes, calculate_atr as calc_atr

class AresIntradayTrendBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Ares", config_file="ares.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "ETH/EUR")
        self.timeframe = self.config.get("timeframe", "5m")
        self.timeframe_long = self.config.get("timeframe_long", "1h")
        self.long_candles = self.config.get("long_candles", 72)
        self.fast_period = self.config.get("fast_sma", 5)
        self.slow_period = self.config.get("slow_sma", 20)
        self.base_order_eur = self.config.get("base_order_eur", 12.0)
        self.max_investment = self.config.get("max_investment_eur", 30.0)
        self.atr_period = self.config.get("atr_period", 14)
        self.atr_sl_mult = self.config.get("atr_sl_multiplier", 1.5)
        self.atr_tp_mult = self.config.get("atr_tp_multiplier", 3.0)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0

        # RiskManager + daily tracker
        self.risk_manager = RiskManager(default_pos_size_pct=1.5, max_pos_size_pct=3.0)
        self._daily_pnl = 0.0
        self._last_reset_day = None

    # ── helpers ──
    def _check_circuit(self):
        if not self.risk_manager.check_daily_loss(self._daily_pnl):
            self.logger.warning("🚨 CIRCUIT BREAKER: daily loss limit hit. Skipping all trades.")
            return True
        return False

    def _atr_from_ohlcv(self, ohlcv):
        highs = [c[2] for c in ohlcv]
        lows  = [c[3] for c in ohlcv]
        closes = [c[4] for c in ohlcv]
        atr_val = calc_atr(highs, lows, closes, self.atr_period)
        current_price = closes[-1]
        atr_pct = (atr_val / current_price) if current_price > 0 else 0
        return atr_val, atr_pct

    async def run_strategy(self):
        if self._check_circuit():
            return

        ohlcv = await self.fetch_ohlcv(self.symbol, self.timeframe, limit=50)
        ohlcv_long = await self.fetch_ohlcv(self.symbol, self.timeframe_long, limit=self.long_candles)
        if not ohlcv:
            return

        ctx = aggregate_timeframes(ohlcv, ohlcv_long) if ohlcv_long else None
        signal = ares_signal(ohlcv, fast_period=self.fast_period, slow_period=self.slow_period, ctx=ctx)
        action = signal["action"]
        current_price = signal["current_price"]
        atr_val, atr_pct = self._atr_from_ohlcv(ohlcv)

        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))
        free_asset = float(self.balance.get(base, 0))

        # ── ATR-based SL/TP ──
        sl_pct_dyn = atr_pct * self.atr_sl_mult if atr_pct > 0 else self.config.get("stop_loss_pct", 0.004)
        tp_pct_dyn = atr_pct * self.atr_tp_mult if atr_pct > 0 else self.config.get("take_profit_pct", 0.008)

        # ── TP/SL check ──
        if self.in_position and self.entry_price > 0:
            pnl_pct = (current_price - self.entry_price) / self.entry_price
            if pnl_pct >= tp_pct_dyn:
                self.logger.info(f"TP hit: {pnl_pct*100:.2f}% (ATR SL/TP)")
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self._record_completed_trade(pnl_pct)
                    self._daily_pnl += pnl_pct
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return
            elif pnl_pct <= -sl_pct_dyn:
                self.logger.info(f"☠️ SL RUTHLESS: {pnl_pct*100:.2f}% — MARKET SELL {self.symbol}")
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_market_sell(self.symbol, amt)
                    self._record_completed_trade(pnl_pct)
                    self._daily_pnl += pnl_pct
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return

        # ── ENTRY ──
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            # Cost filter: ignore trade se profitto netto atteso non copre fee
            expected_profit = tp_pct_dyn * 100  # convert to %
            if not cost_filter(expected_profit):
                self.logger.debug(f"Cost filter blocked: expected {expected_profit:.3f}% ≤ {ROUND_TRIP_COST_PCT*100:.3f}% cost")
                return

            # Position sizing via RiskManager
            total_balance = free_eur + (self.entry_amount * self.entry_price if self.in_position else 0)
            vol_norm = min(1.0, atr_pct / 0.02)  # normalize: 2% ATR = max volatility
            pos_size_eur = self.risk_manager.calculate_size(total_balance, volatility=vol_norm, atr_price=atr_val)

            amount = (pos_size_eur / current_price) * 0.997
            total_invested = pos_size_eur + (float(self.entry_amount * self.entry_price) if self.in_position else 0)

            if amount > 0 and total_invested <= self.max_investment:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self._last_entry_price = current_price
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(f"ARES ENTRY {self.symbol} @ {current_price:.2f} | size={pos_size_eur:.2f}€ | ATR%={atr_pct*100:.2f}% | TP={tp_pct_dyn*100:.2f}% SL={sl_pct_dyn*100:.2f}%")
                    self.save_position_to_db()

        # ── EXIT via signal ──
        elif action == "SELL" and self.in_position:
            if not await self.validate_balance_before_sell(base, self.entry_amount):
                return
            amt = self.entry_amount * 0.997
            if amt > 0:
                await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                pnl = (current_price - self.entry_price) / self.entry_price
                self._record_completed_trade(pnl)
                self._daily_pnl += pnl
                self.logger.info(f"ARES EXIT {self.symbol} @ {current_price:.2f} (PnL: {pnl*100:.2f}%) | signal")
                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()

        self.logger.info(f"Ares | {self.symbol} @ {current_price:.2f} | {action} | ATR%={atr_pct*100:.3f}% | Pos={self.in_position} | EUR={free_eur:.2f} | PnL_daily={self._daily_pnl*100:.2f}%")

    async def on_startup(self):
        self.logger.info(f"[STARTUP] loading position from DB (bot={self.bot_name})")
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split('/')[0])
        else:
            self.logger.info(f"[STARTUP] No position found in DB, starting fresh.")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = AresIntradayTrendBot()
    asyncio.run(bot.start())

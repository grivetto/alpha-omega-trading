"""
Hermes — Sentiment Bot (v3.3).
Timeframe: 15m. RSI + Volume Spike + VWAP + Social Sentiment.
RiskManager integrato + ATR-based SL/TP + cost filter pre-entry.
"""
import asyncio, statistics
from core import DenaroOpportunisticCore, RiskManager
from utils.markov_regime import (
    compute_markov_matrix, scale_thresholds_for_timeframe, markov_confidence_modifier,
)
from utils.indicators import calculate_atr as calc_atr

class HermesSentimentBot(DenaroOpportunisticCore):
    def __init__(self, test_mode=False):
        super().__init__(bot_name="Hermes", config_file="hermes.json", test_mode=test_mode)
        self.symbol = self.config.get("symbol", "SOL/EUR")
        self.timeframe = self.config.get("timeframe", "1m")
        self.base_order_eur = self.config.get("base_order_eur", 8.0)
        self.max_investment = self.config.get("max_investment_eur", 25.0)
        self.tp_pct = self.config.get("take_profit_pct", 0.020)
        self.sl_pct = self.config.get("stop_loss_pct", 0.015)
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self._last_markov = None  # cache last Markov analysis for logging
        # ATR-based SL/TP multipliers
        self.atr_sl_mult = self.config.get("atr_sl_multiplier", 1.5)
        self.atr_tp_mult = self.config.get("atr_tp_multiplier", 2.0)
        # RiskManager
        self.risk_manager = RiskManager(default_pos_size_pct=1.5, max_pos_size_pct=3.0)
        self._daily_pnl = 0.0

    def _calc_rsi(self, prices, period=14):
        if len(prices) < period + 1:
            return 50.0
        gains, losses = [], []
        for i in range(1, len(prices)):
            diff = prices[-i] - prices[-i-1]
            gains.append(max(diff, 0))
            losses.append(max(-diff, 0))
        avg_gain = statistics.mean(gains[:period]) if gains else 0
        avg_loss = statistics.mean(losses[:period]) if losses else 0
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    def _calc_vwap(self, ohlcv):
        if not ohlcv:
            return None
        tp_vol = sum(((c[1] + c[2] + c[3]) / 3) * c[5] for c in ohlcv)
        vol = sum(c[5] for c in ohlcv)
        return tp_vol / vol if vol > 0 else None

    def _markov_analysis(self, ohlcv):
        """Compute Markov regime analysis with auto-scaled thresholds."""
        try:
            from utils.markov_regime import (
                compute_markov_matrix,
                scale_thresholds_for_timeframe,
                markov_confidence_modifier,
            )
            scaled = scale_thresholds_for_timeframe(self.timeframe)
            mr = compute_markov_matrix(
                ohlcv,
                periods=scaled["periods"],
                bull_threshold=scaled["bull_threshold"],
                bear_threshold=scaled["bear_threshold"],
                return_matrix=False,
                return_stickiness=True,
                return_signal=True,
            )
            modifier = markov_confidence_modifier(mr)
            self._last_markov = mr
            return modifier, mr
        except ImportError:
            self._last_markov = None
            return 0.0, {}
        except Exception as e:
            self.logger.warning(f"Markov analysis error: {e}")
            self._last_markov = None
            return 0.0, {}

    def _get_signal(self, ohlcv, markov_modifier=0.0):
        if len(ohlcv) < 20:
            return "HOLD", 0.0, 50.0
        closes = [c[4] for c in ohlcv]
        volumes = [c[5] for c in ohlcv]
        current_price = closes[-1]
        avg_volume = statistics.mean(volumes[-20:]) if volumes else 1
        rsi = self._calc_rsi(closes)
        vwap = self._calc_vwap(ohlcv)
        score = 0.0

        # Volume spike
        if avg_volume > 0:
            vol_ratio = volumes[-1] / avg_volume
            if vol_ratio > 2.0:
                score += 0.3 if current_price > closes[-5] else -0.3

        # RSI extremes
        if rsi < 25:
            score += 0.4
        elif rsi > 75:
            score -= 0.4
        elif rsi < 35:
            score += 0.2
        elif rsi > 65:
            score -= 0.2

        # VWAP position
        if vwap and vwap > 0:
            dist_pct = (current_price - vwap) / vwap * 100
            if dist_pct < -1.5:
                score += 0.2
            elif dist_pct > 1.5:
                score -= 0.2

        # Markov regime modifier (from Hedge Fund Method)
        if markov_modifier != 0.0:
            score += markov_modifier

        score = max(-1, min(1, score))
        threshold = getattr(self, 'buy_threshold', 0.5)
        if score >= threshold:
            action = "BUY"
        elif score <= -threshold:
            action = "SELL"
        else:
            action = "HOLD"
        return action, score, rsi

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
        if not ohlcv:
            return

        current_price = ohlcv[-1][4]
        action, score, rsi = self._get_signal(ohlcv)
        atr_val, atr_pct = self._atr_from_ohlcv(ohlcv)

        base = self.symbol.split("/")[0]
        free_eur = float(self.balance.get("EUR", 0))

        # ── ATR-based SL/TP ──
        sl_pct_dyn = atr_pct * self.atr_sl_mult if atr_pct > 0 else self.config.get("stop_loss_pct", 0.025)
        tp_pct_dyn = atr_pct * self.atr_tp_mult if atr_pct > 0 else self.config.get("take_profit_pct", 0.035)

        # ── TP/SL check ──
        if self.in_position and self.entry_price > 0:
            pnl = (current_price - self.entry_price) / self.entry_price
            if pnl >= tp_pct_dyn:
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    await self.create_limit_sell(self.symbol, amt, current_price * 0.999)
                    self._record_completed_trade(pnl)
                    self._daily_pnl += pnl
                    self.logger.info(f"HERMES TP: +{pnl*100:.2f}% @ {current_price:.2f} (ATR SL/TP)")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return
            elif pnl <= -sl_pct_dyn:
                if not await self.validate_balance_before_sell(base, self.entry_amount):
                    return
                amt = self.entry_amount * 0.997
                if amt > 0:
                    self.logger.warning(f"☠️ HERMES SL RUTHLESS: {pnl*100:.2f}% — MARKET SELL {self.symbol}")
                    await self.create_market_sell(self.symbol, amt)
                    self._record_completed_trade(pnl)
                    self._daily_pnl += pnl
                    self.logger.info(f"HERMES SL: {pnl*100:.2f}% @ {current_price:.2f} (ATR SL/TP)")
                    self.in_position = False
                    self.entry_price = 0
                    self.entry_amount = 0
                    self.save_position_to_db()
                return

        # ── ENTRY ──
        if action == "BUY" and not self.in_position and free_eur >= self.base_order_eur:
            expected_profit = tp_pct_dyn * 100
            if not cost_filter(expected_profit):
                self.logger.debug(f"Cost filter blocked: expected {expected_profit:.3f}%")
                return

            total_balance = free_eur + (self.entry_amount * self.entry_price if self.in_position else 0)
            vol_norm = min(1.0, atr_pct / 0.02)
            pos_size_eur = self.risk_manager.calculate_size(total_balance, volatility=vol_norm, atr_price=atr_val)
            amount = (pos_size_eur / current_price) * 0.997

            if amount > 0 and pos_size_eur <= self.max_investment:
                order = await self.create_limit_buy(self.symbol, amount, current_price * 1.001)
                if order:
                    self._last_entry_price = current_price
                    self.in_position = True
                    self.entry_price = current_price
                    self.entry_amount = amount
                    self.logger.info(f"HERMES ENTRY {self.symbol} @ {current_price:.2f} | size={pos_size_eur:.2f}€ | score={score:.2f} | RSI={rsi:.1f} | ATR%={atr_pct*100:.2f}%")
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
                self.logger.info(f"HERMES EXIT (signal): {pnl*100:.2f}% @ {current_price:.2f} | score={score:.2f}")
                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()
            return

        self.logger.info(f"Hermes | {self.symbol} @ {current_price:.2f} | score={score:.2f} | RSI={rsi:.1f} | {action} | Pos={self.in_position} | EUR={free_eur:.2f} | PnL_daily={self._daily_pnl*100:.2f}%")

    async def on_startup(self):
        restored = self.load_position_from_db()
        if restored:
            await self.startup_validate_position(self.symbol.split("/")[0])
        else:
            self.logger.info("=== HERMES STARTUP: no position found ===")

if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(message)s")
    bot = HermesSentimentBot()
    asyncio.run(bot.start())

"""WAR Scalper — sync version for Denaro WAR main.py.
Uses BinanceEngine (REST) for rapid scalp entries on ATR spikes.
"""
import time
import math
from typing import Optional


class Scalper:
    """ATR-spike scalper. Monitors price drops from local high, enters on pullbacks."""

    def __init__(self, engine, symbol: str, capital: float, config: dict):
        self.eng = engine
        self.symbol = symbol
        self.capital = capital
        self.cfg = config
        self.t = 0          # trade counter
        self.pnl = 0.0      # total P&L in USDC
        self._position = None
        self._entry_price = 0.0
        self._entry_qty = 0.0
        self._entry_time = 0.0
        self._high_30s = 0.0
        self._last_check = 0.0
        self._cooldown_until = 0.0

        # Config
        self.entry_drop = self.cfg.get("entry_drop", 0.008)       # -0.8% from local high
        self.take_profit = self.cfg.get("take_profit", 0.004)     # +0.4%
        self.stop_loss = self.cfg.get("stop_loss", 0.02)          # -2%
        self.atr_spike_threshold = self.cfg.get("atr_spike_threshold", 3.0)
        self.cooldown_s = self.cfg.get("cooldown_after_exit_seconds", 30)
        self.max_hold_s = self.cfg.get("max_hold_seconds", 120)

    def run(self) -> Optional[dict]:
        """Check market and return trade signal if triggered."""
        now = time.time()

        # Manage open position
        if self._position is not None:
            return self._manage_position()

        # Cooldown after last exit
        if now < self._cooldown_until:
            return None

        # Get current price
        try:
            price = self.eng.price(self.symbol)
        except Exception:
            return None

        if not price or price <= 0:
            return None

        # Update 30s high
        if price > self._high_30s or self._high_30s == 0:
            self._high_30s = price

        # Reset high periodically (every 60s)
        if now - self._last_check > 60:
            self._high_30s = price
            self._last_check = now

        # Entry condition: price dropped entry_drop% below local high
        drop = (self._high_30s - price) / self._high_30s
        if drop >= self.entry_drop:
            # Calculate position size (use 50% of allocated capital)
            trade_capital = self.capital * 0.5
            qty = trade_capital / price

            # Round quantity
            qty = self._round_qty(qty)

            if qty > 0:
                self._entry_price = price
                self._entry_qty = qty
                # Place market buy via engine
                try:
                    result = self.eng.market_buy(self.symbol, qty)
                    if result and "orderId" in result:
                        self._position = "LONG"
                        self._entry_time = time.time()
                        self.t += 1
                        return {"action": "BUY", "price": price, "qty": qty}
                except Exception as e:
                    pass  # Order failed, will retry next cycle

        return None

    def _manage_position(self) -> Optional[dict]:
        """Check TP/SL for open position."""
        try:
            price = self.eng.price(self.symbol)
        except Exception:
            return None

        if not price:
            return None

        pnl_pct = (price - self._entry_price) / self._entry_price

        # Take profit
        if pnl_pct >= self.take_profit:
            return self._close_position(price, "TP")

        # Stop loss
        if pnl_pct <= -self.stop_loss:
            return self._close_position(price, "SL")

        # Max hold time
        if self._entry_time > 0 and time.time() - self._entry_time > self.max_hold_s:
            return self._close_position(price, "TIMEOUT")

        return None

    def _close_position(self, price: float, reason: str) -> dict:
        """Market sell to close position."""
        try:
            result = self.eng.market_sell(self.symbol, self._entry_qty)
        except Exception:
            pass

        pnl = (price - self._entry_price) * self._entry_qty
        self.pnl += pnl
        self._position = None
        self._cooldown_until = time.time() + self.cooldown_s
        self._high_30s = 0  # Reset high after trade
        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}

    def _round_qty(self, qty: float) -> float:
        """Round quantity to reasonable decimal places."""
        if qty > 100:
            return math.floor(qty)
        elif qty > 1:
            return math.floor(qty * 100) / 100
        elif qty > 0.01:
            return math.floor(qty * 10000) / 10000
        else:
            return math.floor(qty * 1000000) / 1000000


class WhaleTracker:
    """Order-book imbalance whale detector."""

    def __init__(self, engine, symbol: str, capital: float, config: dict):
        self.eng = engine
        self.symbol = symbol
        self.capital = capital
        self.cfg = config
        self.t = 0
        self.pnl = 0.0
        self._position = None
        self._entry_price = 0.0
        self._entry_qty = 0.0
        self._entry_time = 0.0
        self._cooldown_until = 0.0

        self.imbalance_threshold = self.cfg.get("imbalance_threshold", 3.0)
        self.take_profit = self.cfg.get("take_profit_bps", 80) / 10000   # 80 bps = 0.8%
        self.stop_loss = self.cfg.get("stop_loss_bps", 150) / 10000      # 150 bps = 1.5%
        self.cooldown_s = self.cfg.get("cooldown_after_exit_seconds", 20)
        self.max_hold_s = self.cfg.get("max_hold_seconds", 180)

    def run(self) -> Optional[dict]:
        now = time.time()

        if self._position is not None:
            return self._manage_position()

        if now < self._cooldown_until:
            return None

        try:
            _, _, imbalance = self.eng.order_book_imbalance(self.symbol, 20)
        except Exception:
            return None

        if imbalance >= self.imbalance_threshold:
            # Whale buying pressure detected
            try:
                price = self.eng.price(self.symbol)
            except Exception:
                return None

            trade_capital = self.capital * 0.3
            qty = self._round_qty(trade_capital / price)

            if qty > 0:
                try:
                    result = self.eng.market_buy(self.symbol, qty)
                    if result and "orderId" in result:
                        self._position = "LONG"
                        self._entry_price = price
                        self._entry_qty = qty
                        self._entry_time = now
                        self.t += 1
                        return {"action": "BUY", "price": price, "reason": f"imbalance={imbalance:.1f}"}
                except Exception:
                    pass

        return None

    def _manage_position(self) -> Optional[dict]:
        try:
            price = self.eng.price(self.symbol)
        except Exception:
            return None
        if not price:
            return None

        pnl_pct = (price - self._entry_price) / self._entry_price

        if pnl_pct >= self.take_profit:
            return self._close(price, "TP")
        if pnl_pct <= -self.stop_loss:
            return self._close(price, "SL")
        if self._entry_time > 0 and time.time() - self._entry_time > self.max_hold_s:
            return self._close(price, "TIMEOUT")

        return None

    def _close(self, price: float, reason: str) -> dict:
        try:
            self.eng.market_sell(self.symbol, self._entry_qty)
        except Exception:
            pass
        pnl = (price - self._entry_price) * self._entry_qty
        self.pnl += pnl
        self._position = None
        self._cooldown_until = time.time() + self.cooldown_s
        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}

    def _round_qty(self, qty: float) -> float:
        if qty > 100:
            return math.floor(qty)
        elif qty > 1:
            return math.floor(qty * 100) / 100
        elif qty > 0.01:
            return math.floor(qty * 10000) / 10000
        else:
            return math.floor(qty * 1000000) / 1000000


class NewsReactor:
    """News sentiment reactor — stub that monitors price action."""

    def __init__(self, engine, symbol: str, capital: float, config: dict):
        self.eng = engine
        self.symbol = symbol
        self.capital = capital
        self.cfg = config
        self.t = 0
        self.pnl = 0.0
        self._position = None
        self._entry_price = 0.0
        self._entry_qty = 0.0
        self._entry_time = 0.0
        self._cooldown_until = 0.0
        self._last_price = 0.0
        self._pump_counter = 0

    def run(self) -> Optional[dict]:
        now = time.time()

        if self._position is not None:
            return self._manage_position()

        if now < self._cooldown_until:
            return None

        try:
            price = self.eng.price(self.symbol)
        except Exception:
            return None
        if not price:
            return None

        # Simplified "news" detection: rapid price increase >1% in one check
        if self._last_price > 0:
            change = (price - self._last_price) / self._last_price
            if change > 0.01:  # 1% pump
                self._pump_counter += 1
            else:
                self._pump_counter = 0
        self._last_price = price

        # Enter on 2 consecutive pumps
        if self._pump_counter >= 2:
            trade_capital = self.capital * 0.25
            qty = self._round_qty(trade_capital / price)
            if qty > 0:
                try:
                    result = self.eng.market_buy(self.symbol, qty)
                    if result and "orderId" in result:
                        self._position = "LONG"
                        self._entry_price = price
                        self._entry_qty = qty
                        self._entry_time = now
                        self.t += 1
                        self._pump_counter = 0
                        return {"action": "BUY", "price": price, "reason": "momentum_pump"}
                except Exception:
                    pass

        return None

    def _manage_position(self) -> Optional[dict]:
        try:
            price = self.eng.price(self.symbol)
        except Exception:
            return None
        if not price:
            return None

        pnl_pct = (price - self._entry_price) / self._entry_price
        # TP at 1.5%, SL at 2%
        if pnl_pct >= 0.015:
            return self._close(price, "TP")
        if pnl_pct <= -0.02:
            return self._close(price, "SL")

        # Max hold 10min
        if self._entry_time > 0 and time.time() - self._entry_time > 600:
            return self._close(price, "TIMEOUT")
        return None

    def _close(self, price: float, reason: str) -> dict:
        try:
            self.eng.market_sell(self.symbol, self._entry_qty)
        except Exception:
            pass
        pnl = (price - self._entry_price) * self._entry_qty
        self.pnl += pnl
        self._position = None
        self._cooldown_until = time.time() + 300  # 5 min cooldown
        return {"action": "SELL", "price": price, "pnl": round(pnl, 4), "reason": reason}

    def _round_qty(self, qty: float) -> float:
        if qty > 100:
            return math.floor(qty)
        elif qty > 1:
            return math.floor(qty * 100) / 100
        elif qty > 0.01:
            return math.floor(qty * 10000) / 10000
        else:
            return math.floor(qty * 1000000) / 1000000

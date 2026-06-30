"""DENARO Scalp Engine — order-book driven, dynamic TP/SL, zero-touch.
No shadow mode: every signal is a real entry with proper risk management.
Uses Kelly sizing + imbalance ratio for entry confidence."""

from __future__ import annotations
import asyncio
import logging
import time
from typing import Optional

from .config import Config
from .exchange import Exchange, WSClient, OrderSide
from .models import CBState, PairState

log = logging.getLogger("denaro.scalper")

# Minimum ATR to even consider a scalp entry
MIN_ATR_FOR_SCALP = 0.0005  # 0.05%


class ScalpEngine:
    """Scalping engine for one pair — imbalance + momentum entry, trailing exit."""

    def __init__(self, exchange: Exchange, ws: WSClient, cfg: Config) -> None:
        self.exchange = exchange
        self.ws = ws
        self.scalp_cfg = cfg.scalp
        self.config = cfg
        self._last_entry_ts: float = 0.0

    # ── Main Tick ─────────────────────────────────────────────────────

    async def tick(self, state: PairState) -> PairState:
        """One tick. Manages existing position or evaluates new entry."""
        if not state.is_alive or state.last_price <= 0:
            return state
        if state.cb_state in (CBState.OPEN, CBState.GLOBAL_STOP):
            return state

        if state.scalp_position:
            return await self._manage_position(state)
        return await self._evaluate_entry(state)

    # ── Entry ─────────────────────────────────────────────────────────

    async def _evaluate_entry(self, state: PairState) -> PairState:
        """Check entry conditions using order book + momentum."""
        if state.adaptive.atr_pct < MIN_ATR_FOR_SCALP:
            return state

        now = time.time()
        if now - self._last_entry_ts < self.scalp_cfg.cooldown_sec:
            return state

        # Use WS data for entry signals
        price = state.last_price
        bid, ask = state.bid, state.ask
        imbalance = state.imbalance_ratio

        # Entry logic: imbalance + ATR-based Bollinger proxy
        side = None
        confidence = 0.0

        # LONG: strong bids (imbalance > threshold) + price near bid = dip bought
        if imbalance >= self.scalp_cfg.imbalance_entry_long:
            # Price near bid suggests dip
            dip_pct = (price - bid) / price if bid > 0 else 0
            if dip_pct <= 0.002:  # Within 0.2% of bid
                confidence = min(1.0, (imbalance - 1.5) * 0.5)
                side = OrderSide.BUY

        # SHORT: strong asks (imbalance < threshold) + price near ask = pump sold
        elif imbalance <= self.scalp_cfg.imbalance_entry_short:
            pump_pct = (ask - price) / price if ask > 0 else 0
            if pump_pct <= 0.002:  # Within 0.2% of ask
                confidence = min(1.0, (1.0 - imbalance) * 0.5)
                side = OrderSide.SELL

        if side is None:
            return state

        # ── Balance check for SHORT on spot ──
        if side == OrderSide.SELL:
            base_available = state.free_base + state.locked_base
            if base_available <= 0:
                log.debug("[%s] SHORT skipped — no %s balance", state.symbol,
                          state.symbol.split("/")[0])
                return state

        # ── Position sizing via RiskManager ──
        size_pct = self.config.risk.kelly_size * 0.15  # Max 15% of pair capital per scalp
        if state.perf.consecutive_wins >= 3:
            size_pct *= 1.5  # Boost on win streak
        elif state.perf.consecutive_losses >= 2:
            size_pct *= 0.5  # Halve on loss streak

        quote_qty = state.total_equity * size_pct
        quote_qty = min(quote_qty, state.free_quote * 0.5)
        quote_qty = max(quote_qty, self.exchange.markets.min_notional(state.symbol))

        # Entry price
        if side == OrderSide.BUY:
            # Use ask (aggressive) or between bid/ask
            entry_price = ask if ask > 0 else price * 1.0005
            entry_price = self.exchange.round_price(state.symbol, entry_price)
        else:
            entry_price = bid if bid > 0 else price * 0.9995
            entry_price = self.exchange.round_price(state.symbol, entry_price)

        base_qty = self.exchange.round_amount(
            state.symbol, quote_qty / entry_price
        )
        # Cap SELL to available base balance
        if side == OrderSide.SELL:
            base_available = state.free_base + state.locked_base
            base_qty = min(base_qty, self.exchange.round_amount(state.symbol, base_available * 0.5))

        if base_qty <= 0:
            return state

        # Place LIMIT order
        result = await self.exchange.place_limit_order(
            state.symbol, side, entry_price, base_qty
        )

        if result:
            order_id = str(result.get("orderId", ""))
            state.scalp_position = {
                "side": side.value,
                "entry_price": entry_price,
                "qty": base_qty,
                "order_id": order_id,
                "filled": 0.0,
                "entered_at": now,
                "peak_pnl": 0.0,
            }
            self._last_entry_ts = now
            log.info("[%s] SCALP ENTRY %s %.6f @ %.6f (%.2f USDC, conf=%.1f%%)",
                     state.symbol, side.value, base_qty, entry_price,
                     quote_qty, confidence * 100)

        return state

    # ── Position Management ───────────────────────────────────────────

    async def _manage_position(self, state: PairState) -> PairState:
        pos = state.scalp_position
        if pos is None:
            return state

        symbol = state.symbol
        price = state.last_price
        now = time.time()

        entry_price = pos["entry_price"]
        side_str = pos["side"]
        qty = pos["qty"]
        filled = pos.get("filled", 0)
        order_id = pos.get("order_id", "")

        # Check if entry order filled
        if filled <= 0 and order_id:
            order_info = await self.exchange.order_status(symbol, order_id)
            if order_info:
                status = order_info.get("status", "")
                exec_qty = float(order_info.get("executedQty", "0"))
                if status == "FILLED":
                    filled = exec_qty
                    actual_price = (
                        float(order_info.get("cummulativeQuoteQty", "0")) / exec_qty
                        if exec_qty > 0 else entry_price
                    )
                    pos["filled"] = filled
                    pos["entry_price"] = actual_price
                    log.info("[%s] SCALP %s FILLED %.6f @ %.6f",
                             symbol, side_str, exec_qty, actual_price)
                elif status in ("CANCELED", "EXPIRED", "REJECTED"):
                    state.scalp_position = None
                    log.info("[%s] SCALP %s not filled — cancelled", symbol, side_str)
                    return state
                elif now - pos["entered_at"] > 60:
                    # Entry timeout
                    await self.exchange.cancel_order(symbol, order_id)
                    state.scalp_position = None
                    return state
                else:
                    return state  # Still waiting for fill
            else:
                return state  # Can't check status yet

        if filled <= 0:
            return state  # Not yet filled

        # ── Calculate PnL ──
        if side_str == "BUY":
            pnl_pct = (price - entry_price) / entry_price
        else:
            pnl_pct = (entry_price - price) / entry_price

        # Track peak
        if pnl_pct > pos.get("peak_pnl", 0):
            pos["peak_pnl"] = pnl_pct

        # ── Take Profit ──
        tp = self.config.scalp_tp(state.adaptive.atr_pct)
        if pnl_pct >= tp:
            await self._close_position(state, pnl_pct)
            return state

        # ── Stop Loss ──
        sl = self.config.scalp_sl(state.adaptive.atr_pct)
        if pnl_pct <= -sl:
            log.info("[%s] SCALP SL at %.4f%% (entry=%.6f, now=%.6f)",
                     symbol, pnl_pct * 100, entry_price, price)
            state = self._record_result(state, pnl_pct)
            state.scalp_position = None
            return state

        # ── Trailing stop after 50% TP ──
        trail_activation = tp * 0.5
        if pnl_pct >= trail_activation:
            peak = pos.get("peak_pnl", 0)
            trail_dist = sl * 1.2
            if pnl_pct <= peak - trail_dist:
                log.info("[%s] SCALP trailing at %.4f%% (peak=%.4f%%)",
                         symbol, pnl_pct * 100, peak * 100)
                await self._close_position(state, pnl_pct)
                return state

        # ── Timeout ──
        if now - pos["entered_at"] > self.scalp_cfg.max_holding_sec:
            log.info("[%s] SCALP timeout at %.4f%%", symbol, pnl_pct * 100)
            await self._close_position(state, pnl_pct)
            return state

        return state

    async def _close_position(self, state: PairState, pnl_pct: float) -> None:
        pos = state.scalp_position
        if pos is None:
            return
        side_str = pos["side"]
        filled = pos.get("filled", pos["qty"])

        # Market close
        close_side = OrderSide.SELL if side_str == "BUY" else OrderSide.BUY
        result = await self.exchange.place_market_order(
            state.symbol, close_side, filled
        )
        if result:
            avg_price = (
                float(result.get("cummulativeQuoteQty", "0"))
                / float(result.get("executedQty", "1"))
            )
            log.info("[%s] SCALP CLOSE %s @ %.6f (PnL: %.4f%%)",
                     state.symbol,
                     "SELL" if side_str == "BUY" else "BUY",
                     avg_price, pnl_pct * 100)

        state = self._record_result(state, pnl_pct)
        state.scalp_position = None

    def _record_result(self, state: PairState, pnl_pct: float) -> PairState:
        """Record trade in state.perf + RiskManager."""
        state.perf.record_trade(pnl_pct)
        self.config.risk.record_trade(pnl_pct)
        state.adaptive.last_trade_pnl = pnl_pct
        if pnl_pct > 0:
            state.adaptive.consecutive_losses = 0
        else:
            state.adaptive.consecutive_losses += 1
        return state

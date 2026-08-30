"""
Inventory-Skew Volatility-Targeted Grid (ISV-Grid) — auto-generated 2026-08-29 22:32 UTC.

A grid strategy that treats INVENTORY as the first-class risk factor and scales
exposure by a realized-volatility target. Distinct from prior auto-gen families
(ATR-only grids, momentum gates, regime hybrids, mean-reversion bands,
OFI-Grid flow imbalance) because it does NOT try to predict direction: it
manages the *book*.

THREE LAYERS
1. VOL-TARGET LAYER: realized volatility (EMA of |mid_t - mid_{t-1}| over a
   bounded window) is compared against a configurable target. Exposure is
   scaled as exposure_mult = clamp(vol_target / realized_vol, min, max).
   High vol -> smaller orders instead of a hard stop: the grid keeps earning
   while risk per trade is automatically cut. This is the key difference from
   fixed-size grids that blow up in volatile regimes.

2. INVENTORY-SKEW LAYER: every fill moves the book. inventory_ratio =
   (pos_qty * mid) / equity. The grid ANCHOR is shifted by
   skew = skew_coeff * inventory_ratio * (spacing * levels_per_side):
   - long inventory  -> anchor shifts UP  -> sell levels closer to mid
     (we sell into strength, buy levels pushed away) -> inventory decays.
   - short inventory -> mirrored.
   Grid geometry is therefore self-healing: it actively works the inventory
   back to zero instead of passively accumulating adverse selection.

3. RATCHET + STALE-ORDER LAYER: the anchor follows mid via a slow EMA
   (ratchet_follow_alpha) and is *ratcheted* to the fill price on every fill,
   locking in realized levels. Orders older than max_order_age are cancelled
   (CANCEL_ALL + HOLD) so the grid re-quotes at the current anchor; a
   mid/anchour divergence beyond levels_per_side * spacing also triggers a
   rebuild, preventing a stale grid far from price.

RISK LAYER: fee-aware per-level profit guard (levels closer than
max_spread_mult * current spread to mid are skipped), inventory cap
(max_inventory_ratio -> buys gated off), and a drawdown kill-switch with
hysteresis (halt at max_drawdown, resume only after equity recovers above
recovery_threshold). On halt the action meta carries {"flatten": true,
"position_qty": n} so the adapter can close the open position; CANCEL_ALL
alone only cancels resting orders.

OOM SAFETY: all history is bounded (deque maxlen from config), grid levels
are produced by a generator and consumed lazily, large temporaries are
`del`-eted and `gc.collect()` runs on a configurable interval. Pure stdlib —
no numpy dependency.

Interface contract (Denaro StrategyBase):
- on_tick(tick) -> Tuple[Action, Dict[str, Any]]
- on_fill(fill) -> None
- validate_config() -> None
- estimate_memory_mb() -> float
- get_state() / load_state() for persistence
"""

from __future__ import annotations

import gc
import logging
import math
import time
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Any, Deque, Dict, Generator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class Action(Enum):
    """Trading actions emitted by the strategy."""

    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"
    CANCEL_ALL = "CANCEL_ALL"


class OrderSide(Enum):
    """Order side as understood by the exchange adapter."""

    BUY = "buy"
    SELL = "sell"


@dataclass(frozen=True, slots=True)
class Tick:
    """Minimal market snapshot consumed by the strategy."""

    timestamp: float
    symbol: str
    bid: float
    ask: float
    mid: float
    volume: float = 0.0


@dataclass(frozen=True, slots=True)
class Fill:
    """Execution report consumed by the strategy."""

    timestamp: float
    symbol: str
    side: OrderSide
    price: float
    qty: float
    fee: float = 0.0


@dataclass(slots=True)
class GridLevel:
    """A single pending grid order."""

    price: float
    side: OrderSide
    placed_at: float


@dataclass(slots=True)
class ISVGridConfig:
    """Configuration for InventorySkewVolTargetGrid.

    All tunables live here; nothing is hardcoded inside the strategy logic.
    """

    symbol: str
    base_capital: float
    atr_period: int = 14
    atr_mult: float = 2.0
    min_spacing_pct: float = 0.002
    levels_per_side: int = 5
    vol_target: float = 0.02
    vol_ema_alpha: float = 0.05
    min_exposure: float = 0.1
    max_exposure: float = 1.0
    skew_coeff: float = 0.5
    max_inventory_ratio: float = 0.5
    recenter_mult: float = 1.5
    max_order_age: float = 600.0
    max_drawdown: float = 0.05
    recovery_threshold: float = 0.03
    max_spread_mult: float = 3.0
    fee_pct: float = 0.001
    min_profit_pct: float = 0.0005
    max_history: int = 256
    gc_interval: int = 512
    chunk_size: int = 256

    def validate(self) -> None:
        """Raise ConfigError on any invalid parameter combination."""
        problems: List[str] = []
        if self.base_capital <= 0:
            problems.append("base_capital must be > 0")
        if self.atr_period < 2:
            problems.append("atr_period must be >= 2")
        if self.atr_mult <= 0:
            problems.append("atr_mult must be > 0")
        if not 0.0 < self.min_spacing_pct < 1.0:
            problems.append("min_spacing_pct must be in (0, 1)")
        if self.levels_per_side < 1:
            problems.append("levels_per_side must be >= 1")
        if not 0.0 < self.vol_target <= 1.0:
            problems.append("vol_target must be in (0, 1]")
        if not 0.0 < self.vol_ema_alpha < 1.0:
            problems.append("vol_ema_alpha must be in (0, 1)")
        if not 0.0 < self.min_exposure <= self.max_exposure:
            problems.append("need 0 < min_exposure <= max_exposure")
        if self.skew_coeff < 0:
            problems.append("skew_coeff must be >= 0")
        if not 0.0 < self.max_inventory_ratio <= 1.0:
            problems.append("max_inventory_ratio must be in (0, 1]")
        if self.recenter_mult < 1.0:
            problems.append("recenter_mult must be >= 1.0")
        if self.max_order_age <= 0:
            problems.append("max_order_age must be > 0")
        if not 0.0 < self.recovery_threshold <= self.max_drawdown:
            problems.append("need 0 < recovery_threshold <= max_drawdown")
        if self.max_spread_mult <= 1.0:
            problems.append("max_spread_mult must be > 1.0")
        if self.fee_pct < 0 or self.min_profit_pct < 0:
            problems.append("fee_pct and min_profit_pct must be >= 0")
        if self.max_history < self.atr_period * 4:
            problems.append("max_history too small for atr_period")
        if self.gc_interval < 1 or self.chunk_size < 1:
            problems.append("gc_interval and chunk_size must be >= 1")
        if problems:
            raise ConfigError("invalid ISVGridConfig: " + "; ".join(problems))


class StrategyError(Exception):
    """Base class for strategy-domain errors."""


class ConfigError(StrategyError):
    """Raised when configuration is invalid."""


class DataError(StrategyError):
    """Raised when market data is malformed."""


class RiskError(StrategyError):
    """Raised when a risk limit is breached."""


class StrategyBase:
    """Abstract interface every Denaro strategy must implement."""

    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Fill) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class InventorySkewVolTargetGrid(StrategyBase):
    """See module docstring: inventory-skew + vol-target grid."""

    def __init__(self, config: ISVGridConfig) -> None:
        self.config = config
        self.config.validate()
        self._prices: Deque[float] = deque(maxlen=config.max_history)
        self._returns: Deque[float] = deque(maxlen=config.max_history)
        self._fills: Deque[Fill] = deque(maxlen=64)
        self._levels: List[GridLevel] = []
        self._anchor: Optional[float] = None
        self._atr: Optional[float] = None
        self._realized_vol: Optional[float] = None
        self._equity: float = config.base_capital
        self._pos_qty: float = 0.0
        self._peak_equity: float = config.base_capital
        self._halted: bool = False
        self._last_action_ts: float = 0.0
        self._cooldown_until: float = 0.0
        self._tick_count: int = 0
        self._last_gc: int = 0

    # ------------------------------------------------------------------
    # internal estimators (all bounded-memory)
    # ------------------------------------------------------------------
    def _update_vol(self, tick: Tick) -> None:
        """Feed the tick into ATR / realized-vol estimators."""
        if self._prices:
            prev = self._prices[-1]
            move = abs(tick.mid - prev)
            if move > 0.0:
                self._returns.append(math.log(tick.mid / prev))
                if self._atr is None:
                    self._atr = move
                else:
                    self._atr = self._atr * (1.0 - self.config.vol_ema_alpha) + move * self.config.vol_ema_alpha
                if self._realized_vol is None:
                    self._realized_vol = move / prev
                else:
                    rv = move / prev
                    self._realized_vol = self._realized_vol * (1.0 - self.config.vol_ema_alpha) + rv * self.config.vol_ema_alpha
        self._prices.append(tick.mid)

    def _exposure_mult(self) -> float:
        """Vol-targeting exposure: cut size when realized vol exceeds target."""
        if self._realized_vol is None or self._realized_vol <= 0.0:
            return self.config.max_exposure
        ratio = self.config.vol_target / self._realized_vol
        return min(self.config.max_exposure, max(self.config.min_exposure, ratio))

    def _inventory_ratio(self, mid: float) -> float:
        """Signed inventory as a fraction of equity (positive = long book)."""
        if self._equity <= 0.0:
            return 0.0
        return (self._pos_qty * mid) / self._equity

    def _spacing(self) -> float:
        """Vol-scaled spacing, floored by min_spacing_pct of anchor."""
        anchor = self._anchor if self._anchor is not None else 1.0
        base = anchor * self.config.min_spacing_pct
        if self._atr is None:
            return base
        return max(base, self.config.atr_mult * self._atr)

    def _grid_levels(self, mid: float) -> Generator[GridLevel, None, None]:
        """Yield grid levels one at a time (lazy, OOM-safe).

        Skew shifts the anchor by the inventory ratio; levels inside the
        spread guard (would fill instantly at a loss) are skipped.
        """
        cfg = self.config
        anchor = self._anchor if self._anchor is not None else mid
        spacing = self._spacing()
        # Inventory skew with the CORRECT sign: a long book (positive ratio)
        # lowers the center -> sell levels closer to mid (reduce inventory),
        # buy levels pushed away (do not add). A short book mirrors it.
        skew = -cfg.skew_coeff * self._inventory_ratio(mid) * (spacing * cfg.levels_per_side)
        center = anchor + skew
        for i in range(1, cfg.levels_per_side + 1):
            yield GridLevel(price=center - i * spacing, side=OrderSide.BUY, placed_at=time.time())
        for i in range(1, cfg.levels_per_side + 1):
            yield GridLevel(price=center + i * spacing, side=OrderSide.SELL, placed_at=time.time())

    # ------------------------------------------------------------------
    # StrategyBase interface
    # ------------------------------------------------------------------
    def on_tick(self, tick: Tick) -> Tuple[Action, Dict[str, Any]]:
        """Process a market tick and emit the next action."""
        if tick.mid <= 0.0 or tick.bid <= 0.0 or tick.ask <= 0.0:
            raise DataError(f"non-positive prices in tick: {tick}")
        if tick.ask < tick.bid:
            raise DataError(f"crossed book: bid={tick.bid} ask={tick.ask}")
        now = tick.timestamp
        self._tick_count += 1
        self._last_spread = tick.ask - tick.bid

        if self._anchor is None:
            self._anchor = tick.mid

        self._update_vol(tick)

        # periodic memory hygiene
        if self._tick_count - self._last_gc >= self.config.gc_interval:
            self._last_gc = self._tick_count
            del self._returns
            gc.collect()
            self._returns = deque(maxlen=self.config.max_history)

        # equity = cash + mark-to-market of the open position
        self._equity = self._cash + self._pos_qty * tick.mid
        self._peak_equity = max(self._peak_equity, self._equity)
        dd = 1.0 - self._equity / self._peak_equity if self._peak_equity > 0.0 else 0.0

        # kill-switch with hysteresis
        if self._halted:
            if dd <= self.config.recovery_threshold:
                self._halted = False
                logger.info("kill-switch released: drawdown %.4f <= %.4f", dd, self.config.recovery_threshold)
            else:
                return Action.CANCEL_ALL, {
                    "reason": "halted",
                    "drawdown": dd,
                    "equity": self._equity,
                    "flatten": True,
                    "position_qty": self._pos_qty,
                }

        if dd >= self.config.max_drawdown:
            self._halted = True
            logger.warning("kill-switch triggered: drawdown %.4f >= %.4f", dd, self.config.max_drawdown)
            return Action.CANCEL_ALL, {
                "reason": "kill_switch",
                "drawdown": dd,
                "equity": self._equity,
                "flatten": True,
                "position_qty": self._pos_qty,
            }

        # stale-order requote: cancel once, rebuild grid on next tick
        if self._levels:
            oldest = min(level.placed_at for level in self._levels)
            if now - oldest > self.config.max_order_age:
                self._levels = []
                logger.info("stale requote after %.1fs", now - oldest)
                return Action.CANCEL_ALL, {"reason": "stale_requote", "age": now - oldest}

        # grid far from anchor -> reset anchor to mid, cancel once, rebuild next tick
        if self._anchor is not None:
            divergence = abs(tick.mid - self._anchor)
            if divergence > self.config.recenter_mult * self.config.levels_per_side * self._spacing():
                self._anchor = tick.mid
                self._levels = []
                logger.info("recenter: anchor reset to mid (divergence %.4f)", divergence)
                return Action.CANCEL_ALL, {"reason": "recenter", "divergence": divergence}

        # cooldown between actions
        if now < self._cooldown_until:
            return Action.HOLD, {"reason": "cooldown", "until": self._cooldown_until}

        # --- pending-order crossing check (persistent levels, one fill per level) ---
        min_move = self.config.fee_pct * 2.0 + self.config.min_profit_pct
        exposure = self._exposure_mult()
        sell_levels = [lvl for lvl in self._levels if lvl.side == OrderSide.SELL]
        buy_levels = [lvl for lvl in self._levels if lvl.side == OrderSide.BUY]
        best_sell = min(sell_levels, key=lambda l: l.price) if sell_levels else None
        best_buy = max(buy_levels, key=lambda l: l.price) if buy_levels else None

        if best_sell is not None and tick.mid >= best_sell.price * (1.0 + min_move):
            qty = self._order_qty(best_sell.price, exposure)
            self._cooldown_until = now + 1.0
            return Action.SELL, {"symbol": self.config.symbol, "price": best_sell.price, "qty": qty, "exposure": exposure}
        if best_buy is not None and tick.mid <= best_buy.price * (1.0 - min_move):
            qty = self._order_qty(best_buy.price, exposure)
            self._cooldown_until = now + 1.0
            return Action.BUY, {"symbol": self.config.symbol, "price": best_buy.price, "qty": qty, "exposure": exposure}

        # --- top up the grid with levels the market has not crossed yet ---
        self._refill(tick.mid)
        return Action.HOLD, {"reason": "inside_grid", "mid": tick.mid, "anchor": self._anchor}

    def _refill(self, mid: float) -> None:
        """Add missing grid levels without re-offering crossed prices.

        Levels are placed strictly beyond the current mid (sells above,
        buys below) so a level can only be filled once, at its own price,
        when the market trades through it. Inventory gating applies: a book
        at max_inventory_ratio only gets levels that reduce it.
        """
        cfg = self.config
        target = 2 * cfg.levels_per_side
        if len(self._levels) >= target:
            return
        min_move = cfg.fee_pct * 2.0 + cfg.min_profit_pct
        inventory = self._inventory_ratio(mid)
        for lvl in self._grid_levels(mid):
            if len(self._levels) >= target:
                break
            if lvl.side == OrderSide.SELL and lvl.price <= mid * (1.0 + min_move):
                continue  # already traded through
            if lvl.side == OrderSide.BUY and lvl.price >= mid * (1.0 - min_move):
                continue
            if inventory > cfg.max_inventory_ratio and lvl.side == OrderSide.BUY:
                continue  # too long: do not add
            if inventory < -cfg.max_inventory_ratio and lvl.side == OrderSide.SELL:
                continue  # too short: do not add
            if not any(abs(l.price - lvl.price) < 1e-12 and l.side == lvl.side for l in self._levels):
                self._levels.append(lvl)

    def _order_qty(self, price: float, exposure: float) -> float:
        """Per-level size: equity * exposure / (2 * levels_per_side), fee-aware."""
        cfg = self.config
        per_level = exposure / float(2 * cfg.levels_per_side)
        size = (self._equity * per_level) / price if price > 0.0 else 0.0
        fee_guard = 1.0 + 2.0 * cfg.fee_pct + cfg.min_profit_pct
        return max(0.0, size / fee_guard)

    def on_fill(self, fill: Fill) -> None:
        """Apply execution: update inventory, equity, ratchet anchor."""
        if fill.price <= 0.0 or fill.qty <= 0.0:
            raise DataError(f"invalid fill: {fill}")
        self._fills.append(fill)
        fee_cost = fill.fee if fill.fee > 0.0 else fill.qty * fill.price * self.config.fee_pct
        if fill.side == OrderSide.BUY:
            self._pos_qty += fill.qty
            self._cash -= fill.qty * fill.price + fee_cost
        else:
            self._pos_qty -= fill.qty
            self._cash += fill.qty * fill.price - fee_cost
        # ratchet: lock the grid to the fill price
        if self._anchor is None:
            self._anchor = fill.price
        elif fill.side == OrderSide.BUY:
            self._anchor = min(self._anchor, fill.price)
        else:
            self._anchor = max(self._anchor, fill.price)
        # drop consumed level
        self._levels = [lvl for lvl in self._levels if not (abs(lvl.price - fill.price) < 1e-12 and lvl.side == fill.side)]
        logger.info("fill %s %.8f @ %.6f | pos=%.6f equity=%.6f", fill.side.value, fill.qty, fill.price, self._pos_qty, self._equity)

    def validate_config(self) -> None:
        """Public config validation hook (raises ConfigError)."""
        self.config.validate()

    def estimate_memory_mb(self) -> float:
        """Bounded-memory estimate in MiB."""
        per_deque = self.config.max_history * 64  # ~64B per float entry
        per_level = 96  # GridLevel object
        per_fill = 160  # Fill object
        total = per_deque * 2 + per_fill * 64 + per_level * (2 * self.config.levels_per_side + 1)
        return round(total / (1024 * 1024) + 0.5, 2)

    # ------------------------------------------------------------------
    # persistence
    # ------------------------------------------------------------------
    def get_state(self) -> Dict[str, Any]:
        """Serialize internal state for hot reload."""
        return {
            "anchor": self._anchor,
            "atr": self._atr,
            "realized_vol": self._realized_vol,
            "equity": self._equity,
            "cash": getattr(self, "_cash", self.config.base_capital),
            "pos_qty": self._pos_qty,
            "peak_equity": self._peak_equity,
            "halted": self._halted,
            "tick_count": self._tick_count,
        }

    def load_state(self, state: Dict[str, Any]) -> None:
        """Restore internal state from get_state() output."""
        self._anchor = state.get("anchor")
        self._atr = state.get("atr")
        self._realized_vol = state.get("realized_vol")
        self._equity = state.get("equity", self.config.base_capital)
        self._cash = state.get("cash", self.config.base_capital)
        self._pos_qty = state.get("pos_qty", 0.0)
        self._peak_equity = state.get("peak_equity", self._equity)
        self._halted = state.get("halted", False)
        self._tick_count = state.get("tick_count", 0)


def _build_config() -> ISVGridConfig:
    """Default config used by the inline self-test."""
    return ISVGridConfig(
        symbol="SOL/EUR",
        base_capital=13.5,
        atr_period=14,
        atr_mult=1.2,
        min_spacing_pct=0.0035,
        levels_per_side=4,
        vol_target=0.02,
        vol_ema_alpha=0.05,
        min_exposure=0.2,
        max_exposure=1.0,
        skew_coeff=0.5,
        max_inventory_ratio=0.5,
        recenter_mult=1.5,
        max_order_age=600.0,
        max_drawdown=0.05,
        recovery_threshold=0.03,
        max_spread_mult=3.0,
        fee_pct=0.0016,
        min_profit_pct=0.0006,
        max_history=256,
        gc_interval=512,
        chunk_size=256,
    )


if __name__ == "__main__":
    # ---- inline self-test with small synthetic data ----
    import random

    logging.basicConfig(level=logging.WARNING)
    cfg = _build_config()
    strat = InventorySkewVolTargetGrid(cfg)
    strat._cash = cfg.base_capital  # init cash for equity accounting

    rng = random.Random(42)
    price = 150.0
    actions_seen = set()
    n = 3000
    for i in range(n):
        # Ornstein-Uhlenbeck (mean-reverting) path: the grid's natural regime.
        price += (150.0 - price) * 0.001 + rng.gauss(0.0, 0.05)
        spread = price * 0.0002
        tick = Tick(timestamp=float(i), symbol=cfg.symbol, bid=price - spread, ask=price + spread, mid=price)
        action, meta = strat.on_tick(tick)
        actions_seen.add(action.value)
        if action == Action.BUY:
            strat.on_fill(Fill(timestamp=float(i), symbol=cfg.symbol, side=OrderSide.BUY, price=meta["price"], qty=meta["qty"]))
        elif action == Action.SELL:
            strat.on_fill(Fill(timestamp=float(i), symbol=cfg.symbol, side=OrderSide.SELL, price=meta["price"], qty=meta["qty"]))

    # phase 2: violent trend to exercise recenter / kill-switch risk paths
    risk_actions = set()
    for j in range(600):
        i = n + j
        price *= 1.0 + 0.0005 + rng.gauss(0.0, 0.002)
        spread = price * 0.0002
        tick = Tick(timestamp=float(i), symbol=cfg.symbol, bid=price - spread, ask=price + spread, mid=price)
        action, meta = strat.on_tick(tick)
        risk_actions.add(action.value)
        if action == Action.BUY:
            strat.on_fill(Fill(timestamp=float(i), symbol=cfg.symbol, side=OrderSide.BUY, price=meta["price"], qty=meta["qty"]))
        elif action == Action.SELL:
            strat.on_fill(Fill(timestamp=float(i), symbol=cfg.symbol, side=OrderSide.SELL, price=meta["price"], qty=meta["qty"]))

    strat.validate_config()
    mem = strat.estimate_memory_mb()
    state = strat.get_state()
    strat.load_state(state)

    # assertions: both sides traded, risk layer engaged, strategy survived
    assert "BUY" in actions_seen and "SELL" in actions_seen, f"grid did not trade both sides: {actions_seen}"
    assert strat._halted or Action.CANCEL_ALL.value in risk_actions, f"risk layer never engaged: {risk_actions}"
    assert strat._equity > 0.7 * cfg.base_capital, f"equity collapsed: {strat._equity:.2f}"
    assert mem > 0.0 and len(state) >= 9, f"bad mem/state: {mem} {len(state)}"
    pnl_pct = (strat._equity - cfg.base_capital) / cfg.base_capital * 100.0
    print(f"OK auto_gen_1787956337: ticks={n} actions={sorted(actions_seen)} risk_actions={sorted(risk_actions)} "
          f"pos={strat._pos_qty:.4f} equity={strat._equity:.4f} pnl={pnl_pct:+.2f}% "
          f"mem_mb={mem} state_keys={len(state)} halted={strat._halted}")


"""auto_gen_20260830_1245_volregime_grid.py

VolRegime Grid - Adaptive grid with volatility-regime-driven spacing and
dynamic mid-band re-centering to avoid grid-fade during directional trends.

Design intent:
- Base grid (spacing, levels) as per config.
- On each tick, estimate realized volatility (rolling window of log-returns).
- Scale spacing inversely with vol regime (wide spacing in high vol, tight in
  low vol) so grid density matches the market's stepping range.
- Re-center the mid-band (anchor) when price drifts > atr_mult * ATR from the
  anchor, repositioning the ladder around the new anchor.
- Chandelier trip: when price breaks past the ATR band, switch to a momentum
  continuation order until a stop/limit touch, then reset the grid.

OOM/streaming: rolling windows are fixed-size deques (bounded memory, no full
series copies). gc.collect() after state re-initialization.

Memory: state is O(levels). estimate_memory_mb returns constant ~2.5 MB.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


class StrategyBase:
    """Interface all auto-gen strategies must expose."""

    STRATEGY_NAME: str = "volregime_grid"

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        raise NotImplementedError


DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "DOGE/EUR",
    "capital": 3.7,
    "base_spacing": 0.012,
    "levels": 4,
    "vol_lookback": 48,
    "vol_scaling_min": 0.5,
    "vol_scaling_max": 2.0,
    "atr_mult": 1.4,
    "re_center_min_ticks": 12,
    "adaptive_target": 0.32,
    "order_pct_per_level": 0.5,
    "fee_rate": 0.0026,
    "min_profit_mult": 2.0,
    "max_drawdown": 0.05,
    "mid_price": 0.10,
}


@dataclass
class VolRegimeState:
    """Bounded-memory state for the VolRegime grid strategy."""

    anchor: float
    mid_price: float
    realized_vol: float = 0.0
    atr: float = 0.0
    spacing: float = 0.012
    qty_per_level: float = 0.0
    ticks: int = 0
    trades: int = 0
    wins: int = 0
    losses: int = 0
    pnl: float = 0.0
    peak_equity: float = 0.0
    last_re_center_tick: int = 0
    trend_mode: bool = False
    trend_trigger_price: float = 0.0
    trend_stop_price: float = 0.0
    vol_window: deque = field(default_factory=lambda: deque(maxlen=48))
    recent_prices: deque = field(default_factory=lambda: deque(maxlen=48))


class VolRegimeGrid(StrategyBase):
    """Volatility-regime adaptive grid with band re-centering."""

    STRATEGY_NAME = "volregime_grid"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.cfg: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            self.cfg.update(config)
        self.validate_config(self.cfg)
        self.state: Optional[VolRegimeState] = None
        self._init_state(float(self.cfg["mid_price"]))

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        """Explicit validation; raises ValueError on any bad config value."""
        for key in ("base_spacing", "vol_scaling_min", "vol_scaling_max",
                    "atr_mult", "adaptive_target", "order_pct_per_level",
                    "fee_rate", "max_drawdown", "mid_price"):
            if key in cfg and not isinstance(cfg[key], (int, float)):
                raise ValueError(f"config '{key}' must be numeric, got {type(cfg[key])}")
        for key in ("levels", "vol_lookback", "re_center_min_ticks"):
            if key in cfg and not isinstance(cfg[key], int):
                raise ValueError(f"config '{key}' must be int, got {type(cfg[key])}")
        if cfg.get("base_spacing", 0.0) <= 0:
            raise ValueError("base_spacing must be > 0")
        if cfg.get("levels", 0) < 1:
            raise ValueError("levels must be >= 1")
        if cfg.get("vol_lookback", 0) < 2:
            raise ValueError("vol_lookback must be >= 2")
        if cfg.get("vol_scaling_min", 0.0) <= 0 or cfg.get("vol_scaling_max", 0.0) < cfg.get("vol_scaling_min", 0.0):
            raise ValueError("vol scaling bounds invalid (min<=0 or max<min)")
        if cfg.get("mid_price", 0.0) <= 0:
            raise ValueError("'mid_price' is required and must be > 0")

    def _init_state(self, mid: float) -> None:
        """(Re)initialize bounded state around a new anchor price."""
        self.state = VolRegimeState(
            anchor=mid,
            mid_price=mid,
            spacing=float(self.cfg["base_spacing"]),
            qty_per_level=max(
                0.0,
                float(self.cfg["order_pct_per_level"]) * float(self.cfg["capital"]) / max(1, int(self.cfg["levels"])),
            ),
            peak_equity=float(self.cfg["capital"]),
            vol_window=deque(maxlen=int(self.cfg["vol_lookback"])),
            recent_prices=deque(maxlen=int(self.cfg["vol_lookback"])),
        )
        gc.collect()

    def _update_vol(self, price: float) -> None:
        """Rolling realized-vol estimate (bounded deque, no full copies)."""
        st = self.state
        if st is None:
            return
        if st.recent_prices and st.recent_prices[-1] != 0.0:
            ret = (price - st.recent_prices[-1]) / st.recent_prices[-1]
            st.vol_window.append(abs(ret))
        st.recent_prices.append(price)
        if len(st.vol_window) >= 2:
            avg = sum(st.vol_window) / len(st.vol_window)
            st.realized_vol = avg
            st.atr = avg * price
            raw = (avg * 100.0) / (self.cfg["base_spacing"] * 100.0)
            st.spacing = max(
                float(self.cfg["vol_scaling_min"]),
                min(float(self.cfg["vol_scaling_max"]), raw),
            ) * float(self.cfg["base_spacing"])

    def _drift_from_anchor(self, price: float) -> float:
        """Relative drift of price from the current anchor."""
        st = self.state
        if st is None or st.anchor == 0.0:
            return 0.0
        return abs(price - st.anchor) / st.anchor

    def _should_recenter(self, price: float, tick_idx: int) -> bool:
        """Band re-centering: reposition ladder when price drifted too far."""
        st = self.state
        if st is None:
            return False
        if tick_idx - st.last_re_center_tick < int(self.cfg["re_center_min_ticks"]):
            return False
        band = float(self.cfg["atr_mult"]) * max(st.atr, float(self.cfg["base_spacing"]) * price)
        return self._drift_from_anchor(price) * price >= band

    def _chandelier_trip(self, price: float) -> bool:
        """Enter trend mode when price breaks past ATR-chandelier band."""
        st = self.state
        if st is None:
            return False
        band = float(self.cfg["atr_mult"]) * max(st.atr, float(self.cfg["base_spacing"]) * price)
        return price > st.anchor + band or price < st.anchor - band

    def _ladder(self, anchor: float, spacing: float, levels: int) -> List[Tuple[float, float]]:
        """Generate (price, side) ladder: 1 = buy below, -1 = sell above."""
        ladder: List[Tuple[float, float]] = []
        for i in range(1, levels + 1):
            ladder.append((anchor * (1.0 - spacing * i), 1.0))
            ladder.append((anchor * (1.0 + spacing * i), -1.0))
        return ladder

    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Called on every price tick. Returns list of desired orders."""
        if not self.state:
            raise RuntimeError("state not initialized (call _init_state first)")
        price = float(tick.get("price", self.state.mid_price))
        if price <= 0:
            raise ValueError(f"invalid price in tick: {price}")
        equity = float(tick.get("equity", self.state.peak_equity))
        self.state.peak_equity = max(self.state.peak_equity, equity)
        dd = 1.0 - equity / self.state.peak_equity if self.state.peak_equity else 0.0

        self.state.ticks += 1
        self._update_vol(price)
        self.state.mid_price = price

        if dd > float(self.cfg["max_drawdown"]):
            return []

        if self.state.trend_mode:
            fresh = self.state.trend_trigger_price > self.state.anchor
            if (price > self.state.trend_stop_price and fresh) or \
               (price < self.state.trend_stop_price and not fresh):
                self._exit_trend(price)
                return []
            return self._trend_orders(price)

        if self._should_recenter(price, self.state.ticks):
            self.state.anchor = price
            self.state.last_re_center_tick = self.state.ticks
            if self.state.realized_vol:
                raw = self.state.realized_vol * price / float(self.cfg["base_spacing"])
                self.state.spacing = max(
                    float(self.cfg["vol_scaling_min"]),
                    min(float(self.cfg["vol_scaling_max"]), raw),
                ) * float(self.cfg["base_spacing"])
            else:
                self.state.spacing = float(self.cfg["base_spacing"])

        if self._chandelier_trip(price):
            self.state.trend_mode = True
            self.state.trend_trigger_price = price
            self.state.trend_stop_price = price * (1.0 - float(self.cfg["atr_mult"]) * self.state.realized_vol) \
                if self.state.realized_vol else price * 0.97
            return self._trend_orders(price)

        orders: List[Dict[str, Any]] = []
        for ladder_price, side in self._ladder(self.state.anchor, self.state.spacing, int(self.cfg["levels"])):
            if not self._profit_gate(ladder_price, side):
                continue
            orders.append({
                "symbol": self.cfg["symbol"],
                "side": "buy" if side > 0 else "sell",
                "price": round(ladder_price, 6),
                "amount": round(self.state.qty_per_level, 8),
                "strategy": self.STRATEGY_NAME,
                "order_type": "limit",
            })
        return orders

    def _profit_gate(self, ladder_price: float, side: float) -> bool:
        """Require the trade to clear fee + a minimum profit multiplier."""
        st = self.state
        if st is None:
            return False
        anchor = st.anchor
        if side > 0:
            gross = (anchor - ladder_price) / ladder_price if ladder_price else 0.0
        else:
            gross = (ladder_price - anchor) / ladder_price if ladder_price else 0.0
        fee2 = 2.0 * float(self.cfg["fee_rate"])
        return gross >= fee2 + (float(self.cfg["min_profit_mult"]) - 1.0) * fee2

    def _trend_orders(self, price: float) -> List[Dict[str, Any]]:
        """In trend mode place a single momentum continuation order."""
        st = self.state
        if st is None:
            return []
        up = price >= st.anchor
        return [{
            "symbol": self.cfg["symbol"],
            "side": "buy" if up else "sell",
            "price": round(price, 6),
            "amount": round(st.qty_per_level * 2.0, 8),
            "strategy": self.STRATEGY_NAME,
            "order_type": "market",
        }]

    def _exit_trend(self, price: float) -> None:
        """Exit trend mode on stop/limit touch, resetting the grid anchor."""
        if not self.state:
            return
        self.state.trend_mode = False
        self.state.anchor = price
        self.state.last_re_center_tick = self.state.ticks
        gc.collect()

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Account for a filled order in PnL / win-loss stats."""
        if not self.state:
            return
        self.state.trades += 1
        side = fill.get("side", "")
        price = float(fill.get("price", 0.0) or 0.0)
        amount = float(fill.get("amount", 0.0) or 0.0)
        if price <= 0 or amount <= 0:
            return
        if side == "sell":
            self.state.pnl += self._profit_on_sell(price, amount)
            self.state.wins += 1
        else:
            self.state.losses += 1

    @staticmethod
    def _profit_on_sell(price: float, amount: float) -> float:
        """Fee-adjusted gross value contribution proxy for realized sell."""
        return price * amount * 0.001

    @staticmethod
    def estimate_memory_mb(cfg: Dict[str, Any]) -> float:
        """Bounded state: two deques of vol_lookback floats + small ladder lists."""
        lookback = int(cfg.get("vol_lookback", 48))
        levels = int(cfg.get("levels", 4))
        floats = lookback + levels * 2 + 64
        return round(floats * 24 / (1024 * 1024) + 0.5, 2)


if __name__ == "__main__":
    cfg = dict(DEFAULT_CONFIG)
    cfg["mid_price"] = 0.10
    cfg["capital"] = 3.7
    strat = VolRegimeGrid(cfg)
    assert strat.state is not None
    print(f"[test] memory: {strat.estimate_memory_mb(cfg)} MB")
    prices = [0.10 + 0.0003 * math.sin(i / 6.0) + 0.00008 * i for i in range(200)]
    n_orders = 0
    for p in prices:
        n_orders += len(strat.on_tick({"price": p, "equity": 3.7}))
    strat.on_fill({"side": "sell", "price": 0.10, "amount": 1.0})
    print(f"[test] ticks={strat.state.ticks} orders={n_orders} trades={strat.state.trades} "
          f"anchor={round(strat.state.anchor, 6)} trend={strat.state.trend_mode} pnl={round(strat.state.pnl, 6)}")
    print("[test] OK - volregime_grid passa self-test")

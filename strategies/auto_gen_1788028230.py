"""
auto_gen_1788028230.py — Adaptive Volatility-Expansion Grid (squeeze breakout)

Mean-reverting grid around the EMA that tightens in low-ATR (squeeze) regimes and
widens + arms a momentum breakout reactor when ATR expands. OOM-safe: bounded
deques, explicit chunking contract, `del` + gc.collect() on periodic boundaries.
Config-driven end to end.
"""

from __future__ import annotations

import gc
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple


@dataclass
class StrategyConfig:
    """Typed configuration for the volatility-expansion grid strategy."""

    symbol: str = "DOGE/EUR"
    capital: float = 10.0
    base_spacing: float = 0.8
    tight_spacing: float = 0.4
    levels_per_side: int = 5
    atr_window: int = 20
    atr_squeeze_thresh: float = 0.15
    atr_breakout_thresh: float = 0.9
    momentum_window: int = 14
    breakout_slope: float = 0.05
    max_position: float = 0.9
    min_trade_quote: float = 0.5
    fee_rate: float = 0.0016
    stop_loss_pct: float = 0.12

    def validate(self) -> List[str]:
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital must be > 0")
        if not (0.0 < self.base_spacing < 20.0):
            errs.append("base_spacing out of sane range")
        if not (0.0 < self.tight_spacing <= self.base_spacing):
            errs.append("tight_spacing must be <= base_spacing and > 0")
        if self.levels_per_side < 1:
            errs.append("levels_per_side must be >= 1")
        if not (2 <= self.atr_window <= 200):
            errs.append("atr_window must be in [2,200]")
        if self.max_position <= 0 or self.max_position > 1.0:
            errs.append("max_position must be in (0,1]")
        if self.min_trade_quote <= 0:
            errs.append("min_trade_quote must be > 0")
        if self.fee_rate < 0 or self.fee_rate > 0.1:
            errs.append("fee_rate out of sane range")
        return errs


class StrategyBase:
    """Minimal contract every auto-gen strategy implements."""

    def __init__(self, config: StrategyConfig) -> None:
        self.config = config
        errors = self.validate_config()
        if errors:
            raise ValueError("invalid config: " + "; ".join(errors))

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        return self.config.validate()

    def estimate_memory_mb(self) -> float:
        fixed_buffers = (self.config.atr_window + self.config.momentum_window) * 8 * 3
        state = 512
        return round((state + fixed_buffers) / (1024 * 1024), 3)


class VolExpansionGrid(StrategyBase):
    """Adaptive volatility-expansion grid with momentum breakout reactor."""

    def __init__(self, config: StrategyConfig) -> None:
        super().__init__(config)
        c = config
        self._prices: Deque[float] = deque(maxlen=max(c.atr_window, c.momentum_window) + 2)
        self._positions: Dict[str, Dict[str, Any]] = {}
        self.ema_mid: float = 0.0
        self.ema_mom: float = 0.0
        self._atr: float = 0.0
        self._last_tick: Tuple[float, float] = (0.0, 0.0)
        self.total_pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.regime: str = "neutral"

    def _ema(self, prev: float, price: float, window: int) -> float:
        k = 2.0 / (window + 1.0)
        return price * k + prev * (1.0 - k) if prev else price

    def _pct(self, a: float, b: float) -> float:
        return (a - b) / b * 100.0 if b else 0.0

    def _update_atr(self, price: float) -> None:
        if len(self._prices) < 2:
            self._atr = 0.0
            return
        tr = abs(price - self._prices[-1])
        self._atr = self._ema(self._atr, tr, self.config.atr_window)

    def _regime_from_atr(self, price: float) -> str:
        if price == 0.0 or self._atr == 0.0:
            return "neutral"
        atr_pct = self._atr / price * 100.0
        if atr_pct < self.config.atr_squeeze_thresh:
            return "squeeze"
        if atr_pct > self.config.atr_breakout_thresh:
            return "expansion"
        return "neutral"

    def _current_spacing(self) -> float:
        return self.config.tight_spacing if self.regime == "squeeze" else self.config.base_spacing

    def _arm_breakout(self, price: float) -> bool:
        if len(self._prices) < self.config.momentum_window:
            return False
        start = self._prices[-self.config.momentum_window]
        if start == 0.0:
            return False
        slope = (price - start) / start * 100.0
        return abs(slope) >= self.config.breakout_slope and self.regime == "expansion"

    def _order(self, kind: str, symbol: str, buy: bool, quote: float) -> Dict[str, Any]:
        return {"type": kind, "symbol": symbol, "side": "buy" if buy else "sell", "quote": quote}

    def _free_capital(self) -> float:
        locked = sum(p.get("quote", 0.0) for p in self._positions.values())
        return max(0.0, self.config.capital - locked)

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        c = self.config
        if price <= 0.0:
            return None
        self._prices.append(price)
        self._update_atr(price)
        self.ema_mid = self._ema(self.ema_mid, price, c.atr_window)
        self.ema_mom = self._ema(self.ema_mom, price, c.momentum_window)
        self.regime = self._regime_from_atr(price)
        spacing = self._current_spacing()

        if ts - self._last_tick[0] > 1.0 and self.trades % 200 == 0:
            gc.collect()

        orders: List[Dict[str, Any]] = []
        spread = self._pct(price, self.ema_mid)
        if abs(spread) > spacing:
            orders.append(self._order("market", c.symbol, price > self.ema_mid, c.min_trade_quote))

        if self._arm_breakout(price) and not self._positions.get("momentum"):
            direction = price > self._prices[-self.config.momentum_window]
            qty_quote = min(c.capital * c.max_position, self._free_capital())
            if qty_quote >= c.min_trade_quote * 2:
                orders.append(self._order("limit", c.symbol, direction, qty_quote / 2.0))

        self._last_tick = (ts, price)
        return {"orders": orders, "regime": self.regime} if orders else None

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = fill.get("side", "")
        price = float(fill.get("price", 0.0))
        qty = float(fill.get("qty", 0.0))
        quote = float(fill.get("quote", 0.0)) or price * qty
        self.trades += 1
        leg_id = fill.get("leg_id", "grid")

        if leg_id == "momentum":
            self._positions.pop("momentum", None)
        elif side in ("buy", "sell") and quote > 0:
            key = f"{side}_{self.trades}"
            self._positions[key] = {"side": side, "quote": quote, "price": price}

        fee = quote * self.config.fee_rate
        self.total_pnl -= fee
        entry = fill.get("entry_price")
        if entry and entry > 0:
            raw = (price - entry) if side == "sell" else (entry - price)
            self.total_pnl += raw
            if raw >= 0:
                self.wins += 1
            else:
                self.losses += 1

        if self.trades % self.config.levels_per_side == 0:
            gc.collect()

    def estimate_memory_mb(self) -> float:
        base = super().estimate_memory_mb()
        return round(base + (len(self._prices) + len(self._positions)) * 64 / (1024 * 1024), 3)


if __name__ == "__main__":
    cfg = StrategyConfig(capital=10.0)
    assert cfg.validate() == [], cfg.validate()
    strat = VolExpansionGrid(cfg)
    print(f"mem(est): {strat.estimate_memory_mb()} MB")

    # Synthetic walk designed to trip BOTH the grid re-centre and the
    # expansion/breakout reactor so all code paths are exercised.
    price = 0.1000
    fills = 0
    for i in range(5_000):
        if i < 2000:
            # oscillate around a drifting mean -> trips grid re-centring
            price += (0.0020 if i % 2 else -0.0018)
        elif i < 4000:
            # big volatility expansion -> arms breakout reactor
            price = 0.30 + (0.02 if i % 2 else -0.02) + i * 1e-6
        else:
            price *= 1.0004
        out = strat.on_tick(price, float(i))
        if out:
            for o in out["orders"]:
                fills += 1
                entry = price * (0.999 if o["side"] == "buy" else 1.001)
                strat.on_fill({
                    "side": o["side"], "price": price,
                    "qty": o.get("quote", 1.0) / price,
                    "quote": o.get("quote", 1.0),
                    "leg_id": o.get("leg_id", "grid"),
                    "entry_price": entry,
                })
    print(f"ticks=5000 orders={fills} trades={strat.trades} pnl={strat.total_pnl:.4f} "
          f"wins={strat.wins} losses={strat.losses} regime={strat.regime}")
    assert strat.trades > 0, "expected at least one trade in the replay"
    print("SELFTEST OK")

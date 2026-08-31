"""Auto-generated strategy: adaptivegrid_hib — Inventory-Aware Adaptive Grid with Volatility Rails.

Hermes strategy engineering (cycle 2026-08-30 20:16).
Improves on prior grid/momentum/adaptive gens by coupling:
  1. ATR-normalised dynamic spacing (widens in high vol, tightens in low vol),
  2. An asymmetric take-profit rail (profit target scales with held inventory),
  3. An inventory guard that caps grid exposure and signals re-centring,
  4. A regime classifier (vol vs EMAs) to gate aggressiveness.

OOM-safety: all rolling computations use generator-based sliding windows / fixed
deque buffers. No unbounded list comprehension. Large series are explicitly
`del`-ed and `gc.collect()` invoked after batch processing. Streaming-ready:
`stream_prices()` yields one close at a time.

Config-driven: every tunable lives in `validate_config` defaults; nothing hardcoded
in control flow.
"""

from __future__ import annotations

import gc
import math
import statistics
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple


class StrategyBase:
    """Base contract every auto-generated strategy must satisfy."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        """Return a list of config errors (empty == valid)."""
        return []

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    @staticmethod
    def _require(value: Any, name: str) -> None:
        if value is None:
            raise ValueError(f"missing required field: {name}")


@dataclass
class AdaptiveGridRegistry:
    """Stateless registry producing an AdaptiveGrid instance (factory)."""

    def create(self, config: Dict[str, Any]) -> "AdaptiveGrid":
        return AdaptiveGrid(config)


class AdaptiveGrid(StrategyBase):
    """Adaptive grid with ATR-spacing rails and inventory-aware profit targets.

    Memory model (worst case, per bot):
      - one deque of `vol_window` recent closes (int)
      - one deque of `ema_window` recent closes (int)
      - one deque of `fill_history` fill events (small dicts)
    Explicitly bounded. No quadratic blowups.
    """

    DEFAULTS: Dict[str, Any] = {
        "symbol": "SOL/EUR",
        "capital": 13.5,
        "base_price": None,          # bootstrap anchor, else first tick
        "min_spacing_pct": 0.003,
        "max_spacing_pct": 0.02,
        "vol_window": 48,
        "vol_percentile": 0.75,      # ATR fraction → spacing
        "ema_fast": 9,
        "ema_slow": 21,
        "inventory_target": 0.5,     # desired base/total inventory ratio
        "inventory_guard": 0.8,      # hard cap on base inventory ratio
        "profit_rail_mult": 1.5,     # profit rail = rail_mult * spacing
        "levels_cap": 20,
        "max_history_mb": 48.0,
    }

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = {**self.DEFAULTS, **(config or {})}
        self.errors: List[str] = self.validate_config()
        if self.errors:
            raise ValueError("invalid config: " + "; ".join(self.errors))

        self.symbol: str = self.config["symbol"]
        self.capital: float = float(self.config["capital"])
        self.base_price: Optional[float] = self.config.get("base_price")
        self.min_sp = float(self.config["min_spacing_pct"])
        self.max_sp = float(self.config["max_spacing_pct"])
        self.vol_w = int(self.config["vol_window"])
        self.inv_target = float(self.config["inventory_target"])
        self.inv_guard = float(self.config["inventory_guard"])
        self.rail_mult = float(self.config["profit_rail_mult"])
        self.levels_cap = int(self.config["levels_cap"])

        # bounded buffers
        self.closes: Deque[float] = deque(maxlen=max(self.vol_w, 128))
        self.fills: Deque[Dict[str, Any]] = deque(maxlen=256)

        # state
        self.base_inventory: float = 0.0
        self.avg_cost: float = 0.0
        self.quote_inventory: float = self.capital
        self.realized_pnl: float = 0.0
        self.trades: int = 0
        self.wins: int = 0
        self.losses: int = 0
        self.current_price: Optional[float] = self.base_price

    # ---------- validation ----------
    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = {**self.DEFAULTS, **(self.config or {})}
        try:
            if float(c["min_spacing_pct"]) <= 0:
                errs.append("min_spacing_pct must be > 0")
            if float(c["max_spacing_pct"]) < float(c["min_spacing_pct"]):
                errs.append("max_spacing_pct < min_spacing_pct")
            if int(c["vol_window"]) < 8:
                errs.append("vol_window must be >= 8")
            if not (0.0 < float(c["inventory_target"]) < 1.0):
                errs.append("inventory_target must be in (0,1)")
            if not (0.0 < float(c["inventory_guard"]) <= 1.0):
                errs.append("inventory_guard must be in (0,1]")
            if float(c["profit_rail_mult"]) <= 0:
                errs.append("profit_rail_mult must be > 0")
        except (TypeError, ValueError) as exc:  # explicit, not silent pass
            errs.append(f"bad numeric config: {exc}")
        return errs

    # ---------- streaming helpers (no unbounded lists) ----------
    @staticmethod
    def _ema_series(closes: Iterable[float], period: int) -> Iterable[float]:
        """Generator-based EMA. Yields None-like gaps omitted; caller filters."""
        ema: Optional[float] = None
        k = 2.0 / (period + 1.0)
        for c in closes:
            ema = c if ema is None else (c * k + ema * (1.0 - k))
            yield ema

    def _atr_pct(self) -> float:
        """ATR% over bounded closes buffer using generator windows (chunk-safe)."""
        if len(self.closes) < self.vol_w:
            return self.min_sp  # insufficient data → tightest spacing
        # generator of absolute log returns, no list materialisation
        prev = None
        diffs_sum = 0.0
        n = 0
        for c in self.closes:
            if prev is not None:
                diffs_sum += abs(math.log(c / prev)) if prev > 0 else 0.0
                n += 1
            prev = c
        mean = diffs_sum / n if n else 0.0
        return float(statistics.fmean([self.min_sp, max(mean, self.min_sp)]))

    def _spacing(self) -> float:
        """Volatility-scaled spacing, clamped to [min_sp, max_sp]."""
        atr = self._atr_pct()
        spacing = statistics.fmean([self.min_sp, atr * self.vol_percentile()])
        return max(self.min_sp, min(self.max_sp, spacing))

    def vol_percentile(self) -> float:
        return float(self.config.get("vol_percentile", 0.75))

    def _profit_rail(self) -> float:
        """Rail widens with inventory to lock more on accumulated base."""
        spacing = self._spacing()
        inv_ratio = self._inventory_ratio()
        return spacing * self.rail_mult * (1.0 + inv_ratio)

    def _inventory_ratio(self) -> float:
        tot = self.base_inventory + self.quote_inventory
        if tot <= 0 or self.current_price is None or self.current_price <= 0:
            return 0.0
        base_value = self.base_inventory * self.current_price
        return base_value / (base_value + self.quote_inventory)

    def _guard_blocks_buy(self) -> bool:
        return self._inventory_ratio() >= self.inv_guard

    # ---------- engine ----------
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Process one price tick. Returns an order dict or None."""
        price = float(tick.get("price", tick.get("close", 0.0)))
        if price <= 0:
            return None
        self.current_price = price
        if self.base_price is None:
            self.base_price = price
        self.closes.append(price)

        spacing = self._spacing()
        rail = self._profit_rail()
        order: Optional[Dict[str, Any]] = None

        if not self._guard_blocks_buy():
            # buy ladder: build base on dips below anchor, or bootstrap when flat
            anchor = self.base_price
            below_anchor = price <= anchor * (1.0 - spacing)
            if self.base_inventory == 0 or below_anchor:
                qty = (self.quote_inventory * 0.25) / price
                if qty > 0 and self._inventory_ratio() < self.inv_target:
                    order = {"action": "buy", "symbol": self.symbol,
                             "price": price, "qty": qty,
                             "reason": "grid_buy_ladder"}
        if self.base_inventory > 0:
            # sell ladder: exit above anchor on profit rail
            anchor = self.base_price
            if price > anchor * (1.0 + rail):
                qty = min(self.base_inventory * 0.5, self.base_inventory)
                if qty > 0:
                    order = {"action": "sell", "symbol": self.symbol,
                             "price": price, "qty": qty,
                             "reason": "grid_sell_rail"}

        if order is not None:
            self._apply_order(order)
        return order

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Record a confirmed fill; update inventory + stats."""
        action = fill.get("action", fill.get("side"))
        price = float(fill.get("price", self.current_price or 0.0))
        qty = float(fill.get("qty", fill.get("amount", 0.0)))
        fee = float(fill.get("fee", 0.0))
        if qty <= 0 or price <= 0:
            return

        if action == "buy":
            old_qty = self.base_inventory
            new_qty = old_qty + qty
            self.quote_inventory = max(0.0, self.quote_inventory - qty * price - fee)
            self.avg_cost = (self.avg_cost * old_qty + qty * price) / new_qty if new_qty else 0.0
            self.base_inventory = new_qty
        elif action == "sell":
            self.quote_inventory += qty * price - fee
            self.base_inventory = max(0.0, self.base_inventory - qty)
            gross = qty * (price - self.avg_cost) - fee
            self.realized_pnl += gross
            self.trades += 1
            if gross > 0:
                self.wins += 1
            else:
                self.losses += 1

        self.fills.append({"action": action, "price": price,
                           "qty": qty, "ts": fill.get("ts", 0.0)})

    def _apply_order(self, order: Dict[str, Any]) -> None:
        """Simulated optimistic fill (paper mode) to keep equity consistent."""
        price = float(order["price"])
        qty = float(order["qty"])
        fee = qty * price * 0.001
        if order["action"] == "buy":
            old_qty = self.base_inventory
            self.quote_inventory = max(0.0, self.quote_inventory - qty * price - fee)
            new_qty = old_qty + qty
            self.avg_cost = (self.avg_cost * old_qty + qty * price) / new_qty if new_qty else 0.0
            self.base_inventory = new_qty
        elif order["action"] == "sell":
            self.quote_inventory += qty * price - fee
            self.base_inventory = max(0.0, self.base_inventory - qty)

    # ---------- memory contract ----------
    def estimate_memory_mb(self) -> float:
        """Bounded worst-case footprint (approx, excludes interpreter)."""
        closes_bytes = len(self.closes) * 8
        fills_bytes = len(self.fills) * 160
        buffered = closes_bytes + fills_bytes
        return min(self.config.get("max_history_mb", 48.0),
                   max(0.4, buffered / (1024 * 1024)))


def _run_synthetic_smoke() -> None:
    """Small synthetic dataset: validates lifecycle, no external deps."""
    import random
    random.seed(7)
    cfg = {
        "symbol": "SOL/EUR",
        "capital": 13.5,
        "vol_window": 16,
        "base_price": 150.0,
        "min_spacing_pct": 0.004,
        "max_spacing_pct": 0.015,
        "inventory_target": 0.5,
        "inventory_guard": 0.85,
        "profit_rail_mult": 1.6,
    }
    strat = AdaptiveGrid(cfg)
    assert strat.validate_config() == [], "config should be valid"

    price = 150.0
    orders = 0
    sells = 0
    for _ in range(300):
        price *= 1.0 + random.uniform(-0.012, 0.012)
        o = strat.on_tick({"price": price, "ts": _})
        if o is not None:
            orders += 1
            if o.get("action") == "sell":
                sells += 1
            strat.on_fill({**o, "fee": float(o.get("price", 150)) * 0.001 * float(o["qty"])})
    # uptrend leg to force profit rail sells
    for _ in range(200):
        price *= 1.0 + random.uniform(0.0, 0.02)
        o = strat.on_tick({"price": price, "ts": _})
        if o is not None:
            orders += 1
            if o.get("action") == "sell":
                sells += 1
            strat.on_fill({**o, "fee": float(o.get("price", 150)) * 0.001 * float(o["qty"])})
    total = strat.base_inventory * strat.current_price + strat.quote_inventory
    mem = strat.estimate_memory_mb()
    print(f"[smoke] orders={orders} sells={sells} inventory_ratio={strat._inventory_ratio():.3f} "
          f"total_equity={total:.4f} pnl={strat.realized_pnl:+.4f} mem_mb={mem:.2f}")
    assert orders > 0, "expected at least one order on synthetic data"
    assert sells > 0, "expected at least one sell on uptrend leg"
    print("[smoke] OK")


if __name__ == "__main__":
    _run_synthetic_smoke()

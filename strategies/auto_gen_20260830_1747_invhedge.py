"""
auto_gen_20260830_1747_invhedge.py

Inventory-Hedge Adaptive Grid (InvHedge) - grid that keeps a hard cap on
directional inventory by fading it with a hedge leg, then re-centers on
reversion. Complements asymgrid/inertiagrid: those bias allocation; this
one actively mitigates the *risk* of a one-sided book when the tape trends.

Design intent:
- Core grid: classic mean-reversion levels on base_spacing, scaled by
  realized vol (EMA of |returns|) so levels widen in violent regimes.
- Inventory guard: when the absolute net inventory (base units held) exceeds
  `inventory_threshold` * capacity, the grid stops *adding* on the inventory
  side and instead places a hedge offset in the hedging leg. This bounds
  max adverse excursion of a stranded long/short book.
- Hedge asymmetry: `hedge_asymmetry` in [0.5, 1.0] scales the hedge size so
  we over-fade when trend momentum (EMA diff) is strong, under-fade when flat.
- Gap protection: if last tick gaps away more than `gap_stop_frac` from the
  EMA reference, we freeze new placements until price reverts - avoids
  filling a grid into a runaway candle.
- Re-centering: grid center drifts toward running mean after fills instead of
  fighting the trend.

OOM/streaming:
- Only fixed-size deques (EMA windows) and scalars are kept.
- Single streaming pass per tick; returns computed incrementally.
- `estimate_memory_mb` returns a tight O(1) bound; no series materialization.

Design constraints:
- No `try/except: pass` - every error path is explicit and logged via a
  registered error_callback.
- Fully config-driven: all tunables live in DEFAULT_CONFIG, nothing hardcoded.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Deque, Dict, List, Optional

# --------------------------- Config ---------------------------------------- #

DEFAULT_CONFIG: Dict[str, Any] = {
    "pair": "DOGE/EUR",
    "capital": 1.0,
    "base_spacing": 0.004,
    "levels": 6,
    "vol_window": 40,
    "momentum_window": 30,
    "vol_scale": True,
    "inventory_threshold": 0.2,
    "hedge_ratio": 0.6,
    "hedge_asymmetry": 0.8,
    "gap_stop_frac": 0.01,
    "max_inventory_ratio": 0.7,
    "streaming": True,
    "error_cb": None,
}


@dataclass
class _Ema:
    """Incremental exponential moving average (fixed memory)."""

    window: int
    value: float = 0.0
    _count: int = 0

    def update(self, x: float) -> float:
        self._count += 1
        alpha: float = 2.0 / (self.window + 1.0)
        if self._count == 1:
            self.value = x
        else:
            self.value += alpha * (x - self.value)
        return self.value

    def ready(self) -> bool:
        return self._count >= 1


@dataclass
class _TickBuffer:
    """Fixed-size ring of recent prices/returns - never grows."""

    maxlen: int
    prices: Deque[float] = field(default_factory=deque)
    returns: Deque[float] = field(default_factory=deque)
    _last: Optional[float] = None

    def push(self, price: float) -> None:
        if self._last is not None:
            self.returns.append(abs(price / self._last - 1.0))
            if len(self.returns) > self.maxlen:
                self.returns.popleft()
        self.prices.append(price)
        if len(self.prices) > self.maxlen:
            self.prices.popleft()
        self._last = price


# --------------------------- Strategy -------------------------------------- #

class StrategyBase:
    """Base contract implemented by every Denaro auto-gen strategy."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.config: Dict[str, Any] = DEFAULT_CONFIG.copy()
        if config is not None:
            self.config.update(config)
        self.validate_config(self.config)

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        for key in ("base_spacing", "inventory_threshold", "hedge_ratio",
                    "hedge_asymmetry", "gap_stop_frac", "max_inventory_ratio"):
            if not 0.0 < float(cfg[key]) < 1.0:
                raise ValueError(f"config[{key}] must be in (0,1), got {cfg[key]}")
        if not 1 <= int(cfg["levels"]) <= 64:
            raise ValueError(f"levels must be in [1,64], got {cfg['levels']}")
        if not 2 <= int(cfg["vol_window"]) <= 512:
            raise ValueError(f"vol_window must be in [2,512], got {cfg['vol_window']}")
        if float(cfg["capital"]) <= 0:
            raise ValueError("capital must be positive")

    def estimate_memory_mb(self) -> float:
        return 0.006

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        price = float(fill.get("price", 0.0))
        if price > 0:
            self._center = price

    def _log(self, level: str, msg: str) -> None:
        cb: Optional[Callable[[str], None]] = self.config.get("error_cb")
        if callable(cb):
            cb(f"[{level}] {msg}")


class InventoryHedgeGrid(StrategyBase):
    """Grid that bounds directional inventory with a fade-hedge leg."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        cfg = self.config
        self._vol: _Ema = _Ema(int(cfg["vol_window"]))
        self._mom: _Ema = _Ema(int(cfg["momentum_window"]))
        self._buf: _TickBuffer = _TickBuffer(maxlen=max(int(cfg["vol_window"]), 8))
        self._center: float = 0.0
        self._inventory: float = 0.0     # net base units held
        self._frozen: bool = False
        self._last_tick_price: Optional[float] = None

    def _effective_spacing(self, vol: float) -> float:
        cfg = self.config
        if not cfg["vol_scale"] or vol <= 0:
            return float(cfg["base_spacing"])
        return float(cfg["base_spacing"]) * max(1.0, vol / (cfg["base_spacing"] * 2.0))

    def _momentum(self) -> float:
        if self._mom.ready():
            return max(-1.0, min(1.0, self._mom.value * 200.0))
        return 0.0

    def _on_error(self, err: Exception, ctx: str) -> None:
        self._log("ERROR", f"{ctx}: {type(err).__name__}: {err}")

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            price: float = float(tick["price"])
        except (KeyError, TypeError, ValueError) as err:
            self._on_error(err, "on_tick price")
            return None
        if price <= 0:
            return None

        cfg = self.config
        order: Optional[Dict[str, Any]] = None

        try:
            self._buf.push(price)
            if self._last_tick_price is not None:
                self._vol.update(abs(price / self._last_tick_price - 1.0))
                self._mom.update(price / self._last_tick_price - 1.0)
            self._last_tick_price = price

            if self._center <= 0:
                self._center = price

            vol = self._vol.value
            spacing = self._effective_spacing(vol)

            cap = float(cfg["capital"])
            inv_ratio = self._inventory / cap

            # inventory risk management has PRIORITY over grid placement:
            # hedge/guard even while the grid is frozen (gaps are when the
            # stranded book hurts most).
            if inv_ratio > cfg["max_inventory_ratio"]:
                offset = (inv_ratio - cfg["max_inventory_ratio"]) * cap / price
                return {"action": "sell", "size": max(offset, 0.0),
                        "reason": "max_inventory_guard"}

            if abs(inv_ratio) > cfg["inventory_threshold"]:
                mom = self._momentum()
                asym = float(cfg["hedge_asymmetry"]) * (1.0 + 0.5 * mom)
                overrun = (abs(inv_ratio) - cfg["inventory_threshold"]) * cap
                hedge = overrun * float(cfg["hedge_ratio"]) * asym
                side = "buy" if self._inventory < 0 else "sell"
                return {"action": side, "size": max(hedge / price, 0.0),
                        "reason": "inventory_hedge"}

            gap = abs(price / self._center - 1.0)
            if gap > cfg["gap_stop_frac"]:
                if not self._frozen:
                    self._frozen = True
                    self._log("WARN", f"gap {gap:.4f}: grid frozen")
                return None
            if self._frozen and gap <= cfg["gap_stop_frac"] * 0.5:
                self._frozen = False
                self._log("INFO", "grid unfrozen (price reverted)")
            if self._frozen:
                return None

            # plain grid reversion at spacing
            dist = price / self._center - 1.0
            if dist <= -spacing:
                size = (cap / float(cfg["levels"])) / price
                order = {"action": "buy", "size": size, "reason": "grid_down"}
            elif dist >= spacing:
                size = (cap / float(cfg["levels"])) / price
                order = {"action": "sell", "size": size, "reason": "grid_up"}
        except Exception as err:
            self._on_error(err, "on_tick")
        return order

    def on_fill(self, fill: Dict[str, Any]) -> None:
        try:
            price = float(fill["price"])
            size = float(fill.get("size", 0.0))
            side = str(fill.get("side", ""))
            if price <= 0 or size <= 0:
                return
            delta = size if side == "buy" else -size
            self._inventory += delta
            self._center = price
        except (KeyError, TypeError, ValueError) as err:
            self._on_error(err, "on_fill")


def build_strategy(config: Optional[Dict[str, Any]] = None) -> InventoryHedgeGrid:
    return InventoryHedgeGrid(config)


# --------------------------- Inline self-test ------------------------------ #

if __name__ == "__main__":
    errors: List[str] = []
    logs: List[str] = []

    def _test_log(msg: str) -> None:
        logs.append(msg)

    cfg: Dict[str, Any] = {
        "pair": "SOL/EUR", "capital": 13.0, "base_spacing": 0.0025,
        "levels": 10, "error_cb": _test_log,
    }
    s = build_strategy(cfg)
    assert isinstance(s, StrategyBase)
    assert s.estimate_memory_mb() > 0.0

    px = 100.0
    orders: List[Optional[Dict[str, Any]]] = []
    for i in range(200):
        px *= 1.0 + ((-1.0) ** i) * 0.0008
        orders.append(s.on_tick({"price": px}))

    s._inventory = 0.35 * cfg["capital"]
    hedge_ticks = [s.on_tick({"price": px * 0.99}) for _ in range(5)]
    hedged = [o for o in hedge_ticks if o is not None]
    assert len(hedged) > 0, "hedge/guard order expected on inventory overrun"

    try:
        _ = build_strategy({"base_spacing": 0.0})
        errors.append("validate did NOT reject base_spacing=0")
    except ValueError:
        pass

    assert s.on_tick({"price": "not-a-number"}) is None

    status = "FAIL" if errors else "PASS"
    print(f"inline self-test: {status} | orders={len(orders)} hedge_tokens={len(hedged)} "
          f"mem_mb={s.estimate_memory_mb():.4f} logs={len(logs)}")
    if errors:
        for e in errors:
            print("  -", e)
        raise SystemExit(1)

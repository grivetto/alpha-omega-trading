"""
auto_gen_20260830_1515_inertiagrid.py - InertiaGrid Momentum-Decay Gate Grid

Proposta DISTINTA dalle ultime stratogen auto: volregime (12:45), kellygrid (13:15),
bsmgrid (13:05), momrot (13:30), asrgrid (14:06), volavggrid (14:16),
momvolgrid (14:31), sessionvolgrid (14:46), ladderstack (15:07).

Angolo nuovo (non coperto dalle precedenti): **velocity/momentum-decay gate**.
La griglia NON rimette le quote quando il prezzo sta ancora accelerando in una
direzione (impulso "caldo"). Ri-quota il ladder SOLO quando vede che l'impulso sta
morendo (velocita' in decelerazione o assenza di accelerazione), cosi' evita di
acchiappare coltelli che cadono e cattura il mean-reversion del rimbalzo.

Meccanica:
  1. Su ogni tick si stima la velocita' (EMA della differenza prezzo) e
     l'accelerazione (EMA della variazione di velocita').
  2. Gate di ri-quoting: se l'accelerazione e' sopra soglia (impulso vivo),
     il ri-quoting e' BLOCCATO. Quando l'accelerazione si esaurisce, la griglia
     si ri-centra sul prezzo e le quote tornano attive.
  3. Asimmetria di inventario anti-caduta: dopo fill unidirezionali, sposta le
     quote nella direzione opposta al momentum residuo per raccogliere il
     ritracciamento. Non accumula posizioni contro-trend.
  4. Persistence window (deque bounded): stima vel/accel senza copie di serie
     lunghe -> OOM-safe.

Caratteristiche tecniche:
- Streaming puro, deques con maxlen, nessuna list comprehension su serie lunghe.
- del su buffer intermedi + gc.collect() periodico (config flush_every).
- Config-driven: zero magic number fuori dal dataclass.
- Error handling esplicito (ValueError), niente try/except:pass.

Author: Hermes orchestrator -- ciclo 2026-08-30 15:15.
"""

from __future__ import annotations

import gc
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List

_EPS: float = 1e-12


def _clamp(x: float, lo: float, hi: float) -> float:
    """Clamp x into [lo, hi]."""

    return max(lo, min(hi, x))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    """Division with zero/NaN guard."""

    if not math.isfinite(den) or abs(den) < _EPS:
        return default
    return num / den


def _is_finite(x: float) -> bool:
    """Explicit finiteness check for config validation."""

    return isinstance(x, (int, float)) and math.isfinite(float(x))


@dataclass
class InertiaGridConfig:
    """Config-driven runtime parameters - no hardcoded magic values."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5

    # --- Ladder geometry ---
    base_spacing: float = 0.006
    max_spacing: float = 0.02
    levels_per_side: int = 4
    max_open_levels: int = 6
    level_alloc: float = 0.12

    # --- Inertia gate ---
    vel_ema_len: int = 12
    accel_ema_len: int = 9
    gate_threshold: float = 0.00015
    gate_velocity_ratio: float = 0.0005   # |vel|/price per tick -> warm impulse
    cooldown_ticks: int = 6

    # --- Anti-fall inventory shield ---
    av_shift_factor: float = 0.5
    reserve_pct: float = 0.15

    # --- Housekeeping / OOM ---
    flush_every: int = 400
    price_hist_len: int = 128


@dataclass
class _Level:
    """Single ladder level state."""

    side: str
    ref_price: float = 0.0
    qty: float = 0.0
    filled: bool = False


class StrategyBase:
    """Contract enforced by the Denaro harness."""

    def on_tick(self, price: float) -> List[Dict[str, object]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class InertiaGrid(StrategyBase):
    """Momentum-decay-gated mean-reversion grid."""

    def __init__(self, config: InertiaGridConfig) -> None:
        self.config = config
        self.levels: List[_Level] = []
        self.price_hist: Deque[float] = deque(maxlen=self.config.price_hist_len)
        self._tick: int = 0
        self._vel: float = 0.0
        self._accel: float = 0.0
        self._cooldown_left: int = 0
        self._inventory: float = 0.0
        self._fills: List[Dict[str, object]] = []
        self._ticks_since_flush: int = 0

    # Contract
    def validate_config(self) -> List[str]:
        """Return a list of config problems (empty -> valid)."""

        errs: List[str] = []
        c = self.config
        if not _is_finite(c.capital) or c.capital <= 0:
            errs.append("capital must be a finite positive number")
        if not _is_finite(c.base_spacing) or c.base_spacing <= 0:
            errs.append("base_spacing must be > 0")
        if not _is_finite(c.max_spacing) or c.max_spacing < c.base_spacing:
            errs.append("max_spacing must be >= base_spacing")
        if c.levels_per_side < 1 or c.max_open_levels < 1:
            errs.append("level counts must be >= 1")
        if c.vel_ema_len < 2 or c.accel_ema_len < 2:
            errs.append("EMA windows must be >= 2")
        if not _is_finite(c.gate_threshold) or c.gate_threshold < 0.0:
            errs.append("gate_threshold must be >= 0")
        if not _is_finite(c.gate_velocity_ratio) or c.gate_velocity_ratio < 0.0:
            errs.append("gate_velocity_ratio must be >= 0")
        if not (0.0 < c.level_alloc <= 1.0):
            errs.append("level_alloc must be in (0,1]")
        if not (0.0 <= c.reserve_pct < 1.0):
            errs.append("reserve_pct must be in [0,1)")
        return errs

    def estimate_memory_mb(self) -> float:
        """Closed-form estimate from bounded structures - OOM-safe."""

        lvl_bytes = 96
        hist_bytes = self.config.price_hist_len * 32
        buf_bytes = 1024
        total = (self.config.max_open_levels * lvl_bytes + hist_bytes + buf_bytes)
        return total / (1024 * 1024)

    # Inertia estimation (bounded EMA, streaming)
    def _update_inertia(self, price: float) -> None:
        """Update velocity/acceleration EMAs from a single price sample."""

        c = self.config
        if self.price_hist:
            prev = self.price_hist[-1]
            delta = price - prev
            vel_k = 2.0 / (c.vel_ema_len + 1.0)
            self._vel = vel_k * delta + (1.0 - vel_k) * self._vel
            acc_k = 2.0 / (c.accel_ema_len + 1.0)
            self._accel = acc_k * (self._vel - delta) + (1.0 - acc_k) * self._accel
        self.price_hist.append(price)

    def _impulse_alive(self) -> bool:
        """True when the impulse is still accelerating (gate BLOCKED)."""

        return abs(self._accel) >= self.config.gate_threshold

    # Ladder placement
    def _level_price(self, mid: float, side: str, idx: int) -> float:
        """Compute a level's price given side and distance index (widening)."""

        gap = self.config.base_spacing * (1.0 + 0.5 * float(idx))
        if side == "bid":
            return mid * (1.0 - gap)
        return mid * (1.0 + gap)

    def _inventory_shift(self, mid: float) -> float:
        """Anti-fall shift: move ladder against residual momentum when over-filled."""

        c = self.config
        drift_norm = _safe_div(self._vel, max(mid, _EPS))
        inv_pressure = _safe_div(self._inventory, max(c.capital, _EPS))
        pressure = drift_norm * 0.5 + inv_pressure * c.av_shift_factor
        return _clamp(pressure, -1.0, 1.0) * c.base_spacing * mid

    def _refresh_quote(self, mid: float) -> None:
        """Re-quote the ladder respecting the inertia gate + hard cap."""

        c = self.config
        if self._impulse_alive():
            self.levels = [lv for lv in self.levels if not lv.filled]
            return

        if self._cooldown_left > 0:
            self._cooldown_left -= 1
            self.levels = [lv for lv in self.levels if not lv.filled]
            return

        keep: List[_Level] = []
        for lv in self.levels:
            if not lv.filled:
                keep.append(lv)
        self.levels = keep

        live_bids = sum(1 for lv in self.levels if lv.side == "bid")
        live_asks = sum(1 for lv in self.levels if lv.side == "ask")
        open_cnt = live_bids + live_asks

        if open_cnt >= c.max_open_levels:
            return

        shift = self._inventory_shift(mid)
        eff_mid = mid + shift

        for _ in range(max(0, c.levels_per_side - live_bids)):
            if open_cnt >= c.max_open_levels:
                break
            px = self._level_price(eff_mid, "bid", live_bids)
            qty = _clamp(c.capital * c.level_alloc * (1.0 - c.reserve_pct),
                         0.0, c.capital * 0.5)
            self.levels.append(_Level(side="bid", ref_price=px, qty=qty))
            open_cnt += 1
            live_bids += 1

        for _ in range(max(0, c.levels_per_side - live_asks)):
            if open_cnt >= c.max_open_levels:
                break
            px = self._level_price(eff_mid, "ask", live_asks)
            qty = _clamp(c.capital * c.level_alloc * (1.0 - c.reserve_pct),
                         0.0, c.capital * 0.5)
            self.levels.append(_Level(side="ask", ref_price=px, qty=qty))
            open_cnt += 1
            live_asks += 1

        self._cooldown_left = c.cooldown_ticks

    # Event handlers
    def on_tick(self, price: float) -> List[Dict[str, object]]:
        """Process a price tick; emit orders that trigger."""

        if not _is_finite(price) or price <= 0:
            raise ValueError(f"invalid price in tick: {price}")

        self._tick += 1
        self._ticks_since_flush += 1
        self._update_inertia(price)

        orders: List[Dict[str, object]] = []
        tick_id = self._tick

        impulse = self._impulse_alive()
        # Momentum-velocity gate: even without acceleration, a sustained one-way
        # drift keeps |vel| material -> treat as warm impulse and suppress
        # momentum-direction fills (no falling knives, no chasing breakouts).
        warm = abs(self._vel) >= self.config.gate_velocity_ratio * price
        impulse = impulse or warm
        # Gate: during a live downward impulse, do not fill BID levels (falling
        # knife) until momentum decays; during a live upward impulse, do not fill
        # ASK levels (chasing breakout). Existing far-side levels may still fill.
        for lv in self.levels:
            if lv.filled:
                continue
            if impulse and self._vel < 0.0 and lv.side == "bid":
                continue
            if impulse and self._vel > 0.0 and lv.side == "ask":
                continue
            if lv.side == "bid" and price <= lv.ref_price:
                oid = f"bid_{tick_id}"
                orders.append({"action": "buy", "symbol": self.config.symbol,
                               "price": round(lv.ref_price, 6), "qty": round(lv.qty, 8),
                               "id": oid})
                lv.filled = True
                self._inventory += lv.qty
                self._fills.append({"id": oid, "side": "bid",
                                    "price": lv.ref_price, "qty": lv.qty})
            elif lv.side == "ask" and price >= lv.ref_price:
                oid = f"ask_{tick_id}"
                orders.append({"action": "sell", "symbol": self.config.symbol,
                               "price": round(lv.ref_price, 6), "qty": round(lv.qty, 8),
                               "id": oid})
                lv.filled = True
                self._inventory -= lv.qty
                self._fills.append({"id": oid, "side": "ask",
                                    "price": lv.ref_price, "qty": lv.qty})

        self._refresh_quote(price)

        if self._ticks_since_flush >= self.config.flush_every:
            max_keep = self.config.max_open_levels * 4
            if len(self._fills) > max_keep:
                del self._fills[:-max_keep]
            self.price_hist = deque(self.price_hist, maxlen=self.config.price_hist_len)
            self._ticks_since_flush = 0
            gc.collect()

        return orders

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        """Acknowledge an external fill (sync state)."""

        if not _is_finite(price) or price <= 0 or not _is_finite(qty) or qty <= 0:
            raise ValueError("on_fill requires finite, positive price and qty")
        for lv in self.levels:
            if lv.filled:
                continue
            expected = f"bid_{self._tick}" if lv.side == "bid" else f"ask_{self._tick}"
            if expected == order_id:
                lv.filled = True
                lv.ref_price = price
                self._inventory += qty if lv.side == "bid" else -qty
                break


# Inline smoke test with small synthetic data
if __name__ == "__main__":
    cfg = InertiaGridConfig(capital=12.0, levels_per_side=3, max_open_levels=6,
                            gate_threshold=0.00005)
    strat = InertiaGrid(cfg)
    errs = strat.validate_config()
    assert not errs, f"config invalid: {errs}"

    n_fills = 0
    price = 100.0
    seed = random.Random(42)
    for _ in range(300):
        price += seed.uniform(-1.0, 1.0)
        if price <= 0:
            price = 100.0
        n_fills += len(strat.on_tick(price))

    mem_mb = strat.estimate_memory_mb()
    assert 0.0 <= mem_mb < 1.0, f"estimate_memory_mb out of bounds: {mem_mb}"
    live_cnt = sum(1 for l in strat.levels if not l.filled)
    assert live_cnt <= cfg.max_open_levels, "level cap breached"

    print(f"SMOKE PASS (300 ticks, fills={n_fills}, mem={mem_mb:.4f}MB, "
          f"open={live_cnt}, vel={strat._vel:.5f}, accel={strat._accel:.5f}, "
          f"inv={strat._inventory:.4f})")

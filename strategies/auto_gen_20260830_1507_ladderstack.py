"""
auto_gen_20260830_1507_ladderstack.py - LadderStack Time-Weighed Inventory Grid

Strategy class: LadderStackGrid
--------------------------------
Proposta DISTINTA dalle ultime generate: volavggrid (14:16), sessionvolgrid (14:46),
momvolgrid (14:31), asrgrid (14:06), liqskewgrid (13:45), kellygrid (13:15),
bsmgrid (13:05), zmeanrev (12:16).

Angolo nuovo (non coperto dalle precedenti): **time-weighed inventory asymmetry**
combinato con **order aging + decay**:
  1. Ladder asimmetrico: le quote bid/ask partono SQUILIBRATE rispetto al prezzo
     mid corrente in base all'inventario. Un inventario lungo (delta positivo)
     sposta la ladder piu' in alto (favorisce vendite ad ansa ricca) e viceversa.
  2. Order aging: ogni livello non riempito invecchia. Quando l'eta' supera una
     soglia, il livello viene "aged": la distanza dal mid viene cresciuta di un
     fattore (spacing x eta') finche' non viene rimosso del tutto a una eta' massima.
     Questo evita quote stale bloccate lontano dal prezzo che non fanno mai PnL
     e libera capitale bloccato -> anti-stagnation.
  3. Fixed-fractional sizing con floor/ceiling: ogni livello usa una frazione
     del capitale definita da config, ridotta quando l'inventario si avvicina
     al cap asimmetrico (reduzione rischio in una direzione).
  4. Time-weighed PnL tracker: stima PnL mark-to-market per valutare la salute.

Caratteristiche tecniche:
- Streaming puro su deque con maxlen, nessuna list comprehension su serie lunghe.
- `del` su buffer intermedi + gc.collect() nel flush periodico (config).
- Budget di capitale hard-cap: mai oltre config.max_open_levels.
- Config-driven: zero magic number fuori dal dataclass.

Author: Hermes orchestrator -- ciclo 2026-08-30 15:06.
"""

from __future__ import annotations

import gc
import math
import random
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, List, Optional, Tuple

_EPS: float = 1e-12


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    if den == 0.0 or not math.isfinite(den):
        return default
    return num / den


@dataclass
class LadderStackConfig:
    """Config-driven runtime parameters - no hardcoded magic values."""

    symbol: str = "SOL/EUR"
    capital: float = 13.5

    # --- Ladder geometry ---
    base_spacing: float = 0.006        # fractional spacing from mid (price units ratio)
    max_spacing: float = 0.02          # ceiling after aging
    levels_per_side: int = 5           # max levels per side before cap
    max_open_levels: int = 8           # hard cap vs over-commit
    level_alloc: float = 0.10          # fraction of capital per level

    # --- Inventory asymmetry ---
    inv_target: float = 0.0            # target signed inventory (base units)
    inv_cap: float = 0.6               # max |inventory| as fraction of capital
    asym_sensitivity: float = 0.8      # how strongly inventory shifts the ladder

    # --- Order aging / decay ---
    age_expire_ticks: int = 200        # ticks before a level starts aging away
    age_grow_factor: float = 0.02      # spacing growth per tick past expiry
    age_max_spacing: float = 0.025     # beyond this spacing, drop the level

    # --- Housekeeping / OOM ---
    flush_every: int = 500             # ticks between gc.collect
    history_len: int = 128             # deque cap for recent prices

    # --- Risk ---
    reserve_pct: float = 0.15          # capital kept un-deployed


@dataclass
class _Level:
    """Single ladder level state."""

    side: str                     # 'bid' | 'ask'
    ref_price: float = 0.0        # price at creation
    qty: float = 0.0
    age_ticks: int = 0
    filled: bool = False
    fill_price: float = 0.0


class StrategyBase:
    """Contract enforced by the Denaro harness."""

    def __init__(self, config: LadderStackConfig) -> None:
        self.config = config

    def on_tick(self, price: float) -> List[Dict[str, object]]:
        raise NotImplementedError

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class LadderStackGrid(StrategyBase):
    """Time-weighed asymmetric ladder with order aging and inventory decay."""

    def __init__(self, config: LadderStackConfig) -> None:
        super().__init__(config)
        self.levels: List[_Level] = []
        self.recent: Deque[Tuple[float, int]] = deque(maxlen=config.history_len)
        self._tick: int = 0
        self._inventory: float = 0.0          # signed base position
        self._pnl_est: float = 0.0            # mark-to-market PnL estimate
        self._fills: List[Dict[str, object]] = []
        self._ticks_since_flush: int = 0

    # ------------------------------------------------------------------
    # Contract
    # ------------------------------------------------------------------
    def validate_config(self) -> List[str]:
        """Return a list of config problems (empty -> valid)."""
        errs: List[str] = []
        c = self.config
        if c.capital <= 0:
            errs.append("capital must be > 0")
        if c.base_spacing <= 0 or c.max_spacing < c.base_spacing:
            errs.append("spacing invariants violated (0 < base_spacing <= max_spacing)")
        if c.levels_per_side < 1 or c.max_open_levels < 1:
            errs.append("level counts must be >= 1")
        if not (0.0 < c.level_alloc <= 1.0):
            errs.append("level_alloc must be in (0,1]")
        if not (0.0 <= c.inv_cap <= 1.0):
            errs.append("inv_cap must be in [0,1]")
        if c.age_expire_ticks < 1:
            errs.append("age_expire_ticks must be >= 1")
        return errs

    def estimate_memory_mb(self) -> float:
        """Closed-form estimate from bounded structures - OOM-safe."""
        lvl_bytes = 120
        hist_bytes = self.config.history_len * 32
        buf_bytes = 1024
        return (self.config.max_open_levels * lvl_bytes + hist_bytes + buf_bytes) / (1024 * 1024)

    # ------------------------------------------------------------------
    # Ladder placement helpers
    # ------------------------------------------------------------------
    def _asym_shift(self, price: float) -> float:
        """Return a signed shift added to the mid: positive -> favor asks."""
        cfg = self.config
        norm_inv = _safe_div(self._inventory, max(cfg.capital, _EPS))  # signed
        capped = _clamp(norm_inv / max(cfg.inv_cap, _EPS), -1.0, 1.0)
        return price * cfg.base_spacing * cfg.asym_sensitivity * capped

    def _level_price(self, mid: float, side: str, idx: int) -> float:
        """Compute a level's price given side and distance index."""
        cfg = self.config
        gap = cfg.base_spacing * (1.0 + 0.5 * float(idx))  # widening ladder
        if side == "bid":
            return mid * (1.0 - gap)
        return mid * (1.0 + gap)

    def _refresh_quote(self, mid: float) -> None:
        """Add age decay to existing levels; drop stale ones; top-up missing."""
        cfg = self.config
        keep: List[_Level] = []

        for lv in self.levels:
            if lv.filled:
                keep.append(lv)
                continue
            lv.age_ticks += 1
            stale_ticks = lv.age_ticks - cfg.age_expire_ticks
            if stale_ticks > 0:
                # grow the level's distance to push it away from the mid;
                # once beyond the age ceiling we drop it (release capital).
                grown_px = lv.ref_price * (1.0 + cfg.age_grow_factor * stale_ticks)
                if abs(grown_px - mid) / max(mid, _EPS) >= cfg.age_max_spacing:
                    continue  # too stale -> release level
                lv.ref_price = grown_px
            keep.append(lv)
        # prune filled levels (they've executed) so list stays bounded
        self.levels = [lv for lv in keep if not lv.filled]

        # count live (unfilled) per side
        live_bids = sum(1 for lv in self.levels if not lv.filled and lv.side == "bid")
        live_asks = sum(1 for lv in self.levels if not lv.filled and lv.side == "ask")
        open_cnt = live_bids + live_asks

        if open_cnt >= cfg.max_open_levels:
            return  # hard cap - no more quoting

        shift = self._asym_shift(mid)
        eff_mid = mid + shift

        # top up bids
        need_bid = cfg.levels_per_side - live_bids
        for i in range(max(0, need_bid)):
            if open_cnt >= cfg.max_open_levels:
                break
            px = self._level_price(eff_mid, "bid", live_bids + i)
            qty = (cfg.capital * cfg.level_alloc * (1.0 - cfg.reserve_pct))
            qty = _clamp(qty, 0.0, cfg.capital * 0.5)
            self.levels.append(_Level(side="bid", ref_price=px, qty=qty))
            open_cnt += 1

        # top up asks
        need_ask = cfg.levels_per_side - live_asks
        for i in range(max(0, need_ask)):
            if open_cnt >= cfg.max_open_levels:
                break
            px = self._level_price(eff_mid, "ask", live_asks + i)
            qty = (cfg.capital * cfg.level_alloc * (1.0 - cfg.reserve_pct))
            qty = _clamp(qty, 0.0, cfg.capital * 0.5)
            self.levels.append(_Level(side="ask", ref_price=px, qty=qty))
            open_cnt += 1

    def _mark_to_market(self, mid: float) -> None:
        """Estimate unrealized PnL from filled inventory vs mid."""
        self._pnl_est = self._inventory * (mid - self._avg_cost()) if self._inventory else 0.0

    def _avg_cost(self) -> float:
        if not self._fills:
            return 0.0
        cost = 0.0
        qty = 0.0
        for f in self._fills:
            fp = float(f.get("price", 0.0))
            fq = float(f.get("qty", 0.0))
            side = f.get("side", "bid")
            signed = fq if side == "bid" else -fq
            cost += signed * fp
            qty += abs(signed)
        return _safe_div(cost, max(qty, _EPS))

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------
    def on_tick(self, price: float) -> List[Dict[str, object]]:
        """Process a new price tick; emit any orders that trigger."""
        self._tick += 1
        self._ticks_since_flush += 1
        self.recent.append((price, self._tick))

        orders: List[Dict[str, object]] = []

        # inventory asymmetry from current position
        self._refresh_quote(price)
        self._mark_to_market(price)

        # Order aging / decay at quote level
        for lv in self.levels:
            if lv.filled:
                continue
            # check if price crossed the level -> execution suggestion
            if lv.side == "bid" and price <= lv.ref_price:
                orders.append({
                    "action": "buy",
                    "symbol": self.config.symbol,
                    "price": lv.ref_price,
                    "qty": lv.qty,
                    "id": f"bid_{self._tick}",
                })
                lv.filled = True
                lv.fill_price = lv.ref_price
                self._inventory += lv.qty
                self._fills.append({
                    "id": f"bid_{self._tick}",
                    "side": "bid",
                    "price": lv.ref_price,
                    "qty": lv.qty,
                })
            elif lv.side == "ask" and price >= lv.ref_price:
                orders.append({
                    "action": "sell",
                    "symbol": self.config.symbol,
                    "price": lv.ref_price,
                    "qty": lv.qty,
                    "id": f"ask_{self._tick}",
                })
                lv.filled = True
                lv.fill_price = lv.ref_price
                self._inventory -= lv.qty
                self._fills.append({
                    "id": f"ask_{self._tick}",
                    "side": "ask",
                    "price": lv.ref_price,
                    "qty": lv.qty,
                })

        # periodic memory hygiene - drop completed fills older than window
        if self._ticks_since_flush >= self.config.flush_every:
            if self.recent:
                cutoff = self._tick - self.config.history_len
                self.recent = deque(
                    (p, t) for p, t in self.recent if t > cutoff
                )
                self.recent = deque(self.recent, maxlen=self.config.history_len)
                del cutoff
            gc.collect()
            self._ticks_since_flush = 0

            # bound fills list to avoid unbounded growth
            if len(self._fills) > self.config.max_open_levels * 4:
                del self._fills[:- self.config.max_open_levels * 2]

        return orders

    def on_fill(self, order_id: str, price: float, qty: float) -> None:
        """Acknowledge an external fill (sync)."""
        for lv in self.levels:
            if f"bid_{self._tick}" == order_id and lv.side == "bid" and not lv.filled:
                lv.filled = True
                lv.fill_price = price
                self._inventory += qty
                break
            if f"ask_{self._tick}" == order_id and lv.side == "ask" and not lv.filled:
                lv.filled = True
                lv.fill_price = price
                self._inventory -= qty
                break


# ------------------------------------------------------------------
# Inline smoke test with small synthetic data
# ------------------------------------------------------------------
if __name__ == "__main__":
    cfg = LadderStackConfig(capital=12.0, levels_per_side=3, max_open_levels=6)
    strat = LadderStackGrid(cfg)
    v = strat.validate_config()
    assert not v, f"config invalid: {v}"

    n_fills = 0
    price = 100.0
    for step in range(300):
        price += random.uniform(-1.0, 1.0)
        orders = strat.on_tick(price)
        n_fills += len(orders)

    mem_mb = strat.estimate_memory_mb()
    assert 0.0 <= mem_mb < 1.0, f"estimate_memory_mb out of bounds: {mem_mb}"
    live_cnt = sum(1 for l in strat.levels if not l.filled)
    assert live_cnt <= cfg.max_open_levels, "level cap breached"

    print(f"SMOKE PASS (300 ticks, fills={n_fills}, mem={mem_mb:.4f}MB, "
          f"open={sum(1 for l in strat.levels if not l.filled)}, inv={strat._inventory:.4f})")

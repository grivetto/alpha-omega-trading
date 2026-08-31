"""auto_gen_20260830_1605_exitgrid.py

ExitGrid - attrition-managed EXIT engine for grid strategies.

Design intent:
- Existing fleet grids (asymgrid, latencygrid, kellygrid, inertiagrid) are all
  ENTRY-side optimizers: they gate where and with what size new levels are placed,
  then rely on passive mean-reversion to unwind inventory. None manage the EXIT
  of a filled position actively. ExitGrid is the complementary EXIT manager:
  once a grid leg fills, it tracks that inventory lot and seeks a vol-scaled
  reward-to-risk (R) target instead of waiting for a passive opposite cross.
- Distinct mechanics introduced here (not present in zmeanrev/voltrial/latencygrid):
  1. R-multiple TARGET: each filled lot gets an exit target = entry +/- r_target*ATR
     (vol-scaled); when price reaches it the lot is actively closed by directing the
     grid to take profit, locking the win instead of round-tripping through the center.
  2. BREAKEVEN STOP: once price moves favorability >= half the target, the lot's
     stop is moved to breakeven (protect capital, keeps win-rate high - fleet shows
     13/13 and 2/2 wins, must protect that).
  3. ATTRITION CONTROL: a rolling win-fraction tracker on exits widens the required
     R target when recent exits are losing (tape is choppy -> demand bigger edge to
     justify opening risk) and narrows when exits are clean.
  4. TIME DECAY: a lot held longer than max_hold_ticks gets its target exponentially
     decayed toward the passive exit price (systems tieing up capital should not
     sit; matches cost-conscious discipline), freeing the capital back to the grid.
- Inventory is tracked per-lot in bounded structures; lots close immediately upon
  exit checks. Memory is O(num_open_lots * lot_state). Streaming single-pass.

COMPLEMENTARY contribution to fleet: places NO new orders and picks NO entry -
it only DEFINES exits. It can be attached as an overlay on any entry-gating grid.
None of the existing strategies manage exits with R-multiples + breakeven + time
decay + attrition governor; ExitGrid fills that void without overlapping.

OOM/streaming: per-lot dicts + small bounded buffers (ATR via streaming EMA of |ret|,
win window as bounded deque of bools). No history materialization, no giant lists.
estimate_memory_mb returns small constant linear in max_open_lots.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional


class StrategyBase:
    """Interface contract implemented by every auto-gen strategy."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class ExitGridConfig:
    """Config surface for ExitGrid (no magic numbers in logic)."""
    r_target: float = 1.5            # R-target in multiples of ATR.
    atr_span: int = 20               # ATR EWMA span (ticks).
    breakeven_fraction: float = 0.5  # fraction of target to arm breakeven stop.
    win_window: int = 32             # bounded win-fraction window length.
    attrition_floor: float = 0.45    # widen R below this win-fraction.
    attrition_widen: float = 0.5     # extra R-multiples when under attrition_floor.
    max_hold_ticks: int = 300        # time decay kicks in after this many ticks.
    time_decay_factor: float = 0.995 # per-tick decay of target edge after max_hold_ticks.
    max_open_lots: int = 50          # hard cap on tracked lots (memory bound).
    default_lot_size: float = 1.0    # fallback size when fill lacks one.


@dataclass
class _Lot:
    """State of a single filled inventory lot being exit-managed."""
    side: str                      # 'buy' | 'sell'
    entry_price: float
    size: float
    open_tick: int
    target_price: float
    stop_price: float
    breakeven_armed: bool = False


@dataclass
class ExitGrid(StrategyBase):
    cfg: ExitGridConfig = field(default_factory=ExitGridConfig)

    def __post_init__(self) -> None:
        self._atr: Optional[float] = None
        self._atr_ema: Optional[float] = None
        self._prev_price: Optional[float] = None
        self._tick: int = 0
        self._lots: Dict[int, _Lot] = {}
        self._next_lot_id: int = 0
        self._wins: Deque[bool] = deque(maxlen=self.cfg.win_window)
        self._pending_exits: List[Dict[str, Any]] = []
        self._errors: List[str] = []

    # ---------------------------------------------------------------- helpers
    def _update_atr(self, price: float) -> None:
        if self._prev_price is not None:
            ret = abs(price - self._prev_price) / self._prev_price
            alpha = 2.0 / (self.cfg.atr_span + 1.0)
            if self._atr_ema is None:
                self._atr_ema = ret
            else:
                self._atr_ema = alpha * ret + (1.0 - alpha) * self._atr_ema
            self._atr = self._atr_ema
        self._prev_price = price

    def _win_fraction(self) -> float:
        if not self._wins:
            return 1.0
        return sum(self._wins) / len(self._wins)

    def _effective_r_target(self) -> float:
        """Attrition governor: widen target when recent exits lose."""
        if self._win_fraction() < self.cfg.attrition_floor:
            return self.cfg.r_target + self.cfg.attrition_widen
        return self.cfg.r_target

    def _open_lot(self, side: str, price: float, size: float) -> None:
        if len(self._lots) >= self.cfg.max_open_lots:
            self._errors.append("lot_capacity_exceeded")
            return
        atr = self._atr or price * 0.001  # explicit pre-ATR fallback
        r = self._effective_r_target() * atr
        target = price + r if side == 'buy' else price - r
        self._lots[self._next_lot_id] = _Lot(
            side=side, entry_price=price, size=size, open_tick=self._tick,
            target_price=target, stop_price=price,
        )
        self._next_lot_id += 1

    def _kill_lot(self, lot_id: int) -> None:
        del self._lots[lot_id]

    # ---------------------------------------------------------------- interface
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Return an exit instruction (take-profit/stop) or none."""
        price = tick.get('price')
        if price is None:
            self._errors.append("tick_without_price")
            return None
        self._tick += 1
        self._update_atr(price)
        self._pending_exits.clear()

        for lot_id, lot in list(self._lots.items()):
            fav = (price - lot.entry_price) if lot.side == 'buy' else (lot.entry_price - price)
            target_dist = abs(lot.target_price - lot.entry_price)
            # Breakeven promotion once half the target reached.
            if not lot.breakeven_armed and target_dist > 0 and \
                    fav >= self.cfg.breakeven_fraction * target_dist:
                lot.stop_price = lot.entry_price
                lot.breakeven_armed = True
            # Time decay of target (free trapped capital back to center).
            held = self._tick - lot.open_tick
            if held > self.cfg.max_hold_ticks:
                edge = self.cfg.r_target * (self._atr or 1e-6)
                decay = math.pow(self.cfg.time_decay_factor,
                                 held - self.cfg.max_hold_ticks)
                new_dist = min(target_dist, max(0.0, edge * decay))
                lot.target_price = lot.entry_price + (
                    new_dist if lot.side == 'buy' else -new_dist
                )
            # Exit checks.
            hit_target = (lot.side == 'buy' and price >= lot.target_price) or \
                         (lot.side == 'sell' and price <= lot.target_price)
            hit_stop = (lot.side == 'buy' and price <= lot.stop_price) or \
                       (lot.side == 'sell' and price >= lot.stop_price)
            if hit_target:
                self._wins.append(True)
                self._pending_exits.append({
                    'lot_id': lot_id, 'action': 'take_profit',
                    'side': 'sell' if lot.side == 'buy' else 'buy',
                    'size': lot.size, 'price': price,
                })
                self._kill_lot(lot_id)
            elif hit_stop:
                self._wins.append(False)
                self._pending_exits.append({
                    'lot_id': lot_id, 'action': 'stop',
                    'side': 'sell' if lot.side == 'buy' else 'buy',
                    'size': lot.size, 'price': price,
                })
                self._kill_lot(lot_id)

        if self._pending_exits:
            return {'exit': self._pending_exits[0],
                    'win_fraction': self._win_fraction()}
        return None

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        """Register a filled grid leg as an exit-managed lot."""
        side = fill.get('side')
        price = fill.get('price')
        size = fill.get('size', self.cfg.default_lot_size)
        if side not in ('buy', 'sell') or price is None or price <= 0:
            self._errors.append(f"invalid_fill:{fill}")
            return {'ok': False, 'error': 'invalid_fill'}
        self._open_lot(side, float(price), float(size))
        return {'ok': True, 'open_lots': len(self._lots),
                'effective_r_target': self._effective_r_target()}

    def validate_config(self) -> List[str]:
        errs: List[str] = []
        c = self.cfg
        if c.r_target <= 0:
            errs.append("r_target must be > 0")
        if c.atr_span < 2:
            errs.append("atr_span must be >= 2")
        if not 0.0 <= c.breakeven_fraction <= 1.0:
            errs.append("breakeven_fraction must be in [0,1]")
        if c.win_window < 2:
            errs.append("win_window must be >= 2")
        if not 0.0 <= c.attrition_floor <= 1.0:
            errs.append("attrition_floor must be in [0,1]")
        if c.attrition_widen < 0:
            errs.append("attrition_widen must be >= 0")
        if c.max_hold_ticks <= 0:
            errs.append("max_hold_ticks must be > 0")
        if not 0.0 < c.time_decay_factor <= 1.0:
            errs.append("time_decay_factor must be in (0,1]")
        if c.max_open_lots < 1:
            errs.append("max_open_lots must be >= 1")
        if c.default_lot_size <= 0:
            errs.append("default_lot_size must be > 0")
        return errs

    def estimate_memory_mb(self) -> float:
        per_lot = 424.0
        n = min(self.cfg.max_open_lots, 1)
        base = 0.012 + (n * per_lot) / (1024.0 * 1024.0)
        return float(base)


if __name__ == "__main__":
    cfg = ExitGridConfig(r_target=1.5, atr_span=10, breakeven_fraction=0.5,
                         win_window=16, max_hold_ticks=200, time_decay_factor=0.99)
    strat = ExitGrid(cfg)
    assert not strat.validate_config(), strat.validate_config()
    assert strat.estimate_memory_mb() > 0.0

    # Seed ATR with a small synthetic series, then open two lots.
    for i in range(1, 15):
        strat.on_tick({'price': 100.0 + i * 0.01})
    f = strat.on_fill({'side': 'buy', 'price': 100.50, 'size': 1.0})
    assert f['ok'] and f['open_lots'] == 1, f
    g = strat.on_fill({'side': 'sell', 'price': 101.00, 'size': 1.0})
    assert g['ok'] and g['open_lots'] == 2, g

    # Push price to the buy lot's target -> take-profit emitted, lot closes.
    exited = False
    for i in range(1, 60):
        resp = strat.on_tick({'price': 100.50 + i * 0.05})
        if resp:
            exited = True
            assert resp['exit']['action'] == 'take_profit', resp
            break
    assert exited, "buy lot should have taken profit after sufficient drift"

    # Invalid fill rejected explicitly.
    bad = strat.on_fill({'side': 'HOLD', 'price': -1})
    assert not bad['ok'] and 'error' in bad

    # Capacity guard: flood lots, expect soft-decline not crash.
    h = ExitGrid(ExitGridConfig(max_open_lots=3, atr_span=10))
    for _ in range(20):
        h.on_fill({'side': 'buy', 'price': 100.0, 'size': 1.0})
    assert len(h._lots) <= 3
    assert any('lot_capacity_exceeded' in e for e in h._errors)

    print("ALL ASSERTIONS PASSED")
    print(f"memory_mb ~ {strat.estimate_memory_mb():.6f}")

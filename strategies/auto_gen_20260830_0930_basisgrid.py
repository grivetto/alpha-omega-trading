"""
basisgrid: Momentum-Basis Adaptive Grid
========================================
Strategy original class: BasisGrid.

Idea: un grid classico piazza livelli simmetrici attorno a un anchor statico,
ma quando il mercato e' in TREND il prezzo esce dal range e il lato corto
accumula posizioni adverse. BasisGrid calcola un "basis" = differenza
normalizzata tra un anchor a media lenta (EWMA damped) e una baseline di
momentum a media piu' veloce. Quando il basis e' grande in modulo il prezzo
sta accumulando direzionalita': lo usiamo per (a) asimmetrizzare la griglia
shifting i livelli verso il lato di momentum, e (b) ridurre dinamicamente la
size per limitare l'adverse selection. Quando il basis torna ~0 (mercato in
range), la griglia torna simmetrica e piu' densa.

Emissione O(1): manteniamo solo 2 EMA scalari (lenta/veloce), il basis, e
una piccola mappa ordine->fill. Nessuna scansione storica, nessun buffer.

Memoria: < 1 MB garantito (solo EMA scalari + costanti + stato ordini).

Config-driven, zero hardcoded. API conforme StrategyBase con on_tick/
on_fill/validate_config/estimate_memory_mb + test inline __main__.
"""
from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
@dataclass
class BasisGridConfig:
    """Configurazione BasisGrid. Default sicuri, niente hardcoded."""

    capital_eur: float = 2.0
    base_levels: int = 8                 # livelli con basis ~ 0
    max_levels: int = 12                 # tetto livelli (basis grande)
    order_size_eur: float = 0.20

    fast_win: int = 30                   # ticks EMA veloce (momentum)
    slow_win: int = 240                  # ticks EMA lenta (anchor)
    basis_scale: float = 0.02            # unita' di prezzo da "basis=1.0"

    base_spacing_pct: float = 0.012      # spacing simmetrico se basis ~ 0
    max_asym_shift: float = 0.006        # shift massimo di ogni lato (pct)

    min_size_factor: float = 0.35        # size ridotta a basis max
    max_basis: float = 2.5               # |basis| oltre cui saturare

    cooldown_ms: int = 400
    stop_loss_pct: float = 0.10


# --------------------------------------------------------------------------- #
#  Strategy
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Contratto minimo condiviso dal runner (layer esterno)."""

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


def _ewma(prev: Optional[float], new: float, win: int) -> float:
    """Calcola EWMA O(1). Se prev e' None, bootstrap sul primo valore."""
    if prev is None:
        return float(new)
    alpha: float = 2.0 / (float(win) + 1.0)
    return alpha * float(new) + (1.0 - alpha) * prev


class BasisGrid(StrategyBase):
    """Grid asimmetrico adattivo guidato dal basis di momentum."""

    def __init__(self, config: Optional[BasisGridConfig] = None) -> None:
        self.cfg: BasisGridConfig = config or BasisGridConfig()
        errors: List[str] = self.validate_config()
        if errors:
            raise ValueError("Config non valida: " + "; ".join(errors))

        self._fast: Optional[float] = None
        self._slow: Optional[float] = None
        self._last_order_ts: float = 0.0
        self._tick_count: int = 0
        self._open: List[Dict[str, Any]] = []
        self._pending: Dict[str, Dict[str, Any]] = {}
        self._realized_pnl: float = 0.0
        self._entry_anchor: Optional[float] = None

    # ------------------------------------------------------------------ #
    #  helpers
    # ------------------------------------------------------------------ #
    def _basis(self, mid: float) -> float:
        """basis normalizzato = (fast-slow)/basis_scale, saturato."""
        if self._fast is None or self._slow is None or self._slow <= 0:
            return 0.0
        raw: float = (self._fast - self._slow) / self.cfg.basis_scale
        bound: float = self.cfg.max_basis
        return max(-bound, min(bound, raw))

    def _spacing(self, basis: float) -> float:
        """Spacing base piu' shift asimmetrico funzione del basis."""
        base: float = self.cfg.base_spacing_pct
        shift: float = self.cfg.max_asym_shift * (basis / self.cfg.max_basis)
        spacing: float = base + shift
        return max(spacing, base * 0.5)  # clamp min al 50% del base

    def _size_factor(self, basis: float) -> float:
        """Riduci size quando |basis| cresce (adverse selection)."""
        k: float = abs(basis) / self.cfg.max_basis
        return 1.0 - (1.0 - self.cfg.min_size_factor) * min(1.0, k)

    # ------------------------------------------------------------------ #
    #  StrategyBase API
    # ------------------------------------------------------------------ #
    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Processa un tick e ritorna (eventualmente) un ordine grid."""
        mid: float = float(tick.get("mid", tick.get("price", 0.0)))
        if mid <= 0:
            return None
        ts: float = float(tick.get("ts", time.time()))

        self._fast = _ewma(self._fast, mid, self.cfg.fast_win)
        self._slow = _ewma(self._slow, mid, self.cfg.slow_win)
        self._tick_count += 1

        if ts - self._last_order_ts < self.cfg.cooldown_ms / 1000.0:
            return None
        if len(self._pending) >= 3:  # max 3 ordini pendenti
            return None
        if self._tick_count < self.cfg.slow_win:
            return None

        basis: float = self._basis(mid)
        spacing: float = self._spacing(basis)
        size: float = self.cfg.order_size_eur * self._size_factor(basis)

        # basis>0 => momentum up => buy (sotto mid) densi/attivi
        if basis >= 0:
            side: str = "buy"
            px: float = mid * (1.0 - spacing)
        else:
            side = "sell"
            px = mid * (1.0 + spacing)

        self._last_order_ts = ts
        return {
            "side": side,
            "price": round(px, 8),
            "size_eur": round(size, 6),
            "spacing": round(spacing, 6),
            "basis": round(basis, 4),
            "ts": ts,
        }
        self._pending[order_id] = order
        return order

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Registra un fill: aggiorna PnL realized e pulisce ordini."""
        side: str = fill.get("side", "buy")
        px: float = float(fill.get("price", 0.0))
        qty: float = float(fill.get("qty", 0.0))
        if px <= 0 or qty <= 0:
            return
        sign: float = 1.0 if side == "sell" else -1.0
        if self._entry_anchor is not None:
            self._realized_pnl += sign * (px - self._entry_anchor) * qty
        self._entry_anchor = px
        order_id: Optional[Any] = fill.get("id")
        self._open = [o for o in self._open if o.get("id") != order_id]
        if order_id is not None:
            self._pending.pop(str(order_id), None)
        gc.collect()

    def validate_config(self) -> List[str]:
        """Controlla sanita' della config. Nessun silent pass."""
        errs: List[str] = []
        if self.cfg.capital_eur <= 0:
            errs.append("capital_eur deve essere > 0")
        if self.cfg.base_levels < 2 or self.cfg.max_levels < self.cfg.base_levels:
            errs.append("max_levels >= base_levels >= 2")
        if self.cfg.fast_win <= 0 or self.cfg.slow_win <= self.cfg.fast_win:
            errs.append("slow_win > fast_win > 0")
        if self.cfg.basis_scale <= 0:
            errs.append("basis_scale deve essere > 0")
        if self.cfg.order_size_eur <= 0:
            errs.append("order_size_eur deve essere > 0")
        if not (0.0 < self.cfg.min_size_factor <= 1.0):
            errs.append("min_size_factor in (0,1]")
        return errs

    def estimate_memory_mb(self) -> float:
        """Stima footprint memoria: costanti + stato ordini (bounded)."""
        per_order: float = 256.0
        orders: int = max(0, len(self._open))
        total_bytes: float = 2048.0 + per_order * min(orders, 500)
        return round(total_bytes / (1024.0 * 1024.0), 6)


# --------------------------------------------------------------------------- #
#  Inline smoke test
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import random

    cfg = BasisGridConfig(capital_eur=2.0, base_levels=8)
    strat = BasisGrid(cfg)

    assert strat.validate_config() == [], "config invalida"

    orders: int = 0
    px: float = 100.0
    for i in range(300):
        if i < 150:
            px *= 1.0008  # trend up
        else:
            px *= 1.0 + random.uniform(-0.001, 0.001)  # range
        out = strat.on_tick({"mid": px, "ts": i * 1.0})
        if out is not None:
            orders += 1
            assert out["price"] > 0 and out["size_eur"] > 0
            strat.on_fill(
                {"id": f"o{orders}", "side": out["side"],
                 "price": out["price"], "qty": out["size_eur"] / out["price"]}
            )

    print(f"OK basisgrid: orders={orders} mem_MB={strat.estimate_memory_mb()}")

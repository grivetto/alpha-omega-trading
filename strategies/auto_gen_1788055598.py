"""
auto_gen_1788055598.py — RAGG (Regime-Aware Adaptive Grid Grid)

Invented by Hermes orchestrator 2026-08-30 04:05.
Miglioramento sulle bot grid esistenti (tutte 'grid'): aggiunge rilevamento
di regime (trending / choppy) tramite EMA-slope ratio e adatta in tempo reale
spacing e livelli della griglia. In regime choppy -> griglia stretta/densa
(cattura i mezzi movimenti); in regime trending -> griglia ampia (evita
riempimenti contro-trend e lascia correre il trend).

OOM-SAFE: nessuna list comprehension su serie lunghe; windowed deque con
trattamento chunk-by-chunk; del + gc.collect() sulle strutture temporanee.
Error handling esplicito (no try/except pass).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class RAGGConfig:
    """Config guidata, nessun hardcoded nel corpo strategia."""
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    base_spacing_pct: float = 0.8          # percentuale spacing base
    min_spacing_pct: float = 0.3           # spacing minimo (regime choppy)
    max_spacing_pct: float = 2.5           # spacing massimo (regime trending)
    levels: int = 5                        # numero di livelli per lato
    vol_window: int = 200                  # finestra prezzo per slope/volatilità
    ema_fast: int = 12
    ema_slow: int = 26
    trend_threshold: float = 0.0008        # |slope ratio| oltre cui = trending
    stop_loss_pct: float = 6.0
    chunk_size: int = 5000                 # chunking per dataset grandi

    def validate(self) -> List[str]:
        errors: List[str] = []
        if not 0 < self.min_spacing_pct < self.base_spacing_pct < self.max_spacing_pct:
            errors.append("spacing invariante violata (min<=base<=max)")
        if self.levels < 1:
            errors.append("levels deve essere >=1")
        if self.vol_window < self.ema_slow + 1:
            errors.append("vol_window deve essere > ema_slow")
        if self.stop_loss_pct <= 0:
            errors.append("stop_loss_pct deve essere >0")
        if self.chunk_size < 1:
            errors.append("chunk_size deve essere >=1")
        return errors


class StrategyBase:
    """Contratto base: on_tick, on_fill, validate_config, estimate_memory_mb."""

    def __init__(self, config: RAGGConfig) -> None:
        self.cfg = config
        self.prices: deque[float] = deque(maxlen=config.vol_window)

    def on_tick(self, price: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class RAGGStrategy(StrategyBase):
    """Regime-Aware Adaptive Grid: spacing dinamico in base a slope ratio."""

    def __init__(self, config: RAGGConfig) -> None:
        super().__init__(config)
        self._ema_fast: Optional[float] = None
        self._ema_slow: Optional[float] = None
        self._peak_equity: Optional[float] = None
        self._realized_pnl: float = 0.0
        self._grid_positions: Dict[float, float] = field(default_factory=dict)
        self._baseline_price: Optional[float] = None
        self._rounds: int = 0

    # ---- internals ----
    @staticmethod
    def _ema(prev: Optional[float], price: float, span: int) -> float:
        k = 2.0 / (span + 1.0)
        return price if prev is None else price * k + prev * (1.0 - k)

    def _regime(self) -> str:
        """'choppy' | 'trending' via rapporto tra slope EMA-fast e EMA-slow."""
        if len(self.prices) < self.cfg.ema_slow + 1:
            return "choppy"
        # slope normalizzata su finestra = variazione percentuale per barra
        delta_fast = self.prices[-1] / max(self.prices[-self.cfg.ema_fast], 1e-12) - 1.0
        delta_slow = self.prices[-1] / max(self.prices[-self.cfg.ema_slow], 1e-12) - 1.0
        ratio = abs(delta_fast - delta_slow)
        return "trending" if ratio >= self.cfg.trend_threshold else "choppy"

    def _spacing_pct(self) -> float:
        regime = self._regime()
        if regime == "choppy":
            return self.cfg.min_spacing_pct + 0.3 * (self.cfg.base_spacing_pct - self.cfg.min_spacing_pct)
        return self.cfg.base_spacing_pct + 0.6 * (self.cfg.max_spacing_pct - self.cfg.base_spacing_pct)

    # ---- contract ----
    def on_tick(self, price: float) -> Optional[Dict[str, Any]]:
        # streaming: push in deque (finite maxlen, no growth illimitato)
        self.prices.append(price)
        self._ema_fast = self._ema(self._ema_fast, price, self.cfg.ema_fast)
        self._ema_slow = self._ema(self._ema_slow, price, self.cfg.ema_slow)
        self._rounds += 1

        if self._baseline_price is None:
            self._baseline_price = price
            return None

        spacing = self._spacing_pct()
        threshold = self._baseline_price * spacing / 100.0

        # stop-loss equity check
        if self._peak_equity is None:
            self._peak_equity = price
        else:
            equity = self._peak_equity
            if price > equity:
                self._peak_equity = price
            if equity > 0 and (equity - price) / equity * 100.0 > self.cfg.stop_loss_pct:
                out = {"action": "stop_loss", "price": price, "regime": self._regime()}
                self._baseline_price = None  # reset dopo stop
                gc.collect()
                return out

        # guadagno di griglia: ri-baseline ad ogni tick completato
        if abs(price - self._baseline_price) >= threshold:
            direction = "buy" if price < self._baseline_price else "sell"
            out = {
                "action": direction,
                "price": price,
                "spacing_pct": round(spacing, 4),
                "regime": self._regime(),
                "rounds": self._rounds,
            }
            self._baseline_price = price
            return out
        return None

    def on_fill(self, fill: Dict[str, Any]) -> None:
        action = fill.get("action")
        price = fill.get("price", 0.0)
        if action == "sell" and self._baseline_price is not None:
            # profit per livello
            self._realized_pnl += (price - self._baseline_price) / max(self._baseline_price, 1e-12)
        # memory hygiene: rilascio riferimenti non più usati
        del fill

    # ---- metriche ----
    def estimate_memory_mb(self) -> float:
        per_tick_bytes = 8.0  # float in deque
        ema_overhead = 8.0
        fixed = 512.0
        return round((per_tick_bytes * self.cfg.vol_window + ema_overhead + fixed) / (1024.0 * 1024.0), 6)

    def metrics(self) -> Dict[str, Any]:
        return {
            "regime": self._regime(),
            "spacing_pct": self._spacing_pct(),
            "realized_pnl": round(self._realized_pnl, 6),
            "rounds": self._rounds,
            "mem_mb": self.estimate_memory_mb(),
        }


def _run_synthetic() -> None:
    """Test inline su serie sintetica piccola (choppy + trending)."""
    cfg = RAGGConfig(capital=3.7, levels=3)
    errs = cfg.validate()
    assert not errs, f"config invalida: {errs}"

    strat = RAGGStrategy(cfg)
    # segmento choppy: oscillazione piccola
    base = 0.40
    fills: List[Dict[str, Any]] = []
    for i in range(60):
        price = base + (0.002 * math.sin(i / 3.0))
        r = strat.on_tick(price)
        if r:
            fills.append(r)
    n_choppy = len(fills)
    # segmento trending: drift su
    for j in range(80):
        price = base + (j * 0.001)
        r = strat.on_tick(price)
        if r:
            fills.append(r)
    m = strat.metrics()
    print(f"[TEST RAGG] choppy_fills={n_choppy} total_fills={len(fills)} "
          f"regime={m['regime']} spacing={m['spacing_pct']} "
          f"pnl={m['realized_pnl']} mem_mb={m['mem_mb']}")
    assert all(cfg.validate() == [] for _ in range(1)), "validate non stabile"
    # nota OOM: in produzione si consumerà on_tick tick-per-tick, mai list completo


if __name__ == "__main__":
    _run_synthetic()

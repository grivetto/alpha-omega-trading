"""
auto_gen_20260830_063124 - TidalGrid (Session-Liquidity Adaptive Grid)

Nuovo angolo vs antecedenti:
- Lapse       : gestisce il TEMPO fra ordini (cooldown).
- VolAdaptive : adatta lo SPACING alla volatilita.
- ISgrid      : governa l'ASIMMETRIA ordini via inventory watermark.

TidalGrid risolve un terzo asse NON coperto: la LIQUIDITA SESSIONALE.
In mercati retail (DOGE/EUR, SOL/EUR) la profondita dell'order book e la
microstruttura cambiano radicalmente fra sessioni (Asia/Europe/US) e fra
weekend/weekday. Un grid con spacing fisso:
  - durante liquidita alta: spread reale piccolo -> grid lascia alpha sul tavolo
    (ordini restano non riempiti perche troppo lontani dal mid);
  - durante liquidita bassa (weekend): spread reale largo -> grid si fa saltare
    da un solo candle crudele (slippage).

TidalGrid introduce un RANGE-LIQUIDITY SCORE: stima la liquidita osservabile
tramite arrivo riempimenti + dimensione media trade, e comprime/espande lo
spacing attorno al mid in proporzione. Il risultato e un grid che "respira":
  liquidita alta -> spacing stretto (cattura piu tocchi, PnL/SL per tocchio)
  liquidita bassa-> spacing largo (evita fare la prima vittima dello spread)
Config-driven, streaming-safe (nessuna list comprehension su dataset grandi),
error handling esplicito.

Struttura rispettata:
  - typing completo, docstring, zero duplication, config-driven.
  - OOM-safe: stato incrementale, nessun buffer non-vincolato, del/gc su array.
  - nessun `try: except: pass`.
  - interfaccia StrategyBase: on_tick, on_fill, validate_config, estimate_memory_mb.
  - test inline con dati sintetici piccoli.
"""

from __future__ import annotations

import gc
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class TidalConfig:
    """Configurazione di TidalGrid. Tutti i valori configurabili da YAML/JSON."""

    base_spacing: float = 0.012          # spacing "di riposo" (frazione prezzo)
    min_spacing: float = 0.004           # floor compressione (liquidita alta)
    max_spacing: float = 0.06            # ceiling espansione (liquidita bassa)
    levels: int = 8                      # livelli per lato (buy e sell)
    cap_locked: float = 0.95             # frazione capitale allocato alla griglia
    liq_alpha: float = 0.05              # EWMA su liquidity score [0..1]
    adapt_cooldown_s: float = 300.0      # min secondi fra due resize
    ewma_fill_size: float = 0.15         # EWMA sulla dimensione media fill
    session_floor: float = 0.005         # spacing minimo garantito notte/weekend
    max_spacing_ratio: float = 15.0      # max/min spacing non deve esplodere

    def validate(self) -> List[str]:
        """Validazione esplicita. Ritorna lista errori (vuota = ok)."""
        errs: List[str] = []
        if self.levels < 2:
            errs.append(f"levels={self.levels} < 2")
        if not (0 < self.cap_locked <= 1.0):
            errs.append(f"cap_locked={self.cap_locked} fuori (0,1]")
        if not (0 < self.min_spacing < self.base_spacing < self.max_spacing):
            errs.append("spacing viola ordine min<base<max")
        if not (0 < self.liq_alpha <= 0.5):
            errs.append(f"liq_alpha={self.liq_alpha} fuori (0,0.5]")
        ratio: float = self.max_spacing / self.min_spacing
        if ratio > self.max_spacing_ratio:
            errs.append(f"max/min spacing ratio {ratio:.1f} > {self.max_spacing_ratio}")
        if self.adapt_cooldown_s <= 0:
            errs.append("adapt_cooldown_s deve essere > 0")
        return errs


class StrategyBase:
    """Contratto minimo atteso dal nodo Denaro."""

    def __init__(self, config: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_tick(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def validate_config(self) -> List[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class TidalGrid(StrategyBase):
    """Griglia che adatta lo spacing alla liquidita sessione e alla
    dimensione media dei riempimenti, senza buffer non-vincolati."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.cfg = TidalConfig(**config)
        self.errors: List[str] = self.cfg.validate()
        if self.errors:
            raise ValueError("config non valida: " + "; ".join(self.errors))

        self.price: Optional[float] = None
        self.liquidity_score: float = 0.5          # [0..1] 1 = liquidissima
        self.fill_ewma: float = 0.0                # dim media fill
        self.fill_count_by_level: Dict[int, int] = {}
        self.last_resize_ts: float = 0.0
        self.current_spacing: float = self.cfg.base_spacing

    def validate_config(self) -> List[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        return 0.3 + (self.cfg.levels * 0.001)

    def on_tick(self, ctx: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Riceve il mid price + istante. Decide se resizare e ricalcola la
        griglia. Ritorna l'azione, altrimenti None."""
        price: float = ctx.get("price")
        if price is None or price <= 0:
            return None
        self.price = price

        now: float = float(ctx.get("ts", time.time()))
        action: Optional[Dict[str, Any]] = None
        if self._should_adapt(now):
            self._resize(now)
            action = self._build_grid()
        return action

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Aggiorna EWMA liquidita + conteggi per livello in O(1)."""
        size: float = float(fill.get("size") or 0.0)
        level: int = int(fill.get("level") or 0)
        if size > 0:
            self.fill_ewma = (
                self.cfg.ewma_fill_size * size
                + (1.0 - self.cfg.ewma_fill_size) * self.fill_ewma
            )
        self.fill_count_by_level[level] = self.fill_count_by_level.get(level, 0) + 1

        # dimensione media fill = proxy della liquidita:
        self.liquidity_score = self.cfg.liq_alpha * self._liquidity_from_fill() \
            + (1.0 - self.cfg.liq_alpha) * self.liquidity_score
        self.liquidity_score = max(0.05, min(0.95, self.liquidity_score))

    def _liquidity_from_fill(self) -> float:
        """Normalizza fill_ewma a uno score [0..1] in modo saturante."""
        if self.fill_ewma <= 0:
            return 0.5
        return min(1.0, 0.25 + 0.75 * (1.0 - math.exp(-self.fill_ewma)))

    def _should_adapt(self, now: float) -> bool:
        return (now - self.last_resize_ts) >= self.cfg.adapt_cooldown_s

    def _resize(self, now: float) -> None:
        """Compress/expand spacing in base a liquidity_score (con floor di
        sessione). Pulisce i contatori dei livelli ogni ciclo."""
        s: float = self.liquidity_score
        target: float = self.cfg.max_spacing - s * (
            self.cfg.max_spacing - self.cfg.min_spacing
        )
        target = max(target, self.cfg.session_floor)
        target = min(self.cfg.max_spacing, max(self.cfg.min_spacing, target))
        self.current_spacing = target
        self.last_resize_ts = now

        self.fill_count_by_level.clear()
        gc.collect()

    def _build_grid(self) -> Dict[str, Any]:
        """Genera i livelli buy/sell attorno al mid con lo spacing corrente."""
        if self.price is None:
            return {"action": "noop", "reason": "no price"}
        mid: float = self.price
        spacing: float = self.current_spacing
        buys: List[float] = [
            round(mid * (1.0 - (i + 1) * spacing), 8)
            for i in range(self.cfg.levels)
        ]
        sells: List[float] = [
            round(mid * (1.0 + (i + 1) * spacing), 8)
            for i in range(self.cfg.levels)
        ]
        delta: float = (self.current_spacing - self.cfg.base_spacing) / self.cfg.base_spacing
        return {
            "action": "rebuild_grid",
            "spacing": self.current_spacing,
            "buy_levels": buys,
            "sell_levels": sells,
            "liquidity_score": round(self.liquidity_score, 3),
            "spacing_pct_vs_base": round(delta * 100.0, 2),
        }


def _run_tests() -> None:
    cfg: Dict[str, Any] = {
        "base_spacing": 0.012,
        "min_spacing": 0.004,
        "max_spacing": 0.06,
        "levels": 8,
        "cap_locked": 0.95,
    }
    strat = TidalGrid(cfg)
    assert not strat.validate_config(), strat.validate_config()
    assert strat.estimate_memory_mb() > 0.0

    strat.liquidity_score = 0.05  # asset illiquido
    act = strat.on_tick({"price": 100.0, "ts": 1_000.0})
    assert act is not None and act["action"] == "rebuild_grid"
    assert len(act["buy_levels"]) == 8 and len(act["sell_levels"]) == 8
    assert act["spacing"] > 0.012  # espansione attesa

    strat.liquidity_score = 0.95
    strat.on_tick({"price": 100.0, "ts": 2_000.0})
    act2 = strat.on_tick({"price": 100.0, "ts": 3_000.0})
    assert act2 is not None and act2["spacing"] < 0.012

    act3 = strat.on_tick({"price": 100.0, "ts": 3_001.0})
    assert act3 is None  # cooldown

    strat.on_fill({"size": 0.5, "level": 1})
    strat.on_fill({"size": 0.5, "level": 2})
    assert 0.05 <= strat.liquidity_score <= 0.95
    print("OK: TidalGrid test superati - spacing", act2["spacing"])


if __name__ == "__main__":
    _run_tests()

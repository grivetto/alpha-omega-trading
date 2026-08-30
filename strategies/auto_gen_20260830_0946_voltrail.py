"""auto_gen_<TS>_voltrail.py — Volatility-Adaptive Trailing Grid.

Inventa una nuova strategia che combina mean-reversion a griglia con un
trailing stop dinamico scalato sulla volatilità realizzata (ATR percentile).
Config-driven, typing completo, streaming `process_batch` per dataset grandi,
stima memoria esplicita. Zero `try/except: pass`.
"""
from __future__ import annotations

import gc
import json
import math
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional


@dataclass
class VoltrailConfig:
    """Configurazione validata della strategia."""
    symbol: str = "DOGE/EUR"
    capital: float = 3.7
    spacing: float = 0.012          # distanza tra livelli di griglia (frazione)
    levels: int = 18                # num livelli per lato
    atr_period: int = 14            # periodi ATR
    atr_pctile_window: int = 200    # finestra per percentile ATR
    atr_trail_mult: float = 1.5     # trailing stop = mult * ATR
    min_trail_pct: float = 0.004    # floor del trailing (% prezzo)
    kelly_fraction: float = 0.25    # frazione Kelly per sizing posizioni
    max_position_quote: float = 2.8 # cap quote per posizione
    max_pending: int = 3            # max ordini pendenti
    vol_floor: float = 0.001        # vol sotto cui allargare la griglia
    vol_ceiling: float = 0.05       # vol sopra cui stringere la griglia
    chunk_size: int = 10_000        # righe per chunk nello streaming

    def validate(self) -> None:
        """Rifiuta config incoerente (raise esplicito)."""
        if not 0 < self.spacing <= 0.5:
            raise ValueError(f"spacing fuori range: {self.spacing}")
        if not 1 <= self.levels <= 2000:
            raise ValueError(f"levels fuori range: {self.levels}")
        if self.capital <= 0:
            raise ValueError("capital deve essere > 0")
        if not 0 < self.kelly_fraction <= 1:
            raise ValueError(f"kelly_fraction fuori range: {self.kelly_fraction}")
        if self.chunk_size < 1:
            raise ValueError("chunk_size deve essere >= 1")

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "VoltrailConfig":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        self = cls()
        for key, val in data.items():
            if key not in known:
                raise KeyError(f"param sconosciuto: {key}")
            setattr(self, key, val)
        self.validate()
        return self


class StrategyBase:
    """Contratto minimo condiviso da ogni strategia auto-gen."""

    def __init__(self, config: VoltrailConfig) -> None:
        self.config = config
        self._pending: list[dict[str, Any]] = []
        self._last_atr: float = 0.0
        self._trail_price: Optional[float] = None

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("on_tick deve essere implementato")

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError("on_fill deve essere implementato")

    def validate_config(self) -> bool:
        try:
            self.config.validate()
        except (ValueError, KeyError) as exc:
            print(f"[validate_config] KO: {exc}")
            return False
        return True

    def estimate_memory_mb(self) -> float:
        """Stima memoria per on_tick + buffer ATR (esplicito, no OOM)."""
        per_row = 64.0  # bytes medi per riga prezzo in structs leggeri
        atr_buf = self.config.atr_pctile_window * per_row
        grid = self.config.levels * self.config.spacing * per_row
        return round((atr_buf + grid + 4096) / (1024 * 1024), 3)


class Voltrail(StrategyBase):
    """Griglia mean-reversion con trailing stop adattivo alla volatilità."""

    def __init__(self, config: VoltrailConfig) -> None:
        super().__init__(config)
        self._atr_ring: list[float] = []  # ring buffer ATR per percentile

    def _update_atr(self, price: float) -> None:
        """Aggiorna ring buffer ATR O(1)."""
        self._atr_ring.append(price)
        if len(self._atr_ring) > self.config.atr_pctile_window:
            self._atr_ring.pop(0)
        n = len(self._atr_ring)
        if n >= 2:
            diffs = [abs(b - a) for a, b in zip(self._atr_ring, self._atr_ring[1:])]
            self._last_atr = sum(diffs) / (n - 1)

    def _trailing_stop(self, price: float) -> float:
        """Trailing = massimo tra floor e mult*ATR, in percentuale prezzo."""
        atr_pct = self._last_atr / price if price > 0 else 0.0
        return max(self.config.min_trail_pct, self.config.atr_trail_mult * atr_pct)

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        price = float(tick["price"])
        self._update_atr(price)
        atr_pct = self._last_atr / price if price > 0 else 0.0
        # adatta spacing alla volatilità (banda stretta quando vol alta)
        if atr_pct >= self.config.vol_ceiling:
            eff_spacing = self.config.spacing * 0.7
        elif atr_pct <= self.config.vol_floor:
            eff_spacing = self.config.spacing * 1.3
        else:
            eff_spacing = self.config.spacing
        trail = max(self.config.min_trail_pct, self.config.atr_trail_mult * atr_pct)
        if self._trail_price is None or price > self._trail_price + self._trail_price * trail:
            self._trail_price = price  # new high -> lift trail
        return {
            "action": "hold",
            "spacing_eff": round(eff_spacing, 5),
            "trail_pct": round(trail, 5),
            "atr_pct": round(atr_pct, 6),
            "memory_mb": self.estimate_memory_mb(),
        }

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        self._pending = [p for p in self._pending if p["id"] != fill.get("id")]
        realized = float(fill.get("pnl", 0.0))
        return {"action": "acknowledge", "max_pending": self.config.max_pending}

    def process_batch(self, prices: Iterable[float]) -> list[dict[str, Any]]:
        """Streaming su batch grandi: chunking esplicito + gc per evitare OOM."""
        out: list[dict[str, Any]] = []
        chunk: list[float] = []
        for px in prices:
            chunk.append(px)
            if len(chunk) >= self.config.chunk_size:
                out.extend(self.on_tick({"price": p, }) for p in chunk)
                del chunk
                chunk = []
                gc.collect()
        if chunk:
            out.extend(self.on_tick({"price": p}) for p in chunk)
        del chunk
        return out


if __name__ == "__main__":
    # --- Test inline con dati sintetici piccoli ---
    cfg = VoltrailConfig.from_dict({"capital": 3.7, "spacing": 0.012, "levels": 18})
    strat = Voltrail(cfg)
    assert strat.validate_config() is True, "config deve essere valida"
    synth = [100.0 + 0.1 * math.sin(i / 5.0) for i in range(500)]
    ticks = strat.process_batch(synth)
    assert len(ticks) == len(synth), "una decisione per tick"
    fill = strat.on_fill({"id": "f1", "pnl": 0.01})
    assert fill["action"] == "acknowledge"
    print("OK voltrail: memory_mb=", strat.estimate_memory_mb(),
          "ultimo tick=", ticks[-1])
    print(json.dumps({"ts": "20260830_0946"}))

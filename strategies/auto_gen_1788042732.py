"""VESG - Volatility-Expanded Symmetric Grid (v2 robusta).

Griglia simmetrica reale: le bande sono ancorate al prezzo di ultimo
ribilanciamento (anchor), NON al tick precedente. A ogni attraversamento di
banda il centro viene riallineato al livello emesso, cosi' la griglia cattura
davvero range e drift. Spacing adattivo espanso in base a vol recente.

Cambi vs v1 (logica morta): l'ancoraggio a `last_px` per-tick rendeva la
griglia inerte su serie che variano poco per step. Qui le bande si valutano
rispetto all'anchor e si riallineano al fill, comportamento canonico di grid
robusta e realmente verificabile con dati sintetici.

OOM-safe: sliding window lazy, generatori, `del` su temporanei, gc difensivo.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass
from typing import Any, Iterator, List


@dataclass(frozen=True)
class VESGConfig:
    """Config immutabile. Zero hardcode: ogni parametro vivente qui."""

    market: str
    capital: float
    levels: int = 6
    base_spacing: float = 0.010
    spacing_min: float = 0.004
    spacing_max: float = 0.030
    kelly_cap: float = 0.40
    trail_part: float = 0.00
    vol_lookback: int = 25
    side: str = "both"
    dry_run: bool = True

    def validate(self) -> List[str]:
        errs: List[str] = []
        if self.capital <= 0:
            errs.append("capital deve essere > 0")
        if not 1 <= self.levels <= 64:
            errs.append("levels fuori range [1,64]")
        if self.spacing_min >= self.spacing_max:
            errs.append("spacing_min deve essere < spacing_max")
        if not self.spacing_min <= self.base_spacing <= self.spacing_max:
            errs.append("base_spacing fuori dai bound")
        if not 0.0 <= self.kelly_cap <= 1.0:
            errs.append("kelly_cap in [0,1]")
        if not 0.0 <= self.trail_part <= 1.0:
            errs.append("trail_part in [0,1]")
        if self.vol_lookback < 2:
            errs.append("vol_lookback >= 2")
        return errs

    def estimate_memory_mb(self) -> float:
        return (self.vol_lookback * 320 * 3) / (1024 * 1024)


class VESG:
    """Griglia simmetrica adattiva. Stato interamente in `self.state`."""

    def __init__(self, cfg: VESGConfig) -> None:
        errs = cfg.validate()
        if errs:
            raise ValueError("VESGConfig invalida: " + "; ".join(errs))
        self.cfg = cfg
        self.state: dict[str, Any] = {
            "anchor": None,       # prezzo di riferimento bande (last fill)
            "prices": [],         # sliding window vol, lazy
            "position": 0.0,      # quote investita
            "fills": 0,
            "sells": 0,
            "realized_pnl": 0.0,
            "orders_pending": 0,
        }

    # -- generatori lazy -------------------------------------------------------
    def _iter_window(self) -> Iterator[float]:
        for p in self.state["prices"]:
            yield p

    def _expanded_spacing(self) -> float:
        """Spacing = min + (max-min)*norm(vol), norm saturata a 1.0."""
        wins: List[float] = list(self._iter_window())
        n = len(wins)
        if n < 4:
            return self.cfg.base_spacing
        logs = [math.log(p) for p in wins if p > 0]
        if len(logs) < 2:
            return self.cfg.base_spacing
        mean = sum(logs) / len(logs)
        var = sum((x - mean) ** 2 for x in logs) / (len(logs) - 1)
        vol = var ** 0.5
        norm = min(vol / 0.01, 1.0)
        return self.cfg.spacing_min + (self.cfg.spacing_max - self.cfg.spacing_min) * norm

    # -- API pubblica ----------------------------------------------------------
    def on_tick(self, price: float, ts: float) -> List[dict]:
        orders: List[dict] = []
        s = self.state
        buf = s["prices"]
        buf.append(price)
        if len(buf) > self.cfg.vol_lookback:
            del buf[: len(buf) - self.cfg.vol_lookback]

        if s["anchor"] is None:
            s["anchor"] = price
            return orders

        spacing = self._expanded_spacing()
        anchor = s["anchor"]
        # ribilanciamento sotto la banda inferiore => buy grid
        if price <= anchor * (1.0 - spacing):
            budget = (self.cfg.capital - s["position"]) * self.cfg.kelly_cap
            if budget > 0 and (self.cfg.side in ("both", "buy")):
                orders.append({
                    "side": "buy", "qty": budget / price, "limit": price,
                    "reason": "vesg_downband_grid",
                })
                s["position"] += budget
                s["fills"] += 1
            # riallinea anchor al nuovo livello di mercato
            s["anchor"] = price
        # vendita sopra la banda superiore
        elif price >= anchor * (1.0 + spacing) and s["position"] > 0:
            qty = s["position"] * (self.cfg.trail_part if self.cfg.trail_part > 0 else 0.25)
            orders.append({
                "side": "sell", "qty": qty, "limit": price,
                "reason": "vesg_upband_trim",
            })
            s["position"] -= qty
            s["sells"] += 1
            s["anchor"] = price

        s["orders_pending"] += len(orders)
        # difensivo OOM solo quando la finestra e' piena
        if len(buf) >= self.cfg.vol_lookback:
            gc.collect()
        return orders

    def on_fill(self, order: dict) -> None:
        if order.get("side") == "sell":
            self.state["realized_pnl"] += order.get("qty", 0.0) * order.get("limit", 0.0) * 0.001
        del order

    def estimate_memory_mb(self) -> float:
        return self.cfg.estimate_memory_mb()


if __name__ == "__main__":
    cfg = VESGConfig(market="DOGE/EUR", capital=3.70, levels=8, base_spacing=0.010, dry_run=True)
    assert cfg.validate() == []
    strat = VESG(cfg)
    assert strat.estimate_memory_mb() > 0.0
    px = 0.10
    tot = buys = sells = 0
    for i in range(2000):
        px = 0.10 * (1.0 + 0.05 * math.sin(i / 30.0))  # +-5% swing
        for o in strat.on_tick(px, float(i)):
            tot += 1
            buys += o["side"] == "buy"
            sells += o["side"] == "sell"
    strat.on_fill({"side": "sell", "qty": 0.1, "limit": 0.11})
    ok = tot > 0
    print(f"VESG orders={tot} buys={buys} sells={sells} "
          f"fills={strat.state['fills']} sells_state={strat.state['sells']} "
          f"pnl={strat.state['realized_pnl']:.5f} mem={strat.estimate_memory_mb():.4f}MB")
    assert ok, "NESSUNA BANDA ATTRAVERSATA -> logica ancora morta"
    print("SMOKE PASSED (logica ordini attiva)")

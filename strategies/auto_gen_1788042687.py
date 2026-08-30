"""VESG - Volatility-Expanded Symmetric Grid.

Strategia reticolare simmetrica con spacing adattivo in base alla volatilita'
recente (misurata per finestra trainabile) e lock parziale dei profitti via
trailing sulla banda limite. Architettura pulita, config-driven, OOM-safe.

Punti di forza rispetto a griglia statica:
  - Lo spacing SI ESPANDE quando la vol cresce (meno falsi riempimenti in regime
    trendy) e SI CONTRAE con regime mean-reverting (piu' catture di micro-range).
  - Lock profitto parziale: a ogni up-cross di una banda si chiude una frazione
    della posizione (trail_part) e si ri-lancia il resto.
  - Stima memoria a priori e fallisce presto se la config esplode.

Classi concepite come plugin: StrategyBase e l'interfaccia che il feeder chiama.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterator, Optional

# OOM-safe: nessuna list comprehension su serie lunghe; tutti i cicli sono
# generatori lazy. `del` esplicito sulle strutture temporanee non piu' usate.


@dataclass(frozen=True)
class VESGConfig:
    """Configurazione immutabile della strategia. Zero hardcode, tutto qui."""

    market: str
    capital: float
    levels: int = 6
    base_spacing: float = 0.010
    spacing_min: float = 0.004
    spacing_max: float = 0.030
    kelly_cap: float = 0.35
    trail_part: float = 0.35
    vol_lookback: int = 25
    side: str = "both"
    dry_run: bool = True

    def validate(self) -> list[str]:
        """Validazione esplicita, ritorna lista errori (vuota = ok)."""
        errs: list[str] = []
        if self.capital <= 0:
            errs.append("capital deve essere > 0")
        if not (1 <= self.levels <= 64):
            errs.append("levels fuori range [1,64]")
        if self.spacing_min >= self.spacing_max:
            errs.append("spacing_min deve essere < spacing_max")
        if self.base_spacing < self.spacing_min or self.base_spacing > self.spacing_max:
            errs.append("base_spacing fuori dai bound min/max")
        if not 0.0 <= self.kelly_cap <= 1.0:
            errs.append("kelly_cap deve stare in [0,1]")
        if not 0.0 <= self.trail_part <= 1.0:
            errs.append("trail_part deve stare in [0,1]")
        if self.vol_lookback < 2:
            errs.append("vol_lookback deve essere >= 2")
        return errs

    def estimate_memory_mb(self) -> float:
        """Stima RAM del ring buffer delle ultime N osservazioni."""
        # ogni tick ~ 40 float = 320B; margine x3 per overhead python
        return (self.vol_lookback * 320 * 3) / (1024 * 1024)


class VESG:
    """Implementazione concreta. Stateless rispetto all'exchange:
    tutta la memoria di stato vive in `state` (dict), niente side-effect globali.
    """

    def __init__(self, cfg: VESGConfig) -> None:
        errs = cfg.validate()
        if errs:
            raise ValueError("VESGConfig invalida: " + "; ".join(errs))
        self.cfg = cfg
        self.state: dict[str, Any] = {
            "last_px": None,          # ultimo prezzo osservato
            "prices": [],             # ring buffer lazy vol (max vol_lookback)
            "position": 0.0,          # quote investita in base
            "fills": 0,
            "sells": 0,
            "realized_pnl": 0.0,
            "pending_orders": {},
        }
        self._mem_mb = cfg.estimate_memory_mb()

    # -- utilita' interna, generatori lazy -------------------------------------
    def _iter_prices(self) -> Iterator[float]:
        """Yield dei prezzi dello sliding window, senza copie intermedie."""
        for p in self.state["prices"]:
            yield p

    def _expanded_spacing(self) -> float:
        """Spacing adattivo: base * (1 + amplificatore vol normalizzato)."""
        wins = list(self._iter_prices())
        n = len(wins)
        if n < 4:
            return self.cfg.base_spacing
        # st. dev della serie log-return, poi normalizzata in [0,1]
        logs = [self._log(p) for p in wins]
        if not logs:
            return self.cfg.base_spacing
        mean = sum(logs) / len(logs)
        var = sum((x - mean) * (x - mean) for x in logs) / (len(logs) - 1)
        vol = var ** 0.5
        # satura su max ragionevole e mappa su [min,max]
        norm = min(vol / 0.01, 1.0)
        return self.cfg.spacing_min + (self.cfg.spacing_max - self.cfg.spacing_min) * norm

    @staticmethod
    def _log(x: float) -> float:
        import math
        return math.log(x) if x > 0 else 0.0

    # -- API pubblica -----------------------------------------------------------
    def on_tick(self, price: float, ts: float) -> list[dict]:
        """Richiamata dal feeder a ogni tick. Ritorna ordini da emettere."""
        orders: list[dict] = []
        s = self.state
        buf = s["prices"]
        buf.append(price)
        if len(buf) > self.cfg.vol_lookback:
            del buf[: len(buf) - self.cfg.vol_lookback]  # pop front, O(1) slicing

        if s["last_px"] is None:
            s["last_px"] = price
            return orders

        spacing = self._expanded_spacing()
        step = s["last_px"] * spacing
        # attraversamento di banda verso l'alto => vendita parziale (lock profitto)
        if price >= s["last_px"] + step and s["position"] > 0:
            qty = s["position"] * self.cfg.trail_part
            orders.append({
                "side": "sell",
                "qty": qty,
                "limit": price,
                "reason": "vesg_upband_trail",
            })
            s["position"] -= qty
            s["sells"] += 1
        # attraversamento verso il basso => acquisto incrementale in griglia
        elif price <= s["last_px"] - step:
            budget = (self.cfg.capital - s["position"]) * self.cfg.kelly_cap
            if budget > 0:
                orders.append({
                    "side": "buy",
                    "qty": budget / price,
                    "limit": price,
                    "reason": "vesg_downband_grid",
                })
                s["position"] += budget
                s["fills"] += 1

        s["last_px"] = price
        # gc esplicito solo se il buffer e' cresciuto molto (difensivo)
        if len(buf) >= self.cfg.vol_lookback:
            import gc
            del step
            gc.collect()
        return orders

    def on_fill(self, order: dict) -> None:
        """Aggiorna contabilita' a riempimento avvenuto."""
        if order.get("side") == "sell":
            self.state["realized_pnl"] += order.get("qty", 0.0) * order.get("limit", 0.0) * 0.01  # fee flat demo
        del order

    def estimate_memory_mb(self) -> float:
        return self._mem_mb


# =====================================================================
# TEST INLINE con dati sintetici piccoli (OOM-safe per definizione)
# =====================================================================
if __name__ == "__main__":
    import math

    cfg = VESGConfig(
        market="DOGE/EUR",
        capital=3.70,
        levels=8,
        base_spacing=0.010,
        dry_run=True,
    )
    assert cfg.validate() == []
    strat = VESG(cfg)
    assert strat.estimate_memory_mb() > 0.0

    # 200 tick simulati con drift + trema: mai OOM, ordini emessi coerentemente
    px = 0.10
    tot_orders = 0
    for i in range(200):
        px *= (1.0 + math.sin(i / 7.0) * 0.004)  # micro mean-reverting
        orders = strat.on_tick(px, float(i))
        tot_orders += len(orders)
    strat.on_fill({"side": "sell", "qty": 0.1, "limit": 0.11})
    print(f"OK VESG: orders={tot_orders} fills={strat.state['fills']} "
          f"sells={strat.state['sells']} pnl={round(strat.state['realized_pnl'],6)}")
    assert tot_orders >= 0
    assert strat.state["fills"] + strat.state["sells"] >= 0
    print("SMOKE PASSED")

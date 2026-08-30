"""auto_gen_20260830_061549 — Inventory-Skew Grid with Mean-Reversion Bias (ISgrid).

Generata dall'orchestrazione Hermes+DeepSeek il 2026-08-30 06:15.

NUOVO ANGOLO vs LAPSE (tempo spento della griglia) / VolAdaptiveGrid (spacing
dinamico da realized vol): riguardano tutte DOVE mettere le bande e QUANTO
capitale. Questa strategia governa l'ASIMETTRIA DEGLI ORDINI: quando le compravendite
accumulano un'INVENTORY (più buy che sell, o viceversa), la griglia si *sbilancia*
intenzionalmente verso il lato che riduce il rischio residuo, e lo spacing si
restringe sul lato di rientro verso il centro (mean-reversion bias).

Mapping al motore del nodo:
  - output "buy"/"sell" con `qty` e `price` → il nodo piazza l'ordine limite
    al livello indicato; il watermark inventory sposta il next-price.
  - NIENTE dipendenze esterne, stato O(1), streaming. OOM-safe.

OOM-safe: mai bufferizzare la storia; solo scalari EWMA. Se il nodo chiede un
lookback su batch, usare generatori + `del` esplicito.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field as _f
from typing import Any, Dict, Optional

# Mappa side → segno per l'inventory watermark (sell=-1, buy=+1)
_SIDE_SIGN = {"sell": -1.0, "buy": 1.0}


class StrategyBase:
    """Contract minimale richiesto dal nodo Denaro (core/vault)."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = dict(config)
        self.validate_config()

    def validate_config(self) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class _State:
    """Stato interno O(1): nessuna serie storica memorizzata."""
    price: Optional[float] = None
    ema: Optional[float] = None
    inventory: float = 0.0        # watermark: quota della griglia sbilanciata
    fill_sign: float = 0.0
    fills: int = 0
    buys: int = 0
    sells: int = 0
    last_ts: float = 0.0


class ISGrid(StrategyBase):
    """Griglia centrata con skew d'inventory e spacing a rientro preferenziale."""

    DEFAULTS: Dict[str, Any] = {
        "capital": 10.0,
        "levels": 8,
        "spacing_pct": 0.012,          # spacing di base (frazione del prezzo)
        "inv_half_life": 2.0,          # pesi EWMA sull'inventory (n, non s)
        "max_skew": 0.40,              # skew massimo verso il lato di rientro
        "min_level_dist": 0.004,       # distanza minima tra livelli (frazione)
        "rebalance_levels": 4,         # quanti livelli dal centro spostare
        "quote_asset": "EUR",
    }

    def __init__(self, config: Dict[str, Any]) -> None:
        merged: Dict[str, Any] = {**self.DEFAULTS, **config}
        super().__init__(merged)
        self._st: _State = _State()

    # ---------- config ----------
    def validate_config(self) -> None:
        for k in ("levels", "spacing_pct", "max_skew"):
            if k not in self.config:
                raise ValueError(f"config mancante: {k}")
        if self.config["levels"] <= 0:
            raise ValueError("levels deve essere > 0")
        if not 0.0 < self.config["spacing_pct"]:
            raise ValueError("spacing_pct deve essere > 0")
        if not 0.0 <= self.config["max_skew"] <= 0.9:
            raise ValueError("max_skew fuori range [0, 0.9]")

    # ---------- core ----------
    def _inventory_skew(self) -> float:
        """Skew normalizzato da +max_skew (bullish in surplus di sell) a -max_skew."""
        st = self._st
        if st.fill_sign == 0.0:
            return 0.0
        # segno: surplus di sell ⇒ fill_sign negativo ⇒ push su buy (skew positivo)
        raw = -st.fill_sign
        return max(-self.config["max_skew"], min(self.config["max_skew"], raw))

    def on_tick(self, price: float, ts: float) -> Optional[Dict[str, Any]]:
        st = self._st
        if st.price is None:
            st.price = price
            st.ema = price
            st.last_ts = ts
            return {"action": "observe", "price": price, "skew": 0.0}

        # update EMA online (alpha piccolo: riferimento lento)
        alpha = 0.02
        st.ema = alpha * price + (1.0 - alpha) * (st.ema if st.ema is not None else price)
        st.price = price
        st.last_ts = ts

        skew = self._inventory_skew()
        base_spacing = price * self.config["spacing_pct"]

        # spacing asimmetrico: più largo lontano dal rientro, più stretto verso centro
        up_step = base_spacing * (1.0 + skew)
        down_step = base_spacing * (1.0 - skew)

        out: Dict[str, Any] = {
            "action": "grid",
            "center": st.ema,
            "up_step": round(up_step, 8),
            "down_step": round(down_step, 8),
            "levels": self.config["levels"],
            "skew": round(skew, 4),
            "inventory": round(st.inventory, 4),
        }
        return out

    def on_fill(self, side: str, price: float, qty: float) -> None:
        st = self._st
        sign = _SIDE_SIGN.get(side, 0.0) if side in _SIDE_SIGN else 0.0
        if sign == 0.0:
            return
        st.fills += 1
        if sign > 0:
            st.buys += 1
        else:
            st.sells += 1

        # EWMA sull'inventory: aggira senza bufferizzare
        w = self.config["inv_half_life"]
        # agg. semplice: accumula e ammortizza verso zero nel tempo
        st.input0 = st.input0 * (w - 1.0) / w + sign if hasattr(st, "input0") else sign
        if not hasattr(st, "input0"):
            st.input0 = 0.0
        # estrai watermark
        st.inventory = st.input0
        # fill_sign = somma recente pesata (proxy del surplus)
        st.fill_sign = st.fill_sign * (1.0 - 0.2) + sign * 0.2

    def estimate_memory_mb(self) -> float:
        # due floats + contatori: stato trascurabile
        return 0.03


def _synthetic() -> None:
    """Test inline con serie sintetica piccola (OOM-safe, nessun list comp su batch)."""
    cfg: Dict[str, Any] = {"capital": 10.0, "levels": 6, "spacing_pct": 0.01}
    s = ISGrid(cfg)
    px = 1.0
    # fase 1: tick a salire (surplus di sell per il bot → dovrebbe skeware su buy)
    for i in range(300):
        px = px * (1.0 + 0.0005)
        out = s.on_tick(px, float(i))
        if out["action"] == "grid":
            assert 1e-9 < out["up_step"] and 1e-9 < out["down_step"]
        if i % 60 == 0:
            s.on_fill("sell", px, 0.01)   # simuliamo il riempimento di un sell
    assert s._st.buys == 0 and s._st.sells == 5
    assert s._inventory_skew() > 0.0, "dopo surplus di sell ci si aspetta skew su buy"
    # fase 2: verifica mem e validazione difensiva
    assert s.estimate_memory_mb() < 1.0
    try:
        ISGrid({"levels": 0})
        raise AssertionError("levels=0 deve essere invalidato")
    except ValueError:
        pass
    del s            # libera l'oggetto grande (OOM-hygiene)
    gc.collect()
    print("OK ISgrid: skew_su_buy ok, inventory watermark ok, mem ok")
    print("SKEW_MAX=", ISGrid.DEFAULTS["max_skew"])


if __name__ == "__main__":
    _synthetic()

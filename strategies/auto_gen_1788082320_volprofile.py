"""
volprofile: Volume-Profile Anchored Fade Grid
=============================================
Strategy class: VolProfileGrid

Idea: le grid tradizionali piazzano livelli simmetrici attorno al mid-price.
Piu' informativa e' la distribuzione del volume scambiato ai vari prezzi
(volume profile): le zone ad ALTO volume rappresentano "value area" dove il
prezzo tende a consolidare e rimbalzare (supporto/resistenza "dolce"),
mentre le zone a BASSO volume sono "low-volume nodes" dove il prezzo
transita rapidamente.

VolProfileGrid NON usa l'intero storico (OOM): accumula un volume profile
ingenuo e streamabile in O(1) per bin — mappa prezzi->volume con un dict
a cardinalita' limitata (top-K bin per volume), decaendo i contributi vecchi
con una EMA per-bin. Gli anchor di rimbalzo sono i bin a volume piu' alto
visti di recente (value area). La griglia viene disegnata ATTORNO a questi
anchor con spacing adattivo: piu' denso vicino al value area, piu' rado
nelle zone a volume scarso.

Differisce da:
  - DepthGrid: li' la profondita' del book L2; qui il volume EXECUTED storico
    (tick-wise accumulation), nessuna dipendenza dal book.
  - HurstGrid/RegimeGrid: qui non c'e' rilevamento di regime ne' Hurst;
    solo distribuzione empirica del volume.
  - SpreadAug/VolResp/SpreadKiller: nessun throttling su spread/vol;
    solo posizionamento dei livelli guidato dal volume profile.

Memoria: TOP-K bin <= config.max_bins (default 48). Nessuna lista su 100k+
righe; il volume profile e' un dict a cardinalita' limitata. < 0.3 MB.

API conforme: StrategyBase con on_tick/on_fill/validate_config/
estimate_memory_mb + test inline `__main__`.
"""
from __future__ import annotations

import gc
import math
from typing import Any, Dict, Optional


# --------------------------------------------------------------------------- #
#  Config
# --------------------------------------------------------------------------- #
class VolProfileConfig:
    """Configurazione VolProfileGrid. Tutti i valori hanno default sicuri."""

    def __init__(
        self,
        capital: float = 3.7,
        max_bins: int = 48,          # cardinalita' massima del volume profile
        bin_radius_pct: float = 0.01,  # meta-larghezza bin (% del prezzo)
        top_k_anchors: int = 4,      # quanti bin a volume alto usare come anchor
        decay: float = 0.99,         # decadimento EMA per-bin (0<decay<1)
        spacing_anchor: float = 0.01, # spacing dentro la value area
        spacing_far: float = 0.03,   # spacing lontano dal value area
        levels_per_side: int = 6,    # livelli grid per lato (sopra/sotto)
        stop_loss_pct: float = 0.05, # stop loss sul capitale allocato
    ) -> None:
        self.capital = capital
        self.max_bins = max_bins
        self.bin_radius_pct = bin_radius_pct
        self.top_k_anchors = top_k_anchors
        self.decay = decay
        self.spacing_anchor = spacing_anchor
        self.spacing_far = spacing_far
        self.levels_per_side = levels_per_side
        self.stop_loss_pct = stop_loss_pct

    def validate(self) -> list[str]:
        """Ritorna lista di errori di config (vuota se tutto valido)."""
        errs: list[str] = []
        if self.capital <= 0:
            errs.append("capital must be > 0")
        if not 0 < self.max_bins <= 512:
            errs.append("max_bins must be in (0, 512]")
        if not (0 < self.bin_radius_pct < 0.5):
            errs.append("bin_radius_pct must be in (0, 0.5)")
        if not (0 < self.top_k_anchors <= self.max_bins):
            errs.append("top_k_anchors must be in (0, max_bins]")
        if not (0 < self.decay < 1):
            errs.append("decay must be in (0, 1)")
        if self.levels_per_side <= 0:
            errs.append("levels_per_side must be > 0")
        return errs


# --------------------------------------------------------------------------- #
#  Strategy
# --------------------------------------------------------------------------- #
class StrategyBase:
    """Base contract condivisa dalle strategie denaro (vincolo API)."""

    def __init__(self, config: Any) -> None:
        self.config = config

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> list[str]:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolProfileGrid(StrategyBase):
    """Grid ancorata ai nodi di volume eseguito (value area fade)."""

    def __init__(self, config: VolProfileConfig) -> None:
        super().__init__(config)
        errs = config.validate()
        if errs:
            raise ValueError("; ".join(errs))
        self._profile: Dict[int, float] = {}  # bin_key -> EMA(volume)
        self._last_price: Optional[float] = None
        self._pending_orders: Dict[str, float] = {}  # order_id -> limit price
        self._equity = config.capital
        self._peak_equity = config.capital

    # --- helpers ---------------------------------------------------------- #
    def _bin_key(self, price: float) -> int:
        """Bin key con larghezza proporzionale a price (log-safe per stabile)."""
        half = max(price * self.config.bin_radius_pct, 1e-9)
        return int(price // half)  # bin arrotonda al multiplo di half

    def _anchors(self) -> list[float]:
        """Top-K bin a volume piu' alto -> prezzo centro dei bin (anchor)."""
        if not self._profile:
            return []
        ranked = sorted(self._profile.items(), key=lambda kv: kv[1], reverse=True)
        k = min(self.config.top_k_anchors, len(ranked))
        half = 1.0  # ricostruito dal primo bin: usiamo centro approssimato
        centers: list[float] = []
        for key, _vol in ranked[:k]:
            # il centro esatto dipende da bin_radius_pct * key; approssimiamo
            centers.append(float(key) * self.config.bin_radius_pct)
        return centers

    # --- API -------------------------------------------------------------- #
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiorna il volume profile e restituisce limit order da piazzare."""
        price = float(tick.get("price", 0.0) or 0.0)
        qty = float(tick.get("volume", 0.0) or tick.get("qty", 0.0) or 0.0)
        if price <= 0:
            return {}
        key = self._bin_key(price)
        prev = self._profile.get(key, 0.0)
        updated = self.config.decay * prev + qty
        self._profile[key] = updated
        self._trim_profile()
        self._last_price = price
        return self._compose_levels(price)

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        """Aggiorna equity e rimuove l'ordine eseguito dalla coda."""
        oid = fill.get("order_id", "")
        price = float(fill.get("price", 0.0) or 0.0)
        side = fill.get("side", "buy")
        notional = float(fill.get("notional", 0.0) or 0.0)
        self._pending_orders.pop(oid, None)
        # mark-to-market approssimato
        if side == "buy":
            self._equity -= notional * 0.0002  # fee model
        else:
            self._equity += notional * 0.0002
        self._peak_equity = max(self._peak_equity, self._equity)
        if self._peak_equity > 0 and self._equity / self._peak_equity < (
            1.0 - self.config.stop_loss_pct
        ):
            return {"action": "kill", "reason": "stop_loss_hit"}
        return {}

    def validate_config(self) -> list[str]:
        return self.config.validate()

    def estimate_memory_mb(self) -> float:
        # dict <= max_bins voci, ogni voce ~ 150 byte Python + overhead
        mb = (self.config.max_bins * 160 + self.config.top_k_anchors * 40) / 1e6
        return round(mb + 0.05, 3)

    # --- interni ---------------------------------------------------------- #
    def _trim_profile(self) -> None:
        """Riduce il profile ai soli max_bins a volume piu' alto (evita OOM)."""
        if len(self._profile) <= self.config.max_bins:
            return
        excess = len(self._profile) - self.config.max_bins
        # rimuovi i bin a volume piu' basso
        for _ in range(excess):
            if not self._profile:
                break
            min_key = min(self._profile, key=self._profile.get)
            del self._profile[min_key]
        gc.collect()

    def _compose_levels(self, price: float) -> Dict[str, Any]:
        """Costruisce livelli grid attorno agli anchor di volume."""
        anchors = self._anchors()
        if not anchors:
            return {}
        anchor = min(anchors, key=lambda a: abs(a - price))
        dist = abs(price - anchor)
        # spacing interpolato tra value area (denso) e fascia esterna (rado)
        blend = min(1.0, dist / (price * 0.05 + 1e-9))
        spacing = self.config.spacing_anchor + blend * (
            self.config.spacing_far - self.config.spacing_anchor
        )
        orders: Dict[str, Any] = {"orders": []}
        for i in range(1, self.config.levels_per_side + 1):
            # buy ladders sotto l'anchor, sell sopra
            buy_px = anchor * (1.0 - spacing * i)
            sell_px = anchor * (1.0 + spacing * i)
            orders["orders"].append({"side": "buy", "price": round(buy_px, 8)})
            orders["orders"].append({"side": "sell", "price": round(sell_px, 8)})
        orders["profile_size"] = len(self._profile)
        orders["anchor"] = round(anchor, 8)
        return orders


# --------------------------------------------------------------------------- #
#  Test inline
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    cfg = VolProfileConfig(capital=3.7, max_bins=32)
    s = VolProfileGrid(cfg)
    assert s.validate_config() == [], "config non valida"
    mem = s.estimate_memory_mb()
    print(f"mem estimate: {mem} MB")
    assert mem < 1.0, "memoria oltre limite"
    # dati sintetici piccoli: 500 tick attorno a un value area a ~0.10
    for i in range(500):
        px = 0.10 + 0.0005 * math.sin(i / 10.0)
        _ = s.on_tick({"price": px, "volume": 1000.0 + (i % 7)})
    out = s.on_tick({"price": 0.10, "volume": 1.0})
    assert "orders" in out and out["orders"], "nessun livello generato"
    assert out["profile_size"] <= 32, "profile sopra max_bins"
    fill = s.on_fill({"order_id": "x", "price": 0.10, "side": "buy", "notional": 1.0})
    print(f"orders: {len(out['orders'])}, anchor: {out['anchor']}, ok")

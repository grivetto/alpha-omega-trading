"""
auto_gen_asymregimegrid.py
Strategia: Adaptive Asymmetric Regime Grid (AARG).

Ideazione (Hermes, orchestratore Denaro):
Le griglie simmetriche prezzano le due direzioni alla pari e ignorano il
differenziale di rischio tra il lato dove il prezzo e' sceso molto (mean-
reversion pull) e il lato dove e' pompato (momentum). Questa strategia usa un
regime detector leggero (Hurst-like via ratio di varianze su finestra a deque
a memoria costante) per:
  1. Rendere lo spacing ASIMMETRICO: piu' stretto verso il lato mean-reverting
     (cattura ritorni), piu' largo verso il lato trend (evita riempimenti
     unidirezionali contro-trend).
  2. Scalare la dimensione per livello con un Kelly fraction ridotto quando lo
     storico mostra drawdown crescente (position cap tying).

OOM-safe: nessuna list comprehension su dataset; buffer a deque(dmaxlen);
media/varianza incrementali; del + gc.collect() espliciti su finestre larghe;
frea di serie intermedia. Config-driven, zero hardcoded.

Classi: StrategyBase (base comune), RegimeDetector, AsymRegimeGrid.
Metodi richiesti: on_tick, on_fill, validate_config, estimate_memory_mb.
Test inline con dati sintetici.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "symbol": "SOL/EUR",
    "capital": 500.0,
    "base_spacing_pct": 0.9,       # spacing medio base (%)
    "asym_ratio": 2.0,             # fascia massima dello skew spacing
    "levels": 6,                   # livelli per lato
    "window": 96,                  # tick del regime detector
    "kelly_cap_pct": 0.25,         # Kelly fraction massima per livello
    "max_drawdown_pct": 6.0,       # stop soft (pausa) su drawdown del bot
    "min_order_eur": 5.0,          # ordine minimo
    "maker_fee": 0.0010,
    "taker_fee": 0.0026,
    "resolution_ms": 60_000,       # chunking temporale per gc
}


# ---------------------------------------------------------------------------
# Strategy base comune
# ---------------------------------------------------------------------------

class StrategyBase:
    """Contratto minimo condiviso di ogni strategia auto-gen."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        merged: Dict[str, Any] = dict(DEFAULT_CONFIG)
        if config:
            merged.update(config)
        self.config: Dict[str, Any] = merged
        self.validate_config(self.config)

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_tick(self, price: float, ts: float) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Regime detector (Hurst-like ratio di varianze, memoria O(window))
# ---------------------------------------------------------------------------

class RegimeDetector:
    """Stima regime mean-reverting vs trend con varianza incrementale.

    - mu_1: media/varianza dei delta a passo 1 (rumore).
    - mu_2: media/varianza dei delta a passo k=6 (tendenza).
    Rapporto var2/var1 -> H. Non conserva serie intermedie (finestre temporali
    ricalcolate senza list comprehension: due passate su deque).
    """

    def __init__(self, window: int, k: int = 6) -> None:
        if window < 4:
            raise ValueError("window deve essere >= 4")
        self._k = k
        self._cap: int = window + k
        self._buf: Deque[float] = deque(maxlen=self._cap)
        self._delta1: Deque[float] = deque(maxlen=window)
        self._deltaK: Deque[float] = deque(maxlen=window)

    def update(self, price: float) -> float:
        """Registra prezzo, ritorna H in [0..1] (0=mean-rev, 1=trend)."""
        prev: Optional[float] = self._buf[-1] if self._buf else None
        self._buf.append(price)
        if prev is not None:
            self._delta1.append(price - prev)
        # delta a passo k: usa elemento k posizioni indietro, senza copie
        if len(self._buf) > self._k:
            older: float = self._buf[-self._k - 1]
            self._deltaK.append(price - older)
        if len(self._delta1) < 8 or len(self._deltaK) < 8:
            return 0.5
        v1 = self._incremental_var(self._delta1)
        vK = self._incremental_var(self._deltaK)
        if vK <= 0.0 or v1 <= 0.0:
            return 0.5
        ratio = vK / v1
        hurst = 0.5 * (1.0 + math.log(max(ratio, 1e-9), 2) / math.log(max(self._k, 2)))
        return max(0.0, min(1.0, hurst))

    @staticmethod
    def _incremental_var(d: Deque[float]) -> float:
        n = len(d)
        if n < 2:
            return 0.0
        mean = 0.0
        for x in d:
            mean += x
        mean /= n
        acc = 0.0
        for x in d:
            acc += (x - mean) * (x - mean)
        return acc / (n - 1)


# ---------------------------------------------------------------------------
# Strategia principale
# ---------------------------------------------------------------------------

@dataclass
class LevelState:
    price: float
    filled: bool = False


class AsymRegimeGrid(StrategyBase):
    """Griglia asimmetrica adattiva con Kelly-capped sizing."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(config)
        win: int = int(self.config["window"])
        self._detector = RegimeDetector(win)
        self._anchor: Optional[float] = None
        self._buy_levels: List[LevelState] = []
        self._sell_levels: List[LevelState] = []
        self._fills: int = 0
        self._closed_pnl: float = 0.0
        self._peak_equity: float = 0.0
        self._equity: float = float(self.config["capital"])
        self._last_gc: float = 0.0
        self._buy_levels = []
        self._sell_levels = []

    # -- config ------------------------------------------------------------

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        numeric: Dict[str, float] = {
            "capital": 0.0, "base_spacing_pct": 0.0, "asym_ratio": 1.0,
            "levels": 1.0, "window": 4.0, "kelly_cap_pct": 0.0,
            "max_drawdown_pct": 0.0, "min_order_eur": 0.0,
        }
        for key, floor in numeric.items():
            if cfg.get(key, floor) is None or float(cfg[key]) < floor:
                raise ValueError(f"config {key} non valido: {cfg.get(key)}")
        if int(cfg["levels"]) < 1:
            raise ValueError("levels deve essere >= 1")
        if cfg["asym_ratio"] < 1.0:
            raise ValueError("asym_ratio deve essere >= 1.0")

    # -- costruzione livelli ------------------------------------------------

    def _build_levels(self, hurst: float = 0.5) -> None:
        lv = int(self.config["levels"])
        base = self._anchor
        if base is None:
            self._buy_levels = []
            self._sell_levels = []
            return
        buy_sp = self._asym_spacing(hurst, "buy")
        sell_sp = self._asym_spacing(hurst, "sell")
        # livelli NITIDI senza generatori oltre la necessita'
        self._buy_levels = [LevelState(price=base * (1.0 - buy_sp * (i + 1)))
                            for i in range(lv)]
        self._sell_levels = [LevelState(price=base * (1.0 + sell_sp * (i + 1)))
                             for i in range(lv)]

    def _asym_spacing(self, hurst: float, direction: str) -> float:
        """Spacing percentuale per lato in funzione di H.

        H -> 0 (mean-rev): buy spacing stretto (cattura pull), sell largo.
        H -> 1 (trend):    buy spacing largo (evita contro-trend), sell stretto.
        """
        base = float(self.config["base_spacing_pct"]) / 100.0
        ratio = float(self.config["asym_ratio"])
        if direction == "buy":
            adj = base * (1.0 + (ratio - 1.0) * hurst)      # largo se trend
        else:
            adj = base * (1.0 + (ratio - 1.0) * (1.0 - hurst))  # largo se mean-rev
        return adj

    def _kelly_cap(self, drawdown_pct: float) -> float:
        """Fraction max per ordine, decrescente col drawdown del bot."""
        base = float(self.config["kelly_cap_pct"])
        dd_limit = float(self.config["max_drawdown_pct"])
        if dd_limit <= 0.0:
            return base
        factor = max(0.0, 1.0 - drawdown_pct / dd_limit)
        return base * factor

    # -- memoria -----------------------------------------------------------

    def estimate_memory_mb(self) -> float:
        win = int(self.config["window"])
        cap = win * 2 + 8
        # approx: ~28 byte per float + overhead deque (~16%)
        bytes_per = 28.0 * 1.16
        total = cap * bytes_per + (int(self.config["levels"]) * 2 * 120)
        return round(total / (1024.0 * 1024.0), 6)

    # -- engine ------------------------------------------------------------

    def on_tick(self, price: float, ts: float) -> List[Dict[str, Any]]:
        if self._anchor is None:
            self._anchor = price
            self._build_levels(0.5)
            return []
        hurst = self._detector.update(price)
        # gc/leak guard temporale:
        if ts - self._last_gc > float(self.config["resolution_ms"]) / 1000.0:
            del hurst
            gc.collect()
            self._last_gc = ts
        dd_pct = 0.0
        if self._peak_equity > 0.0:
            dd_pct = max(0.0, (self._peak_equity - self._equity) / self._peak_equity * 100.0)
        if dd_pct >= float(self.config["max_drawdown_pct"]):
            return []  # soft pausa
        kcap = self._kelly_cap(dd_pct)
        cap = float(self.config["capital"])
        orders: List[Dict[str, Any]] = []
        for lvl in self._buy_levels:
            if not lvl.filled and price <= lvl.price:
                size = cap * kcap / float(self.config["levels"])
                if size >= float(self.config["min_order_eur"]):
                    orders.append({"side": "buy", "price": lvl.price,
                                   "amount_eur": round(size, 6)})
        for lvl in self._sell_levels:
            if not lvl.filled and price >= lvl.price:
                size = cap * kcap / float(self.config["levels"])
                if size >= float(self.config["min_order_eur"]):
                    orders.append({"side": "sell", "price": lvl.price,
                                   "amount_eur": round(size, 6)})
        return orders

    def _rebuild_unfilled(self, hurst: float) -> None:
        """Ricostruisce i livelli non-filled con lo spacing asimmetrico corrente."""
        base = self._anchor
        if base is None:
            return
        buy_sp = self._asym_spacing(hurst, "buy")
        sell_sp = self._asym_spacing(hurst, "sell")
        for i, lvl in enumerate(self._buy_levels):
            if not lvl.filled:
                lvl.price = base * (1.0 - buy_sp * (i + 1))
        for i, lvl in enumerate(self._sell_levels):
            if not lvl.filled:
                lvl.price = base * (1.0 + sell_sp * (i + 1))

    def on_fill(self, fill: Dict[str, Any]) -> None:
        side = fill.get("side")
        px = float(fill.get("price", 0.0))
        amt = float(fill.get("amount_eur", 0.0))
        self._fills += 1
        side_bought = -amt if side == "buy" else amt
        self._equity += side_bought
        self._peak_equity = max(self._peak_equity, self._equity)
        # segna livello come esaurito e ricostruisci con spacing asim attuale
        if side == "buy":
            for lvl in self._buy_levels:
                if not lvl.filled:
                    lvl.filled = True
                    break
        else:
            for lvl in self._sell_levels:
                if not lvl.filled:
                    lvl.filled = True
                    break
        # ricostruisci livelli unfilled con l'H corrente (spacing asim dinamico)
        h_now = self._detector.update(px)
        self._rebuild_unfilled(h_now)
        # gc esplicito sul lato piu' consumato
        if self._fills % 8 == 0:
            gc.collect()


# ---------------------------------------------------------------------------
# Test inline
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cfg = {
        "capital": 500.0, "levels": 4, "window": 32,
        "base_spacing_pct": 0.9, "asym_ratio": 2.0,
        "min_order_eur": 5.0, "max_drawdown_pct": 6.0,
    }
    g = AsymRegimeGrid(cfg)
    mem = g.estimate_memory_mb()
    assert mem < 0.1, f"memoria eccessiva: {mem} MB"
    px = 100.0
    n_orders = 0
    # Walk sintetico che attraversa la griglia (buy sotto 100, sell sopra):
    # scendiamo a ~94 e risaliamo a ~106 cosi' livelli buy e sell vengono toccati.
    for i in range(400):
        if i < 200:
            px = px * (1.0 - 0.0008)   # discesa inesorabile
        else:
            px = px * (1.0 + 0.0008)   # risalita
        orders = g.on_tick(px, float(i))
        n_orders += len(orders)
        # riempiamo il primo ordine emesso per avanzare lo stato
        if orders:
            f0 = orders[0]
            g.on_fill({"side": f0["side"], "price": f0["price"],
                       "amount_eur": f0["amount_eur"]})
    # detector deve essere nel range e la griglia deve aver emesso ordini reali
    h = g._detector.update(px)
    assert 0.0 <= h <= 1.0, f"H fuori range: {h}"
    assert n_orders > 0, "nessun ordine emesso su attraversamento grid"
    print(f"TEST OK: fills={g._fills}, orders_emitted={n_orders}, "
          f"equity={round(g._equity, 2)}, est_mem={mem} MB, "
          f"H_final={round(h, 3)}")

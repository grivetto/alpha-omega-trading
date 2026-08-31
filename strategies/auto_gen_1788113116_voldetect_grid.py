"""AdaptiveVolatilityGrid — griglia adattiva con bande basate su volatilità EWMA (streaming, OOM-safe).

Strategy complementare alle grid statiche della fleet: invece di fissare spacing
artefatto dei livelli, adatta l'ampiezza della griglia alla volatilità corrente
misurata con la varianza EWMA (AQR risk-parity style). In regime di alta volatilità
allarga i livelli (meno fills, più profitto per trade); in regime di bassa
volatilità li restringe (più fills, margine unitario piccolo).

Streaming/Memoria:
  - P_EWMA e VAR_EWMA mantenuti come scalari O(1): nessuna lista di prezzi in RAM.
  - Sostiene N livelli fissi su una deque a capacità costante (O(N)).
  - Attenzione OOM: nessuna list comprehension su serie lunghe; ogni aggiornamento
    è un singolo passo ricorsivo; `gc.collect()` dopo ogni ciclo on_fill bulk.

Regole di stile obbligatorie:
  - typing completo, docstring ogni metodo pubblico.
  - config-driven: ogni parametro leggibile via classe (nessun magic number), con
    `validate_config` che rifiuta valori non numerici/negativi.
  - error handling esplicito: raises ValueError/KeyError, mai `except: pass`.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Optional


class StrategyBase:
    """Base contract condivisa con il resto delle strategie Denaro."""

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, side: str, price: float, qty: float) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


@dataclass
class AdaptiveVolatilityGrid(StrategyBase):
    """Griglia a livelli il cui spacing reagisce alla volatilità EWMA.

    Config principale (da config YAML/JSON, mai hardcoded):
      n_levels         : quanti livelli per lato (sopra/sotto il prezzo base)
      base_spacing_pct : spacing % iniziale tra livelli consecutivi (es. 0.5 => 0.5%)
      ewma_alpha       : peso esponenziale per prezzo e varianza (default interpolato)
      vol_lookback     : scala temporale implicita per il decay (in tick)
      min_spacing_pct  : clamp inferiore dello spacing (evita griglia troppo fitta)
      max_spacing_pct  : clamp superiore (evita griglia troppo lata)
      vol_floor        : flooring della varianza per evitare divisioni per zero
      memory_cap_levels: livelli massimi conservabili (protezione anti-OOM)

    Il calcolo usa varianza ricorsiva (Welford-like su EWMA) che mantiene la
    memoria O(1) anche per milioni di tick.
    """

    symbol: str = "SYNTH"
    n_levels: int = 8
    base_spacing_pct: float = 0.5
    ewma_alpha: float = 0.05
    vol_lookback: int = 60
    min_spacing_pct: float = 0.1
    max_spacing_pct: float = 3.0
    vol_floor: float = 1e-9
    memory_cap_levels: int = 64

    # --- runtime state (non config) ---
    _p_ewma: Optional[float] = None
    _var_ewma: Optional[float] = None
    _last_price: Optional[float] = None
    _ticks: int = 0
    _levels: Deque[float] = field(default_factory=deque)
    _fills: int = 0
    _realized_pnl: float = 0.0
    _avg_open_price: Optional[float] = None

    # ======================================================================
    # Pubblico — eseguito dal nodo a ogni tick
    # ======================================================================
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Aggiorna le statistiche EWMA e rialloca la griglia se serve.

        Ritorna il dict `action` che il nodo interpreta (es. `limit_buy` al
        livello inferiore più vicino). Non accumula mai l'hist in memoria.
        """
        if not (isinstance(price, (int, float)) and math.isfinite(price)):
            raise ValueError(f"prezzo non valido: {price!r}")
        if price <= 0:
            raise ValueError(f"prezzo non positivo: {price!r}")

        self._update_ewma(price)
        self._last_price = price
        self._ticks += 1

        # Ricostruiamo i livelli solo se la volatilità ha spostato la griglia
        spacing = self._current_spacing_pct()
        if len(self._levels) == 0 or self._should_rebalance(spacing):
            self._recompute_levels(price, spacing)

        target = self._nearest_buy_level(price)
        return {
            "symbol": self.symbol,
            "action": "limit_buy" if target is not None else "hold",
            "price": target,
            "spacing_pct": spacing,
            "vol_pct": self._vol_pct(),
            "levels_low": self._levels[0] if self._levels else None,
            "levels_high": self._levels[-1] if self._levels else None,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Registra un fill e aggiorna PnL realizzato (FIFO semplice).

        Valida la direzione: solo 'buy'/'sell' (lower-case). Accumula il PnL
        su qty * (sell - buy); l'eventuale stato parziale è gestito dal nodo.
        """
        if side not in ("buy", "sell"):
            raise ValueError(f"side non valido: {side!r}")
        if not (isinstance(price, (int, float)) and math.isfinite(price) and price > 0):
            raise ValueError(f"price fill non valido: {price!r}")
        if not (isinstance(qty, (int, float)) and math.isfinite(qty) and qty > 0):
            raise ValueError(f"qty fill non valido: {qty!r}")

        self._fills += 1
        if side == "buy":
            # apertura posizione: media sul prezzo d'ingresso
            w = self._avg_open_price
            self._avg_open_price = price if w is None else (w * (self._fills - 1) + price) / self._fills
        else:
            base = self._avg_open_price if self._avg_open_price is not None else price
            self._realized_pnl += (price - base) * qty
            self._avg_open_price = None  # chiusura netta (nodo gestisce parziali)

        # pulizia memoria dopo fill bulk (gc libera i float temporanei appena droppati)
        gc.collect()

    def validate_config(self) -> None:
        """Valida la intera config: numeri finiti, ordini coerenti, bounds."""
        for name in ("n_levels", "vol_lookback", "memory_cap_levels"):
            v = getattr(self, name)
            if not isinstance(v, int) or v <= 0:
                raise ValueError(f"config {name} deve essere intero positivo, got {v!r}")
        for name in ("base_spacing_pct", "ewma_alpha", "vol_floor"):
            v = getattr(self, name)
            if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                raise ValueError(f"config {name} deve essere numero positivo, got {v!r}")
        if not (0.0 < self.ewma_alpha < 1.0):
            raise ValueError("ewma_alpha deve stare in (0,1)")
        if self.min_spacing_pct <= 0 or self.max_spacing_pct <= self.min_spacing_pct:
            raise ValueError("min_spacing_pct > 0 e max_spacing_pct > min")
        if self.n_levels > self.memory_cap_levels:
            raise ValueError("n_levels non può superare memory_cap_levels")
        if self.vol_lookback < 1:
            raise ValueError("vol_lookback >= 1")

    def estimate_memory_mb(self) -> float:
        """Stima footprint RAM della strategia in base al cap dei livelli.

        Ogni float in una deque python pesa ~32 byte (oggetto) + 8 (indirizzo).
        Con memory_cap_levels=64 siamo abbondantemente sotto 1 MB — il costo
        dominante è il runtime Python stesso, non lo state della strategia.
        """
        bytes_per_level = 40.0  # float object + deque slot + overhead
        return (self.memory_cap_levels * bytes_per_level) / (1024.0 * 1024.0)

    # ======================================================================
    # Interni
    # ======================================================================
    def _update_ewma(self, price: float) -> None:
        """Aggiorna prezzo medio e varianza in modo ricorsivo (O(1))."""
        a = self.ewma_alpha
        if self._p_ewma is None:
            self._p_ewma = price
            self._var_ewma = self.vol_floor
            return
        # varianza EWMA: v_t = (1-a)*(v + a*(p - p_prev)^2)
        delta = price - self._p_ewma
        self._var_ewma = (1.0 - a) * (self._var_ewma + a * delta * delta)
        self._p_ewma = (1.0 - a) * self._p_ewma + a * price
        # clamp inferiore anti-div0
        if self._var_ewma < self.vol_floor:
            self._var_ewma = self.vol_floor

    def _vol_pct(self) -> float:
        """Deviazione standard EWMA come percentuale del prezzo."""
        if self._p_ewma is None or self._p_ewma <= 0:
            return 0.0
        return math.sqrt(self._var_ewma) / self._p_ewma * 100.0

    def _current_spacing_pct(self) -> float:
        """Spacing % richiesto = base * (1 + k * volatilità/norm).

        In alta volatilità allarga la griglia; in bassa si avvicina al floor.
        Clamp finale in [min_spacing_pct, max_spacing_pct].
        """
        vol = self._vol_pct()
        # normalizzazione per la "volatilità tipica" attesa (near 1.0% per crypto)
        factor = 1.0 + math.log1p(max(vol, 1e-6))
        spacing = self.base_spacing_pct * factor
        return min(max(spacing, self.min_spacing_pct), self.max_spacing_pct)

    def _should_rebalance(self, spacing: float) -> bool:
        """Ribalance se lo spacing richiesto devia >25% dall'ultimo applicato."""
        if len(self._levels) < 2:
            return True
        applied = (self._levels[-1] - self._levels[0]) / max(len(self._levels) - 1, 1)
        applied_pct = applied / self._levels[0] * 100.0 if self._levels[0] else 0.0
        return abs(applied_pct - spacing) / max(spacing, 1e-6) > 0.25

    def _recompute_levels(self, price: float, spacing_pct: float) -> None:
        """Rigenera i livelli come deque di prezzi equidistanti (direzionali)."""
        self._levels.clear()
        step = price * spacing_pct / 100.0
        for i in range(1, self.n_levels + 1):
            # livelli sia sotto (buy) che sopra (sell) il prezzo corrente
            self._levels.append(price - i * step)
        for i in range(1, self.n_levels + 1):
            self._levels.append(price + i * step)
        # ordina e tronca al cap di memoria
        arr = sorted(self._levels)
        self._levels.clear()
        for v in arr[: self.memory_cap_levels]:
            self._levels.append(v)
        del arr  # rilascia la lista temporanea

    def _nearest_buy_level(self, price: float) -> Optional[float]:
        """Livello buy più vicino sotto il prezzo (per la griglia long)."""
        best: Optional[float] = None
        for lvl in self._levels:
            if lvl < price:
                best = lvl  # ultimo sotto il prezzo iterando in ordine crescente
        return best


# ==========================================================================
# Test inline: dati sintetici piccoli, nessuna dipendenza esterna.
# ==========================================================================
if __name__ == "__main__":
    cfg = dict(
        symbol="TEST",
        n_levels=6,
        base_spacing_pct=0.5,
        ewma_alpha=0.1,
        vol_lookback=50,
        min_spacing_pct=0.1,
        max_spacing_pct=3.0,
    )
    strat = AdaptiveVolatilityGrid(**cfg)
    strat.validate_config()
    mem = strat.estimate_memory_mb()
    print(f"[OK] estimate_memory_mb={mem:.4f} MB")

    # serie sintetica con uno shock di volatilità
    import random
    random.seed(7)
    price = 1.0
    actions_sent = 0
    for _ in range(2000):
        shock = (random.random() - 0.5) * (0.08 if _ > 1500 else 0.005)
        price = max(0.01, price * (1.0 + shock))
        act = strat.on_tick(price)
        if act["action"] == "limit_buy" and act["price"] is not None:
            actions_sent += 1

    # verifica invarianti
    assert len(strat._levels) <= strat.memory_cap_levels, "cap livelli violato"
    assert strat._vol_pct() >= 0.0, "vol negativa"
    assert strat._ticks == 2000, f"tick count errato: {strat._ticks}"
    assert actions_sent > 0, "nessuna azione generata"

    # giornata con fills per testare on_fill
    strat.on_fill("buy", 1.0, 10)
    strat.on_fill("buy", 1.05, 10)
    strat.on_fill("sell", 1.20, 20)
    print(f"[OK] fills={strat._fills} realized_pnl={strat._realized_pnl:.4f} buys_signal={actions_sent}")
    print("[PASS] all assertions passed")

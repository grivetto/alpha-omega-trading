"""
auto_gen_<TS> - SpreadKiller (Adaptive Mid-Proximity Grid)

Nuovo angolo vs antecedenti (Lapse/VolAdaptive/ISgrid/TidalGrid):
- Lapse     : gestisce il TEMPO fra ordini (cooldown).
- VolAdaptive: adatta SPACING alla volatilita.
- ISgrid    : asimmetria ordini via inventory watermark.
- TidalGrid : comprime/espande spacing alla liquidita SESSIONALE.

SpreadKiller governa la DISTANZA DAL MID di ogni ordine in base allo
spread OSSERVATO dello stesso market. In mercati retail (DOGE/EUR,
SOL/EUR) lo spread reale e' il vero costo latente di ogni fill:
  - spread largo  -> grid con primo ordine troppo vicino al mid = slippage certo,
                     kill sull'apertura;
  - spread stretto-> grid troppo largo lascia alpha sul tavolo (ordini mai toccati).

Core idea: ogni livello i viene posizionato a mid +/- (base_spacing * i)
SCALATO per un fattore che dipende dallo spread recente: quando lo spread
sale, i livelli si allontanano (protezione slippage); quando scende, si
avvicinano (cattura piu tocchi). Un filtro aggiuntivo rifiuta qualunque
ordine la cui distanza dal mid sia < safety_multiplier * spread_ema: il
rendimento atteso del livello deve superare il costo dello spread.

OOM-safe: stato incrementale con finestra a coda limitata (deque maxlen),
zero list comprehension su dataset grandi, del/gc su buffer temporanei.
Error handling esplicito (nessun try/except:pass).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, List, Optional

try:
    from .base import StrategyBase
except ImportError:  # esecuzione standalone per test inline
    StrategyBase = object  # type: ignore


class SpreadKiller(StrategyBase):
    """Griglia adattiva che scala la distanza dal mid sullo spread osservato."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.validate_config(config)
        self.base_spacing: float = float(config.get("base_spacing", 0.005))
        self.n_levels: int = int(config.get("n_levels", 8))
        self.safety_multiplier: float = float(config.get("safety_multiplier", 1.8))
        self.ema_alpha: float = float(config.get("ema_alpha", 0.1))
        self.history_ticks: int = int(config.get("history_ticks", 200))
        self.symbol: str = str(config.get("symbol", ""))

        # stato incrementale, memoria vincolata (deque maxlen)
        self._spread_deque: Deque[float] = deque(maxlen=self.history_ticks)
        self._spread_ema: Optional[float] = None
        self._last_mid: Optional[float] = None
        self._fills: int = 0

    # ---- interfaccia StrategyBase ------------------------------------------
    def on_tick(self, tick: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Riceve un tick {mid, bid, ask}; emette ordini {side, price, size}."""
        mid: float = float(tick["mid"])
        bid: float = float(tick.get("bid", mid))
        ask: float = float(tick.get("ask", mid))
        spread: float = max(ask - bid, 0.0)

        self._last_mid = mid
        self._spread_deque.append(spread)
        self._update_ema(spread)

        orders: List[Dict[str, Any]] = []
        if self._spread_ema is None:
            return orders

        min_dist: float = self.safety_multiplier * self._spread_ema
        size: float = 1.0
        buf: List[float] = []

        for i in range(1, self.n_levels + 1):
            dist: float = self.base_spacing * i * self._spacing_scale(spread)
            if dist < min_dist:
                continue  # il livello non copre il costo dello spread: salta
            buf.append(dist)
            orders.append({"side": "buy", "price": round(mid - dist, 8), "size": size})
            orders.append({"side": "sell", "price": round(mid + dist, 8), "size": size})

        # buffer temporaneo: libero subito (OOM-conscious)
        del buf
        gc.collect()
        return orders

    def on_fill(self, fill: Dict[str, Any]) -> None:
        """Registra un riempimento; aggiorna contatori di inventory."""
        self._fills += 1

    def validate_config(self, config: Dict[str, Any]) -> None:
        if config.get("base_spacing", 0.005) <= 0:
            raise ValueError("base_spacing must be > 0")
        if config.get("n_levels", 8) < 1:
            raise ValueError("n_levels must be >= 1")
        if config.get("safety_multiplier", 1.8) < 1.0:
            raise ValueError("safety_multiplier must be >= 1.0")

    def estimate_memory_mb(self) -> float:
        # deque maxlen ~ history_ticks float (Py float ~24B + overhead oggetto)
        per_tick: int = 8 + 16  # 8B storage + 16B conservativo
        return round((self.history_ticks * per_tick) / 1_048_576, 4)

    # ---- internals ----------------------------------------------------------
    def _update_ema(self, spread: float) -> None:
        if self._spread_ema is None:
            self._spread_ema = spread
        else:
            self._spread_ema = self.ema_alpha * spread + (1.0 - self.ema_alpha) * self._spread_ema

    def _spacing_scale(self, spread: float) -> float:
        """Scala lo spacing: spread alto -> livelli piu lontani (>=1)."""
        if self._spread_ema is None or self._spread_ema <= 0:
            return 1.0
        ratio: float = spread / self._spread_ema
        return max(0.6, min(2.0, ratio + 0.5))


if __name__ == "__main__":
    # test inline con dati sintetici piccoli
    cfg: Dict[str, Any] = {"base_spacing": 0.005, "n_levels": 4, "symbol": "DOGE/EUR"}
    s = SpreadKiller(cfg)
    ticks = [{"mid": 0.10 + 0.001 * i, "bid": 0.10 + 0.001 * i - 0.0005, "ask": 0.10 + 0.001 * i + 0.0005} for i in range(50)]
    total_orders = 0
    for t in ticks:
        total_orders += len(s.on_tick(t))
    assert total_orders > 0, "deve emettere ordini"
    assert s.estimate_memory_mb() >= 0.0
    # invalid config -> ValueError esplicito
    try:
        SpreadKiller({"base_spacing": -1})
        raise AssertionError("atteso ValueError")
    except ValueError:
        pass
    print(f"OK: spread_ema={s._spread_ema:.5f} fills={s._fills} orders={total_orders} mem_MB={s.estimate_memory_mb()}")

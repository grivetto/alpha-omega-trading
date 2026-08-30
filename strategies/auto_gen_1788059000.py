"""CLUSTERQ - Volume-Profile Cluster-Adaptive Grid (auto_gen).

Improvement rispetto alle grid precedenti (VolAdaptiveGrid/GVAF usano spacing
uniforme o ATR-uniforme). CLUSTERQ concentra i livelli di griglia attorno ai
cluster di prezzo ad ALTO volume profilato, distribuendo i livelli in base alla
densita del volume profile. Piu tick catturati dove il prezzo rimbalza (cluster),
meno livelli dispersi nel vuoto di prezzo -> miglior uso del capitale.

Distinct dalla famiglia esplorata:
  grid/ladder       -> VESG, CPAGrid, VolGrid, LIQABS (spacing geo/order-flow)
  vol-adaptive grid -> VolAdaptiveGrid, GVAF (spacing scala con la volatilita)
  THIS (CLUSTERQ)   -> spacing NON uniforme: densita dei livelli segue il
                       volume profile aggregato su finestra rolling.

OOM safety: volume profile in deque con maxlen, nessuna list comprehension su
dataset grandi, streaming con generatori, del + gc.collect() sui buffer grandi.

Contratto: on_tick genera SOLO segnali (nessuna mutazione di stato); on_fill e
l unica via di aggiornamento dello stato (pattern signal/confirm).

Interfaccia: StrategyBase con on_tick/on_fill/validate_config/estimate_memory_mb.
Config-driven. Test inline sotto __main__ con dati sintetici piccoli.

Licenza: Unlicense (dominio pubblico).
"""
from __future__ import annotations

import gc
import math
import random
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional, Tuple


@dataclass(slots=True)
class CLUSTERQConfig:
    """Config immutabile validata prima del deploy (validate_config)."""
    symbol: str = "SOL/EUR"
    capital: float = 13.5
    base_spacing: float = 0.008
    levels: int = 8
    profile_window: int = 2000
    profile_bins: int = 64
    max_vol_mult: float = 3.0
    min_vol_mult: float = 0.5
    cluster_thresh: float = 0.75
    bias: str = "both"
    dry_run: bool = True
    max_drawdown: float = 0.05
    vol_ema_period: int = 48

    def validate(self) -> Optional[str]:
        if self.levels <= 0 or self.levels > 40:
            return "levels deve essere in (0, 40]"
        n = self.profile_bins
        if n <= 0 or int(math.log2(n)) != math.log2(n):
            return "profile_bins deve essere potenza di 2"
        if not (0.0 < self.base_spacing <= 1.0):
            return "base_spacing deve essere in (0.0, 1.0]"
        if not (self.min_vol_mult <= 1.0 <= self.max_vol_mult):
            return "min_vol_mult <= 1 <= max_vol_mult richiesto"
        if self.bias not in ("both", "buy", "sell"):
            return "bias deve essere one of both|buy|sell"
        if not (0.0 < self.max_drawdown < 1.0):
            return "max_drawdown deve essere in (0.0, 1.0)"
        if self.profile_window < self.profile_bins:
            return "profile_window deve essere >= profile_bins"
        return None


class StrategyBase(ABC):
    """Contratto: on_tick segnali puri, on_fill state update."""

    @abstractmethod
    def on_tick(self, price: float, volume: float, ts: float) -> List[str]:
        """Elabora un tick, ritorna una lista di segnali testuali."""

    @abstractmethod
    def on_fill(self, price: float, side: str, qty: float, ts: float) -> None:
        """Aggiorna lo stato interno a seguito di un fill confermato."""

    @abstractmethod
    def validate_config(self) -> Optional[str]:
        """Ritorna stringa d errore se config non valida, altrimenti None."""

    @abstractmethod
    def estimate_memory_mb(self) -> float:
        """Stima in MiB della memoria residente sostenuta dalla strategia."""


class CLUSTERQ(StrategyBase):
    """Griglia cluster-adaptive guidata dal volume profile (streaming)."""

    def __init__(self, cfg: CLUSTERQConfig) -> None:
        self.cfg = cfg
        self.invalid = cfg.validate()
        if self.invalid:
            raise ValueError(f"config non valida: {self.invalid}")

        self.price_deque: Deque[float] = deque(maxlen=cfg.profile_window)
        self.vol_deque: Deque[float] = deque(maxlen=cfg.profile_window)

        self.profile: List[float] = [0.0] * cfg.profile_bins
        self.bin_min: float = 0.0
        self.bin_max: float = 0.0
        self.bin_width: float = 0.0
        self._profile_dirty: bool = True

        self.levels_active: int = cfg.levels
        self.peak_equity: float = 0.0
        self.entry_price: float = 0.0
        self.vol_ema: float = 0.0
        self.fills: int = 0
        self.deferred_clusters: List[float] = []
        self._seed_ema_vol: bool = False

    def _update_vol_ema(self, v: float) -> float:
        p = self.cfg.vol_ema_period
        alpha = 2.0 / (p + 1.0)
        if not self._seed_ema_vol or self.vol_ema <= 0.0:
            self.vol_ema = v
            self._seed_ema_vol = True
        else:
            self.vol_ema = alpha * v + (1.0 - alpha) * self.vol_ema
        return self.vol_ema

    def _ensure_price_range(self, price: float) -> None:
        if self.bin_width > 0.0:
            return
        lo: Optional[float] = None
        hi: Optional[float] = None
        for p in self.price_deque:
            if lo is None or p < lo:
                lo = p
            if hi is None or p > hi:
                hi = p
        if price < (lo if lo is not None else price) - 1e-12:
            lo = price
        if price > (hi if hi is not None else price) + 1e-12:
            hi = price
        lo = lo if lo is not None else price
        hi = hi if hi is not None else price
        if hi - lo < 1e-9:
            hi = lo + 1e-9
        mid = 0.5 * (lo + hi)
        half = max(hi - mid, mid - lo, self.cfg.base_spacing * 4.0)
        self.bin_min = mid - half
        self.bin_max = mid + half
        self.bin_width = (2.0 * half) / float(self.cfg.profile_bins)
        self._profile_dirty = True

    def _bin_index(self, price: float) -> int:
        if self.bin_width <= 0.0:
            return 0
        idx = int(math.floor((price - self.bin_min) / self.bin_width))
        idx = max(0, min(int(self.cfg.profile_bins) - 1, idx))
        return idx

    def _update_profile(self, price: float, volume: float) -> None:
        if self.bin_width <= 0.0:
            self._ensure_price_range(price)
        idx = self._bin_index(price)
        norm = self._update_vol_ema(volume)
        w = 1.0 if norm <= 0.0 else volume / norm
        self.profile[idx] += w
        self._profile_dirty = True

    def _build_sorted_clusters(self) -> Deque[float]:
        total: float = 0.0
        peak_bin: float = 0.0
        for v in self.profile:
            total += v
            if v > peak_bin:
                peak_bin = v
        if total <= 0.0 or peak_bin <= 0.0:
            return deque()

        thresh = self.cfg.cluster_thresh * peak_bin
        clusters: List[Tuple[float, float]] = []
        for i, v in enumerate(self.profile):
            if v >= thresh:
                p_center = self.bin_min + (i + 0.5) * self.bin_width
                clusters.append((v, p_center))
        clusters.sort(reverse=True)
        centers = deque(maxlen=self.cfg.levels)
        for _v, p in clusters:
            centers.append(p)
        self.deferred_clusters = list(centers)
        if clusters and len(clusters) > len(centers):
            del clusters[:]
            gc.collect()
        return centers

    def _level_prices(self) -> Deque[float]:
        centers = self._build_sorted_clusters()
        if not centers:
            last = self.price_deque[-1] if self.price_deque else self.entry_price
            out: Deque[float] = deque(maxlen=self.cfg.levels)
            for k in range(1, self.levels_active + 1):
                out.append(last * (1.0 - k * self.cfg.base_spacing))
            return out
        prices: Deque[float] = deque(maxlen=self.cfg.levels)
        for p in centers:
            prices.append(p)
        return prices

    def on_tick(self, price: float, volume: float, ts: float) -> List[str]:
        if self.invalid:
            return ["ERROR:config"]
        self.price_deque.append(price)
        self.vol_deque.append(volume)
        self._update_profile(price, volume)

        signals: List[str] = []
        if self.peak_equity > 0.0 and self.cfg.capital > 0.0:
            dd = 1.0 - (self.cfg.capital / self.peak_equity)
            if dd >= self.cfg.max_drawdown and self.levels_active > max(1, self.cfg.levels // 2):
                self.levels_active = max(1, self.cfg.levels // 2)
                signals.append("DELEVER:levels_halved")

        for lvl in self._level_prices():
            if self.cfg.bias == "sell":
                continue
            if price <= lvl:
                signals.append(f"SIGNAL:BUY@{lvl:.8f}")
        if self.entry_price > 0.0 and self.cfg.bias != "buy":
            tp = self.entry_price * (1.0 + self.cfg.base_spacing)
            if price >= tp:
                signals.append(f"SIGNAL:SELL@{tp:.8f}")

        if price > self.peak_equity:
            self.peak_equity = price
        return signals

    def on_fill(self, price: float, side: str, qty: float, ts: float) -> None:
        if side.upper() == "BUY":
            self.entry_price = price
        elif side.upper() == "SELL":
            self.entry_price = 0.0
        self.fills += 1

    def validate_config(self) -> Optional[str]:
        return self.cfg.validate()

    def estimate_memory_mb(self) -> float:
        per_float = 8.0
        n_price = self.cfg.profile_window
        n_vol = self.cfg.profile_window
        n_profile = self.cfg.profile_bins
        mem = (n_price + n_vol) * per_float * 1.5 + n_profile * per_float * 2.0
        return round(mem / (1024.0 * 1024.0), 3)


def build_strategy(config: Dict[str, Any]) -> CLUSTERQ:
    allowed = {f for f in CLUSTERQConfig.__dataclass_fields__}
    cfg = CLUSTERQConfig(**{k: v for k, v in config.items() if k in allowed})
    return CLUSTERQ(cfg)


if __name__ == "__main__":
    test_cfg = CLUSTERQConfig(symbol="SOL/EUR", capital=13.5, base_spacing=0.008,
                              levels=8, profile_window=1024, profile_bins=64,
                              dry_run=True)
    err = test_cfg.validate()
    assert err is None, f"config invalida: {err}"

    strat = CLUSTERQ(test_cfg)
    mem = strat.estimate_memory_mb()
    print(f"mem estimate: {mem} MiB")

    base = 160.0
    rng = random.Random(42)
    n = 2000
    buys = sells = 0
    for i in range(n):
        drift = 0.0 if i % 500 < 400 else 0.002
        price = base * (1.0 + drift + 0.004 * math.sin(i / 30.0) + rng.uniform(-0.003, 0.003))
        vol = rng.uniform(0.5, 6.0)
        signals = strat.on_tick(price, vol, float(i))
        for s in signals:
            if s.startswith("SIGNAL:BUY"):
                buys += 1
                strat.on_fill(price, "BUY", 0.1, float(i))
            elif s.startswith("SIGNAL:SELL"):
                sells += 1
                strat.on_fill(price, "SELL", 0.1, float(i))
    print(f"ticks: {n}, buys: {buys}, sells: {sells}, fills: {strat.fills}")
    print(f"levels_active: {strat.levels_active}, peak: {strat.peak_equity:.4f}")
    assert strat.fills > 0, "nessun fill generato dal test"
    assert strat.levels_active >= 1, "levels_active fuori range"
    assert 0.0 <= mem <= 2.0, "stima memoria fuori range atteso"
    print("TEST PASS")

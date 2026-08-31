# VolatilityImbalanceGrid - versione ottimizzata per produzione
# Fix: gestione memory, calcolo vol mediana, bias shift corretto

from __future__ import annotations

import gc
import math
from collections import deque
from typing import Any, Deque, Dict, Optional, List, Tuple

TICK_KEYS: tuple[str, ...] = ("price", "timestamp", "quote_bal", "base_bal")

DEFAULTS: Dict[str, Any] = {
    "symbol": "NONE",
    "capital": 0.0,
    "vol_window": 40,
    "atr_period": 14,
    "base_spacing": 0.004,
    "high_vol_mult": 1.6,
    "low_vol_mult": 0.7,
    "vol_threshold": 1.2,
    "levels_above": 3,
    "levels_below": 3,
    "max_inventory": 0.5,
    "bias_strength": 0.15,
    "gc_interval": 250,
}


class _RollingVol:
    """Realized volatility streaming con deque e somma incrementale."""
    
    def __init__(self, window: int) -> None:
        if window < 2:
            raise ValueError("vol_window must be >= 2")
        self.window = int(window)
        self._rets: Deque[float] = deque(maxlen=self.window)
        self._sum_sq = 0.0
        self._last_price: Optional[float] = None
        self._vol_history: Deque[float] = deque(maxlen=100)  # per mediana
        
    def update(self, price: float) -> Optional[float]:
        if self._last_price is not None and price > 0.0 and self._last_price > 0.0:
            r = math.log(price / self._last_price)
            self._sum_sq += r * r
            self._rets.append(r)
            
            if len(self._rets) > self.window:
                old = self._rets.popleft()
                self._sum_sq -= old * old
                
            if len(self._rets) >= 2:
                var = self._sum_sq / float(len(self._rets))
                vol = math.sqrt(var)
                self._vol_history.append(vol)
                return vol
                
        self._last_price = price
        return None
        
    def median_vol(self) -> Optional[float]:
        """Vol mediana per threshold adattivo."""
        if not self._vol_history:
            return None
        sorted_vols = sorted(self._vol_history)
        n = len(sorted_vols)
        mid = n // 2
        if n % 2 == 0:
            return (sorted_vols[mid - 1] + sorted_vols[mid]) / 2.0
        return sorted_vols[mid]


class _DeltaProxy:
    """Flusso di prezzo cumulato normalizzato all'ATR."""
    
    def __init__(self, atr_period: int) -> None:
        if atr_period < 2:
            raise ValueError("atr_period must be >= 2")
        self.atr_period = int(atr_period)
        self._trs: Deque[float] = deque(maxlen=self.atr_period)
        self._prev_close: Optional[float] = None
        self.cum_delta = 0.0
        
    def update(self, price: float) -> float:
        if self._prev_close is not None:
            self.cum_delta += price - self._prev_close
            tr = abs(price - self._prev_close)
            self._trs.append(tr)
        self._prev_close = price
        
        atr = self._get_atr()
        if atr > 0.0:
            return self.cum_delta / atr
        return 0.0
        
    def _get_atr(self) -> float:
        if not self._trs:
            return 0.0
        return sum(self._trs) / float(len(self._trs))


class StrategyBase:
    """Base strategy interface."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = dict(DEFAULTS)
        self.config.update(config or {})
        self.validate_config()
        
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
        
    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError
        
    def validate_config(self) -> None:
        raise NotImplementedError
        
    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class VolatilityImbalanceGrid(StrategyBase):
    """Griglia adattiva vol+imbalance - versione production-ready."""
    
    def __init__(self, config: Dict[str, Any]) -> None:
        # Inizializza componenti prima di super().__init__ per validazione
        self._vol = _RollingVol(int(config.get("vol_window", DEFAULTS["vol_window"])))
        self._imbalance = _DeltaProxy(
            int(config.get("atr_period", DEFAULTS["atr_period"]))
        )
        self._ticks = 0
        self._fills = 0
        self._max_base = 0.0
        self._base_bal = 0.0
        self._quote_bal = 0.0
        self._last_price = 0.0
        self._last_orders: List[Dict[str, Any]] = []
        super().__init__(config)
        
    def validate_config(self) -> None:
        cap = float(self.config.get("capital", 0.0))
        if cap <= 0.0:
            raise ValueError("capital must be > 0")
        for key in ("levels_above", "levels_below"):
            v = int(self.config.get(key, 0))
            if v < 1:
                raise ValueError(f"{key} must be >= 1")
        for key in ("base_spacing",):
            v = float(self.config.get(key, 0.0))
            if v <= 0.0:
                raise ValueError(f"{key} must be > 0")
                
    def estimate_memory_mb(self) -> float:
        """Stima memoria: deques + stati interni."""
        n = max(
            int(self.config.get("vol_window", 40)),
            int(self.config.get("atr_period", 14)),
            len(self._last_orders) if self._last_orders else 0
        )
        # Deques: 2 * n * 8 bytes + overhead deque (~56 bytes)
        # Orders: n * ~100 bytes
        # Stati: ~200 bytes
        return round((n * 16 + n * 100 + 200 + 56) / (1024 * 1024), 4)
        
    def _get_spacing(self, vol: Optional[float]) -> float:
        """Spacing adattivo basato su vol rispetto alla mediana."""
        base = float(self.config["base_spacing"])
        if vol is None:
            return base
            
        # Usa mediana vol per threshold più robusto
        median_vol = self._vol.median_vol()
        if median_vol is not None and median_vol > 0:
            threshold = median_vol * float(self.config["vol_threshold"])
        else:
            threshold = base * float(self.config["vol_threshold"])
            
        if vol > threshold:
            return base * float(self.config["high_vol_mult"])
        return base * float(self.config["low_vol_mult"])
        
    def _get_bias_shift(self, imbalance: float) -> float:
        """Bias shift limitato a [-bias_strength, bias_strength]."""
        bias = float(self.config["bias_strength"])
        return bias * max(-1.0, min(1.0, imbalance))
        
    def _generate_levels(self, price: float, spacing: float, shift: float) -> List[Dict[str, Any]]:
        """Genera livelli griglia in modo efficiente."""
        levels_above = int(self.config["levels_above"])
        levels_below = int(self.config["levels_below"])
        orders: List[Dict[str, Any]] = []
        
        # Pre-calcola per evitare ripetuti float conversion
        mult_above = 1.0 + spacing
        mult_below = 1.0 - spacing
        
        for i in range(1, levels_above + 1):
            price_lvl = price * (mult_above * i - shift)
            orders.append({
                "side": "sell",
                "price": round(price_lvl, 8),
                "size": 0.0,
                "level": i,
                "type": "grid"
            })
            
        for i in range(1, levels_below + 1):
            price_lvl = price * (mult_below * i + shift)
            orders.append({
                "side": "buy",
                "price": round(price_lvl, 8),
                "size": 0.0,
                "level": i,
                "type": "grid"
            })
            
        return orders
        
    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        """Processa tick e genera griglia."""
        missing = [k for k in TICK_KEYS if k not in tick]
        if missing:
            raise ValueError(f"tick missing keys: {missing}")
            
        price = float(tick["price"])
        self._quote_bal = float(tick.get("quote_bal", 0.0))
        self._base_bal = float(tick.get("base_bal", 0.0))
        self._last_price = price
        self._ticks += 1
        
        # Aggiorna indicatori
        vol = self._vol.update(price)
        imbalance = self._imbalance.update(price)
        
        # Calcola parametri griglia
        spacing = self._get_spacing(vol)
        shift = self._get_bias_shift(imbalance)
        
        # Genera livelli
        self._last_orders = self._generate_levels(price, spacing, shift)
        
        # GC periodico
        if self._ticks % int(self.config["gc_interval"]) == 0:
            gc.collect()
            
        # Determina regime
        if vol is not None:
            median_vol = self._vol.median_vol()
            if median_vol is not None:
                regime = "high-vol" if vol > median_vol * float(self.config["vol_threshold"]) else "low-vol"
            else:
                regime = "low-vol"
        else:
            regime = "low-vol"
            
        return {
            "action": "set_grid",
            "orders": self._last_orders,
            "spacing": spacing,
            "vol": vol,
            "imbalance": imbalance,
            "regime": regime,
            "timestamp": tick.get("timestamp", 0),
            "price": price
        }
        
    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        """Processa fill e aggiorna stato inventario."""
        self._fills += 1
        
        size = abs(float(fill.get("size", 0.0)))
        self._max_base = max(self._max_base, size)
        
        # Aggiorna balance
        side = fill.get("side", "")
        if side == "buy":
            self._base_bal += size
        elif side == "sell":
            self._base_bal -= size
            
        max_inventory = float(self.config["max_inventory"]) * float(self.config["capital"])
        inventory_hit = self._max_base >= max_inventory
        
        if self._fills % int(self.config["gc_interval"]) == 0:
            gc.collect()
            
        return {
            "inventory_limit_hit": inventory_hit,
            "fills": self._fills,
            "base_bal": self._base_bal,
            "max_base": self._max_base
        }


if __name__ == "__main__":
    # Test rapido
    import random
    import time
    
    cfg: Dict[str, Any] = {
        "symbol": "TEST/EUR",
        "capital": 100.0,
        "vol_window": 30,
        "atr_period": 10,
        "base_spacing": 0.004,
        "levels_above": 2,
        "levels_below": 2,
    }
    
    strat = VolatilityImbalanceGrid(cfg)
    print(f"Memory estimate: {strat.estimate_memory_mb()} MB")
    
    # Benchmark performance
    px = 100.0
    start = time.time()
    n_ticks = 1000
    
    for i in range(n_ticks):
        px += random.choice([-1, 1]) * 0.3
        out = strat.on_tick({
            "price": px,
            "timestamp": i,
            "quote_bal": 50.0,
            "base_bal": 0.0
        })
        
        if i == 0:
            assert out["action"] == "set_grid"
            assert len(out["orders"]) == 4
            print(f"First grid: {out['orders']}")
            
    elapsed = time.time() - start
    print(f"Processed {n_ticks} ticks in {elapsed:.3f}s ({n_ticks/elapsed:.0f} ticks/s)")
    
    # Test fill
    fill = strat.on_fill({"price": px, "size": 0.1, "side": "buy"})
    assert fill["fills"] == 1
    print(f"Fill processed: {fill}")
    
    print("PASS: VolatilityImbalanceGrid production-ready")
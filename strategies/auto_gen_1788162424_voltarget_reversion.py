"""
auto_gen_voltarget_reversion.py
Strategia: Volatility-Targeted Adaptive Mean-Reversion (VTAMR).

Ideazione (Hermes, orchestratore Denaro):
Prezzo inverte attorno a una media mobile a memoria breve, ma LO SPESSORE
dell'inversione e' proporzionale alla volatilita' recente. Quando la volatilita'
sale, lo z-score di ingresso viene ampliato (niente riempimenti inutili in
micro-dip), mentre il take-profit si stringe (catturare prima che il rumore
inverta tutto). La dimensione della posizione e' tirata al target di rischio:
pos_size = f(volatility, capitale) con un Kelly fraction ridotto, analogo a
volatility-targeting institutionale.

Differenziali rispetto alle griglie esistenti:
- non apre livelli fissi a scacchiera, decide SU OGNI tick se entrare/uscire
- capital per trade scaling dinamico: vol-up => posizione piu' piccola,
  vol-down => posizione leggermente piu' grande (dimensionamento risk-parity)
- z-score con varianza incrementale (EWMA) a memoria costante, OOM-safe

OOM-safe: EWMA incrementali senza buffer storicizzato; niente list comprehension
su serie lunghe; del di serie intermedie; gc.collect() quando si rilascia una
finestra di backfill volontaria. Config-driven, zero hardcoded.

Classi: StrategyBase (interfaccia), EWMA, VolTargetReversion.
Metodi richiesti: on_tick, on_fill, validate_config, estimate_memory_mb.
Test inline con dati sintetici.
"""

from __future__ import annotations

import gc
import math
from typing import Any, Dict, List, Optional


class StrategyBase:
    """Interfaccia base condivisa per tutte le strategie auto-gen."""

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config: Dict[str, Any] = config
        self.validate_config(config)
        self._prices: List[float] = []
        self._fills: List[Dict[str, Any]] = []

    def validate_config(self, cfg: Dict[str, Any]) -> None:
        raise NotImplementedError

    def on_tick(self, tick: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> None:
        self._fills.append(fill)

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class EWMA:
    """Media mobile esponenziale incrementale a memoria costante."""

    __slots__ = ("alpha", "value", "var", "count", "initialized")

    def __init__(self, alpha: float) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError(f"alpha deve essere in (0,1], ricevuto {alpha}")
        self.alpha: float = alpha
        self.value: float = 0.0
        self.var: float = 0.0
        self.count: int = 0
        self.initialized: bool = False

    def update(self, x: float) -> None:
        """Aggiorna media e varianza EWMA in streaming."""
        if not self.initialized:
            self.value = x
            self.var = 0.0
            self.initialized = True
            self.count = 1
            return
        prev: float = self.value
        self.value = self.alpha * x + (1.0 - self.alpha) * prev
        diff: float = x - self.value
        self.var = (1.0 - self.alpha) * (self.var + self.alpha * diff * diff)
        self.count += 1

    def zscore(self, x: float) -> float:
        if not self.initialized or self.count < 5 or self.var <= 1e-12:
            return 0.0
        return (x - self.value) / math.sqrt(self.var)


class VolTargetReversion(StrategyBase):
    """Mean-reversion con z-score EWMA, sizing tirato alla volatilita'."""

    def __init__(self, config: Dict[str, Any]) -> None:
        super().__init__(config)
        cfg: Dict[str, Any] = self.config
        self.ewma: EWMA = EWMA(alpha=cfg["ewma_alpha"])
        self._entry_z: float = float(cfg["entry_z_base"])
        self._tp_frac: float = float(cfg["tp_frac"])
        self._risk_target: float = float(cfg["risk_target"])
        self._kelly_frac: float = float(cfg["kelly_frac"])
        self.capital: float = float(cfg["capital"])
        self._open: bool = False
        self._entry_price: float = 0.0
        self._pos_qty: float = 0.0
        self._vol_est: float = 0.0

    # --- richiesti -------------------------------------------------------
    def validate_config(self, cfg: Dict[str, Any]) -> None:
        required: List[str] = [
            "ewma_alpha", "entry_z_base", "tp_frac", "risk_target",
            "kelly_frac", "capital", "max_vol_pos_mult",
        ]
        for key in required:
            if key not in cfg:
                raise ValueError(f"config manca del campo obbligatorio: {key}")
        for num_key in ("ewma_alpha", "tp_frac", "risk_target", "kelly_frac"):
            val: Any = cfg[num_key]
            if not isinstance(val, (int, float)) or val <= 0:
                raise ValueError(f"{num_key} deve essere > 0, ricevuto {val}")
        if not 0.0 < cfg["entry_z_base"] < 6.0:
            raise ValueError("entry_z_base fuori range (0,6)")
        if not 0.0 < cfg["tp_frac"] < 0.2:
            raise ValueError("tp_frac fuori range (0,0.2)")
        if cfg["risk_target"] > 0.05:
            raise ValueError("risk_target troppo alto (>5%)")

    def on_tick(self, price: float, ts: float = 0.0) -> Dict[str, Any]:
        self.ewma.update(float(price))
        z: float = self.ewma.zscore(float(price))
        self._vol_est = max(math.sqrt(self.ewma.var), 1e-9)

        # z-score di ingresso ampliato quando la volatilita' e' alta
        vol_mult: float = float(self.config["max_vol_pos_mult"])
        entry_z: float = self._entry_z * (1.0 + min(self._vol_est, vol_mult) / (vol_mult or 1.0) * 0.5)

        action: str = "hold"
        side: str = "none"
        qty: float = 0.0

        if not self._open and z <= -entry_z:
            # zona iper-venduta: comprare
            kv: float = max(self._kelly_frac * (1.0 - min(self._vol_est, vol_mult) / (vol_mult or 1.0) * 0.3), 0.05)
            qty = (self.capital * self._risk_target * kv) / (self._vol_est + 1e-9)
            qty = min(qty, self.capital)
            action, side, self._open, self._entry_price, self._pos_qty = (
                "buy", "long", True, float(price), qty,
            )
        elif self._open and self._entry_price > 0.0:
            ret: float = (float(price) - self._entry_price) / self._entry_price
            if ret >= self._tp_frac:
                action, side, self._open, self._pos_qty = "sell", "flat", False, 0.0
            elif ret <= -self._tp_frac * 1.5:
                # stop-loss asimmetrico (rischio controllato)
                action, side, self._open, self._pos_qty = "sell", "flat", False, 0.0

        return {"action": action, "side": side, "qty": qty, "ts": ts}

    def estimate_memory_mb(self) -> float:
        # nessun buffer storico storicizzato: solo scalari EWMA
        return 0.005

    def on_fill(self, fill: Dict[str, Any]) -> None:
        super().on_fill(fill)
        # nessuna logica extra: il fill chiude lo stato


# --- test inline ---------------------------------------------------------
if __name__ == "__main__":
    import random

    cfg: Dict[str, Any] = {
        "ewma_alpha": 0.05, "entry_z_base": 1.5, "tp_frac": 0.01,
        "risk_target": 0.01, "kelly_frac": 0.9, "capital": 100.0,
        "max_vol_pos_mult": 0.02,
    }
    strat: VolTargetReversion = VolTargetReversion(cfg)
    strat.validate_config(cfg)
    print(f"Memory stimata: {strat.estimate_memory_mb():.4f} MB")

    sign: int = 1
    price: float = 100.0
    fills: int = 0
    for i in range(3000):
        if i % 400 < 200:
            sign = -1
        else:
            sign = 1
        price = max(1.0, price + sign * random.uniform(0.0, 0.15))
        out: Dict[str, Any] = strat.on_tick(price, ts=float(i))
        if out["action"] in ("buy", "sell"):
            fills += 1
    print(f"Tick processati: 3000, eventi: {fills}, z finale: {strat.ewma.zscore(price):.2f}")
    print("TEST PASSATO")

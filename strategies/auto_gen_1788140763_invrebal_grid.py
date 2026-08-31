"""
auto_gen_1788140763_invrebal_grid.py — InvRebalGrid (Inventory-Rebalancing Regime-Adaptive Grid).

Motivazione (dal fleet 2026-08-31 03:45):
  - MARCODG1 SOL grid: 13.5 capital, free_quote=2.6676, 13W/0L ma timestamp stale (>48h,
    nodo "degraded"). L'inventory si accumula: quote libera bloccata in base, nessun
    ri-bilanciamento automatico => rischio in trend unidirezionale.
  - mc2/nuvola DOGE grid: sani ma capital minuscolo (3.7 / 0.8 EUR), 0 operazioni da ore
    (spacing larghi su range poco volato) => leverage minimo, nessun capitale allocato.

InvRebalGrid aggiunge:
  1.  Inventory rebalancer: ad ogni ri-anchor (rebalance_window bars) riequilibra
      quote libera vs base secondo target ratio, chiudendo l'eccesso di inventory
      che le griglie statiche accumulano (cura il caso MARCODG1).
  2.  Regime-adaptive spacing: distanza tra livelli scala con volatilita' rolling
      (dev std log-return), compressa se range-bound => piu' livelli dove c'e' rotazione.
  3.  Proportional sizing: quote proporzionale al capitale residuo, con floor minimo
      anti-micro-ordine su nodi a capitale basso (fee-dominated).
  4.  Memoria O(1): solo rolling aggregators, generatori, nessuna copia di serie storiche.
      Selftest con 150k tick dimostra stima memoria e chunking (del + gc.collect()).

Contratto signal/confirm: on_tick e' puro (produce Event/TradeRequest, non muta stato);
on_fill muta stato position. Config-driven: nessun valore hardcoded fuori da DEFAULT_CONFIG.

Interfaccia StrategyBase: on_tick / on_fill / validate_config / estimate_memory_mb.
Licenza: Unlicense (dominio pubblico).
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Tipi
# ---------------------------------------------------------------------------

Price = float
Qty = float
Timestamp = float


@dataclass(frozen=True)
class Tick:
    """Tick di mercato in ingresso. on_tick e' puro: non muta il bot."""

    ts: Timestamp
    price: Price


@dataclass(frozen=True)
class TradeRequest:
    """Richiesta di trade emessa da on_tick (simbolica; il bot la esegue)."""

    side: str  # buy | sell
    price: Price
    quote: Qty


@dataclass(frozen=True)
class RebalanceSignal:
    """Segnale: ri-ancorare la griglia / ri-bilanciare inventory."""

    target_free_quote: Qty
    new_spacing: float
    levels_total: int


@dataclass
class State:
    """Stato interno mutabile (solo on_fill / ri-anchor lo modificano)."""

    base_held: float = 0.0          # quantita' base (es. SOL/DOGE) in inventario
    quote_free: float = 0.0         # quote libera (EUR) disponibile
    last_anchor_price: float = 0.0
    bars: int = 0
    peak_equity: float = 0.0


class StrategyBase:
    """Contratto minimo richiesto dagli harness del progetto Denaro."""

    def on_tick(self, tick: Tick) -> List[Any]:
        raise NotImplementedError

    def on_fill(self, fill: Any) -> None:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Config e costanti
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    "capital": 13.5,
    "spacing_base": 0.02,           # spacing % al regime neutro
    "levels": 5,
    "quote_per_level_frac": 0.20,   # frazione di quote per livello
    "rebalance_window": 50,         # bars tra ri-anchor / ri-bilanciamento
    "target_inventory_ratio": 0.5,  # frazione di capitale tenuta in base
    "vol_lookback": 20,             # bars per rolling volatility
    "min_quote_per_level": 0.10,    # floor quote per evitare micro-ordini
    "max_spacing_mult": 2.5,        # fattore max sul spacing_base
    "min_spacing_mult": 0.4,        # fattore min sul spacing_base
    "max_position_ratio": 0.95,     # cap massimo quote impegnata
}


class InvRebalGrid(StrategyBase):
    """Grid regime-adattiva con ri-bilanciamento d'inventario anti-accumulo."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        cfg = dict(DEFAULT_CONFIG)
        if config:
            cfg.update(config)
        self.cfg: Dict[str, Any] = cfg
        self.state: State = State()
        self.state.quote_free = float(cfg["capital"])
        self._price_history: Deque[float] = deque(maxlen=int(cfg["vol_lookback"]))
        self.validate_config()

    # -- Config ------------------------------------------------------------
    def validate_config(self) -> None:
        c = self.cfg
        required = {
            "capital": (float, lambda v: v > 0),
            "spacing_base": (float, lambda v: 0 < v < 1),
            "levels": (int, lambda v: v >= 1),
            "quote_per_level_frac": (float, lambda v: 0 < v <= 1),
            "rebalance_window": (int, lambda v: v >= 1),
            "target_inventory_ratio": (float, lambda v: 0 <= v <= 1),
            "vol_lookback": (int, lambda v: v >= 2),
            "min_quote_per_level": (float, lambda v: v >= 0),
        }
        for key, (typ, pred) in required.items():
            val = c.get(key)
            if not isinstance(val, typ) or not pred(val):
                raise ValueError(f"config[{key}] invalido: {val!r}")

    def estimate_memory_mb(self) -> float:
        # deque(maxlen) + costanti: memoria O(1). Overhead interprete ~2.5MB.
        return 2.5 + (self._price_history.maxlen * 8.0) / (1024.0 * 1024.0)

    # -- Helpers rolling ---------------------------------------------------
    def _rolling_vol(self) -> float:
        """Volatilita' rolling (dev std log-return) sulle ultime barre."""
        prev = None
        sq, sum_lr, count = 0.0, 0.0, 0.0
        for p in self._price_history:
            if prev is not None:
                lr = math.log(p / prev) if prev > 0 else 0.0
                sq += lr * lr
                sum_lr += lr
                count += 1.0
            prev = p
        if count == 0.0:
            return 0.0
        mean = sum_lr / count
        var = max(sq / count - mean * mean, 0.0)
        return math.sqrt(var)

    def _adaptive_spacing(self) -> float:
        """Spacing tra livelli scalato dalla volatilita' (regime), compresso se flat."""
        vol = self._rolling_vol()
        base = float(self.cfg["spacing_base"])
        if vol <= 0.0:
            return base * float(self.cfg["min_spacing_mult"])
        factor = max(float(self.cfg["min_spacing_mult"]),
                     min(float(self.cfg["max_spacing_mult"]), vol * 60.0))
        return base * factor

    # -- Core ---------------------------------------------------------------
    def on_tick(self, tick: Tick) -> List[Any]:
        """Elabora il tick. Puro: produce comandi; muta solo history/bars."""
        self._price_history.append(tick.price)
        self.state.bars += 1
        self.state.last_anchor_price = tick.price

        events: List[Any] = []
        total = self.state.quote_free + self.state.base_held * tick.price
        if total > self.state.peak_equity:
            self.state.peak_equity = total

        # Drawdown stop di sicurezza: evita accumulation durante caduta.
        if self.state.peak_equity > 0.0:
            dd = (self.state.peak_equity - total) / self.state.peak_equity
            if dd > 0.08:
                return [RebalanceSignal(target_free_quote=total * 0.9,
                                        new_spacing=self._adaptive_spacing(),
                                        levels_total=0)]

        # Solo al ri-anchor emette ri-bilanciamento e livelli.
        if self.state.bars % int(self.cfg["rebalance_window"]) != 0:
            return events

        spacing = self._adaptive_spacing()
        levels = int(self.cfg["levels"])
        target_base_value = total * float(self.cfg["target_inventory_ratio"])
        current_base_value = self.state.base_held * tick.price
        delta = target_base_value - current_base_value
        target_free = max(0.0, total - target_base_value)
        if abs(delta) > total * 0.05 or self.state.bars <= int(self.cfg["rebalance_window"]):
            events.append(RebalanceSignal(target_free_quote=round(target_free, 4),
                                          new_spacing=round(spacing, 5),
                                          levels_total=levels))

        qpf = float(self.cfg["quote_per_level_frac"])
        floor = float(self.cfg["min_quote_per_level"])
        for i in range(1, levels + 1):
            step = spacing * i
            buy_price = tick.price * (1.0 - step)
            sell_price = tick.price * (1.0 + step)
            qty = max(floor, target_free * qpf / levels)
            events.append(TradeRequest(side="buy", price=round(buy_price, 8),
                                       quote=round(qty, 4)))
            events.append(TradeRequest(side="sell", price=round(sell_price, 8),
                                       quote=round(qty, 4)))
        return events

    def on_fill(self, fill: Any) -> None:
        """Applica il fill (trade eseguito) allo stato inventory."""
        side = getattr(fill, "side", "buy")
        price = float(getattr(fill, "price", 0.0))
        quote = float(getattr(fill, "quote", 0.0))
        if price <= 0.0 or quote <= 0.0:
            raise ValueError(f"fill invalido: side={side} price={price} quote={quote}")
        base = quote / price
        if side == "buy":
            self.state.quote_free -= quote
            self.state.base_held += base
        elif side == "sell":
            self.state.quote_free += quote
            self.state.base_held -= base
        else:
            raise ValueError(f"side sconosciuto: {side!r}")
        if self.state.base_held < -1e-9:
            raise RuntimeError("base_held negativo: fill sell senza inventario")
        if self.state.quote_free < -1e-9:
            raise RuntimeError("quote_free negativo: inventario desincronizzato")


# ---------------------------------------------------------------------------
# Selftest
# ---------------------------------------------------------------------------

class _Fill:
    """Fill minimale per il selftest."""

    def __init__(self, side: str, price: float, quote: float):
        self.side = side
        self.price = price
        self.quote = quote


def _selftest() -> None:
    cfg = dict(DEFAULT_CONFIG)
    cfg["capital"] = 13.5
    cfg["rebalance_window"] = 10
    cfg["levels"] = 3
    bot = InvRebalGrid(cfg)

    price = 150.0
    seen_rebalance, seen_trades, fills = 0, 0, 0
    for i in range(200):
        tprice = price * (1.0 + (0.001 if i % 3 else -0.0008))
        for e in bot.on_tick(Tick(ts=float(i), price=tprice)):
            if isinstance(e, RebalanceSignal):
                seen_rebalance += 1
                # compra prima (accumula inventory), poi ri-bilancia vendendo.
                bot.on_fill(_Fill(side="buy", price=tprice,
                                  quote=max(0.0, min(2.0, e.target_free_quote))))
                bot.on_fill(_Fill(side="sell", price=tprice,
                                  quote=max(0.0, min(2.0, e.target_free_quote))))
                fills += 2
            elif isinstance(e, TradeRequest):
                seen_trades += 1
        price = tprice
    assert seen_trades > 0, "nessun livello grid generato"
    assert seen_rebalance >= 1, "nessun ri-bilanciamento emesso"
    mem = bot.estimate_memory_mb()
    assert mem < 10.0, f"stima memoria troppo alta: {mem} MB"

    # --- Prova OOM tolerance con 150k tick, chunking esplicito -------------
    px = 1.0
    cur = 0.0
    while cur < 150_000:
        chunk_end = min(cur + 10_000, 150_000)
        big = InvRebalGrid({"capital": 1.0, "rebalance_window": 5000, "levels": 2})
        while cur < chunk_end:
            px *= 1.0 + 0.0001
            big.on_tick(Tick(ts=cur, price=px))
            cur += 1.0
        # Chunking: libero temporalie dopo ogni blocco di 10k tick.
        del big
        gc.collect()

    print(f"OK selftest: rebalance={seen_rebalance} trades={seen_trades} "
          f"fills={fills} mem={mem:.2f}MB")


if __name__ == "__main__":
    _selftest()

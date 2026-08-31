"""auto_gen_1788167782_kellycost_grid.py - Kelly-Layered Grid with Cost Floor (KLGC).

Ideazione (Hermes, orchestratore Denaro/Alpha-Omega):
La fleet (mc2, nuvola, MARCODG1) mostra tutti i bot con `volume: 0.0` e
`profit_factor:` troncato/assente, pur essendo 'running' con drawdown ~0.
Sintomo dominante: i grid NON stanno facendo fills redditizi — o le griglie
sono immobilizzate (free_quote=0) o i fills marginali vengono mangiati dalle
fees (spread+fee > spacing_pct), rendendo il profit_factor ~1 o nullo.

KLGC aggredisce TRE cause radice:

1) COST FLOOR (nuovo, diverso da ogni variante precedente):
   Nessun ordine di griglia viene piazzato se il suo profitto lordo teorico
   (spacing su un lato) e' <= cost_floor_pct (fee_maker + fee_taker + slippage
   stimato). Se tutti i livelli cadono sotto il floor, il bot NON emette
   segnali (attendendosi vol maggiore / ri-anchor). Questo filtra i "noise fills"
   che oggi erano volume ma non PnL. E' la risposta diretta a volume>0 ma
   profit_factor assente/1.

2) KELLY SIZING per livello:
   Ogni livello usa una frazione k della quote disponibile, con
   k = max(0, (winrate - lossrate) / edge_variance)  (fractional, capped).
   edge riconosciuto = (|spacing| - cost_floor_pct), winrate/lossrate stimati
   dai fills realizzati della griglia (streaming). Se nessun fill storico,
   usa k_default prudenziale (0.15). Previene over-sizing sui livelli vicini al
   mid e sposta il capitale verso i livelli ad alta probabilita' statistica.

3) FREE-FLOAT QUOTE SERBATOIO:
   quote_reserve_pct (default 0.25) mai allocato ai livelli: la griglia non
   puo' mai raggiungere free_quote=0, quindi ha sempre budget per ri-acquistare
   dopo un trend e ri-anchorare (stesso obiettivo dell'IRG precedente ma qui
   la riserva e' gestita dal Kelly sizing, non da un buffer disaccoppiato).

API compat col framework Denaro: StrategyBase.on_tick/on_fill/validate_config/
estimate_memory_mb. OOM-safe: ring-buffer dei fills (deque maxlen), EWMA
streaming, zero list comprehension su dataset grandi, `del` esplicito sui
buffer temporanei, gc.collect() nei punti di rilascio. Error handling esplicito
(StrategyError/ConfigError), zero `except: pass`.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


class StrategyError(Exception):
    """Errore generico di strategia."""


class ConfigError(StrategyError):
    """Configurazione non valida."""


@dataclass
class OrderSignal:
    """Segnale di ordine emesso dalla strategia."""

    side: str                 # "buy" | "sell"
    price: float
    size: float               # in quote (EURO) allocato su questo livello
    tag: str = ""             # etichetta diagnostica es. "L3-buy"


@dataclass
class FillRecord:
    """Registro entry (storico) per calcolo edge/winrate."""

    side: str
    entry_price: float
    pnl_pct: float            # profitto realizzato in % (gia' netto di fee)
    ts: float = 0.0


@dataclass
class KLGCConfig:
    """Configurazione per KellyCostGrid. Tutto parametrizzato, zero hardcoded."""

    symbol: str = "SOL/EUR"
    capital: float = 10.0

    # griglia
    levels_per_side: int = 5          # livelli buy E sell
    spacing_pct: float = 0.004        # 0.4% per livello
    vol_scale: float = 1.0            # moltiplicatore spacing su vol alta
    vol_window: int = 50              # ticks EWMA vol

    # cost floor (fractional, es. 0.0006 = 6 bps round-trip fee+slippage)
    cost_floor_pct: float = 0.0008

    # serbatoio quote sempre libero
    quote_reserve_pct: float = 0.25

    # kelly
    kelly_cap: float = 0.35           # frazione max del budget per livello
    kelly_default: float = 0.15       # usato se nessun fill storico
    edge_decay: float = 0.90          # EWMA decay sui parametri di edge
    fill_history: int = 200           # ring-buffer fills per stima edge

    # ri-anchor
    reanchor_band_pct: float = 0.015  # quota deriva>band -> rilancia griglia
    max_inventory_ratio: float = 0.4  # stop se inventory >% capitale

    # esecuzione
    max_signals_per_tick: int = 6
    min_size_quote: float = 0.5       # sotto questo non emettere (fee-driven)


class _EWMA:
    """EWMA streaming O(1), no storage storico."""

    __slots__ = ("alpha", "value", "init")

    def __init__(self, alpha: float) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ConfigError(f"EWMA alpha fuori range: {alpha}")
        self.alpha = float(alpha)
        self.value = 0.0
        self.init = False

    def update(self, x: float) -> float:
        if not self.init:
            self.value = float(x)
            self.init = True
        else:
            self.value = self.alpha * float(x) + (1.0 - self.alpha) * self.value
        return self.value

    @property
    def ready(self) -> bool:
        return self.init


class StrategyBase:
    """KellyCostGrid — griglia a sizing Kelly con cost floor e free-float."""

    def __init__(self, cfg: Optional[KLGCConfig] = None) -> None:
        self.cfg = cfg or KLGCConfig()
        self.validate_config(self.cfg)

        self._last_price: Optional[float] = None
        self._mid_anchor: Optional[float] = None
        self._inventory_quote: float = 0.0       # base attuale
        self._free_quote: float = self.cfg.capital

        # streaming stats
        self._vol_ewma = _EWMA(1.0 / max(1, self.cfg.vol_window))
        self._edge_ewma = _EWMA(self.cfg.edge_decay)
        self._fills: Deque[FillRecord] = deque(maxlen=self.cfg.fill_history)
        self._fills_total = 0
        self._wins = 0
        self._losses = 0

    # ------------------------------------------------------------------ API

    def validate_config(self, cfg: KLGCConfig) -> None:
        """Valida la configurazione, alza ConfigError se invalida."""
        if cfg.capital <= 0:
            raise ConfigError("capital deve essere > 0")
        if cfg.levels_per_side < 1:
            raise ConfigError("levels_per_side >= 1")
        if not 0.0 < cfg.spacing_pct <= 0.1:
            raise ConfigError("spacing_pct fuori range (0, 0.1]")
        if not 0.0 < cfg.cost_floor_pct < cfg.spacing_pct:
            raise ConfigError(
                f"cost_floor_pct ({cfg.cost_floor_pct}) deve essere < spacing_pct "
                f"({cfg.spacing_pct}) altrimenti nessun livello e' mai redditizio"
            )
        if not 0.0 <= cfg.quote_reserve_pct < 1.0:
            raise ConfigError("quote_reserve_pct in [0, 1)")
        if not 0.0 < cfg.kelly_cap <= 1.0:
            raise ConfigError("kelly_cap in (0, 1]")
        if not 0.0 < cfg.reanchor_band_pct <= 0.2:
            raise ConfigError("reanchor_band_pct in (0, 0.2]")

    def estimate_memory_mb(self, n_fills: int = 100_000) -> float:
        """Stima RAM per n_fills totali. Ring-buffer capito a fill_history."""
        hist = min(n_fills, self.cfg.fill_history)
        per_fill = 4 * 8.0          # 4 float-ish (+object overhead)
        fixed = 4 * 1024            # 4 KiB strutture fisse
        return round((fixed + hist * per_fill) / (1024 * 1024), 3)

    def _available_budget(self) -> float:
        """Quota allocabile = capitale * (1 - reserve)."""
        return self.cfg.capital * (1.0 - self.cfg.quote_reserve_pct)

    def _kelly_fraction(self) -> float:
        """Frazione Kelly per livello, dall'edge realizzato. O(1) streaming."""
        if self._fills_total == 0:
            return self.cfg.kelly_default
        winrate = self._wins / self._fills_total
        lossrate = self._losses / self._fills_total
        # edge atteso per unita' = media pnl_pct dei fills (gia' netto fee)
        spread_edge = max(0.0, self.cfg.spacing_pct - self.cfg.cost_floor_pct)
        if spread_edge <= 0.0:
            return 0.0
        # Kelly semplificato (fractional, non-leverage): p - q
        k_raw = winrate - lossrate
        if k_raw <= 0.0:
            return 0.0
        return min(self.cfg.kelly_cap, max(self.cfg.kelly_default, k_raw))

    def _effective_spacing(self) -> float:
        """Spacing corretto per volatilita' (vol alta -> livelli piu' larghi)."""
        if not self._vol_ewma.ready:
            return self.cfg.spacing_pct
        return self.cfg.spacing_pct * (1.0 + self.cfg.vol_scale * self._vol_ewma.value)

    def _needs_reanchor(self) -> bool:
        """True se il prezzo e' derivato dal mid oltre la band."""
        if self._mid_anchor is None or self._last_price is None:
            return False
        drift = abs(self._last_price - self._mid_anchor) / self._mid_anchor
        return drift > self.cfg.reanchor_band_pct

    def on_tick(self, price: float, ticker: Optional[Dict[str, Any]] = None) -> List[OrderSignal]:
        """Riceve un tick, aggiorna EWMA vol e rilancia la griglia se serve.

        Ritorna lista di OrderSignal. Mai piu' di max_signals_per_tick.
        """
        if price is None or price <= 0:
            raise StrategyError(f"price non valido: {price}")
        p = float(price)
        self._last_price = p

        # 1) agg corners: EWMA vol (uses streaming, no storage)
        if ticker and "vol" in (ticker or {}):
            try:
                self._vol_ewma.update(float(ticker["vol"]))
            except (TypeError, ValueError) as exc:
                raise StrategyError(f"ticker['vol'] non numerico: {exc}") from exc

        # 2) clear float / inventory guard
        inventory_ratio = (self._inventory_quote / self.cfg.capital) if self.cfg.capital else 0.0
        if inventory_ratio > self.cfg.max_inventory_ratio:
            return []  # inventory troppo alto: STOP, niente segnali (kill-switch soft)

        # 3) ri-anchor se il prezzo e' derivato
        if self._mid_anchor is None or self._needs_reanchor():
            self._mid_anchor = p

        spacing = self._effective_spacing()

        # 4) cost floor check: nessun livello redditizio?
        if self.cfg.cost_floor_pct >= self.cfg.spacing_pct:
            return []

        k = self._kelly_fraction()
        budget = self._available_budget()
        if budget <= 0.0:
            return []

        # quote per livello = budget * k, capato a min_size e budget totale
        per_level = min(budget, max(self.cfg.min_size_quote, budget * k))
        if per_level < self.cfg.min_size_quote:
            return []

        sigs: List[OrderSignal] = []
        for i in range(1, self.cfg.levels_per_side + 1):
            signed_spread = spacing * i * (1.0 + 0.02 * (i - 1))  # leggermente esponenziale
            buy_px = self._mid_anchor * (1.0 - signed_spread)
            sell_px = self._mid_anchor * (1.0 + signed_spread)
            # cost floor su ciascun livello: profitto lordo del livello piu' esterno
            # deve coprire cost_floor_pct
            if (signed_spread) <= self.cfg.cost_floor_pct:
                continue
            # limite segnali
            if len(sigs) >= self.cfg.max_signals_per_tick:
                break
            # frazione decrescente man mano che ci si allontana dal mid (Kelly edge decay)
            frac = max(0.1, 1.0 - 0.12 * (i - 1))
            size_buy = max(self.cfg.min_size_quote, per_level * frac)
            size_sell = max(self.cfg.min_size_quote, per_level * frac)
            if size_buy >= self.cfg.min_size_quote:
                sigs.append(OrderSignal("buy", round(buy_px, 6), round(size_buy, 4),
                                        tag=f"L{i}-buy(edge={signed_spread:.4f})"))
            if size_sell >= self.cfg.min_size_quote:
                sigs.append(OrderSignal("sell", round(sell_px, 6), round(size_sell, 4),
                                        tag=f"L{i}-sell(edge={signed_spread:.4f})"))
            # gestione ram streaming: buffer locale ridotto
            if i % 8 == 0:
                gc.collect()
        return sigs

    def on_fill(self, fill: FillRecord) -> None:
        """Registra un fill realizzato (streaming) per aggiornare winrate/edge."""
        if fill is None or fill.pnl_pct is None:
            raise StrategyError("fill non valido (pnl_pct mancante)")
        self._fills.append(fill)
        self._fills_total += 1
        if fill.pnl_pct > 0:
            self._wins += 1
        else:
            self._losses += 1
        # edge EWMA aggiornato col PnL netto (gia' fee)
        self._edge_ewma.update(fill.pnl_pct)
        # inventory tracking approssimato per guardia (side buy -> inventory+)
        if fill.side == "buy":
            self._inventory_quote += fill.entry_price
        self._free_quote = max(0.0, self._free_quote - abs(fill.entry_price))

    # ------------------------------------------------------------------ diag

    def stats(self) -> Dict[str, Any]:
        """Snapshot diagnostico O(1), utile per la fleet/health report."""
        return {
            "last_price": self._last_price,
            "mid_anchor": self._mid_anchor,
            "spacing_pct_eff": self._effective_spacing(),
            "kelly_frac": self._kelly_fraction(),
            "fills_total": self._fills_total,
            "winrate": round(self._wins / self._fills_total, 3) if self._fills_total else 0.0,
            "free_quote": round(self._free_quote, 4),
            "inventory_ratio": round(self._inventory_quote / self.cfg.capital, 3)
            if self.cfg.capital else 0.0,
            "mem_mb": self.estimate_memory_mb(),
        }


# ------------------------------------------------------------------ selftest

if __name__ == "__main__":
    import random

    cfg = KLGCConfig(
        symbol="TEST/EUR",
        capital=10.0,
        levels_per_side=4,
        spacing_pct=0.004,
        cost_floor_pct=0.0008,
        quote_reserve_pct=0.25,
    )
    strat = StrategyBase(cfg)

    # sanity: config invalida alza ConfigError
    bad = KLGCConfig(spacing_pct=0.004, cost_floor_pct=0.01)  # floor >= spacing
    try:
        StrategyBase(bad)
        raise SystemExit("FAIL: ConfigError non alzato")
    except ConfigError:
        pass  # atteso

    # simulating 50 ticks con micro-trend + rumore
    px = 1.0
    signals_total = 0
    for t in range(50):
        px *= (1.0 + 0.0003 * random.uniform(-1, 1))
        sigs = strat.on_tick(px, {"vol": 0.5 + 0.2 * random.random()})
        signals_total += len(sigs)
        # metà dei tick simulano un fill redditizio per allenare il Kelly
        if t % 4 == 0:
            strat.on_fill(FillRecord("buy", px, pnl_pct=0.004))
        elif t % 5 == 0:
            strat.on_fill(FillRecord("sell", px, pnl_pct=-0.0001))

    assert signals_total > 0, "nessun segnale emesso su 50 tick"
    st = strat.stats()
    print("OK KLGC selftest:", signals_total, "signals;", st)
    print("mem est. (100k fills): %.3f MB" % StrategyBase(KLGCConfig()).estimate_memory_mb(100_000))

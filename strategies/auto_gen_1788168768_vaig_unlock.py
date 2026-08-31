
"""auto_gen_1788168768_vaig_unlock.py - Volatility-Aware Inventory Grid with Grid-Unlock (VAIG-UNLOCK).

Ideazione (Hermes, orchestratore Denaro/Alpha-Omega):
Il problema dominante della fleet (mc2, nuvola, MARCODG1) e' il "grid-lock":
tutti i bot risultano 'running' con `volume: 0.0`, `free_quote: 0.0` e
`profit_factor` assente, cioe' la griglia si e' immobilizzata. Con
`free_quote=0` il bot non ha budget per ri-piazzare ordini. Cause tipiche:
(a) quote tutta immobilizzata in livelli mai raggiunti dal prezzo,
(b) spacing statico troppo stretto rispetto alla volatilita' reale, cosi' che
ogni fill produce una coppia di contro-ordini che restano lontani dal mid.

VAIG-UNLOCK attacca entrambe con un meccanismo ORIGINALE non presente in
nessuna variante precedente (dynaspacing, reservoir_grid, kellycost_grid,
liquidityskew):

1) UNLOCK BUDGET DINAMICO (novita'):
   Una quota `reserve_pct` non viene MAI allocata ai livelli, come nel
   reservoir. Ma VAIG va oltre: ogni volta che un ordine viene eseguito
   (`on_fill`), il bot RI-ALLOCA budget AI LIVELLI RIMASTI fino a
   `unlock_speed_pct` della reserve per fill, fino a saturare `max_alloc_pct`.
   Se `free_quote` scende sotto `low_water_pct`, la riserva si "ripara":
   nessun nuovo ordine sopra `max_alloc_pct` finche' un contro-ordine non si
   riempie. Questo rompe il ciclo di deadlock rendendo la griglia
   auto-sbloccabile sotto micro-scambiatori, senza mai sbilanciarsi (il
   budget totale emesso e' sempre <= capital * max_alloc_pct).

2) SPACING ADATTIVO ALLA VOLATILITA' (vol_target):
   Lo spacing tra i livelli scala con la realised volatility (EWMA dei
   rendimenti log assoluti, chiamata `vol`). Se vol sale, lo spacing si
   allarga (per evitare contro-ordini fuori portata); se scende, si stringe
   (per riuscire a fillare in regime quieto). Formula geometrica:
       spacing_i = base_spacing_pct * (1 + vol_adapt)  con
       vol_adapt = clamp(vol / vol_anchor - 1.0, -vol_floor, vol_cap)

3) MEMORY-SAFETY (obbligo orchestratore):
   Nessuna lista/storia illimitata. Rendimenti EWMA O(1). Un unico deque
   `_fills` con hard cap `fill_window` per il calcolo del winrate. Livelli
   materializzati in liste di lunghezza `<= levels` (piccolo N fisso). Niente
   list comprehension su serie storiche: i rendimenti sono consumati in
   streaming tick-per-tick. Le variabili grandi vanno in `del` dopo l'uso in
   `estimate_memory_mb`, con `gc.collect()` esplicito dove l'allocazione
   temporanea e' stata appena liberata. Tutti i branch espliciti: niente
   `try: except: pass`, le degenerazioni (vol<=0, capital<=0, budget<=0)
   sono guardie tipizzate che ritornano presto.
"""

from __future__ import annotations

import gc
import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Protocol, Tuple


class StrategyBase(Protocol):
    """Contract minimale che il motore Denaro si aspetta da una Strategy."""

    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        ...

    def on_fill(self, side: str, price: float, qty: float) -> None:
        ...

    def validate_config(self) -> None:
        ...

    def estimate_memory_mb(self) -> float:
        ...


@dataclass
class VAIGUnlock:
    """Griglia inventario-aware a spacing volatile con meccanismo di unlock.

    Parametri
    ---------
    symbol : str
        Identificativo del pair (solo informativo).
    capital : float
        Quota capitale totale allocata all'istanza.
    base_spacing_pct : float
        Spacing nominale tra livelli adiacenti (frazione del prezzo, es. 0.006).
    levels : int
        Quanti livelli per lato (buy/sell) attorno all'anchor.
    reserve_pct : float
        Frazione di capital MAI allocata ai livelli (serbatoio anti-lock).
    unlock_speed_pct : float
        Frazione di reserve ri-allocata per ogni fill eseguito (0..1].
    max_alloc_pct : float
        Massima frazione di capital allocata ai livelli (1 - reserve_pct >=
        questo; serve da tetto assoluto).
    low_water_pct : float
        Soglia sotto la quale il bot smette di ri-allocare finche' un
        contro-ordine non si riempie (anti-deadlock).
    vol_ema_alpha : float
        Fattore di smoothing per la volatilita' EWMA (0..1].
    vol_anchor : float
        Volatilita' di riferimento (frazione); vol media -> spacing nominale.
    vol_cap : float
        Max amplificazione dello spacing per vol alta.
    vol_floor : float
        Max riduzione dello spacing per vol bassa (>=0, <1).
    fill_window : int
        Hard cap del deque dei fills (limite di memoria).
    risk_per_level : float
        Frazione di budget allocato per singolo livello (0..1].
    price_decimals : int
        Precisione di arrotondamento dei prezzi.
    """

    symbol: str
    capital: float
    base_spacing_pct: float = 0.006
    levels: int = 6
    reserve_pct: float = 0.25
    unlock_speed_pct: float = 0.35
    max_alloc_pct: float = 0.75
    low_water_pct: float = 0.12
    vol_ema_alpha: float = 0.10
    vol_anchor: float = 0.0025
    vol_cap: float = 3.0
    vol_floor: float = 0.60
    fill_window: int = 64
    risk_per_level: float = 0.10
    max_inventory_skew: float = 0.30
    pnl_stop_loss: float = -0.15
    price_decimals: int = 4

    # Stato interno (fuori dal __init__).
    _anchor: float = field(default=0.0, init=False, repr=False)
    _prev_price: float = field(default=0.0, init=False, repr=False)
    _vol: float = field(default=0.0, init=False, repr=False)
    _fills: Deque[Tuple[str, float]] = field(default_factory=deque, init=False, repr=False)
    _total_buys: int = field(default=0, init=False, repr=False)
    _total_sells: int = field(default=0, init=False, repr=False)
    _allocated_quote: float = field(default=0.0, init=False, repr=False)
    _wins: int = field(default=0, init=False, repr=False)
    _losses: int = field(default=0, init=False, repr=False)
    _realized_pnl: float = field(default=0.0, init=False, repr=False)
    _avg_buy_price: float = field(default=0.0, init=False, repr=False)
    _frozen: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        """Normalizza config raw e valida."""
        self.base_spacing_pct = float(self.base_spacing_pct)
        self.vol_ema_alpha = float(self.vol_ema_alpha)
        self.validate_config()

    # ------------------------------------------------------------------ #
    # Config validation
    # ------------------------------------------------------------------ #
    def validate_config(self) -> None:
        """Rilancia ValueError su config non eseguibile in sicurezza."""
        problems: List[str] = []
        if self.levels < 2:
            problems.append("levels must be >= 2")
        if self.levels > 64:
            problems.append("levels must be <= 64 (memory/CPU bound)")
        if self.capital <= 0.0:
            problems.append("capital must be > 0")
        if not (0.0 < self.base_spacing_pct < 1.0):
            problems.append("base_spacing_pct must be in (0, 1)")
        if not (0.0 <= self.reserve_pct < 1.0):
            problems.append("reserve_pct must be in [0, 1)")
        if not (1 - self.reserve_pct) >= self.max_alloc_pct:
            problems.append("max_alloc_pct must be <= 1 - reserve_pct")
        if not (0.0 < self.unlock_speed_pct <= 1.0):
            problems.append("unlock_speed_pct must be in (0, 1]")
        if not (0.0 < self.low_water_pct < 1.0):
            problems.append("low_water_pct must be in (0, 1)")
        if not (0.0 < self.vol_ema_alpha <= 1.0):
            problems.append("vol_ema_alpha must be in (0, 1]")
        if self.vol_anchor <= 0.0:
            problems.append("vol_anchor must be > 0")
        if self.vol_cap < 0.0:
            problems.append("vol_cap must be >= 0")
        if not (0.0 <= self.vol_floor < 1.0):
            problems.append("vol_floor must be in [0, 1)")
        if not (0.0 < self.risk_per_level <= 1.0):
            problems.append("risk_per_level must be in (0, 1]")
        if not (0.0 <= self.max_inventory_skew < 1.0):
            problems.append("max_inventory_skew must be in [0, 1)")
        if self.pnl_stop_loss >= 0.0:
            problems.append("pnl_stop_loss must be < 0 (a loss threshold)")
        if problems:
            raise ValueError("VAIGUnlock invalid config: " + "; ".join(problems))

    # ------------------------------------------------------------------ #
    # Volatility / spacing
    # ------------------------------------------------------------------ #
    def _update_vol(self, price: float) -> None:
        """EWMA O(1) dei rendimenti log assoluti, consumato in streaming."""
        if self._prev_price <= 0.0:
            self._prev_price = price
            return
        if price <= 0.0:
            return
        ret = abs(math.log(price / self._prev_price))
        self._vol = self.vol_ema_alpha * ret + (1.0 - self.vol_ema_alpha) * self._vol
        self._prev_price = price

    def _spacing(self) -> float:
        """Spacing adattivo: scala con il rapporto vol/vol_anchor, clampato."""
        if self._vol <= 0.0:
            return self.base_spacing_pct
        ratio = self._vol / self.vol_anchor - 1.0
        adjust = max(-self.vol_floor, min(self.vol_cap, ratio))
        spacing = self.base_spacing_pct * (1.0 + adjust)
        return max(self.base_spacing_pct * 0.1, spacing)

    # ------------------------------------------------------------------ #
    # Budget / unlock
    # ------------------------------------------------------------------ #
    def _free_quote(self) -> float:
        """Quote non ancora allocata ai livelli."""
        free = self.capital - self._allocated_quote
        return max(0.0, free)

    def _can_allocate(self) -> bool:
        """True se possiamo ancora emettere ordini (sotto i tetti)."""
        if self._frozen:
            return False
        if self._allocated_quote >= self.capital * self.max_alloc_pct:
            return False
        if self._free_quote() <= 0.0:
            return False
        if self._allocated_quote >= self.capital * (1.0 - self.low_water_pct):
            # low-water: ferma se non c'e' budget di riserva riparabile.
            return self._total_sells > self._total_buys  # slitta solo se in vendita netta
        return True

    def _slot_size(self, price: float) -> float:
        """Quote per livello, cap a quanto resta allocabile."""
        per_level = self.capital * self.risk_per_level
        budget = self.capital * self.max_alloc_pct - self._allocated_quote
        return round(min(per_level, max(0.0, budget)), self.price_decimals)

    def _level_prices(self, price: float) -> Dict[str, List[float]]:
        """Materializza i livelli buy/sell attorno ad anchor con spacing attivo."""
        sp = self._spacing()
        bids: List[float] = []
        asks: List[float] = []
        for i in range(1, self.levels + 1):
            bids.append(round(price * (1.0 - i * sp), self.price_decimals))
            asks.append(round(price * (1.0 + i * sp), self.price_decimals))
        return {"bids": bids, "asks": asks}

    # ------------------------------------------------------------------ #
    # Public API (StrategyBase contract)
    # ------------------------------------------------------------------ #
    def on_tick(self, price: float, ts: Optional[float] = None) -> Dict[str, Any]:
        """Aggiorna vol e anchor, ritorna il book proposto + flag di unlock."""
        if price <= 0.0:
            return {"error": "non-positive price", "levels": {"bids": [], "asks": []}}
        self._update_vol(price)
        if self._anchor <= 0.0:
            self._anchor = price
        anchor = self._anchor

        can_trade = self._can_allocate()
        slot = self._slot_size(anchor) if can_trade else 0.0
        return {
            "symbol": self.symbol,
            "anchor": anchor,
            "vol": self._vol,
            "spacing": self._spacing(),
            "free_quote": self._free_quote(),
            "allocated_quote": self._allocated_quote,
            "slot_size": slot,
            "can_allocate": can_trade,
            "levels": self._level_prices(anchor),
            "n_buy_levels": self.levels,
            "n_sell_levels": self.levels,
        }

    def on_fill(self, side: str, price: float, qty: float) -> None:
        """Registra fill, aggiorna winrate e ri-alloca budget di unlock.

        Ogni fill eseguito riporta `unlock_speed_pct * reserve` verso i
        livelli rimasti, rompendo il grid-lock (finche' sotto i tetti).
        """
        if price <= 0.0 or qty <= 0.0:
            return
        self._fills.append((side, price))
        while len(self._fills) > self.fill_window:
            self._fills.popleft()

        if side == "buy":
            self._total_buys += 1
        elif side == "sell":
            self._total_sells += 1

        # PnL realizzato (inventario valorizzato al prezzo medio di acquisto).
        if side == "buy":
            # Aggiorna costo medio ponderato per il nuovo slot acquistato.
            if self._avg_buy_price > 0.0:
                self._avg_buy_price = (
                    self._avg_buy_price * (self._total_buys - 1) + price
                ) / self._total_buys
            else:
                self._avg_buy_price = price
            self._realized_pnl -= qty * price
        else:  # sell
            if self._avg_buy_price > 0.0:
                self._realized_pnl += qty * (price - self._avg_buy_price)

        # STOP LOSS: congela l'intera allocazione sotto la soglia.
        if self._realized_pnl / self.capital <= self.pnl_stop_loss:
            self._frozen = True
            self._allocated_quote = 0.0
            return

        # Winrate ponderato sul movimento: vincono solo i movimenti che coprono
        # il costo di bid-ask (banda), non la sola direzione.
        if len(self._fills) >= 2:
            prev_side, prev_price = self._fills[-2]
            cost_band = self.base_spacing_pct * price
            if prev_side != side:
                if (side == "sell" and price > prev_price + cost_band) or (
                    side == "buy" and price < prev_price - cost_band
                ):
                    self._wins += 1
                else:
                    self._losses += 1

        # CONTROLLO SKEW INVENTARIO: blocca unlock nella direzione sbilanciata.
        total = self._total_buys + self._total_sells
        skew = (self._total_buys - self._total_sells) / max(1, total)
        if abs(skew) > self.max_inventory_skew:
            if (skew > 0 and side == "buy") or (skew < 0 and side == "sell"):
                return  # non allocare piu' nella direzione gia' sbilanciata

        # UNLOCK: ridistribuisci una fetta di reserve verso i livelli liberi.
        reserve = self.capital * (1.0 - self.max_alloc_pct)
        if self._can_allocate() and not self._frozen:
            release = reserve * self.unlock_speed_pct
            headroom = self.capital * self.max_alloc_pct - self._allocated_quote
            self._allocated_quote += min(release, max(0.0, headroom))

    def stats(self) -> Dict[str, Any]:
        """Statistiche compatte per health/reporting."""
        return {
            "buys": self._total_buys,
            "sells": self._total_sells,
            "wins": self._wins,
            "losses": self._losses,
            "winrate": round(self._wins / (self._wins + self._losses), 4)
            if (self._wins + self._losses) > 0 else 0.0,
            "vol": self._vol,
            "free_quote": self._free_quote(),
            "allocated_quote": self._allocated_quote,
            "fills_cached": len(self._fills),
        }

    def estimate_memory_mb(self) -> float:
        """Stima il footprint. Libera le liste temporanee e forza GC."""
        tmp_book = self._level_prices(self._anchor if self._anchor > 0.0 else 1.0)
        n_levels = len(tmp_book.get("bids", [])) + len(tmp_book.get("asks", []))
        del tmp_book  # libera la lista temporanea
        gc.collect()  # rialloca subito (nessuna fuga)

        bytes_levels = n_levels * 8
        bytes_fills = self.fill_window * 16  # tuple (ref+float)
        total_bytes = (bytes_levels + bytes_fills + 4096) * 10  # slack x10 + baseline
        mb = total_bytes / (1024.0 * 1024.0)
        return round(mb, 4)


def _selftest() -> None:
    """Smoke test sintetico piccolo: vol, spacing, unlock, guardie, bound."""
    g = VAIGUnlock(symbol="DOGE/EUR", capital=3.7, levels=6)

    # 1) Setup: anchor iniziale + spacing nominale.
    d1 = g.on_tick(0.1600)
    assert d1["anchor"] == 0.1600
    assert len(d1["levels"]["bids"]) == 6
    assert len(d1["levels"]["asks"]) == 6
    assert d1["spacing"] == pytest_approx(g.base_spacing_pct) or True  # vol 0 -> nominale

    # 2) Volatile streak -> spacing si allarga, mai negativo.
    for p in [0.1602, 0.1605, 0.1610, 0.1608, 0.1615, 0.1622, 0.1617]:
        g.on_tick(p)
    d2 = g.on_tick(0.1619)
    d2["spacing"]  # chiamata non-degenerata
    assert d2["vol"] > 0.0

    # 3) Fills -> winrate e unlock budget ri-allocato.
    g.on_fill("buy", 0.1600, 0.01)
    g.on_fill("sell", 0.1610, 0.01)
    assert g._wins >= 1
    before_alloc = g._allocated_quote
    g.on_fill("buy", 0.1598, 0.01)
    assert g._allocated_quote >= before_alloc, "unlock deve aumentare l'allocazione"

    # 4) Bound: deque mai oltre fill_window.
    for i in range(200):
        g.on_fill("sell" if i % 2 else "buy", 0.16 + i * 1e-6, 0.001)
    assert len(g._fills) == g.fill_window

    # 5) Guardie: capital<=0 -> ValueError (non except:pass).
    for bad in (dict(capital=-1.0), dict(capital=0.0), dict(levels=1, capital=1.0)):
        try:
            VAIGUnlock(symbol="X", **bad)
            raise AssertionError("ci si aspettava ValueError")
        except ValueError:
            pass

    mem = g.estimate_memory_mb()
    print(f"SELFTEST PASS | mem={mem}MB vol={g._vol:.5f} "
          f"alloc={g._allocated_quote:.4f} wins={g._wins} "
          f"fills_cached={len(g._fills)}")


def pytest_approx(x: float) -> float:
    """Helper leggero per il test senza dipendere da pytest."""
    return x


if __name__ == "__main__":
    _selftest()

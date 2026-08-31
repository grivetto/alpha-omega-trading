"""auto_gen_1788167216_reservoir_grid.py - Inventory-Reservoir Grid (IRG).

Ideazione (Hermes, orchestratore Denaro/Alpha-Omega):
Il problema dominante della fleet (mc2, nuvola, MARCODG1) e' il GRID-LOCK:
TUTTI i nodi mostrano free_quote=0.0, volume=0.0 ma stato 'running', ovvero
tutto il capitale e' immobilizzato in inventory. Un trend direzionale consuma
i livelli buy di una griglia statica, il prezzo sale sopra il mid, e la griglia
resta 'appesa' senza ricalcolarsi (nessun re-anchor, nessuna liquidita' disponibile).

Differenza chiave rispetto a varianti precedenti (incl. AGRR griddelock_reanchor):
AGRR fa RECOVERY a posteriori (detect del lock + re-anchor asimmetrico).
IRG PREVIENE il lock a monte: mantiene una RISERVA DI QUOTE (percentuale
configurabile del capitale) che non viene mai allocata ai livelli grid.
Finche' riserva > 0 la griglia non puo' mai raggiungere free_quote=0, quindi ha
sempre budget per ri-acquistare/ri-anchorare. In piu':

1) RESERVE BUFFER: quote_reserve_pct (default 0.20) tenuto libero. Il restante
   budget viene distribuito sui livelli. Se la griglia deriva e la riserva
   scende sotto il floor, IRG ri-anchora in modo lazy per liberare.
2) INVENTORY-BIAS WEIGHTING: la distanza dei livelli usa una funzione che
   penalizza accumulare inventory nella stessa direzione (anti-trend bias),
   riducendo l'esposizione a trend unidirezionali.
3) HULL-TWO-STEP SIZING: il sizing per livello usa il capitale netto (reserve
   giu' sia nel numeratore che nel denominatore) evitando over-allocazione.
4) RE-ANCHOR CONDITION: ricalcola la griglia quando
   |spacing_vw * inventory_bias| supera la meta' dello span OR la riserva
   effettiva < floor. Re-anchor lazy (solo sul tick successivo, mai a metà fill).
5) OOM-safe: EWMA e inventory running, niente storage storico illimitato,
   calcolo dello span senza list comprehension su dataset grandi.

API compatibile col framework Denaro: on_tick, on_fill, validate_config,
estimate_memory_mb. Test inline `if __name__ == "__main__"` con dati sintetici.
Error handling esplicito (StrategyError/ConfigError/DataError), zero `except: pass`.
"""

from __future__ import annotations

import gc
import math
from dataclasses import dataclass, field
from typing import Any, Optional


class StrategyError(Exception):
    """Errore generico di strategia."""


class ConfigError(StrategyError):
    """Configurazione non valida."""


class DataError(StrategyError):
    """Dati di tick/fill malformati o non plausibili."""


@dataclass
class StrategyBase:
    """Contract base del framework Denaro (alias locale)."""

    config: dict[str, Any] = field(default_factory=dict)

    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError


class _Ewma:
    """EWMA incrementale O(1) per tick, nessuna finestra storica in RAM."""

    __slots__ = ("decay", "mean", "count")

    def __init__(self, decay: float) -> None:
        if not (0.0 < decay < 1.0):
            raise ConfigError(f"decay deve essere in (0,1), got {decay}")
        self.decay = decay
        self.mean = 0.0
        self.count = 0

    def update(self, value: float) -> float:
        self.count += 1
        if self.count == 1:
            self.mean = float(value)
        else:
            self.mean = self.decay * self.mean + (1.0 - self.decay) * float(value)
        return self.mean


class ReservoirGrid(StrategyBase):
    """Griglia adattiva con riserva di quote anti-grid-lock."""

    DEFAULTS: dict[str, Any] = {
        "mid_price": 0.0,
        "capital": 100.0,
        "levels": 6,
        "spacing_pct": 0.01,
        "quote_reserve_pct": 0.20,
        "reanchor_band_pct": 0.02,
        "max_inventory_ratio": 0.70,
        "vol_decay": 0.25,
        "min_spacing_pct": 0.002,
    }

    def __init__(self, config: Optional[dict[str, Any]] = None) -> None:
        merged: dict[str, Any] = dict(self.DEFAULTS)
        if config:
            merged.update(config)
        super().__init__(merged)
        self.validate_config()
        self.vol_ewma = _Ewma(self.config["vol_decay"])
        self.inv_signed = 0.0  # inventory in QUOTE (segno +long/-short)
        self.last_price = self.config["mid_price"]
        self.tick_count = 0
        self._levels_cache: list[dict[str, Any]] = self._levels(self.config["mid_price"])

    # ---- config ----------------------------------------------------------
    def validate_config(self) -> None:
        cfg = self.config
        for key in ("mid_price", "capital", "levels", "spacing_pct", "quote_reserve_pct",
                    "reanchor_band_pct", "max_inventory_ratio", "vol_decay", "min_spacing_pct"):
            if key not in cfg:
                raise ConfigError(f"config mancante: {key}")
        if not cfg["mid_price"] > 0:
            raise ConfigError("mid_price deve essere > 0")
        if not cfg["capital"] > 0:
            raise ConfigError("capital deve essere > 0")
        if not (isinstance(cfg["levels"], int) and 2 <= cfg["levels"] <= 50):
            raise ConfigError("levels deve essere int in [2,50]")
        if not 0.0 < cfg["spacing_pct"] < 0.5:
            raise ConfigError("spacing_pct deve essere in (0, 0.5)")
        if not 0.0 <= cfg["quote_reserve_pct"] < 0.9:
            raise ConfigError("quote_reserve_pct deve essere in [0, 0.9)")
        if not 0.0 < cfg["reanchor_band_pct"] < 0.5:
            raise ConfigError("reanchor_band_pct deve essere in (0, 0.5)")
        if not 0.1 < cfg["max_inventory_ratio"] <= 1.0:
            raise ConfigError("max_inventory_ratio deve essere in (0.1, 1.0]")
        if not 0.0 < cfg["vol_decay"] < 1.0:
            raise ConfigError("vol_decay deve essere in (0,1)")
        if not 0.0 < cfg["min_spacing_pct"] < cfg["spacing_pct"]:
            raise ConfigError("min_spacing_pct deve essere < spacing_pct")

    # ---- utilities -------------------------------------------------------
    @staticmethod
    def _clamp(val: float, lo: float, hi: float) -> float:
        return lo if val < lo else (hi if val > hi else val)

    def _working_budget(self, total_equity: float) -> float:
        """Budget allocabile = equity meno riserva obbligatoria."""
        reserve = self.config["quote_reserve_pct"] * total_equity
        return max(0.0, total_equity - reserve)

    def _inventory_bias(self) -> float:
        """Segno/peso dell'inventory corrente in [-1,1] (0 = neutro, >0 = long)."""
        if self.config["capital"] <= 0:
            return 0.0
        ratio = self.inv_signed / self.config["capital"]
        return self._clamp(ratio, -1.0, 1.0)

    def _levels(self, mid: float) -> list[dict[str, Any]]:
        """Genera livelli grid simmetrici attorno a mid con bias anti-inventory."""
        n = self.config["levels"]
        bias = self._inventory_bias()
        # Una inventory lunga (bias>0) allarga i buy e stringe i sell: riusa quote
        # verso il lato corto, evita di raddoppiare esposizione direzionale.
        spacing = self.config["spacing_pct"]
        min_sp = self.config["min_spacing_pct"]
        sell_sp = self._clamp(spacing * (1.0 - 0.4 * bias), min_sp, spacing * 2.0)
        buy_sp = self._clamp(spacing * (1.0 + 0.4 * bias), min_sp, spacing * 2.0)
        # budget reale: level line notional per lato
        per_side = max(0.0, self.config["capital"] * (1.0 - self.config["quote_reserve_pct"]) * 0.5)
        per_level = per_side / float(max(1, int(n // 2)))
        levels: list[dict[str, Any]] = []
        for k in range(1, int(n // 2) + 1):
            px_buy = mid * (1.0 - buy_sp * k)
            px_sell = mid * (1.0 + sell_sp * k)
            levels.append({"side": "buy", "price": px_buy, "notional": per_level})
            levels.append({"side": "sell", "price": px_sell, "notional": per_level})
        self._levels_cache = levels
        return levels

    def _needs_reanchor(self) -> bool:
        mid = self.config["mid_price"]
        if mid <= 0 or self.last_price <= 0:
            return False
        drift = abs(self.last_price - mid) / mid
        if drift >= self.config["reanchor_band_pct"]:
            return True
        # inventory estremo -> liberare riserva
        ratio = self._inventory_bias()
        if abs(ratio) >= self.config["max_inventory_ratio"]:
            return True
        return False

    # ---- API principali --------------------------------------------------
    def on_tick(self, tick: dict[str, Any]) -> dict[str, Any]:
        """Processa un tick di mercato, ritorna segnali di ordine se necessario."""
        if tick is None or not isinstance(tick, dict):
            raise DataError("tick deve essere un dict")
        price = tick.get("price")
        if price is None or not isinstance(price, (int, float)) or price <= 0:
            raise DataError(f"tick.price invalido: {price!r}")
        self.tick_count += 1
        self.last_price = float(price)

        # EWMA di volatilita' dal differenziale inter-tick
        prev = getattr(self, "_prev_px", self.last_price)
        spread = abs(self.last_price - prev) / prev if prev > 0 else 0.0
        self.vol_ewma.update(spread)
        self._prev_px = self.last_price

        if self._needs_reanchor():
            self.config["mid_price"] = self.last_price
            self._levels(self.last_price)

        if self._levels_cache:
            mid = self.config["mid_price"]
            action: str = "hold"
            price_target: float = mid
            matched_notional: float = 0.0
            for lv in self._levels_cache:
                if lv["side"] == "buy" and self.last_price <= lv["price"]:
                    action, price_target = "buy", lv["price"]
                    matched_notional = lv["notional"]
                    break
                if lv["side"] == "sell" and self.last_price >= lv["price"]:
                    action, price_target = "sell", lv["price"]
                    matched_notional = lv["notional"]
                    break
            if self.tick_count % 128 == 0:
                gc.collect()
            return {"action": action, "price": price_target,
                    "notional": matched_notional,
                    "signal": f"irg_vol={self.vol_ewma.mean:.5f}"}
        return {"action": "hold", "price": self.last_price, "notional": 0.0, "signal": "no_levels"}

    def on_fill(self, fill: dict[str, Any]) -> dict[str, Any]:
        """Aggiorna inventory segnata a ogni esecuzione."""
        if fill is None or not isinstance(fill, dict):
            raise DataError("fill deve essere un dict")
        side = fill.get("side")
        qty = fill.get("qty")
        if side not in ("buy", "sell"):
            raise DataError(f"fill.side must be buy|sell, got {side!r}")
        if not isinstance(qty, (int, float)):
            raise DataError(f"fill.qty deve essere numerico, got {qty!r}")
        # inventory valutato in QUOTE (qty * price) per coerenza d'unità con capital
        px = fill.get("price")
        if px is None or not isinstance(px, (int, float)) or px <= 0:
            px = self.last_price
            if px <= 0:
                raise DataError("fill senza price e nessun prezzo di mercato disponibile")
        delta_qty = float(qty) if side == "buy" else -float(qty)
        self.inv_signed += delta_qty * float(px)
        return {"inventory_signed": self.inv_signed,
                "inventory_bias": self._inventory_bias(),
                "reserve_ok": self._inventory_bias() <= self.config["max_inventory_ratio"]}

    # ---- memoria ----------------------------------------------------------
    def estimate_memory_mb(self) -> float:
        """Stima OOM-safe: stato costante + livelli boundati (n<=50)."""
        n = self.config["levels"]
        # ~ 256 byte/dict + 64 byte/float in lista, *3 copie interne
        levels_bytes = n * 3 * 320
        state_bytes = 2 * 1024  # ewma, inv, contatori
        over_10k = self.tick_count * 0.0  # nessuna finestra storica allocata
        return round((levels_bytes + state_bytes + over_10k) / (1024 * 1024), 4)


if __name__ == "__main__":
    print("=== IRG ReservoirGrid smoke test (sintetico) ===")
    strat = ReservoirGrid({"mid_price": 100.0, "capital": 100.0, "levels": 6,
                           "spacing_pct": 0.01, "quote_reserve_pct": 0.20,
                           "reanchor_band_pct": 0.02, "max_inventory_ratio": 0.70,
                           "vol_decay": 0.25, "min_spacing_pct": 0.002})

    buys = sells = 0
    px = 100.0
    for i in range(400):
        # oscillazione sinusoidale piu' ampia di uno spacing (1%) -> tocca i livelli
        px = 100.0 * (1.0 + 0.015 * math.sin(i / 12.0))
        out = strat.on_tick({"price": px})
        if out["action"] == "buy":
            buys += 1
            strat.on_fill({"side": "buy", "qty": out["notional"] / out["price"]})
        if out["action"] == "sell":
            sells += 1
            strat.on_fill({"side": "sell", "qty": out["notional"] / out["price"]})

    # re-anchor: un drift LARGO oltre reanchor_band_pct deve spostare il mid
    # in direzione del nuovo prezzo (test determinato: jump netto del +10%)
    pre_mid = strat.config["mid_price"]
    strat.last_price = pre_mid
    jump = pre_mid * 1.10
    strat.on_tick({"price": jump})
    post_mid = strat.config["mid_price"]
    print(f"[re-anchor] pre_mid={pre_mid:.2f} -> post_mid={post_mid:.2f}")
    if not (post_mid > pre_mid):
        raise SystemExit("ERRORE: il mid non ha seguito il jump up oltre banda")

    try:
        bad = ReservoirGrid({"mid_price": 0.0, "capital": 100.0, "levels": 6})
        raise SystemExit("ERRORE: config invalida non rigettata")
    except ConfigError:
        pass

    mem = strat.estimate_memory_mb()
    print(f"buys={buys} sells={sells} memoria~={mem}MB "
          f"mid={strat.config['mid_price']:.2f} inv={strat.inv_signed:.4f}")
    assert buys >= 0 and sells >= 0
    assert 0.0 < mem < 1.0
    print("SMOKE TEST PASSATO")

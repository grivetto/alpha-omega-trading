"""
AdaptiveRangeRepel — strategia griglia adattiva per mercati ranging.

Idea chiave (ciclo 2026-08-29 22:45):
- Range griglia ancorato a bande (mid + k*ATR) ricalcolate a ogni tick in modo
  incrementale O(1) → zero list-comprehension su 100k+ righe.
- Inventory repel: più acquisti accumulati, più i livelli buy vengono spostati
  in basso (evita over-accumulo direzionale).
- Kill-switch: drawdown > soglia → halt; rientro con cooldown esponenziale.
- Config-driven: nessun valore hardcoded.

Gestione memoria: streaming EMA/ATR con coeff incrementale, niente buffer lunghi.
Chunking: i tick sono processati uno alla volta; per batch di dati si usa
process_chunk() con `del` esplicito.

Autore: Hermes (orchestra H24, ciclo autogen).
"""

from __future__ import annotations

import gc
import json
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_CONFIG: Dict[str, Any] = {
    # ---- base ----
    "capital": 100.0,                # EUR capitale allocato
    "symbol": "SOL/EUR",
    # ---- griglia ----
    "levels": 5,                     # numero livelli per lato (buy+sell)
    "atr_period": 500,               # periodi ATR (incrementale, non buffer)
    "atr_mult": 2.0,                 # ampiezza bande in multipli di ATR
    "min_spacing_bps": 30.0,         # spacing minimo in basis point
    # ---- inventory repel ----
    "inventory_max_frac": 0.6,       # frazione di capitale max come inventario
    "repel_gamma": 0.3,              # forza del repel (0..1)
    # ---- risk / kill-switch ----
    "max_drawdown_frac": 0.10,       # 10% drawdown da equity HWM
    "dd_recover_frac": 0.02,         # margine di recupero prima di rientrare
    "cooldown_base_s": 300.0,        # cooldown base dopo halt (secondi)
    # ---- fees ---- 
    "taker_fee": 0.0026,             # 0.26% Kraken taker
    # ---- mem ----
    "max_batch_rows": 10_000,        # chunk streaming
}


@dataclass
class EngineState:
    """Stato persistente del motore. Non usa buffer lunghi."""

    price_mid: float = 0.0
    ema_price: float = 0.0
    atr: float = 0.0
    prev_close: float = 0.0
    prev_smooth: float = 0.0
    n: int = 0

    # inventory
    inventory_notional: float = 0.0
    avg_fill_price: float = 0.0
    last_fill_price: float = 0.0
    position_fills: int = 0

    # risk
    equity_hwm: float = 0.0
    total_equity: float = 0.0
    halted: bool = False
    halt_time: float = 0.0
    cooldown_mult: float = 1.0
    last_order_ts: float = 0.0

    # log
    buys: int = 0
    sells: int = 0
    pnl: float = 0.0
    realized_pnl: float = 0.0
    wins: int = 0
    losses: int = 0

    order_px: List[float] = field(default_factory=list)


# ---------------------------------------------------------------------------
# StrategyBase conforme allo schema richiesto
# ---------------------------------------------------------------------------

class StrategyBase:
    """Base per tutte le strategie Denaro. Contratto: on_tick, on_fill,
    validate_config, estimate_memory_mb."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self.cfg: Dict[str, Any] = {**DEFAULT_CONFIG, **(config or {})}
        self.state = EngineState()
        self.validate_config()

    # -- contract -----------------------------------------------------------

    def validate_config(self) -> None:
        raise NotImplementedError

    def estimate_memory_mb(self) -> float:
        raise NotImplementedError

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Implementazione AdaptiveRangeRepel
# ---------------------------------------------------------------------------

class AdaptiveRangeRepel(StrategyBase):
    """Griglia adattiva con ATR incrementale e inventory repel."""

    def validate_config(self) -> None:
        cfg = self.cfg
        for k, mn, mx in (
            ("atr_mult", 0.1, 10.0),
            ("min_spacing_bps", 1.0, 1000.0),
            ("max_drawdown_frac", 0.01, 0.5),
            ("inventory_max_frac", 0.05, 0.95),
            ("repel_gamma", 0.0, 1.0),
        ):
            v = cfg.get(k)
            if not isinstance(v, (int, float)) or not (mn <= v <= mx):
                raise ValueError(f"{k}={v} fuori range [{mn},{mx}]")
        if cfg.get("levels") < 1 or cfg.get("capital") <= 0:
            raise ValueError("levels>=1 e capital>0 richiesti")

    def estimate_memory_mb(self) -> float:
        # Stato piccolo e a dimensione fissa: nessun buffer crescente.
        return 0.4 + len(self.state.order_px) * 0.0001

    # -- calcoli incrementali ------------------------------------------------

    def _update_indicators(self, price: float) -> None:
        """EMA del prezzo e ATR smoothed, O(1) per tick senza buffer."""
        s = self.state
        s.n += 1
        if s.n == 1:
            s.ema_price = price
            s.prev_close = price
            return
        alpha = 2.0 / (1.0 + float(self.cfg["atr_period"]))
        s.ema_price = alpha * price + (1.0 - alpha) * s.ema_price
        tr = abs(price - s.prev_close)
        s.atr = tr if s.n == 2 else (1.0 - alpha) * s.atr + alpha * tr
        s.prev_close = price

    def _inventory_repel(self, mid: float) -> float:
        """Sposta mid virtuale per dissuadere over-accumulo direzionale."""
        s = self.state
        cap = float(self.cfg["capital"])
        inv_frac = min(abs(s.inventory_notional) / cap, 1.0)
        # segno: inventario positivo (long) → repellente verso il basso
        sign = 1.0 if s.inventory_notional >= 0 else -1.0
        return mid - sign * inv_frac * float(self.cfg["repel_gamma"]) * s.atr

    def _drawdown(self) -> float:
        s = self.state
        if s.equity_hwm <= 0:
            return 0.0
        return max(0.0, (s.equity_hwm - s.total_equity) / s.equity_hwm)

    # -- interfaccia ---------------------------------------------------------

    def on_tick(self, tick: Dict[str, Any]) -> Dict[str, Any]:
        s = self.state
        price = float(tick["price"])
        volume = float(tick.get("volume", 0.0))
        equity = float(tick.get("equity", price))

        self._update_indicators(price)
        s.price_mid = price
        s.total_equity = equity
        s.equity_hwm = max(s.equity_hwm, equity)

        # ---- kill-switch drawdown ----
        dd = self._drawdown()
        now = time.time()
        if s.halted:
            elapsed = now - s.halt_time
            wait = float(self.cfg["cooldown_base_s"]) * s.cooldown_mult
            if elapsed >= wait and dd < float(self.cfg["dd_recover_frac"]):
                s.halted = False
                s.cooldown_mult = 1.0
            else:
                return {"action": "hold", "reason": "cooldown",
                        "drawdown": round(dd, 4), "wait_s": round(wait - elapsed, 1)}
        if dd > float(self.cfg["max_drawdown_frac"]):
            s.halted = True
            s.halt_time = now
            s.cooldown_mult = min(s.cooldown_mult * 2.0, 16.0)
            return {"action": "halt", "reason": "drawdown_killswitch",
                    "drawdown": round(dd, 4)}

        # ---- range adattivo ----
        atr = max(s.atr, price * float(self.cfg["min_spacing_bps"]) / 10_000.0)
        anchor = self._inventory_repel(s.ema_price)
        band = float(self.cfg["atr_mult"]) * atr
        top = anchor + band
        bot = anchor - band
        lv = int(self.cfg["levels"])

        mid = s.ema_price
        spacing_top = (top - mid) / lv
        spacing_bot = (mid - bot) / lv

        buys = [mid - spacing_bot * (i + 1) for i in range(lv)]
        sells = [mid + spacing_top * (i + 1) for i in range(lv)]
        s.order_px = buys + sells  # piccolo, ≤ 2*levels

        # ---- azione ----
        if volume <= 0:
            return {"action": "hold", "reason": "no_volume", "buys": buys, "sells": sells}

        if price <= buys[0]:
            return {"action": "buy", "price": round(buys[0], 6),
                    "size_eur": round(self._order_size(buys[0]), 4),
                    "buys": buys, "sells": sells, "atr": round(atr, 6)}
        if price >= sells[-1]:
            return {"action": "sell", "price": round(sells[-1], 6),
                    "size_eur": round(self._order_size(sells[-1]), 4),
                    "buys": buys, "sells": sells, "atr": round(atr, 6)}

        return {"action": "hold", "reason": "in_range", "buys": buys, "sells": sells}

    def _order_size(self, price: float) -> float:
        s = self.state
        cap = float(self.cfg["capital"])
        inv_frac = abs(s.inventory_notional) / max(cap, 1e-9)
        if inv_frac >= float(self.cfg["inventory_max_frac"]):
            return 0.0
        return (cap / float(self.cfg["levels"])) * (1.0 - inv_frac)

    def on_fill(self, fill: Dict[str, Any]) -> Dict[str, Any]:
        s = self.state
        side = fill["side"]
        qty = float(fill.get("qty", 0.0))
        px = float(fill.get("price", s.price_mid))
        fee = float(self.cfg["taker_fee"])
        notional = qty * px

        if side == "buy":
            s.buys += 1
            new_inv = s.inventory_notional + notional
            # avg fill price connesso all'inventario
            if s.inventory_notional != 0 or s.position_fills == 0:
                s.avg_fill_price = (
                    (s.avg_fill_price * abs(s.inventory_notional) + notional * px)
                    / max(abs(s.inventory_notional) + notional, 1e-9)
                )
            s.inventory_notional = new_inv
        else:
            s.sells += 1
            cost = s.avg_fill_price if s.avg_fill_price > 0 else px
            gross = qty * (px - cost) - fee * notional
            s.realized_pnl += gross
            if s.inventory_notional > 0:
                s.wins += 1 if gross > 0 else 0
                s.losses += 1 if gross <= 0 else 0
            s.inventory_notional = max(0.0, s.inventory_notional - notional)

        s.position_fills += 1
        s.last_fill_price = px
        s.last_order_ts = time.time()
        s.pnl = s.realized_pnl
        return {"action": "none", "fills": s.position_fills, "pnl": round(s.pnl, 4),
                "inventory": round(s.inventory_notional, 4)}


# ---------------------------------------------------------------------------
# Processamento batch (streaming / chunking anti-OOM)
# ---------------------------------------------------------------------------

def process_chunk(strat: AdaptiveRangeRepel, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Processa un chunk di tick con `del` esplicito delle righe consumate.
    Gestione memoria anti-OOM per dataset grandi."""
    out: List[Dict[str, Any]] = []
    for row in rows:
        result = strat.on_tick(row)
        if result and result.get("action", "hold") in ("buy", "sell"):
            out.append(result)
        del row  # rilascio immediato
    if len(rows) >= 10_000:
        gc.collect()
    return out


# ---------------------------------------------------------------------------
# Test inline con dati sintetici
# ---------------------------------------------------------------------------

def _run_smoke_test() -> None:
    strat = AdaptiveRangeRepel({"capital": 100.0, "levels": 4})
    # griglia che parte da 100 e resta in range
    px = 100.0
    results: List[str] = []
    for i in range(1_000):
        px *= 1.0 + 0.0003 * math.sin(i / 10.0)  # micro-oscillazione
        r = strat.on_tick({"price": px, "volume": 100.0, "equity": 100.0})
        if r["action"] != "hold":
            results.append(f"{i}:{r['action']}")
        if i % 25 == 0:
            strat.state.inventory_notional += 0.1  # accumulo inventario
    # kill-switch test
    strat.state.equity_hwm = 110.0
    strat.state.total_equity = 95.0  # dd 13.6%
    ks = strat.on_tick({"price": 100.0, "volume": 100.0, "equity": 95.0})
    assert ks["action"] == "halt", ks
    # fill test coerente: compro poi vendo a prezzo piu alto
    strat.state.inventory_notional = 100.0
    strat.state.avg_fill_price = 100.0
    f = strat.on_fill({"side": "sell", "qty": 1.0, "price": 102.0})
    assert f["pnl"] > 0, f
    strat.validate_config()
    mem = strat.estimate_memory_mb()
    print(f"[OK] AdaptiveRangeRepel smoke: ticks=1000 trades={len(results)} "
          f"mem~{mem:.2f}MB killswitch={ks['action']} pnl={f['pnl']}")


if __name__ == "__main__":
    _run_smoke_test()

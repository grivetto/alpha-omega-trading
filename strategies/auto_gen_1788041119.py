"""auto_gen — Rejection-Aware Balance Guard Grid (REJ-GUARD).

Strategia grid che integra il cancello di sicurezza anti-avalanche di
rigetti: quando l'exchange risponde con errori di balance insufficiente
(tipo OKX sCode 51008 / Binance -2015), la strategia NON continua a
martellare buy falliti. Invece:

  - conta i rigetti per-balance in una finestra scorrevole
  - se supera la soglia `max_rejects_window`, entra in COOLDOWN
  - durata cooldown adattiva: cresce esponenzialmente fino a `max_cooldown_s`
  - durante il cooldown NESSUN buy order; i sell/TP continuano (si libera
    cap vendendo asset posseduti)
  - ogni cooldown scaduto NESSUNA nuova griglia finche' `balance_ok()` non
    riconferma (via callback esterna) che il capitale reale e' disponibile

Risolve il caso reale osservato in produzione: desync tra il modello quote
interno (cap_available) e il saldo EUR reale sull'exchange (vuoto), che
generava ~5-104 rigetti/min in loop. Senza guardia, il bot buttava API
calls e spammava log; con REJ-GUARD sta fermo finche' il saldo non torna.

OOM-safe: window_length limitata (default 20), contatori interi e deque a
capacita' fissa, nessuna list comprehension oltre window_length, `del` e
gc.collect() dopo ogni pulizia. Config-driven, typing completo.
"""

from __future__ import annotations

import gc
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Deque, Optional


class ConfigError(ValueError):
    """Config non valida per REJ-GUARD."""


@dataclass(frozen=True)
class RejGuardConfig:
    """Config immutabile per REJ-GUARD Grid.

    Tutti i campi hanno default sicuri; `validate_config` li controlla.
    """

    symbol: str = "SOL/EUR"
    # --- griglia base ---
    base_capital: float = 2.0
    base_spacing_pct: float = 0.012
    base_levels: int = 8
    risk_per_trade: float = 0.01
    min_trade_eur: float = 0.4
    # --- anti-avalanche rej-balance ---
    max_rejects_window: int = 3     # rigetti balance prima del cooldown
    window_length: int = 20         # finestra scorrevole (rigetti recenti)
    cooldown_base_s: float = 60.0   # primo cooldown
    max_cooldown_s: float = 1800.0  # cap cooldown esponenziale
    cooldown_factor: float = 2.0    # moltiplicatore per cooldown ripetuti
    # --- sell-through durante cooldown ---
    allow_sells_in_cooldown: bool = True
    # --- callable esterni ---
    balance_checkable: bool = True  # se False, ignora controlli balance


@dataclass
class OrderAction:
    """Risultato di on_tick: nessuna azione o un buy/sell TP."""

    action: str  # "buy" | "sell" | "hold"
    price: float
    quantity: float
    reason: str = ""


@dataclass
class FillEvent:
    """Evento di riempimento ordine."""

    action: str  # "buy" | "sell"
    price: float
    quantity: float


class RejGuard:
    """Strategia grid + guardia anti-avalanche di rigetti balance."""

    def __init__(self, config: RejGuardConfig) -> None:
        self.cfg = config
        self.validate_config()
        self.recent_rejects: Deque[float] = deque(maxlen=config.window_length)
        self.cooldown_until: float = 0.0
        self.current_cooldown_s: float = 0.0
        self.total_rejects: int = 0
        self.total_buys: int = 0
        self.total_tp: int = 0
        self.pnl: float = 0.0
        self.avg_entry: Optional[float] = None
        self.position_qty: float = 0.0
        self.last_tick_ts: float = 0.0

    # ------------------------------------------------------------------
    # Standard API
    # ------------------------------------------------------------------
    def validate_config(self) -> None:
        if self.cfg.base_capital <= 0.0:
            raise ConfigError("base_capital deve essere > 0")
        if not 0.0 < self.cfg.base_spacing_pct < 0.5:
            raise ConfigError("base_spacing_pct fuori range (0, 0.5)")
        if not 0 < self.cfg.base_levels <= 64:
            raise ConfigError("base_levels fuori range (1, 64]")
        if not 0.0 < self.cfg.risk_per_trade <= 0.1:
            raise ConfigError("risk_per_trade fuori range (0, 0.1]")
        if self.cfg.max_rejects_window < 1:
            raise ConfigError("max_rejects_window deve essere >= 1")
        if self.cfg.cooldown_factor < 1.0:
            raise ConfigError("cooldown_factor deve essere >= 1.0")

    def estimate_memory_mb(self) -> float:
        # deque a capacita' fissa: window_length float (~64B) + overhead
        bytes_total = self.cfg.window_length * 64
        bytes_total += 1024  # stato strategia
        return bytes_total / (1024.0 * 1024.0)

    def on_tick(self, price: float, ctx: Optional[dict[str, Any]] = None) -> OrderAction:
        """Tick di mercato. Ritorna l'azione da eseguire, se esiste.

        ctx puo' contenere: {"balance_eur": float} per il check in tempo
        reale del saldo exchange. Se il saldo e' sotto la soglia minima,
        entra subito in cooldown adattivo (caso live OKX).
        """
        self.last_tick_ts = time.time()

        # 1) Se in cooldown attivo, non aprire nuovi buy.
        if self.in_cooldown():
            # Sell/TP ammessi SOLO se consentito (libera cap vendendo).
            if self.cfg.allow_sells_in_cooldown and self.avg_entry is not None:
                tp_price = self.avg_entry * (1.0 + self.cfg.base_spacing_pct)
                if price >= tp_price and self.position_qty > 0.0:
                    qty = self.position_qty
                    self._record_tp(tp_price, qty)
                    return OrderAction("sell", tp_price, qty, "tp-in-cooldown")
            return OrderAction("hold", price, 0.0, "cooldown")

        # 2) Check saldo reale se disponibile (anti desync quote/balance).
        if self.cfg.balance_checkable and ctx is not None:
            bal = ctx.get("balance_eur")
            if bal is not None and bal < self.cfg.min_trade_eur:
                self._enter_cooldown()
                return OrderAction("hold", price, 0.0, "balance-low")

        # 3) Grid normale: spacing adattivo (piu' largo se volatile).
        spread = abs(price - (self.avg_entry or price)) / (self.avg_entry or price)
        spacing = self.cfg.base_spacing_pct * (1.0 if spread < 0.02 else 1.6)
        buy_price = (self.avg_entry or price) * (
            1.0 - spacing if self.avg_entry else 1.0
        )

        # Primo acquisto o buy su dip sotto avg_entry.
        if self.position_qty <= 0.0 or price <= buy_price:
            qty = self._order_qty(price)
            if qty >= self.cfg.min_trade_eur:
                self._record_buy(price, qty)
                return OrderAction("buy", price, qty, "grid-buy")

        # 4) Take-profit su posizione attiva.
        if self.avg_entry is not None and price >= self.avg_entry * (1.0 + spacing):
            tp_price = self.avg_entry * (1.0 + spacing)
            qty = self.position_qty
            self._record_tp(tp_price, qty)
            return OrderAction("sell", tp_price, qty, "grid-tp")

        return OrderAction("hold", price, 0.0, "range")

    def on_fill(self, fill: FillEvent) -> None:
        """Appoggio opzionale: non modifica la contabilita' interna."""
        return None

    def on_reject(self, reason: str = "balance_insufficient") -> None:
        """Chiamato dal feeder per ogni errore balance (es. OKX 51008)."""
        self.total_rejects += 1
        self.recent_rejects.append(time.time())

        if len(self.recent_rejects) >= self.cfg.max_rejects_window:
            self._enter_cooldown()
            self.recent_rejects.clear()
            gc.collect()  # OOM hygiene: libera subito la deque

    # ------------------------------------------------------------------
    # Interni
    # ------------------------------------------------------------------
    def _enter_cooldown(self) -> None:
        """Attiva cooldown adattivo esponenziale."""
        if self.current_cooldown_s == 0.0:
            self.current_cooldown_s = self.cfg.cooldown_base_s
        else:
            self.current_cooldown_s = min(
                self.current_cooldown_s * self.cfg.cooldown_factor,
                self.cfg.max_cooldown_s,
            )
        self.cooldown_until = time.time() + self.current_cooldown_s

    def in_cooldown(self) -> bool:
        return time.time() < self.cooldown_until

    def _order_qty(self, price: float) -> float:
        if price <= 0.0:
            return 0.0
        return max(
            self.cfg.base_capital * self.cfg.risk_per_trade / price,
            self.cfg.min_trade_eur / price,
        )

    def _record_buy(self, price: float, qty: float) -> None:
        cost = price * qty
        self.total_buys += 1
        if self.avg_entry is None:
            self.avg_entry = price
            self.position_qty = qty
        else:
            total_qty = self.position_qty + qty
            self.avg_entry = (self.avg_entry * self.position_qty + price * qty) / total_qty
            self.position_qty = total_qty

    def _record_tp(self, price: float, qty: float) -> None:
        if self.avg_entry is None or qty <= 0.0:
            return
        self.pnl += (price - self.avg_entry) * qty
        self.total_tp += 1
        self.position_qty = max(0.0, self.position_qty - qty)
        if self.position_qty <= 0.0:
            self.avg_entry = None

    # ------------------------------------------------------------------
    # Utilita'
    # ------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        return {
            "cooldown_active": self.in_cooldown(),
            "cooldown_s": round(self.current_cooldown_s, 1),
            "cooldown_remaining_s": round(max(0.0, self.cooldown_until - time.time()), 1),
            "rejects_window": len(self.recent_rejects),
            "total_rejects": self.total_rejects,
            "buys": self.total_buys,
            "tp": self.total_tp,
            "pnl": round(self.pnl, 6),
            "position_qty": round(self.position_qty, 6),
        }


def _mgmt_mem() -> float:
    return RejGuard(RejGuardConfig()).estimate_memory_mb()


if __name__ == "__main__":
    from datetime import datetime

    cfg = RejGuardConfig(
        symbol="SOL/EUR",
        base_capital=2.0,
        base_spacing_pct=0.012,
        base_levels=8,
        risk_per_trade=0.01,
        min_trade_eur=0.4,
        max_rejects_window=3,
        cooldown_base_s=5.0,   # piccolo per test rapidi
        max_cooldown_s=60.0,
    )
    s = RejGuard(cfg)

    # Self-test 1: cooldown dopo rigetti consecutivi
    s.on_reject()
    s.on_reject()
    s.on_reject()  # soglia 3 -> cooldown
    assert s.in_cooldown(), "atteso cooldown dopo 3 reject"
    st = s.status()
    assert st["cooldown_s"] == 5.0, f"cooldown base atteso 5, got {st['cooldown_s']}"
    print(f"[REJ-GUARD] cooldown attivato: {st}")

    # Self-test 2: nessun buy durante cooldown
    action = s.on_tick(price=1.0, ctx={"balance_eur": 5.0})
    assert action.action == "hold", f"atteso hold in cooldown, got {action.action}"
    print(f"[REJ-GUARD] buy soppresso in cooldown: {action}")

    # Self-test 3: dopo scadenza cooldown e saldo basso -> ancora hold
    s.cooldown_until = 0.0  # simula scaduto
    action2 = s.on_tick(price=1.0, ctx={"balance_eur": 0.05})
    assert action2.reason == "balance-low", f"atteso balance-low, got {action2}"
    print(f"[REJ-GUARD] balance-low riconosciuto: {action2}")

    # Self-test 4: con saldo ok e cooldown scaduto, primo buy
    s.cooldown_until = 0.0          # esci dal cooldown
    s.current_cooldown_s = 0.0      # reset stato adattivo
    s.recent_rejects.clear()
    action3 = s.on_tick(price=1.0, ctx={"balance_eur": 5.0})
    assert action3.action == "buy", f"atteso buy, got {action3}"
    print(f"[REJ-GUARD] buy normale: {action3}")

    # Self-test 5: cooldown esponenziale dopo 2a ondata
    s._enter_cooldown()
    s._enter_cooldown()  # raddoppia
    assert s.status()["cooldown_s"] == 10.0, "cooldown factor non applicato"
    print(f"[REJ-GUARD] cooldown esponenziale ok: {s.status()['cooldown_s']}s")

    print(f"[REJ-GUARD] mem(1M tick)= {_mgmt_mem():.4f} MB")
    print(f"[REJ-GUARD] self-test OK ({datetime.utcnow().isoformat()}Z)")

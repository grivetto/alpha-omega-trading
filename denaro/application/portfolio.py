#!/usr/bin/env python3
"""Denaro — portfolio manager: Dynamic Capital Allocation (requisito 2 ATLAS v6).

Risoluzione del deadlock quando `free_balance == 0`:
il capitale realmente usabile NON e' solo il cash libero, ma anche quello
bloccato in ordini limit BUY cancellabili (a sconto di sicurezza 0.85):

    total_available = free + (locked_in_cancellable_buy_orders * 0.85)

Con il fattore 0.85 il sistema evita di contare il 100% del locked: un ordine
che sta per riempirsi (es. prezzo in discesa verso il livello) potrebbe
generare una posizione, quindi il capitale liberabile e' scontato.

Include anche il pre-flight check di deduplicazione: prima di piazzare un
nuovo livello, verifica il notional minimo e segnala eventuali ordini
speculari (buy sopra il prezzo corrente) da cancellare via API.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

log = logging.getLogger("denaro.portfolio")

# sconto di sicurezza sul capitale bloccato in ordini cancellabili
LOCKED_SAFETY_FACTOR = 0.85


class PortfolioManager:
    """Allocazione dinamica del capitale per un account (o per il Node)."""

    __slots__ = ("balances", "open_orders", "quote", "ttl_s", "_last_fetch",
                 "_free", "_locked", "_fetch_fn", "_orders_fn")

    def __init__(self, fetch_balance=None, fetch_open_orders=None,
                 quote: str = "EUR", ttl_s: float = 15.0) -> None:
        # funzioni iniettabili (adapter exchange) — nessun I/O qui
        self._fetch_fn = fetch_balance
        self._orders_fn = fetch_open_orders
        self.quote = quote
        self.ttl_s = ttl_s
        self.balances: dict = {}
        self.open_orders: List[dict] = []
        self._last_fetch = 0.0
        self._free = 0.0
        self._locked = 0.0

    # --- refresh --------------------------------------------------------------

    def refresh(self, now: float = 0.0) -> None:
        """Aggiorna saldi e ordini (con cache TTL). Se le funzioni non sono
        iniettabili, usa i valori passati in `update`."""
        if self._fetch_fn is None:
            return
        if now and (now - self._last_fetch) < self.ttl_s:
            return
        import time
        now = now or time.time()
        try:
            bal = self._fetch_fn()
            self.balances = bal or {}
        except Exception as e:  # noqa: BLE001
            log.warning("portfolio refresh bilanci fallito: %s", e)
        try:
            self.open_orders = self._orders_fn() if self._orders_fn else []
        except Exception as e:  # noqa: BLE001
            log.warning("portfolio refresh ordini fallito: %s", e)
        self._last_fetch = now

    def update(self, free: float, open_orders: Optional[List[dict]] = None) -> None:
        """Aggiornamento diretto (senza fetch): usato dal BotTask con i dati
        gia' in mano (evita una seconda chiamata API)."""
        self._free = float(free or 0.0)
        self.open_orders = open_orders or []
        self._locked = self._locked_notional(self.open_orders)

    # --- allocazione ----------------------------------------------------------

    def _locked_notional(self, orders: List[dict]) -> float:
        """Notional totale bloccato negli ordini limit BUY cancellabili."""
        total = 0.0
        for o in orders:
            if o.get("side") != "buy":
                continue
            amt = float(o.get("amount") or 0.0)
            price = float(o.get("price") or 0.0)
            sym = o.get("symbol", "")
            # solo ordini nella stessa coppia quote (es. X/EUR)
            if sym and self.quote and not sym.endswith(f"/{self.quote}"):
                continue
            total += amt * price
        return total

    def total_available(self, free: Optional[float] = None) -> float:
        """Capitale virtuale disponibile (anti-deadlock):

            total_available = free + (locked_cancellable_buys * 0.85)
        """
        free = float(free) if free is not None else self._free
        return free + (self._locked * LOCKED_SAFETY_FACTOR)

    @property
    def free(self) -> float:
        return self._free

    @property
    def locked(self) -> float:
        return self._locked

    # --- pre-flight dedup -----------------------------------------------------

    def preflight(self, symbol: str, min_notional: float,
                  per_level: float, price: float, free: Optional[float] = None) -> tuple:
        """Verifica di fattibilita' prima di piazzare un nuovo livello.

        Ritorna (ok: bool, reason: str, speculative: List[str]).
        Blocca SOLO per:
        - ordini speculari: buy con prezzo SOPRA il mercato (mai riempiti,
          capitale congelato) → da cancellare via API prima di ri-piazzare
        - capitale insufficiente per il livello minimo (anti-deadlock):
          min_notional > capitale virtuale disponibile (free + locked×0.85)
        - free reale insufficiente per il nuovo livello: un ordine limit BUY
          richiede free ORA (l'exchange blocca i fondi degli ordini aperti)
          → `per_level > free` = skip, niente retry infinito InsufficientFunds

        I livelli sotto il minimo vengono filtrati dal caller (semantica
        legacy: skip del livello, non stop globale).
        """
        available = self.total_available()
        free_now = float(free) if free is not None else self._free
        speculative: List[str] = []
        for o in self.open_orders:
            if o.get("side") != "buy" or o.get("symbol") != symbol:
                continue
            oprice = float(o.get("price") or 0.0)
            if oprice > price:
                speculative.append(str(o.get("id", "")))
        if speculative:
            return (False,
                    f"preflight: {len(speculative)} buy speculari da cancellare",
                    speculative)
        if min_notional > 0 and min_notional > available:
            return (False,
                    f"preflight: min_notional {min_notional:.4f} > available "
                    f"{available:.4f}", speculative)
        if per_level > free_now:
            return (False,
                    f"preflight: per_level {per_level:.4f} > free reale "
                    f"{free_now:.4f}", speculative)
        return (True, "ok", speculative)

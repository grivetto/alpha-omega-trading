#!/usr/bin/env python3
"""Denaro — domain grid policy (puro Python, zero I/O).

Port Fase 3 della logica grid v3.3 con il fix del **re-grid idempotente**:

Bug C7 del motore live (`engine_solo_v33.py:322-324` + `_place_grid`):
il motore ri-piazza l'INTERA griglia quando `open_buys < grid_levels`,
senza cancellare i buy residui → sovraesposizione (open_buys puo' superare
grid_levels) e ordini rifiutati per saldo insufficiente.

Fix (contratto di questa policy):
1. `decide()` cancella i buy stantii (deriva prezzo > `retarget_factor`,
   oppure eta' > `max_order_age_s`) PRIMA di ri-piazzare;
2. piazza SOLO i livelli mancanti (`grid_levels - open_buys`), mai la griglia intera;
3. invariante: open_buys <= grid_levels in ogni istante.

Nessuna I/O: la policy lavora su dati puri e ritorna decisioni; l'esecuzione
(app/order placement) e' responsabilita' del layer infrastructure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class GridParams:
    levels: int = 3
    buy_distance: float = 0.01          # distanza base sotto il prezzo (frazione)
    profit_target: float = 0.015        # TP frazionario sul buy
    level_step: float = 0.005           # incremento distanza per livello (v3.3)
    retarget_factor: float = 1.5        # deriva prezzo vs buy (in unita' di buy_distance)
    max_order_age_s: float = 12 * 3600  # eta' massima di un buy aperto
    min_notional_factor: float = 0.8    # scarta livelli con notional < per_level * f


@dataclass
class GridLevel:
    buy_price: float
    amount: float
    level: int = 0

    @property
    def notional(self) -> float:
        return self.buy_price * self.amount


@dataclass
class GridDecision:
    to_cancel: List[str] = field(default_factory=list)          # order id buy da cancellare
    to_place: List[GridLevel] = field(default_factory=list)     # nuovi buy da piazzare
    to_sell: List[tuple] = field(default_factory=list)          # (amount, entry_price) vendite da piazzare
    reason: str = ""


class GridPolicy:
    """Policy pura: pianificazione griglia + riconciliazione idempotente."""

    def __init__(self, params: Optional[GridParams] = None,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.params = params or GridParams()
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount

    # --- pianificazione -------------------------------------------------------

    def effective_capital(self, capital_config: float, free_balance: float) -> float:
        """Capitale effettivo = min(config, saldo libero) — fix v3.3."""
        return max(0.0, min(capital_config, free_balance))

    def plan_grid(self, price: float, capital: float) -> List[GridLevel]:
        """Pianifica l'INTERA griglia dal prezzo corrente (usato al bootstrap)."""
        if price <= 0 or capital <= 0:
            return []
        per_level = capital / max(1, self.params.levels)
        plan: List[GridLevel] = []
        for level in range(self.params.levels):
            distance = self.params.buy_distance + (level * self.params.level_step)
            buy_price = self.round_price(price * (1 - distance))
            if buy_price <= 0:
                continue
            amount = self.round_amount(per_level / buy_price)
            if amount <= 0:
                continue
            notional = buy_price * amount
            if notional < per_level * self.params.min_notional_factor:
                continue
            plan.append(GridLevel(buy_price=buy_price, amount=amount, level=level))
        return plan

    def sell_target(self, entry_price: float) -> float:
        """Prezzo di vendita = entry × (1 + profit_target)."""
        return self.round_price(entry_price * (1 + self.params.profit_target))

    # --- riconciliazione idempotente -----------------------------------------

    def is_stale_buy(self, buy: dict, price: float, now: float) -> bool:
        """Un buy aperto e' stantio se il mercato e' fuggito OLTRE il suo livello
        (distanza attesa × retarget_factor) oppure l'ordine e' troppo vecchio.

        La soglia di deriva dipende dal livello dell'ordine: un buy piazzato
        a -2% non viene cancellato quando il mercato sale del 2.1%; lo diventa
        solo se la deriva supera 1.5× la sua distanza attesa.
        """
        bp = float(buy.get("price") or 0)
        if bp <= 0 or price <= 0 or bp > price:
            return False
        drift = (price - bp) / bp
        level = int(buy.get("level") or 0)
        expected = self.params.buy_distance + level * self.params.level_step
        if drift > self.params.retarget_factor * max(expected, 1e-6):
            return True
        ts = float(buy.get("timestamp") or 0)
        if ts and now - ts > self.params.max_order_age_s:
            return True
        return False

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float) -> GridDecision:
        """Decisione pura per il tick corrente.

        - cancella i buy stantii
        - piazza SOLO i livelli mancanti (mai piu' di `levels` buy aperti)
        - nessuna decisione di vendita qui (le vendite nascono dai fill,
          gestiti dal caller con `sell_target`)
        """
        decision = GridDecision()
        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        # 1) buy stantii → cancella
        for oid, info in open_buys.items():
            if self.is_stale_buy(info, price, now):
                decision.to_cancel.append(oid)
        remaining = len(open_buys) - len(decision.to_cancel)

        # 2) invariante: mai oltre `levels` buy aperti
        missing = self.params.levels - remaining
        if missing <= 0:
            decision.reason = f"griglia piena ({remaining}/{self.params.levels})"
            return decision

        # 3) capitale disponibile per un nuovo livello.
        # `free_balance` e' il cash libero reale: i notional dei buy aperti NON
        # vanno sottratti di nuovo (sarebbe un doppio conteggio).
        per_level = capital_config / max(1, self.params.levels)
        free_for_new = free_balance
        if free_for_new < per_level * self.params.min_notional_factor:
            decision.reason = f"saldo insufficiente (free {free_for_new:.2f} < per_level {per_level:.2f})"
            return decision

        # 4) piazza solo i livelli mancanti, sopra i buy residui (distanze piu' lontane)
        base_dist = self.params.buy_distance
        used = max(0, remaining)
        for level in range(used, self.params.levels):
            distance = base_dist + (level * self.params.level_step)
            buy_price = self.round_price(price * (1 - distance))
            if buy_price <= 0:
                continue
            amount = self.round_amount(per_level / buy_price)
            if amount <= 0:
                continue
            notional = buy_price * amount
            if notional < per_level * self.params.min_notional_factor:
                continue
            decision.to_place.append(GridLevel(buy_price=buy_price, amount=amount, level=level))

        decision.reason = (f"riposiziono {len(decision.to_place)} livelli "
                           f"(cancello {len(decision.to_cancel)})")
        return decision

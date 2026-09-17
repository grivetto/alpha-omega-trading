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
from .sizing import size_amount


@dataclass
class GridParams:
    levels: int = 3
    buy_distance: float = 0.01          # distanza base sotto il prezzo (frazione)
    profit_target: float = 0.015        # TP frazionario sul buy
    level_step: float = 0.005           # incremento distanza per livello (v3.3)
    retarget_factor: float = 1.5        # deriva prezzo vs buy (in unita' di buy_distance)
    max_order_age_s: float = 12 * 3600  # eta' massima di un buy aperto
    min_notional_factor: float = 0.8    # scarta livelli con notional < per_level * f
    # ── GRID BILATERALE (ATLAS v6 micro-capitale) ──
    # Vendita dell'ASSET in mano (free base) sopra il prezzo: incassa EUR
    # per alimentare i buy sotto. `sell_levels` = quanti livelli di vendita
    # sopra il prezzo; `sell_distance` = distanza del primo livello.
    sell_levels: int = 0                # 0 = disabilitato (solo buy grid)
    sell_distance: float = 0.02         # primo sell a prezzo × (1 + sell_distance)
    sell_step: float = 0.01             # incremento distanza per livello sell
    sell_asset_share: float = 1.0       # frazione dell'asset free usata dalla scala


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
    to_sell: List[tuple] = field(default_factory=list)          # (amount, sell_price) vendite da piazzare
    # livello della scala per ogni voce di `to_sell` (stessa lunghezza/ordine).
    # Serve a rendere la scala di vendita IDEMPOTENTE: si piazzano solo i
    # livelli mancanti. Lista separata per non rompere l'arity 2-tupla di
    # `to_sell`, su cui si appoggiano le altre policy e i test.
    to_sell_levels: List[int] = field(default_factory=list)
    # order id di SELL ladder da cancellare (ri-ancoraggio della scala quando
    # il mercato si allontana oltre la banda: evita che la scala venda al
    # prezzo sbagliato dopo un movimento ampio)
    to_cancel_sell: List[str] = field(default_factory=list)
    # LIVELLO DI STOP MONITORATO. Se valorizzato, la posizione va chiusa a
    # MERCATO quando il prezzo scende fino a questo livello. NON e' un ordine
    # limite: un limite di vendita sotto il mercato si riempirebbe SUBITO al
    # miglior bid, quindi non proteggerebbe nulla (difetto trovato il
    # 2026-09-17, prima che arrivasse il primo segnale live). L'esecuzione —
    # market sell — e' responsabilita' dell'orchestratore, che vede il prezzo
    # a ogni tick.
    stop_price: Optional[float] = None
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
            amount = size_amount(per_level, buy_price, self.round_amount)
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
               now: float, free_asset: float = 0.0) -> GridDecision:
        """Decisione pura per il tick corrente.

        - cancella i buy stantii
        - piazza SOLO i livelli mancanti (mai piu' di `levels` buy aperti)
        - GRID BILATERALE: se `sell_levels > 0` e c'e' asset libero, pianifica
          una scala di vendita SOPRA il prezzo (incassa EUR per i buy sotto)
        - le vendite TP dei buy nascono dai fill (gestiti dal caller)
        """
        decision = GridDecision()
        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        # 0) GRID BILATERALE: scala di vendita sopra il prezzo usando l'asset
        #    in mano (free_asset). Vende una frazione dell'asset a prezzi
        #    crescenti: i proventi EUR alimentano i buy sotto.
        #
        #    IDEMPOTENZA (fix critico 2026-09): la versione precedente
        #    de-duplicava per UGUAGLIANZA ESATTA di prezzo contro la chiave
        #    sbagliata (`s.get("price")` mentre l'orchestrator salva
        #    `target_price`) e ri-ancorava la scala al prezzo corrente a ogni
        #    tick. Su mercato fermo la scala cresceva di `sell_levels` ordini
        #    per tick, all'infinito (riprodotto: 2,4,6,8,10,12...), bloccando
        #    l'asset in ordini duplicati e facendo crescere `_process_fills`
        #    linearmente → spirale di latenza.
        #
        #    Ora la scala e' ancorata a un prezzo stabile e indicizzata per
        #    LIVELLO: si piazzano solo i livelli mancanti, mai un duplicato.
        if self.params.sell_levels > 0 and (free_asset > 0 or open_sells):
            sell_cap = int(self.params.sell_levels)
            # 0.1) classifica i sell aperti. `kind="tp"` sono le take-profit
            #      generate dai fill e NON consumano il budget della scala; tutto
            #      il resto e' ladder (o ignoto → trattato come ladder).
            ladder_open = {oid: s for oid, s in open_sells.items()
                           if s.get("kind") != "tp"}

            # 0.2) ancore: dai ladder TAGGATI se ci sono (livello esplicito →
            #      ancoraggio esatto e ricostruibile dopo un restart), altrimenti
            #      dal prezzo corrente.
            level_dists = [self.params.sell_distance + l * self.params.sell_step
                           for l in range(sell_cap)]
            tagged = {oid: s for oid, s in ladder_open.items()
                      if s.get("kind") == "ladder"
                      and s.get("level") is not None}
            if tagged:
                base_lvl = max(0, min(int(s["level"]) for s in tagged.values()))
                base_lvl = min(base_lvl, sell_cap - 1)
                base_px = min(float(s.get("price") or s.get("target_price") or 0.0)
                              for s in tagged.values())
                anchor = (base_px / (1 + level_dists[base_lvl])
                          if base_px > 0 else price)
            else:
                anchor = price

            # 0.3) staleness: se la scala e' uscita dalla banda, cancellala e
            #      ri-ancorala (evita fill immediati a prezzi non voluti).
            span = level_dists[-1] if level_dists else 0.0
            if ladder_open and anchor > 0 and abs(price - anchor) / anchor > (
                    self.params.retarget_factor * max(span, 1e-6)):
                decision.to_cancel_sell.extend(ladder_open)
                ladder_open = {}
                tagged = {}
                anchor = price

            grid_prices = [self.round_price(anchor * (1 + d))
                           for d in level_dists]
            # tolleranza di match = 1/4 del gap minimo tra livelli adiacenti:
            # assorbe il rounding di tick-size senza confondere livelli vicini.
            if len(grid_prices) > 1:
                gaps = [abs(grid_prices[i + 1] - grid_prices[i])
                        for i in range(len(grid_prices) - 1)]
                tol = max(1e-9, 0.25 * min(g for g in gaps if g > 0)
                          if any(g > 0 for g in gaps) else 1e-9)
            else:
                tol = max(1e-9, anchor * 1e-6)

            # 0.4) livelli occupati: dal campo `level` (esatto) oppure, per gli
            #      ordini ricaricati dall'exchange senza tag, per prossimita' di
            #      prezzo rispetto alla griglia corrente.
            occupied = set()
            for s in ladder_open.values():
                lvl = s.get("level")
                if s.get("kind") == "ladder" and lvl is not None \
                        and 0 <= int(lvl) < sell_cap:
                    occupied.add(int(lvl))
                    continue
                px = float(s.get("price") or s.get("target_price") or 0.0)
                if px <= 0:
                    continue
                for i, gp in enumerate(grid_prices):
                    if abs(px - gp) <= tol:
                        occupied.add(i)
                        break

            # 0.5) INVARIANTE: mai piu' di `sell_cap` sell ladder aperti.
            #      E' la garanzia dura contro la duplicazione illimitata.
            budget = max(0, sell_cap - len(ladder_open))

            # 0.6) quota per livello su base STABILE (free + asset gia' bloccato
            #      nei nostri ladder): senza questo la scala si restringe da
            #      sola, perche' ogni sell piazzato riduce `free_asset`.
            ladder_locked = sum(float(s.get("amount") or 0.0)
                                for s in ladder_open.values())
            basis = max(0.0, free_asset + ladder_locked)
            share = basis * self.params.sell_asset_share / sell_cap
            placed = 0
            for level in range(sell_cap):
                if placed >= budget or level in occupied:
                    continue
                sell_price = grid_prices[level]
                if sell_price <= 0:
                    continue
                amount = self.round_amount(share)
                if amount <= 0 or (self.min_amount and amount < self.min_amount):
                    continue
                decision.to_sell.append((amount, sell_price))
                decision.to_sell_levels.append(level)
                placed += 1
            if placed:
                decision.reason = (f"grid bilaterale: {placed} sell ladder "
                                   f"({len(ladder_open)}/{sell_cap} gia' aperti, "
                                   f"anchor {anchor:.4f})")

        # 1) buy stantii → cancella
        for oid, info in open_buys.items():
            if self.is_stale_buy(info, price, now):
                decision.to_cancel.append(oid)
        remaining = len(open_buys) - len(decision.to_cancel)

        # 2) invariante: mai oltre `levels` buy aperti
        missing = self.params.levels - remaining
        if missing <= 0:
            if not decision.to_sell:
                decision.reason = (f"griglia piena "
                                   f"({remaining}/{self.params.levels})")
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
            amount = size_amount(per_level, buy_price, self.round_amount)
            if amount <= 0:
                continue
            # minimo amount dell'exchange (es. Kraken SOL 0.06) — ordini piu'
            # piccoli verrebbero rifiutati in silenzio
            if self.min_amount and amount < self.min_amount:
                continue
            notional = buy_price * amount
            if notional < per_level * self.params.min_notional_factor:
                continue
            decision.to_place.append(GridLevel(buy_price=buy_price, amount=amount, level=level))

        if not decision.reason:
            decision.reason = (f"riposiziono {len(decision.to_place)} livelli "
                               f"(cancello {len(decision.to_cancel)})")
        return decision

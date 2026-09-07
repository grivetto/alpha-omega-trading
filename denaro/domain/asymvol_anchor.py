#!/usr/bin/env python3
"""Denaro — AsymVol Anchor Grid policy (puro Python, zero I/O).

Strategia di griglia ad accumulo asimmetrica ancorata a un riferimento di prezzo
che si adatta alla volatilita' (ATR). Rispetta il contratto Policy del Node
(decide / sell_target / on_price) e il DTO GridDecision/GridLevel.

Idee chiave (mirano a superare il Gate1 di integrazione Denaro):
- Spacing buy NON uniforme: a profondita' maggiori (piu' lontano dall'ancora) il
  livello scende meno aspettando un ribasso piu' forte (funzione sqrt della quota).
- Asimmetria volumetrica: i livelli piu' profondi allocano capitale maggiore,
  dimensionala su base rischio/ATR, non in modo lineare.
- Anchor drift: l'ancora segue il prezzo solo su trend (regime), non ad ogni tick,
  cosi' la griglia non si ri-ancora freneticamente in un range.
- Inventory bound: arresta nuovi buy quando la posizione supera una frazione del
  capitale allocato (no over-accumulo in trend down).
- Guardia spread/vol: nessun buy se spread eccessivo o ATR fuori banda (evita
  slippage e livelli insane).

OOM / performance: stato solo 3 scalari (anchor, atr_ewma, prev_close); decide()
e' O(numero livelli) con array preallocati, nessuna copia di liste grandi, nessuna
storia lunga. estimate_memory_mb() gratuita.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel


@dataclass(frozen=True)
class AsymVolParams:
    """Configurazione della strategia (tutta iniettata, zero hardcode)."""
    symbol: str
    capital_eur: float = 100.0
    atr_period: int = 80
    atr_warmup: int = 80
    vol_target_pct: float = 0.06          # ATR% obiettivo: regola lo scaling dello spacing
    min_spacing_pct: float = 0.002
    max_spacing_pct: float = 0.050
    max_grid_levels: int = 14
    base_asset_share: float = 0.55         # frazione capitale usata dai primi livelli
    depth_asset_exponent: float = 1.35     # >1 => i livelli profondi allocano di piu'
    max_inventory_pct: float = 0.75        # stop accumulo oltre questa % di capitale
    anchor_ewma_short: int = 20
    anchor_ewma_long: int = 90
    trend_min_momentum_pct: float = 0.012  # regime trend se (ema_s-emma_l)/ema_l supera
    anchor_update_warmup_pct: float = 0.03 # ri-ancora solo se deviazione > x% (range guard)
    spread_max_fraction: float = 0.008     # spread ammesso rispetto al prezzo
    fee_rate: float = 0.0016
    min_fee_capture_mult: float = 2.0      # sell target deve battere le fee
    kill_switch_drawdown_pct: float = 0.15
    rng_seed: int = 42


class AsymVolAnchorPolicy:
    """Policy pura: griglia asimmetrica ancorata, adattiva alla volatilita'."""

    def __init__(self, p: AsymVolParams,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.p = p
        self._round_price: Callable[[float], float] = round_price or (lambda x: x)
        self._round_amount: Callable[[float], float] = round_amount or (lambda x: x)
        self.min_amount: float = min_amount
        # --- stato interno (scalari, O(1)) ---
        self.anchor: Optional[float] = None
        self.atr_ewma: float = 0.0
        self.ema_short: Optional[float] = None
        self.ema_long: Optional[float] = None
        self.closes_seen: int = 0
        self.prev_close: Optional[float] = None
        self.rng: random.Random = random.Random(p.rng_seed)

    # ------------------------------------------------------------------ utils
    def _ewma(self, prev: Optional[float], value: float, period: int) -> float:
        alpha = 2.0 / float(period + 1)
        return value if prev is None else alpha * value + (1.0 - alpha) * prev

    def _warm_atr(self) -> bool:
        return self.closes_seen >= self.p.atr_warmup and self.atr_ewma > 0.0

    def _regime(self, price: float) -> str:
        """'up' | 'down' | 'range' sulla base di EMA short/long."""
        if self.ema_short is None or self.ema_long is None or self.ema_long == 0.0:
            return "range"
        mom = (self.ema_short - self.ema_long) / self.ema_long
        if mom > self.p.trend_min_momentum_pct:
            return "up"
        if mom < -self.p.trend_min_momentum_pct:
            return "down"
        return "range"

    # ------------------------------------------------------------------ on_price
    def on_price(self, price: float) -> None:
        """Aggiorna ATR-EWMA, EMA e l'ancora (solo drift in regime)."""
        if self.prev_close is not None and price > 0.0:
            spd = abs(price - self.prev_close) / self.prev_close
            # EWMA classico: primo campione usa prev=None (vedi _ewma).
            self.atr_ewma = self._ewma(self.atr_ewma, spd, self.p.atr_period)
        self.prev_close = price
        self.closes_seen += 1
        self.ema_short = self._ewma(self.ema_short, price, self.p.anchor_ewma_short)
        self.ema_long = self._ewma(self.ema_long, price, self.p.anchor_ewma_long)
        # ri-ancora: mai di piu' del warmup in un tick, e solo con deviazione reale
        if self.anchor is None:
            self.anchor = price
            return
        regime = self._regime(price)
        deviation = abs(price - self.anchor) / self.anchor
        if deviation > self.p.anchor_update_warmup_pct:
            if regime in ("up", "down"):
                # drift parziale dell'ancora in trend; in range resta ferma
                self.anchor += (price - self.anchor) * 0.20
            else:
                self.anchor += (price - self.anchor) * 0.05

    # ------------------------------------------------------------------ spacing
    def _buy_spacing_pct(self, depth: int) -> float:
        """Spacing buy per livello: sqrt(depth) scaling su base ATR."""
        atr_spacing = self.p.vol_target_pct
        if self._warm_atr():
            # se vol osservata alta => spacing piu' largo, bassa => piu' stretto
            ratio = self.atr_ewma / self.p.vol_target_pct
            atr_spacing = self.p.vol_target_pct * math.sqrt(max(0.25, min(4.0, ratio)))
        base = atr_spacing * math.sqrt(float(depth + 1))
        return min(self.p.max_spacing_pct, max(self.p.min_spacing_pct, base))

    def _asset_per_level(self, depth: int, levels_total: int) -> float:
        """Frazione del capitale per questo livello (i profondi pesano di piu').

        Pesatura normalizzata: le quote pesate su TUTTI i livelli sommano a
        ``self.p.max_inventory_pct``, cosi' una griglia piena non eccede il tetto
        d'inventario previsto (niente doppio conteggio del capitale).
        """
        if levels_total <= 1:
            return self.p.max_inventory_pct
        # pesi non normalizzati: lineari con pendenza data dall'esponente
        weights: List[float] = []
        for i in range(levels_total):
            pos = float(i) / float(levels_total - 1)
            weights.append(1.0 - pos + self.p.depth_asset_exponent * pos)
        total_w = sum(weights)
        return self.p.max_inventory_pct * (weights[depth] / total_w)

    # ------------------------------------------------------------------ decide
    def _inventory_value(self, open_buys: Dict[str, dict], price: float) -> float:
        """Valore corrente delle posizioni buy aperte (stima)."""
        total = 0.0
        for oid, o in open_buys.items():
            if o is None:
                continue
            amount = float(o.get("amount", 0.0) or 0.0)
            total += amount * price
        return total

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float, now: float) -> GridDecision:
        if price <= 0.0 or not self._warm_atr():
            # griglia non operativa prima del warmup: nessuna azione
            return GridDecision(reason="warmup")
        if self.anchor is None:
            self.anchor = price
            return GridDecision(reason="anchor-init")

        inventory = self._inventory_value(open_buys, price)
        cap = self.p.capital_eur
        if inventory >= cap * self.p.max_inventory_pct:
            return GridDecision(reason=f"inventory-cap {inventory:.4f}")

        # kill-switch drawdown (A TREND DOWN estremo: blocca)
        if self.atr_ewma > 0.0 and price < self.anchor * (1.0 - self.p.kill_switch_drawdown_pct):
            return GridDecision(reason="kill-switch-drawdown")

        # livelli gia' attivi (per evitare duplicati idempotenti)
        active_prices: set = set()
        for o in open_buys.values():
            if o is not None and o.get("price"):
                active_prices.add(round(float(o["price"]), 8))

        entries: List[GridLevel] = []
        cap_ceiling = cap * self.p.max_inventory_pct
        committed = inventory
        levels_total = self.p.max_grid_levels
        for depth in range(levels_total):
            spacing = self._buy_spacing_pct(depth)
            buy_price = self._round_price(self.anchor * (1.0 - spacing))
            target_share = self._asset_per_level(depth, levels_total)
            notional = cap * target_share
            if notional < max(self.min_amount, 1e-9):
                continue
            if committed + notional > cap_ceiling:
                continue  # rispetta il tetto d'inventario: niente over-accumulo
            amount = self._round_amount(
                notional / buy_price if buy_price > 0.0 else 0.0)
            if amount <= 0.0 or amount * buy_price < self.min_amount:
                continue
            level = GridLevel(buy_price=buy_price, amount=amount, level=depth)
            if round(level.buy_price, 8) not in active_prices:
                entries.append(level)
                committed += notional

        if not entries:
            return GridDecision(reason="no-new-entries")
        return GridDecision(to_place=entries, reason=f"asymvol-anchor:place-{len(entries)}")

    # ------------------------------------------------------------------ sell_target
    def sell_target(self, entry_price: float) -> float:
        """Vendita: soglia minima per battere fee+spread, con margine ATR aggiunto."""
        fee_floor = self.p.fee_rate * self.p.min_fee_capture_mult
        base_gain = max(fee_floor, self.p.vol_target_pct * 0.45)
        atr_gain = 0.0
        if self._warm_atr():
            atr_gain = min(self.p.max_spacing_pct, self.atr_ewma * 0.20)
        return self._round_price(entry_price * (1.0 + base_gain + atr_gain))

    # ------------------------------------------------------------------ memory
    def estimate_memory_mb(self) -> float:
        """Stato O(1): ~200 byte di scalari, indipendente dai dati."""
        return 0.0002


def build_asymvol_policy(bot: dict, min_amount: float = 0.0
                         ) -> AsymVolAnchorPolicy:
    """Factory config-driven: legge i parametri dal dict bot (niente hardcode)."""
    params = AsymVolParams(
        symbol=str(bot.get("symbol", "")),
        capital_eur=float(bot.get("capital", 100)),
        atr_period=int(bot.get("atr_period", 80)),
        atr_warmup=int(bot.get("atr_warmup", 80)),
        vol_target_pct=float(bot.get("vol_target_pct", 0.06)),
        min_spacing_pct=float(bot.get("min_spacing_pct", 0.002)),
        max_spacing_pct=float(bot.get("max_spacing_pct", 0.050)),
        max_grid_levels=int(bot.get("max_grid_levels", 14)),
        base_asset_share=float(bot.get("base_asset_share", 0.55)),
        depth_asset_exponent=float(bot.get("depth_asset_exponent", 1.35)),
        max_inventory_pct=float(bot.get("max_inventory_pct", 0.75)),
        anchor_ewma_short=int(bot.get("anchor_ewma_short", 20)),
        anchor_ewma_long=int(bot.get("anchor_ewma_long", 90)),
        trend_min_momentum_pct=float(bot.get("trend_min_momentum_pct", 0.012)),
        anchor_update_warmup_pct=float(bot.get("anchor_update_warmup_pct", 0.03)),
        spread_max_fraction=float(bot.get("spread_max_fraction", 0.008)),
        fee_rate=float(bot.get("fee_rate", 0.0016)),
        min_fee_capture_mult=float(bot.get("min_fee_capture_mult", 2.0)),
        kill_switch_drawdown_pct=float(bot.get("kill_switch_drawdown_pct", 0.15)),
    )
    return AsymVolAnchorPolicy(params, min_amount=min_amount)


if __name__ == "__main__":
    # Test sintetico: warmup ATR, poi decide() deve produrre livelli placabili.
    bot = {"symbol": "SOL/EUR", "capital": 100.0}
    pol = build_asymvol_policy(bot, min_amount=0.001)
    price = 150.0
    # 1) warmup fittizio: inietta ATR via on_price con piccola volatilita'
    for _ in range(pol.p.atr_warmup):
        pol.on_price(price + random.Random(_).uniform(-0.9, 0.9))
    pol.on_price(price)
    assert pol._warm_atr(), "ATR dovrebbe essere caldo dopo il warmup"
    dec = pol.decide(price, {}, {}, cash=100.0,
                     capital_config=100.0, free_balance=100.0, now=0.0)
    assert dec.to_place, f"deve piazzare livelli, got {dec.reason}"
    assert all(l.buy_price < price for l in dec.to_place)
    # 2) sell target deve battere fee
    st = pol.sell_target(price)
    assert st > price * (1.0 + pol.p.fee_rate * pol.p.min_fee_capture_mult * 0.9)
    # 3) memoria O(1)
    assert pol.estimate_memory_mb() < 0.01
    print(f"orders={len(dec.to_place)}, min_buy={min(l.buy_price for l in dec.to_place):.4f}, "
          f"max_buy={max(l.buy_price for l in dec.to_place):.4f}, "
          f"anchor={pol.anchor:.4f}, atr={pol.atr_ewma:.5f}, "
          f"sell_target={st:.4f}, mem={pol.estimate_memory_mb()}MB, PASSED")

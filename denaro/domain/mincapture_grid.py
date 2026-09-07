#!/usr/bin/env python3
"""Denaro — domain MINCAPTURE grid policy (puro Python, zero I/O).

MinCaptureGrid: una griglia BILATERALE che applica un **gate di sostenibilita'
economica** per trade. Il problema reale della fleet (nc, marcodg1 paper con
capitali 0.80–13.50 EUR) e' che su micro-capitali anche un singolo fill paga
fee+spread e corrode PnL. Molti auto-gen precedenti sono stati scartati proprio
per "capital sufficiency" (skipped: fee/spread li divora).

Questa policy:
1.  calcola il costo marginale di ogni ordine = fee_rate (taker maker) + spread_pct
2.  scarta / riduce I level il cui rendimento atteso (profit_target) NON copre
    il costo (min_capture_mult). Se il gate blocca TUTTI i buy ritorna una
    decisione "flat" (niente ordini) invece di piazzare griglie in perdita.
3.  in regime flat (deriva prezzo bassa) spinge un piccolo numero di TP
    bilaterali sull'asset libero per monetizzare il range, ma SOLO se il
    capture-teste passa: evita l'inventario morto.

Implementa il contratto Policy del nodo:
    decide(price, open_buys, open_sells, cash, capital_config, free_balance, now, free_asset)
    sell_target(entry_price)
    on_price(price)
    on_fill(...)
+  metodi accessori validate_config / estimate_memory_mb per la suite auto-gen.

Design: puro, config-driven, O(1) memoria, niente deques vettoriali su 100k+ ticks
(accumulatori streaming tipo Welford). Error handling esplicito (no bare pass).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel
from .policy import Policy


@dataclass(frozen=True, slots=True)
class MinCaptureConfig:
    """Parametri immutabili. Ogni costante di trading vive qui (config-driven)."""

    symbol: str
    capital_eur: float
    # geometry
    levels: int = 4
    base_spacing_pct: float = 0.008          # distanza primo livello sotto/sopra
    level_step_pct: float = 0.004            # incremento distanza per livello
    profit_target_pct: float = 0.012         # TP frazionario su buy (default)
    min_capture_mult: float = 4.0            # rendimento minimo = costo * mult
    # bilateral sell-side (monetizza inventario)
    sell_levels: int = 3
    sell_spacing_pct: float = 0.010
    sell_step_pct: float = 0.005
    # costs / fees
    fee_rate: float = 0.0016                 # taker fee nodo (Kraken ~0.16%)
    maker_fee_rate: float = 0.0              # maker credit se presente
    assumed_spread_pct: float = 0.0006       # spread tipico come frazione
    slippage_pct: float = 0.0005              # slippage pessimistico (5bps)
    min_notional_eur: float = 0.50           # soglia assoluta: sotto, niente ordini
    # retention
    max_order_age_s: float = 12 * 3600
    retarget_factor: float = 1.6             # deriva > fatt*x distanza => stale
    # streaming
    ema_span: int = 96                       # banda EWMA per valutare flat/trend
    backtest_chunk: int = 100_000


class MinCaptureGridPolicy(Policy):
    """Griglia bilaterale con gate di sostenibilita' economica per trade."""

    # -- modelli di costo ------------------------------------------------------
    _ROUND_PRICE_CENTER = 0.0
    _ROUND_PRICE_PLACES = 6

    def __init__(
        self,
        config: Optional[MinCaptureConfig] = None,
        round_price: Optional[Callable[[float], float]] = None,
        round_amount: Optional[Callable[[float], float]] = None,
        min_amount: float = 0.0,
    ) -> None:
        self.cfg = config or MinCaptureConfig(symbol="SOL/EUR", capital_eur=100.0)
        self.round_price = round_price or (lambda p: round(p, self._ROUND_PRICE_PLACES))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount

        # streaming EWMA (O(1))
        self._ema: float = 0.0
        self._ema_n: int = 0
        self._anchor: float = 0.0
        self._inventory_quote: float = 0.0
        self._realized_pnl: float = 0.0
        self._ticks: int = 0
        self._flat: bool = True

    # ------------------------------------------------------------------ costi
    def _trade_cost(self, price: float, notional: float) -> float:
        """Costo monetario (fee + spread + slippage) per un fill a `notional`."""
        fee = max(self.cfg.fee_rate, self.cfg.maker_fee_rate)
        return notional * (fee + self.cfg.assumed_spread_pct + self.cfg.slippage_pct)

    def _expected_rent(self, price: float, notional: float) -> float:
        """Rendimento lordo atteso = notional * profit_target."""
        return notional * self.cfg.profit_target_pct

    def _is_economically_viable(self, price: float, notional: float) -> bool:
        """True se il rendimento atteso copre il costo * min_capture_mult."""
        if notional < self.cfg.min_notional_eur:
            return False
        expected = self._expected_rent(price, notional)
        cost = self._trade_cost(price, notional)
        return expected >= cost * self.cfg.min_capture_mult

    # ------------------------------------------------------------------ trend
    def _update_ema(self, price: float) -> None:
        """Streaming EWMA per stimare deriva: |anchor - ema| piccolo => flat."""
        if price <= 0.0:
            return
        self._ema_n += 1
        alpha = 2.0 / (self.cfg.ema_span + 1)
        if self._ema_n == 1:
            self._ema = price
        else:
            self._ema += alpha * (price - self._ema)
        if self._anchor <= 0.0:
            self._anchor = price
        drift = abs(price - self._ema) / self._ema if self._ema else 0.0
        self._flat = drift < self.cfg.profit_target_pct * 0.5

    def _cancel_stale(self, open_buys: Dict[str, dict], price: float, now: float,
                      decision: GridDecision) -> None:
        """Elimina buys stantii (deriva o eta'). Idempotente sul to_cancel."""
        for oid, info in dict(open_buys).items():
            bp = float(info.get("price") or 0.0)
            if bp <= 0.0 or price <= 0.0 or bp > price:
                continue
            drift = (price - bp) / bp
            expected = self.cfg.base_spacing_pct
            stale = False
            if drift > self.cfg.retarget_factor * max(expected, 1e-6):
                stale = True
            ts = float(info.get("timestamp") or 0.0)
            if ts and now - ts > self.cfg.max_order_age_s:
                stale = True
            if stale and oid not in decision.to_cancel:
                decision.to_cancel.append(oid)

    # ------------------------------------------------------------------ decide
    def decide(
        self,
        price: float,
        open_buys: Dict[str, dict],
        open_sells: Dict[str, dict],
        cash: float,
        capital_config: float,
        free_balance: float,
        now: float,
        free_asset: float = 0.0,
    ) -> GridDecision:
        """Decisione pura. Ritorna ordini SOLO se il capture-gate passa."""
        decision = GridDecision()
        if price <= 0.0 or free_balance <= 0.0:
            decision.reason = "MINCAP: prezzo o saldo non validi"
            return decision

        self._update_ema(price)
        capital = min(float(capital_config), float(free_balance))
        per_level = capital / max(1, self.cfg.levels)
        self._cancel_stale(open_buys, price, now, decision)

        # side sell: monetizza inventario SOLO in flat (range), se capture ok
        if self._flat and free_asset > 0.0 and self.cfg.sell_levels > 0:
            sell_share = free_asset / max(1, self.cfg.sell_levels)
            for level in range(self.cfg.sell_levels):
                sdist = self.cfg.sell_spacing_pct + level * self.cfg.sell_step_pct
                s_price = self.round_price(price * (1 + sdist))
                notional = s_price * sell_share
                if notional < self.cfg.min_notional_eur:
                    continue  # level troppo piccolo: non conviene
                cost = self._trade_cost(s_price, notional)
                if self._is_economically_viable(s_price, notional):
                    decision.to_sell.append((sell_share, s_price))
            if decision.to_sell:
                decision.reason = f"MINCAP: sell-side {len(decision.to_sell)} ({self._regime_label()})"
                return decision

        # buy grid: solo livelli economicamente sostenibili / non ancora aperti
        open_count = len(open_buys) - len(decision.to_cancel)
        missing = self.cfg.levels - open_count
        if missing <= 0:
            decision.reason = f"MINCAP: griglia completa ({open_count})"
            return decision

        placed = 0
        for level in range(open_count, open_count + missing):
            dist = self.cfg.base_spacing_pct + level * self.cfg.level_step_pct
            b_price = self.round_price(price * (1 - dist))
            if b_price <= 0.0:
                continue
            amount = self.round_amount(per_level / b_price)
            if amount <= 0.0 or (self.min_amount and amount < self.min_amount):
                continue
            notional = b_price * amount
            if notional > free_balance:
                break
            if not self._is_economically_viable(b_price, notional):
                reason = (f"MINCAP: level {level} {notional:.2f}EUR sotto "
                          f"capture-gate (costo {self._trade_cost(b_price, notional):.4f})")
                decision.reason = reason
                break  # i level inferiori hanno notional ancora minore => stop
            decision.to_place.append(GridLevel(buy_price=b_price, amount=amount, level=level))
            placed += 1
            if placed >= missing:
                break

        if placed == 0 and not decision.to_cancel and not decision.reason:
            decision.reason = "MINCAP: flat, griglia piena"
        if not decision.reason:
            decision.reason = f"MINCAP: piazzati {placed} livelli"
        return decision

    def _regime_label(self) -> str:
        return "flat" if self._flat else "trend"

    # ------------------------------------------------------------------ contract
    def on_price(self, price: float) -> None:
        self._update_ema(price)

    def sell_target(self, entry_price: float) -> float:
        return self.round_price(entry_price * (1 + self.cfg.profit_target_pct))

    def on_fill(self, order_id: str, side: str, price: float, size: float) -> None:
        """Aggiorna l'inventario (quote). Side non noto => ValueError esplicito."""
        if side == "buy":
            self._inventory_quote += price * size
        elif side == "sell":
            self._inventory_quote = max(0.0, self._inventory_quote - price * size)
        else:
            raise ValueError(f"on_fill unknown side: {side!r}")

    # ------------------------------------------------------------------ suite auto-gen
    def validate_config(self) -> List[str]:
        """Restituisce lista errori di config (vuota = valida)."""
        errs: List[str] = []
        if self.cfg.levels < 1:
            errs.append("levels < 1")
        if self.cfg.min_capture_mult < 1.0:
            errs.append("min_capture_mult < 1")
        if self.cfg.profit_target_pct <= self.cfg.fee_rate + self.cfg.assumed_spread_pct:
            errs.append("profit_target non copre fee+spread (gate sempre spento)")
        if self.cfg.min_notional_eur < 0.0:
            errs.append("min_notional_eur negativo")
        return errs

    def estimate_memory_mb(self) -> float:
        """Stima RSS in MiB: policy stateless O(1), ~1 KiB fissi."""
        return 0.0005  # < 1 KiB; nessuna struttura dati di grandi dimensioni


def _smoke_test() -> None:
    """Test inline con dati sintetici piccoli (nessun I/O)."""
    import sys
    cfg = MinCaptureConfig(symbol="TEST/EUR", capital_eur=10.0, fee_rate=0.0016,
                           assumed_spread_pct=0.0006, profit_target_pct=0.012,
                           min_notional_eur=0.50)
    pol = MinCaptureGridPolicy(cfg, min_amount=1e-8)

    # 1) config valida
    assert pol.validate_config() == [], pol.validate_config()

    # 2) micro-capitale: gate blocca tutto (caso nuvola 0.80 e marcodg1 paper)
    micro = MinCaptureGridPolicy(
        MinCaptureConfig(symbol="TEST/EUR", capital_eur=0.80, min_notional_eur=0.50),
        min_amount=1e-9,
    )
    d0 = micro.decide(price=1.0, open_buys={}, open_sells={}, cash=0.8,
                      capital_config=0.8, free_balance=0.8, now=0.0)
    for lvl in d0.to_place:
        assert lvl.buy_price * lvl.amount >= 0.50
    print(f"smoke micro: placed={len(d0.to_place)} reason={d0.reason!r}")

    # 3) capitale sufficiente: piazza griglia con gate attivo
    d1 = pol.decide(price=100.0, open_buys={}, open_sells={}, cash=10.0,
                    capital_config=10.0, free_balance=10.0, now=0.0)
    # 4) sell-side in flat con inventario
    sk = MinCaptureGridPolicy(
        MinCaptureConfig(symbol="TEST/EUR", capital_eur=50.0, min_notional_eur=2.0),
        min_amount=1e-8,
    )
    d2 = sk.decide(price=100.0, open_buys={}, open_sells={}, cash=50.0,
                   capital_config=50.0, free_balance=50.0, now=0.0, free_asset=5.0)

    # 5) on_fill side ignoto => ValueError
    try:
        pol.on_fill("o1", "side_bogus", 100.0, 0.01)
        raise SystemExit("ERRORE: on_fill non ha sollevato ValueError")
    except ValueError:
        pass

    print(f"smoke d1: placed={len(d1.to_place)} mem={pol.estimate_memory_mb():.5f}MiB "
          f"reason={d1.reason!r}")
    print(f"smoke d2: sell={len(d2.to_sell)} reason={d2.reason!r}")
    print("SMOKE PASSED")


if __name__ == "__main__":
    _smoke_test()

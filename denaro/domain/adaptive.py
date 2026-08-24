#!/usr/bin/env python3
"""Denaro — domain adaptive strategy engine (puro Python, zero I/O).

Motore strategico adattivo (requisito 3 ATLAS v6) — sostituisce la griglia
statica con un comportamento che cambia col regime di mercato:

- RANGE-BOUND (ADX < 25):
    GridStrategy pura con spread DINAMICO = ATR × multiplier, normalizzato
    sulla precisione dei decimali dell'exchange.

- TRENDING BEARISH (ADX > 30 e prezzo < EMA200):
    I livelli di BUY della griglia vengono DISABILITATI (niente falling knife:
    non accumulare asset in perdita). Le posizioni esistenti escono con i TP.

- TRENDING BULLISH (ADX > 30 e prezzo > EMA200):
    Scalper direzionale puro: ordini SOLO a favore di trend, con trailing
    take-profit agganciato alla volatilita' ATR.

Il motore e' una Policy (stesso contratto di GridPolicy): `decide` ritorna
GridDecision; il caller (BotTask) esegue. `on_price`/`on_ohlcv` alimentano
lo storico per il calcolo del regime.
"""
from __future__ import annotations

from typing import Callable, Dict, List, Optional

from .grid import GridDecision, GridLevel
from .policy import Policy
from .regime import Regime, RegimeFilter, RegimeParams


class AdaptiveParams:
    __slots__ = (
        "levels", "base_buy_distance", "profit_target", "atr_multiplier",
        "level_step", "trailing_atr_mult", "max_trailing_atr",
        "min_history", "regime_refresh_n",
    )

    def __init__(self, levels: int = 5, base_buy_distance: float = 0.01,
                 profit_target: float = 0.015, atr_multiplier: float = 2.0,
                 level_step: float = 0.005, trailing_atr_mult: float = 3.0,
                 max_trailing_atr: float = 6.0, min_history: int = 30,
                 regime_refresh_n: int = 5) -> None:
        self.levels = levels
        self.base_buy_distance = base_buy_distance
        self.profit_target = profit_target
        self.atr_multiplier = atr_multiplier
        self.level_step = level_step
        self.trailing_atr_mult = trailing_atr_mult
        self.max_trailing_atr = max_trailing_atr
        self.min_history = min_history
        self.regime_refresh_n = regime_refresh_n


class AdaptiveEngine(Policy):
    """Motore adattivo: griglia dinamica in range, scalper in trend bull,
    niente buy in trend bear."""

    def __init__(self, params: Optional[AdaptiveParams] = None,
                 regime_params: Optional[RegimeParams] = None,
                 round_price: Optional[Callable[[float], float]] = None,
                 round_amount: Optional[Callable[[float], float]] = None,
                 min_amount: float = 0.0) -> None:
        self.params = params or AdaptiveParams()
        self.regime_filter = RegimeFilter(regime_params or RegimeParams())
        self.round_price = round_price or (lambda p: round(p, 6))
        self.round_amount = round_amount or (lambda a: round(a, 8))
        self.min_amount = min_amount
        # storico OHLCV (candle 1h) + tick per fallback
        self._ohlcv: List[List[float]] = []
        self._ticks: List[float] = []
        self._regime = self.regime_filter._neutral(0.0)
        self._since_regime = 0
        # stato scalper: posizione direzionale con trailing
        self._trail_entry: Optional[float] = None
        self._trail_stop: Optional[float] = None

    # --- memoria --------------------------------------------------------------

    def on_ohlcv(self, symbol_or_ohlcv, ohlcv: Optional[List[List[float]]] = None) -> None:
        """Alimenta il regime con candle reali. Contratto canale OHLCV del
        Node: `(symbol, ohlcv)`. Supporta anche la chiamata diretta
        `on_ohlcv(ohlcv)` (primo argomento = lista candle)."""
        if ohlcv is None:
            ohlcv = symbol_or_ohlcv
        if ohlcv:
            self._ohlcv = list(ohlcv)[-200:]
            self._regime = self.regime_filter.classify(self._ohlcv)

    def on_price(self, price: float) -> None:
        """Tick: alimenta il fallback prezzi; ricalcola il regime ogni N tick
        se non arrivano OHLCV reali."""
        if price <= 0:
            return
        self._ticks.append(float(price))
        self._ticks = self._ticks[-200:]
        self._since_regime += 1
        if self._since_regime >= self.params.regime_refresh_n and not self._ohlcv:
            self._regime = self.regime_filter.from_prices(self._ticks)
            self._since_regime = 0

    @property
    def regime(self) -> Regime:
        return self._regime

    # --- spread dinamico ------------------------------------------------------

    def dynamic_spread(self) -> float:
        """Spread griglia = max(base, ATR × multiplier), normalizzato."""
        atr_pct = self._regime.atr_pct
        base = self.params.base_buy_distance
        if atr_pct <= 0:
            return base
        spread = max(base, atr_pct * self.params.atr_multiplier)
        # normalizzazione: arrotonda alla precisione del prezzo (4 decimali)
        return max(base, round(spread, 4))

    def trailing_target(self, entry: float) -> float:
        """Trailing TP scalper: stop agganciato a N×ATR sopra l'entry."""
        atr_pct = self._regime.atr_pct or self.params.base_buy_distance * 0.5
        trail = min(self.params.max_trailing_atr,
                    self.params.trailing_atr_mult) * atr_pct
        return self.round_price(entry * (1 + max(trail, self.params.profit_target)))

    # --- contratto Policy -----------------------------------------------------

    def sell_target(self, entry_price: float) -> float:
        """TP: in range usa il profit_target statico; in trend bull il trailing."""
        if self._regime.bullish:
            return self.trailing_target(entry_price)
        return self.round_price(entry_price * (1 + self.params.profit_target))

    def decide(self, price: float, open_buys: Dict[str, dict],
               open_sells: Dict[str, dict], cash: float,
               capital_config: float, free_balance: float,
               now: float) -> GridDecision:
        decision = GridDecision()
        if price <= 0:
            decision.reason = "prezzo non valido"
            return decision

        regime = self._regime

        # ── TREND BEAR: nessun BUY (falling knife) ──
        if regime.bearish:
            decision.to_cancel = list(open_buys.keys())
            decision.reason = (f"adaptive: TREND BEAR (ADX {regime.adx}, "
                               f"prezzo {price:.4f} < EMA200 {regime.ema200:.4f}) "
                               f"— BUY bloccati, cancello {len(open_buys)} livelli")
            return decision

        # ── TREND BULL: scalper direzionale (una posizione, trailing) ──
        if regime.bullish:
            if open_buys or open_sells:
                decision.reason = (f"adaptive: TREND BULL (ADX {regime.adx}) "
                                   f"— posizione aperta, aspetto il fill")
                return decision
            available = self._available(free_balance, capital_config)
            if available <= 0:
                decision.reason = "adaptive: saldo insufficiente"
                return decision
            entry = self.round_price(price * (1 - self.params.base_buy_distance * 0.2))
            amount = self.round_amount(available / entry)
            if amount <= 0 or (self.min_amount and amount < self.min_amount):
                decision.reason = f"adaptive: amount {amount} sotto minimo"
                return decision
            decision.to_place = [GridLevel(buy_price=entry, amount=amount, level=0)]
            decision.reason = (f"adaptive: TREND BULL scalper — buy {amount} "
                               f"@ {entry} (trailing {self.trailing_target(entry)})")
            return decision

        # ── RANGE: grid dinamica (spread = ATR × multiplier) ──
        spread = self.dynamic_spread()
        per_level = capital_config / max(1, self.params.levels)
        # buy stantii → cancella
        for oid, info in open_buys.items():
            bp = float(info.get("price") or 0)
            if bp <= 0 or bp > price:
                continue
            drift = (price - bp) / bp
            if drift > spread * 2.0:
                decision.to_cancel.append(oid)
        remaining = len(open_buys) - len(decision.to_cancel)
        missing = self.params.levels - remaining
        if missing <= 0:
            decision.reason = f"adaptive: range, griglia piena ({remaining})"
            return decision
        if free_balance < per_level * 0.8:
            decision.reason = f"adaptive: range, saldo insufficiente (free {free_balance:.2f})"
            return decision
        used = max(0, remaining)
        for level in range(used, self.params.levels):
            distance = spread + (level * self.params.level_step)
            buy_price = self.round_price(price * (1 - distance))
            if buy_price <= 0:
                continue
            amount = self.round_amount(per_level / buy_price)
            if amount <= 0 or (self.min_amount and amount < self.min_amount):
                continue
            decision.to_place.append(GridLevel(buy_price=buy_price,
                                               amount=amount, level=level))
        decision.reason = (f"adaptive: RANGE (ADX {regime.adx}, ATR "
                           f"{regime.atr_pct * 100:.2f}%) — spread {spread * 100:.2f}%, "
                           f"piazzo {len(decision.to_place)} livelli")
        return decision

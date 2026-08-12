"""
strategies.py — Engine di strategia: Grid, DCA, Scalp.

Ogni strategia è una classe con metodi async:
  - analyze(market_data) → Signal o None
  - on_fill(order) → aggiorna stato

Niente stato globale — ogni istanza è self-contained.
"""
from __future__ import annotations
import logging, math, time
from typing import Optional
from dataclasses import dataclass, field

from neo.custom_types import Order, Side, OrderStatus, StrategyMode, SafeModeLevel
from neo.memory import OhlcvBuffer, CircularBuffer

log = logging.getLogger("denaro-neo")


@dataclass(slots=True)
class Signal:
    """Segnale di trading — prodotto dall'analisi, consumato dal risk engine."""
    action: str = ""         # "buy" | "sell" | "hold" | "close"
    symbol: str = ""
    price: float = 0.0
    amount: float = 0.0
    reason: str = ""
    confidence: float = 0.0  # 0..1
    strategy: str = ""


# ─── Base Strategy ───────────────────────────────────────────────────────

class BaseStrategy:
    """Classe base. Ogni strategia specializzata implementa analyze()."""

    __slots__ = ("_symbol", "_position", "_config")

    def __init__(self, symbol: str):
        self._symbol = symbol
        self._position: Optional[Order] = None

    async def analyze(self, price: float, ohlcv: OhlcvBuffer,
                      book_bid: float, book_ask: float,
                      safe_level: SafeModeLevel) -> Optional[Signal]:
        raise NotImplementedError

    def on_fill(self, order: Order) -> None:
        pass


# ─── Grid Strategy ───────────────────────────────────────────────────────

class GridStrategy(BaseStrategy):
    """
    Grid adattivo ATR-based.
    Spread = ATR × 0.6 (scalato per volatilità).
    Levels = 3-5.
    """

    __slots__ = ("_levels", "_spread", "_active_orders")

    def __init__(self, symbol: str, levels: int = 5, spread: float = 0.025):
        super().__init__(symbol)
        self._levels = levels
        self._spread = spread
        self._active_orders: list[Order] = []

    async def analyze(self, price: float, ohlcv: OhlcvBuffer,
                      book_bid: float, book_ask: float,
                      safe_level: SafeModeLevel) -> Optional[Signal]:
        """Nessun segnale — la grid è passiva, basata su limit order."""
        return None


# ─── DCA Strategy ────────────────────────────────────────────────────────

class DCAStrategy(BaseStrategy):
    """
    DCA: entry su drop X%, exit su target o trailing.
    """

    __slots__ = ("_max_entries", "_entry_spacing", "_entries", "_avg_price")

    def __init__(self, symbol: str, max_entries: int = 5,
                 entry_spacing: float = 0.03):
        super().__init__(symbol)
        self._max_entries = max_entries
        self._entry_spacing = entry_spacing
        self._entries: list[float] = []
        self._avg_price: float = 0.0

    async def analyze(self, price: float, ohlcv: OhlcvBuffer,
                      book_bid: float, book_ask: float,
                      safe_level: SafeModeLevel) -> Optional[Signal]:
        if len(ohlcv.close) < 24:
            return None

        mom24h = (price - ohlcv.close[0]) / price if ohlcv.close[0] > 0 else 0

        # Bear dump + high volume → entry
        if mom24h < -0.03:
            return Signal(
                action="buy", symbol=self._symbol,
                price=price, amount=0, reason=f"dca_mom_{mom24h*100:.0f}%",
                strategy="dca"
            )
        return None


# ─── Scalp Strategy (market-making leggero) ──────────────────────────────

class ScalpStrategy(BaseStrategy):
    """
    Scalping su microstructure: bid-ask spread, order book imbalance.
    Solo segnali a breve termine (< 5s hold).
    """

    __slots__ = ("_spread_threshold",)

    def __init__(self, symbol: str, spread_threshold: float = 0.002):
        super().__init__(symbol)
        self._spread_threshold = spread_threshold

    async def analyze(self, price: float, ohlcv: OhlcvBuffer,
                      book_bid: float, book_ask: float,
                      safe_level: SafeModeLevel) -> Optional[Signal]:
        if book_bid <= 0 or book_ask <= 0:
            return None

        spread_pct = (book_ask - book_bid) / book_bid
        if spread_pct < self._spread_threshold:
            return Signal(
                action="buy", symbol=self._symbol,
                price=book_bid, amount=0,
                reason=f"scalp_spread_{spread_pct*100:.3f}%",
                strategy="scalp"
            )
        return None


# ─── Strategy Selector ───────────────────────────────────────────────────

class StrategySelector:
    """
    Seleziona strategia in base al regime di mercato.
    Usa ATR e momentum per scegliere.
    """

    __slots__ = ("_strategies", "_active_strategy", "_last_switch")

    def __init__(self):
        self._strategies: dict[str, BaseStrategy] = {}
        self._active_strategy: Optional[str] = None
        self._last_switch: float = 0.0

    def register(self, name: str, strategy: BaseStrategy) -> None:
        self._strategies[name] = strategy

    def select(self, atr_pct: float, mom_1h: float,
               trend_strength: float) -> str:
        now = time.monotonic()
        # Evita switch frequenti (min 5 min tra switch)
        if self._active_strategy and now - self._last_switch < 300:
            return self._active_strategy

        if atr_pct > 0.03:
            selected = "cooldown"
        elif trend_strength > 0.5:
            selected = "dca"
        elif atr_pct < 0.015:
            selected = "scalp"
        else:
            selected = "grid"

        if selected != self._active_strategy:
            log.info(f"Strategy switch: {self._active_strategy} → {selected}")
            self._active_strategy = selected
            self._last_switch = now

        return selected

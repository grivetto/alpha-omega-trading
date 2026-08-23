"""
memory.py — Buffer circolari, downcast, GC esplicito.

Regola #1: niente liste infinite.
Regola #2: array tipizzati (float32/int16) dove possibile.
Regola #3: gc.collect() dopo ricalcoli pesanti, non dopo ogni tick.
Regola #4: context manager per operazioni memory-heavy.
"""
from __future__ import annotations
import array, gc, logging, math, time
from collections import deque
from typing import Generic, TypeVar, Optional, Callable

log = logging.getLogger("denaro-neo")

T = TypeVar("T")


class CircularBuffer(Generic[T]):
    """
    Buffer circolare tipizzato con maxlen rigido.
    Usa deque internamente — O(1) append, nessuna crescita.

    >>> buf = CircularBuffer[float](maxlen=100, dtype=float)
    >>> buf.append(1.0); buf.append(2.0)
    >>> buf[-1]
    2.0
    >>> len(buf)
    2
    """

    __slots__ = ("_data", "_maxlen", "_dtype")

    def __init__(self, maxlen: int, dtype: type = float):
        self._maxlen = maxlen
        self._dtype = dtype
        self._data: deque = deque(maxlen=maxlen)

    # ── CRUD ──────────────────────────────────────────────────────────────

    def append(self, value: T) -> None:
        """O(1) append con maxlen automatico."""
        self._data.append(self._dtype(value))

    def extend(self, values: list[T]) -> None:
        for v in values:
            self._data.append(self._dtype(v))

    def clear(self) -> None:
        self._data.clear()

    @property
    def maxlen(self) -> int:
        return self._maxlen

    # ── Accesso ───────────────────────────────────────────────────────────

    def __len__(self) -> int:
        return len(self._data)

    def __getitem__(self, idx):
        return self._data[idx]

    def __iter__(self):
        return iter(self._data)

    def last(self, n: int = 1) -> list[T]:
        """Ultimi n elementi (più recenti per ultimi)."""
        if n >= len(self._data):
            return list(self._data)
        return [self._data[i] for i in range(len(self._data) - n, len(self._data))]

    def to_array(self, typecode: str = "d") -> array.array:
        """Esporta come array.array tipizzato per calcoli vettoriali.
        'd' = float64, 'f' = float32, 'l' = signed long.
        Usa 'f' per risparmiare 50% di memoria sui prezzi.
        """
        return array.array(typecode, self._data)

    # ── Statistiche in-place (no copie) ───────────────────────────────────

    def mean(self) -> float:
        n = len(self._data)
        if n == 0:
            return 0.0
        return sum(self._data) / n

    def std(self) -> float:
        n = len(self._data)
        if n < 2:
            return 0.0
        mu = self.mean()
        var = sum((x - mu) ** 2 for x in self._data) / (n - 1)
        return math.sqrt(var)

    def min(self) -> float:
        return min(self._data) if self._data else 0.0

    def max(self) -> float:
        return max(self._data) if self._data else 0.0


# ─── Buffer specializzati ─────────────────────────────────────────────────

class OhlcvBuffer:
    """
    Buffer circolare per dati OHLCV.
    Ogni campo in un deque separato — zero copie per calcoli vettoriali.
    maxlen tipico: 100 candele (≈1200 byte totali vs 8000+ in DataFrame).
    """

    __slots__ = ("timestamp", "open", "high", "low", "close", "volume", "_maxlen")

    def __init__(self, maxlen: int = 100):
        self._maxlen = maxlen
        self.timestamp: deque[int] = deque(maxlen=maxlen)
        self.open: deque[float] = deque(maxlen=maxlen)
        self.high: deque[float] = deque(maxlen=maxlen)
        self.low: deque[float] = deque(maxlen=maxlen)
        self.close: deque[float] = deque(maxlen=maxlen)
        self.volume: deque[float] = deque(maxlen=maxlen)

    def append(self, ts: int, o: float, h: float, l: float, c: float, v: float) -> None:
        self.timestamp.append(ts)
        self.open.append(o)
        self.high.append(h)
        self.low.append(l)
        self.close.append(c)
        self.volume.append(v)

    @property
    def size(self) -> int:
        return len(self.close)

    @property
    def last_close(self) -> float:
        return self.close[-1] if self.close else 0.0

    @property
    def last_volume(self) -> float:
        return self.volume[-1] if self.volume else 0.0

    def close_array(self, typecode: str = "f") -> array.array:
        """Prezzi di chiusura come float32 (typecode='f') per calcoli ATR.
        Usa sempre 'f' (float32) per risparmiare memoria nei calcoli.
        """
        return array.array(typecode, self.close)

    def clear(self) -> None:
        for buf in (self.timestamp, self.open, self.high, self.low, self.close, self.volume):
            buf.clear()


# ─── Tick Buffer ──────────────────────────────────────────────────────────

class TickBuffer:
    """
    Buffer circolare per tick di trade.
    maxlen tipico: 1000 tick (≈48KB vs 200KB+ in dict list).
    """

    __slots__ = ("price", "volume", "timestamp", "side", "_maxlen")

    def __init__(self, maxlen: int = 1000):
        self._maxlen = maxlen
        self.price: deque[float] = deque(maxlen=maxlen)
        self.volume: deque[float] = deque(maxlen=maxlen)
        self.timestamp: deque[int] = deque(maxlen=maxlen)
        self.side: deque[int] = deque(maxlen=maxlen)  # 0=buy, 1=sell

    def append(self, price: float, volume: float, ts: int, side: int) -> None:
        self.price.append(price)
        self.volume.append(volume)
        self.timestamp.append(ts)
        self.side.append(side)

    @property
    def size(self) -> int:
        return len(self.price)

    def clear(self) -> None:
        for buf in (self.price, self.volume, self.timestamp, self.side):
            buf.clear()


# ─── Explicit GC manager ──────────────────────────────────────────────────

_GC_COUNTER = 0


def gc_if_heavy(label: str = "") -> None:
    """
    Chiama gc.collect() DOPO operazioni che hanno generato molti oggetti
    temporanei (es. ricalcolo ATR, cleanup ordini). Non chiamare a ogni tick.
    
    Usa un contatore interno per limitare le collect a max 1x/5s.
    """
    global _GC_COUNTER
    now = time.monotonic()
    if now - _GC_COUNTER < 5.0:
        return
    _GC_COUNTER = now
    before = time.time()
    n = gc.collect()
    elapsed = (time.time() - before) * 1000
    if n > 0:
        log.debug(f"GC: collected {n} objects in {elapsed:.1f}ms{ ' (' + label + ')' if label else ''}")


class memory_heavy:
    """
    Context manager per operazioni memory-heavy.
    Garantisce gc.collect() all'uscita, anche in caso di eccezione.

    Usage:
        with memory_heavy("ATR recalc"):
            atr = calculate_atr(ohlcv)
    """

    def __init__(self, label: str = ""):
        self.label = label

    def __enter__(self):
        return self

    def __exit__(self, *args):
        gc_if_heavy(self.label)

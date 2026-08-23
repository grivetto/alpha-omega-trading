"""
Circular buffers for Alpha-Omega Trading System.

Merges: neo/memory.py (typed arrays, explicit GC) + shadowgrid_v2.py (OHLCV handling).

Regola #1: niente liste infinite.
Regola #2: array tipizzati (float32/int16) dove possibile.
Regola #3: gc.collect() dopo ricalcoli pesanti, non dopo ogni tick.
Regola #4: context manager per operazioni memory-heavy.
"""
from __future__ import annotations
import array
import gc
import logging
import math
import time
from collections import deque
from typing import Generic, TypeVar, List, Optional

log = logging.getLogger("alpha_omega.buffers")

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

    def extend(self, values: List[T]) -> None:
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

    def last(self, n: int = 1) -> List[T]:
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

    def high_array(self, typecode: str = "f") -> array.array:
        return array.array(typecode, self.high)

    def low_array(self, typecode: str = "f") -> array.array:
        return array.array(typecode, self.low)

    def volume_array(self, typecode: str = "f") -> array.array:
        return array.array(typecode, self.volume)

    def clear(self) -> None:
        for buf in (self.timestamp, self.open, self.high, self.low, self.close, self.volume):
            buf.clear()

    def to_ohlcv_list(self) -> List[tuple]:
        """Convert to list of (ts, o, h, l, c, v) tuples for CCXT compatibility."""
        return list(zip(self.timestamp, self.open, self.high, self.low, self.close, self.volume))


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

    def to_tick_list(self) -> List[tuple]:
        return list(zip(self.price, self.volume, self.timestamp, self.side))


# ─── Explicit GC manager ──────────────────────────────────────────────────

_GC_COUNTER = 0.0


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


# ─── Technical Analysis Helpers ───────────────────────────────────────────

def compute_atr_adx_rsi(
    ohlcv: OhlcvBuffer,
    period: int = 14
) -> tuple[float, float, float]:
    """Compute ATR(14)%, ADX(14), RSI(14) from OhlcvBuffer.
    Returns: (atr_pct, adx, rsi)
    """
    if ohlcv.size < period + 1:
        return 0.0, 0.0, 50.0
    
    # Get arrays as float32 for memory efficiency
    closes = ohlcv.close_array("f")
    highs = ohlcv.high_array("f")
    lows = ohlcv.low_array("f")
    
    # True Range
    tr = np_maximum_reduce([
        highs[1:] - lows[1:],
        np_abs(highs[1:] - closes[:-1]),
        np_abs(lows[1:] - closes[:-1])
    ])
    atr = float(np_mean(tr[-period:]))
    atr_pct = (atr / closes[-1]) * 100 if closes[-1] > 0 else 0.0
    
    # RSI
    diffs = np_diff(closes[-(period+1):])
    gains = np_where(diffs > 0, diffs, 0)
    losses = np_where(diffs < 0, -diffs, 0)
    avg_gain = float(np_mean(gains)) if len(gains) > 0 else 0
    avg_loss = float(np_mean(losses)) if len(losses) > 0 else 0
    rs = avg_gain / avg_loss if avg_loss > 0 else 100
    rsi = 100 - (100 / (1 + rs))
    
    # ADX (simplified)
    up_move = highs[1:] - highs[:-1]
    down_move = lows[:-1] - lows[1:]
    plus_dm = np_where((up_move > down_move) & (up_move > 0), up_move, 0)
    minus_dm = np_where((down_move > up_move) & (down_move > 0), down_move, 0)
    
    tr_period = tr[-period:]
    tr14 = float(np_mean(tr_period))
    if tr14 > 0:
        pdi = float(np_mean(plus_dm[-period:])) / tr14 * 100
        mdi = float(np_mean(minus_dm[-period:])) / tr14 * 100
        dx = abs(pdi - mdi) / (pdi + mdi) * 100 if (pdi + mdi) > 0 else 0
    else:
        dx = 0
    adx = dx
    
    return atr_pct, adx, rsi


def detect_regime(adx: float, rsi: float, 
                  adx_range_threshold: float = 25,
                  adx_trend_threshold: float = 30) -> dict:
    """Detect market regime based on ADX and RSI."""
    if adx < adx_range_threshold:
        regime = "range"
        suitability = "grid"
    elif adx > adx_trend_threshold:
        regime = "trend"
        suitability = "scalper"
    else:
        regime = "transitional"
        suitability = "caution"
    
    # Trend direction
    if rsi > 55:
        trend = "bullish"
    elif rsi < 45:
        trend = "bearish"
    else:
        trend = "neutral"
    
    return {
        "regime": regime,
        "suitability": suitability,
        "trend": trend,
        "adx": adx,
        "rsi": rsi,
    }


def detect_volatility_regime(atr_pct: float, atr_history: List[float],
                              spike_mult: float = 2.0,
                              extreme_mult: float = 3.0) -> dict:
    """Detect volatility regime from ATR history."""
    if len(atr_history) < 20:
        return {"regime": "unknown", "ratio": 1.0, "action": "normal"}
    
    median_atr = float(np_median(atr_history))
    ratio = atr_pct / median_atr if median_atr > 0 else 1.0
    
    if ratio >= extreme_mult:
        regime = "extreme"
        action = "pause"
    elif ratio >= spike_mult:
        regime = "high"
        action = "reduce"
    elif ratio <= 0.5:
        regime = "low"
        action = "expand"
    else:
        regime = "normal"
        action = "normal"
    
    return {
        "regime": regime,
        "ratio": ratio,
        "current_atr": atr_pct,
        "median_atr": median_atr,
        "action": action,
    }


# NumPy-like helpers using stdlib (avoid numpy dependency for core buffers)
def np_mean(arr) -> float:
    return sum(arr) / len(arr) if arr else 0.0

def np_median(arr) -> float:
    if not arr:
        return 0.0
    sorted_arr = sorted(arr)
    n = len(sorted_arr)
    if n % 2 == 0:
        return (sorted_arr[n//2 - 1] + sorted_arr[n//2]) / 2
    return sorted_arr[n//2]

def np_diff(arr) -> list:
    return [arr[i] - arr[i-1] for i in range(1, len(arr))]

def np_abs(arr) -> list:
    return [abs(x) for x in arr]

def np_where(cond, x, y) -> list:
    return [x[i] if cond[i] else y[i] for i in range(len(cond))]

def np_maximum_reduce(arrays) -> list:
    return [max(vals) for vals in zip(*arrays)]

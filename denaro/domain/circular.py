#!/usr/bin/env python3
"""Denaro — CircularBuffer tipizzato (TODO punto 3: buffer circolari).

Buffer circolare a dimensione fissa basato su `array.array` (float64):
- maxlen RIGIDO: l'append oltre il limite scarta il piu' vecchio (memoria
  costante, nessuna crescita indefinita delle deques storiche)
- statistiche vettorizzate: mean/std/sum/min/max senza copie Python
- usato per OHLCV, returns, microstruttura (buffer storici di ATLAS/Node)
"""
from __future__ import annotations

import array
import math
from typing import Iterable, List, Optional


class CircularBuffer:
    """Buffer circolare tipizzato (float64) a capacita' fissa."""

    __slots__ = ("_buf", "_maxlen", "_len")

    def __init__(self, maxlen: int, initial: Optional[Iterable[float]] = None) -> None:
        if maxlen <= 0:
            raise ValueError("maxlen deve essere > 0")
        self._maxlen = int(maxlen)
        self._buf: array.array = array.array("d")
        self._len = 0
        if initial:
            for v in initial:
                self.append(float(v))

    # --- mutazione -----------------------------------------------------------

    def append(self, value: float) -> None:
        if self._len < self._maxlen:
            self._buf.append(float(value))
            self._len += 1
        else:
            # rotazione: sposta i primi maxlen-1 elementi e sovrascrivi l'ultimo
            del self._buf[0]
            self._buf.append(float(value))

    def extend(self, values: Iterable[float]) -> None:
        for v in values:
            self.append(float(v))

    def clear(self) -> None:
        self._buf = array.array("d")
        self._len = 0

    # --- accesso -------------------------------------------------------------

    def __len__(self) -> int:
        return self._len

    def __getitem__(self, idx: int) -> float:
        return self._buf[idx]

    def to_list(self) -> List[float]:
        return list(self._buf)

    @property
    def maxlen(self) -> int:
        return self._maxlen

    @property
    def is_full(self) -> bool:
        return self._len >= self._maxlen

    # --- statistiche (senza copie Python) ------------------------------------

    def sum(self) -> float:
        return sum(self._buf)

    def mean(self) -> float:
        if self._len == 0:
            return 0.0
        return sum(self._buf) / self._len

    def std(self) -> float:
        if self._len < 2:
            return 0.0
        mu = self.mean()
        var = sum((x - mu) ** 2 for x in self._buf) / (self._len - 1)
        return math.sqrt(var)

    def min(self) -> float:
        return min(self._buf) if self._len else 0.0

    def max(self) -> float:
        return max(self._buf) if self._len else 0.0

    def last(self) -> Optional[float]:
        return self._buf[-1] if self._len else None

    def __repr__(self) -> str:  # pragma: no cover - debug
        return f"CircularBuffer(len={self._len}/{self._maxlen}, last={self.last()})"

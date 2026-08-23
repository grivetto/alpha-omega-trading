#!/usr/bin/env python3
"""Denaro — rate limiter centralizzato (token bucket).

Un bucket per exchange, condiviso da TUTTI i bot del nodo (D3 del blueprint):
a densita' massima nessun bot puo' superare il budget API dell'exchange.

- `TokenBucket` e' puro e sincrono (testabile senza event loop)
- `AsyncTokenBucket` aggiunge l'attesa asincrona per l'uso nei task
"""
from __future__ import annotations

import asyncio
import time
from typing import Optional


class TokenBucket:
    """Token bucket: capacita' (burst) + refill rate (token/sec)."""

    def __init__(self, capacity: float, refill_rate: float,
                 now: Optional[float] = None) -> None:
        if capacity <= 0 or refill_rate <= 0:
            raise ValueError("capacity e refill_rate devono essere > 0")
        self.capacity = float(capacity)
        self.refill_rate = float(refill_rate)
        self._tokens = float(capacity)
        self._last = now if now is not None else time.time()

    def _refill(self, now: float) -> None:
        elapsed = max(0.0, now - self._last)
        self._tokens = min(self.capacity, self._tokens + elapsed * self.refill_rate)
        self._last = now

    def try_acquire(self, tokens: float = 1.0, now: Optional[float] = None) -> bool:
        """Tenta di prelevare `tokens` senza bloccare. True se concessi."""
        now = now if now is not None else time.time()
        self._refill(now)
        if self._tokens + 1e-9 >= tokens:
            self._tokens -= tokens
            return True
        return False

    def wait_time(self, tokens: float = 1.0, now: Optional[float] = None) -> float:
        """Secondi da attendere prima che `tokens` siano disponibili (0 se ok)."""
        now = now if now is not None else time.time()
        self._refill(now)
        deficit = max(0.0, tokens - self._tokens)
        if deficit <= 0:
            return 0.0
        return deficit / self.refill_rate

    @property
    def available(self) -> float:
        return self._tokens

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (f"TokenBucket(cap={self.capacity}, rate={self.refill_rate}, "
                f"tokens={self._tokens:.2f})")


class AsyncTokenBucket:
    """Wrapper asyncio sul TokenBucket: `acquire` attende senza busy-wait."""

    def __init__(self, bucket: TokenBucket) -> None:
        self._bucket = bucket
        self._lock = asyncio.Lock()

    async def acquire(self, tokens: float = 1.0) -> None:
        while True:
            async with self._lock:
                if self._bucket.try_acquire(tokens):
                    return
                delay = self._bucket.wait_time(tokens)
            await asyncio.sleep(min(delay, 1.0))


class RateLimiterRegistry:
    """Registry dei bucket per exchange — un bucket per nome di exchange."""

    def __init__(self) -> None:
        self._buckets: dict = {}

    def register(self, exchange: str, capacity: float, refill_rate: float) -> TokenBucket:
        bucket = TokenBucket(capacity, refill_rate)
        self._buckets[exchange] = bucket
        return bucket

    def get(self, exchange: str) -> Optional[TokenBucket]:
        return self._buckets.get(exchange)

    def async_bucket(self, exchange: str) -> Optional[AsyncTokenBucket]:
        bucket = self._buckets.get(exchange)
        return AsyncTokenBucket(bucket) if bucket else None

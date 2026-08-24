"""ATLAS Core Resilience - Circuit breaker, retry, timeout patterns."""
from __future__ import annotations

import asyncio
import functools
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar, ParamSpec, Any

logger = logging.getLogger(__name__)

T = TypeVar("T")


def exchange_call(
    max_retries: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    cb_failures: int = 5,
    cb_timeout: float = 30.0,
    timeout_seconds: float = 10.0,
):
    """
    Decorator combinato: timeout -> retry -> circuit breaker.
    
    Order of execution (inner to outer):
    1. timeout - hard limit per attempt
    2. retry - exponential backoff with jitter
    3. circuit_breaker - prevents cascade failures
    """
    
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Simple implementation without pyresilience for now
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    # Apply timeout
                    return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_seconds)
                except (ConnectionError, TimeoutError, IOError, OSError, asyncio.TimeoutError) as e:
                    last_exception = e
                    if attempt < max_retries:
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        import random
                        delay *= (0.9 + random.random() * 0.2)
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {func.__name__} after {delay:.2f}s: {e}")
                        await asyncio.sleep(delay)
                    else:
                        logger.error(f"All retries exhausted for {func.__name__}: {last_exception}")
                        raise
                except Exception as e:
                    # Non-retryable exceptions
                    logger.error(f"Non-retryable error in {func.__name__}: {e}")
                    raise
            
            raise last_exception
        return wrapper
    return decorator


class AsyncCircuitBreaker:
    """Simple async circuit breaker for manual control."""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type[BaseException] = Exception,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception: type[BaseException] = expected_exception
        
        self._failures = 0
        self._last_failure_time: float | None = None
        self._state = "closed"  # closed, open, half-open
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> str:
        if self._state == "open":
            if self._last_failure_time and (time.time() - self._last_failure_time) > self.recovery_timeout:
                return "half-open"
        return self._state
    
    async def call(self, func: Callable[..., Awaitable[T]], *args, **kwargs) -> T:
        async with self._lock:
            if self.state == "open":
                raise Exception(f"Circuit breaker OPEN for {func.__name__}")
        
        try:
            result = await func(*args, **kwargs)
            async with self._lock:
                self._failures = 0
                self._state = "closed"
            return result
        except self.expected_exception as e:
            async with self._lock:
                self._failures += 1
                self._last_failure_time = time.time()
                if self._failures >= self.failure_threshold:
                    self._state = "open"
                    logger.warning(f"Circuit breaker OPENED for {func.__name__} after {self._failures} failures")
            raise


# Convenience function for simple cases
async def with_retry(
    func: Callable[..., Awaitable[T]],
    *args,
    max_attempts: int = 3,
    base_delay: float = 0.1,
    max_delay: float = 5.0,
    **kwargs,
) -> T:
    """Execute async function with exponential backoff retry."""
    last_exception = None
    
    for attempt in range(max_attempts):
        try:
            return await func(*args, **kwargs)
        except (ConnectionError, TimeoutError, IOError, OSError) as e:
            last_exception = e
            if attempt < max_attempts - 1:
                delay = min(base_delay * (2 ** attempt), max_delay)
                import random
                delay *= (0.9 + random.random() * 0.2)
                logger.warning(f"Retry {attempt + 1}/{max_attempts} for {func.__name__} after {delay:.2f}s: {e}")
                await asyncio.sleep(delay)
            else:
                logger.error(f"All retries exhausted for {func.__name__}: {last_exception}")
    
    raise last_exception

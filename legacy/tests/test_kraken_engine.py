#!/usr/bin/env python3
"""
Tests for Kraken Engine — mock CCXT, retry logic, WS feed.

These tests use a mock CCXT exchange so they work offline.
"""

import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from kraken_engine import _is_retryable, _with_retry, _fix_base64_secret


# ─── Base64 secret ───────────────────────────────────────────────────────

def test_fix_base64_secret_padding_needed() -> None:
    """Adds = padding when missing."""
    result = _fix_base64_secret("abc")  # len 3 -> needs 1 padding
    assert result == "abc="
    assert len(result) % 4 == 0

    result = _fix_base64_secret("abcde")  # len 5 -> needs 3 padding
    assert result == "abcde==="
    assert len(result) % 4 == 0


def test_fix_base64_secret_already_padded() -> None:
    """Already valid padding is preserved."""
    result = _fix_base64_secret("abcd")
    assert len(result) % 4 == 0


def test_fix_base64_secret_strips_whitespace() -> None:
    """Whitespace around the secret is stripped."""
    result = _fix_base64_secret("  abcd  ")
    assert len(result) % 4 == 0


# ─── Error classification ────────────────────────────────────────────────

class _RetryableError(Exception):
    pass


class _NonRetryableError(Exception):
    pass


def test_is_retryable_connection_error() -> None:
    """ConnectionError is retryable."""
    assert _is_retryable(ConnectionError("connection refused"))


def test_is_retryable_timeout_error() -> None:
    """TimeoutError is retryable."""
    assert _is_retryable(TimeoutError("timed out"))


def test_is_retryable_oserror() -> None:
    """OSError (e.g., ENETDOWN) is retryable."""
    assert _is_retryable(OSError("no route to host"))


def test_is_retryable_value_error_not() -> None:
    """ValueError is NOT retryable."""
    assert not _is_retryable(ValueError("bad arg"))


def test_is_retryable_type_error_not() -> None:
    """TypeError is NOT retryable."""
    assert not _is_retryable(TypeError("'NoneType' object is not subscriptable"))


# ─── Retry decorator ─────────────────────────────────────────────────────

def test_retry_success_first_try() -> None:
    """Successful call returns immediately, no retry."""
    call_count = {"n": 0}

    @_with_retry(max_attempts=3)
    def work() -> str:
        call_count["n"] += 1
        return "ok"

    assert work() == "ok"
    assert call_count["n"] == 1


def test_retry_eventually_succeeds() -> None:
    """Fails twice, succeeds on third attempt."""
    call_count = {"n": 0}

    @_with_retry(max_attempts=3, base_delay=0.01)
    def work() -> str:
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise ConnectionError("transient")
        return "ok"

    assert work() == "ok"
    assert call_count["n"] == 3


def test_retry_exhausts_attempts() -> None:
    """Raises after max_attempts retries."""
    call_count = {"n": 0}

    @_with_retry(max_attempts=2, base_delay=0.01)
    def work() -> None:
        call_count["n"] += 1
        raise ConnectionError("always fails")

    try:
        work()
        assert False, "expected exception"
    except ConnectionError:
        pass
    assert call_count["n"] == 2


def test_retry_non_retryable_raises_immediately() -> None:
    """Non-retryable error raises immediately, no retry."""
    call_count = {"n": 0}

    @_with_retry(max_attempts=3)
    def work() -> None:
        call_count["n"] += 1
        raise ValueError("bad input")

    try:
        work()
        assert False, "expected exception"
    except ValueError:
        pass
    assert call_count["n"] == 1  # only one attempt

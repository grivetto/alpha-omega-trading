#!/usr/bin/env python3
"""
NOTIFIER — Telegram notification system with rate limiting, retry, and dedup.

Features:
  - Real Telegram Bot API via urllib (zero extra deps)
  - Rate limiting: max 1 msg/sec (Telegram: 30/sec, we stay conservative)
  - Exponential backoff retry on 429/flake
  - In-flight dedup: identical messages within 60s window are collapsed
  - Multiple severity levels with emoji prefix
  - Graceful fallback to log-only if TELEGRAM_BOT_TOKEN is not set

Env vars:
  TELEGRAM_BOT_TOKEN  — Bot token from @BotFather
  TELEGRAM_CHAT_ID    — Target chat ID (or @channelusername)
  LOG_LEVEL           — (inherited from main)
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import urllib.request
import urllib.error
from typing import Optional
from dataclasses import dataclass, field

log = logging.getLogger("kraken_v2")

# ─── Config ───────────────────────────────────────────────────────────────────
_BOT_TOKEN: str | None = os.environ.get("TELEGRAM_BOT_TOKEN") or None
_CHAT_ID: str | None = os.environ.get("TELEGRAM_CHAT_ID") or None
_ENABLED = bool(_BOT_TOKEN and _CHAT_ID)

_API_BASE = f"https://api.telegram.org/bot{_BOT_TOKEN}" if _BOT_TOKEN else ""
_RATE_LIMIT_SEC = 1.0        # 1 msg / sec
_RETRY_MAX = 3
_RETRY_BASE_DELAY = 1.0
_DEDUP_WINDOW = 60.0         # seconds — collapse identical msgs


# ─── Rate limiter ─────────────────────────────────────────────────────────────
@dataclass
class _RateLimiter:
    _last_send: float = 0.0

    def acquire(self) -> None:
        now = time.time()
        wait = self._last_send + _RATE_LIMIT_SEC - now
        if wait > 0:
            time.sleep(wait)
        self._last_send = time.time()


_limiter = _RateLimiter()


# ─── Dedup ring ───────────────────────────────────────────────────────────────
@dataclass
class _DedupRing:
    _sent: dict[str, float] = field(default_factory=dict)

    def is_duplicate(self, text: str) -> bool:
        now = time.time()
        # Purge old entries
        stale = [k for k, ts in self._sent.items() if now - ts > _DEDUP_WINDOW]
        for k in stale:
            del self._sent[k]
        if text in self._sent:
            return True
        self._sent[text] = now
        return False


_dedup = _DedupRing()


# ─── Severity emoji map ───────────────────────────────────────────────────────
_SEVERITY_EMOJI = {
    "critical": "🚨",
    "error":    "⚠️",
    "warning":  "⚡",
    "info":     "📡",
    "success":  "✅",
    "startup":  "🚀",
    "shutdown": "🔌",
    "cb_open":  "🧊",
    "cb_close": "🔥",
    "trade":    "💹",
    "fill":     "📊",
}


def _format_message(msg: str, severity: str = "info") -> str:
    emoji = _SEVERITY_EMOJI.get(severity, "📡")
    return f"{emoji} Denaro · {msg}"


def _send_sync(text: str) -> bool:
    """Send a single message via Telegram Bot API. Returns True on success."""
    if not _ENABLED:
        return False

    url = f"{_API_BASE}/sendMessage"
    # parse_mode OMITTED entirely — None → null in JSON → Telegram HTTP 400
    payload_data = {
        "chat_id": _CHAT_ID,
        "text": text,
        "disable_web_page_preview": True,
    }
    payload = json.dumps(payload_data).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    last_err: Optional[str] = None
    for attempt in range(1, _RETRY_MAX + 1):
        try:
            _limiter.acquire()
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status == 200:
                    return True
                last_err = f"HTTP {resp.status}"
        except urllib.error.HTTPError as e:
            last_err = f"HTTP {e.code}"
            if e.code == 429:
                retry_after = int(e.headers.get("Retry-After", "5"))
                log.warning(f"Telegram 429 — retrying in {retry_after}s "
                            f"(attempt {attempt}/{_RETRY_MAX})")
                time.sleep(retry_after)
                continue
            if e.code >= 500:
                delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
                log.warning(f"Telegram {e.code} — retrying in {delay:.0f}s "
                            f"(attempt {attempt}/{_RETRY_MAX})")
                time.sleep(delay)
                continue
            break  # 4xx non-429 → don't retry
        except (urllib.error.URLError, OSError) as e:
            last_err = str(e)
            delay = _RETRY_BASE_DELAY * (2 ** (attempt - 1))
            log.warning(f"Telegram connection error: {e} — "
                        f"retrying in {delay:.0f}s (attempt {attempt}/{_RETRY_MAX})")
            time.sleep(delay)
            continue

    log.error(f"Telegram send failed after {_RETRY_MAX} attempts: {last_err}")
    return False


# ─── Public API ────────────────────────────────────────────────────────────────


def notify(msg: str, severity: str = "info") -> None:
    """
    Send a notification.

    Falls back to log-only when Telegram is not configured.
    Deduplicates identical messages within _DEDUP_WINDOW seconds.

    Args:
        msg: Message text (plain text, will be HTML-escaped by parse_mode).
        severity: One of info, warning, error, critical, success,
                  startup, shutdown, cb_open, cb_close, trade, fill.
    """
    text = _format_message(msg, severity)

    if _dedup.is_duplicate(text):
        log.debug(f"[NOTIFY DEDUP] {text}")
        return

    log.info(f"[NOTIFY] {text}")

    ok = _send_sync(text)
    if not ok and _ENABLED:
        log.warning(f"Telegram notification failed (logged as fallback): {msg}")


def notify_startup(symbol: str, mode: str, capital: float) -> None:
    """Formatted startup notification with key params."""
    msg = (f"Kraken Grid v2\n"
           f"Pair: {symbol}\n"
           f"Mode: {mode}\n"
           f"Capital: €{capital:.2f}")
    notify(msg, severity="startup")


def notify_shutdown(symbol: str) -> None:
    """Formatted shutdown notification."""
    notify(f"Shutting down — {symbol}", severity="shutdown")


def notify_trade(symbol: str, side: str, amount: float,
                 price: float, pnl_pct: float) -> None:
    """Formatted trade fill notification."""
    emoji = "🟢" if pnl_pct >= 0 else "🔴"
    msg = (f"{emoji} {side.upper()} {amount:.2f} @ €{price:.6f} "
           f"({pnl_pct:+.2f}%)")
    notify(msg, severity="trade" if pnl_pct >= 0 else "error")


def notify_cb_open(reason: str, equity: float) -> None:
    """Circuit breaker opened."""
    notify(f"CB OPEN — {reason} | Equity: €{equity:.2f}",
           severity="cb_open")


def notify_cb_close(equity: float) -> None:
    """Circuit breaker closed — trading resumed."""
    notify(f"CB CLOSED — Trading resumed | Equity: €{equity:.2f}",
           severity="cb_close")

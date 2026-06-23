"""Denaro v3 Circuit Breaker — Unified pre-trade risk control.

Interrogato PRIMA di ogni trade. Se il circuito è aperto,
NESSUN ordine viene piazzato. Protegge il capitale a livello di core.
"""

import json
import os
import hashlib
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from loguru import logger

from .config import RiskConfig


@dataclass
class TradeRecord:
    """Immutable trade record for P&L tracking."""
    timestamp: float
    symbol: str
    side: str  # 'buy' or 'sell'
    amount: float
    price: float
    pnl: float = 0.0  # Realized P&L in quote currency
    fee: float = 0.0


class CircuitBreaker:
    """Global risk controller. One instance per process.

    States:
    - CLOSED: Trading allowed (normal operation)
    - HALF_OPEN: Reduced position size (-50%)
    - OPEN: ALL trading blocked
    """

    STATE_CLOSED = "closed"
    STATE_HALF_OPEN = "half_open"
    STATE_OPEN = "open"

    def __init__(self, config: RiskConfig, state_file: str = "circuit_breaker.json"):
        self._config = config
        self._state_file = state_file
        self._state = self.STATE_CLOSED
        self._reason = ""
        self._trades: List[TradeRecord] = []
        self._peak_equity: float = 0.0
        self._current_equity: float = 0.0
        self._consecutive_losses: int = 0
        self._daily_pnl: float = 0.0
        self._daily_date: str = ""
        self._total_pnl: float = 0.0
        self._load_state()

    # ── State Persistence ──────────────────────────────────
    def _load_state(self):
        """Load persisted circuit breaker state with checksum verification."""
        if not os.path.exists(self._state_file):
            return
        try:
            with open(self._state_file) as f:
                data = json.load(f)
            # Verify checksum
            stored_hash = data.pop("_checksum", "")
            computed = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
            if stored_hash != computed:
                logger.warning("Circuit breaker state corrupted — resetting to CLOSED")
                self._state = self.STATE_CLOSED
                return
            self._state = data.get("state", self.STATE_CLOSED)
            self._reason = data.get("reason", "")
            self._peak_equity = data.get("peak_equity", 0.0)
            self._total_pnl = data.get("total_pnl", 0.0)
            self._consecutive_losses = data.get("consecutive_losses", 0)
        except Exception as e:
            logger.error(f"Failed to load circuit breaker state: {e}")
            self._state = self.STATE_CLOSED

    def _save_state(self):
        """Atomically persist circuit breaker state."""
        data = {
            "state": self._state,
            "reason": self._reason,
            "peak_equity": self._peak_equity,
            "total_pnl": self._total_pnl,
            "consecutive_losses": self._consecutive_losses,
            "updated": datetime.now(timezone.utc).isoformat(),
        }
        checksum = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
        data["_checksum"] = checksum
        try:
            fd, tmp = tempfile.mkstemp(dir=os.path.dirname(self._state_file) or ".")
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, self._state_file)
        except Exception as e:
            logger.error(f"Failed to save circuit breaker state: {e}")

    # ── Risk Checks ────────────────────────────────────────
    def update_equity(self, total_usdc: float):
        """Update current equity. Called every loop cycle."""
        self._current_equity = total_usdc
        if total_usdc > self._peak_equity:
            self._peak_equity = total_usdc
        self._check_daily_reset()
        self._evaluate()

    def _check_daily_reset(self):
        """Reset daily P&L counter at midnight UTC."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if today != self._daily_date:
            self._daily_pnl = 0.0
            self._daily_date = today
            logger.info("Daily P&L reset")

    def _evaluate(self):
        """Evaluate all risk conditions. Most severe wins."""
        reasons = []

        # L3: Total drawdown > max_drawdown_pct
        if self._peak_equity > 0:
            drawdown = (self._peak_equity - self._current_equity) / self._peak_equity * 100
            if drawdown > self._config.max_drawdown_pct:
                reasons.append(f"Drawdown {drawdown:.1f}% > {self._config.max_drawdown_pct}%")

        # L2: Daily loss > max_daily_loss_pct
        if self._peak_equity > 0:
            daily_loss_pct = abs(self._daily_pnl) / self._peak_equity * 100
            if self._daily_pnl < 0 and daily_loss_pct > self._config.max_daily_loss_pct:
                reasons.append(f"Daily loss {daily_loss_pct:.1f}% > {self._config.max_daily_loss_pct}%")

        # L1: Consecutive losses
        if self._consecutive_losses >= self._config.max_consecutive_losses:
            reasons.append(f"Consecutive losses: {self._consecutive_losses} >= {self._config.max_consecutive_losses}")

        if reasons:
            # Daily loss or drawdown = full stop. Consecutive losses only = half.
            if any("Daily loss" in r or "Drawdown" in r for r in reasons):
                self._transition(self.STATE_OPEN, "; ".join(reasons))
            else:
                self._transition(self.STATE_HALF_OPEN, "; ".join(reasons))
        elif self._state != self.STATE_CLOSED:
            # Recover: if we're in half_open and have a winning trade, go back
            if self._consecutive_losses == 0:
                self._transition(self.STATE_CLOSED, "Recovered — no active risk conditions")

    def _transition(self, new_state: str, reason: str):
        """Transition to a new state. Only escalates, never downgrades silently."""
        if new_state != self._state:
            logger.warning(f"Circuit breaker: {self._state} → {new_state} | {reason}")
            self._state = new_state
            self._reason = reason
            self._save_state()

    # ── Pre-Trade Check ────────────────────────────────────
    def can_trade(self, amount_usdc: float) -> tuple[bool, str, float]:
        """Check if a trade is allowed. Returns (allowed, reason, max_amount).

        Called BEFORE every order placement.
        """
        if self._state == self.STATE_OPEN:
            return False, f"CIRCUIT OPEN: {self._reason}", 0.0

        if self._state == self.STATE_HALF_OPEN:
            reduced = amount_usdc * (self._config.reduced_size_pct / 100.0)
            return True, "HALF_OPEN: reduced size", reduced

        # VaR check (simplified: risk per trade)
        max_risk = self._current_equity * (self._config.max_risk_per_trade_pct / 100.0)
        if amount_usdc > max_risk * 2:  # 2x because grid has both sides
            return True, "CLOSED", min(amount_usdc, max_risk * 2)

        return True, "CLOSED", amount_usdc

    # ── Trade Recording ────────────────────────────────────
    def record_trade(self, trade: TradeRecord):
        """Record a completed trade for P&L tracking."""
        self._trades.append(trade)
        self._total_pnl += trade.pnl
        self._daily_pnl += trade.pnl

        if trade.pnl < 0:
            self._consecutive_losses += 1
        else:
            self._consecutive_losses = 0

        # Keep only last 1000 trades in memory
        if len(self._trades) > 1000:
            self._trades = self._trades[-500:]

        self._save_state()
        self._evaluate()

    # ── Properties ─────────────────────────────────────────
    @property
    def state(self) -> str:
        return self._state

    @property
    def reason(self) -> str:
        return self._reason

    @property
    def peak_equity(self) -> float:
        return self._peak_equity

    @property
    def total_pnl(self) -> float:
        return self._total_pnl

    @property
    def daily_pnl(self) -> float:
        return self._daily_pnl

    @property
    def consecutive_losses(self) -> int:
        return self._consecutive_losses

    @property
    def drawdown_pct(self) -> float:
        if self._peak_equity > 0:
            return (self._peak_equity - self._current_equity) / self._peak_equity * 100
        return 0.0

    def summary(self) -> dict:
        """Human-readable state summary for logging."""
        return {
            "state": self._state,
            "peak": round(self._peak_equity, 2),
            "equity": round(self._current_equity, 2),
            "drawdown_pct": round(self.drawdown_pct, 2),
            "daily_pnl": round(self._daily_pnl, 2),
            "total_pnl": round(self._total_pnl, 2),
            "consecutive_losses": self._consecutive_losses,
        }

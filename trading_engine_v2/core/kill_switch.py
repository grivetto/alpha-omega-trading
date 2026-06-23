"""Unified Kill-Switch & Risk Manager for Denaro."""
from typing import Optional

class KillSwitch:
    """Multi-level circuit breaker:
    - Level 1: consecutive losses >= 3 → block new entries
    - Level 2: daily loss > 3% → block new entries + reduce open size
    - Level 3: daily loss > 5% → liquidate ALL + halt
    - Level 4: VaR 95% > 4% equity → reduce position size to 50%
    """

    def __init__(self):
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._equity = 0.0
        self._day_start_equity = 0.0
        self._halted = False
        self._last_day = ""

    def update(self, equity: float, daily_pnl: float, trade_won: Optional[bool] = None):
        self._equity = equity
        self._daily_pnl = daily_pnl

        if trade_won is True:
            self._consecutive_losses = 0
        elif trade_won is False:
            self._consecutive_losses += 1

    def reset_day(self, start_equity: float):
        self._day_start_equity = start_equity
        self._consecutive_losses = 0
        self._daily_pnl = 0.0
        self._halted = False

    @property
    def status(self) -> dict:
        daily_loss_pct = abs(self._daily_pnl) / max(self._day_start_equity, 1) * 100
        return {
            "halted": self._halted,
            "level": self._get_level(),
            "consecutive_losses": self._consecutive_losses,
            "daily_pnl": round(self._daily_pnl, 2),
            "daily_loss_pct": round(daily_loss_pct, 2),
            "consecutive_losses_block": self._consecutive_losses >= 3,
            "daily_loss_3pct_block": daily_loss_pct > 3.0,
            "daily_loss_5pct_liquidate": daily_loss_pct > 5.0,
        }

    def _get_level(self) -> int:
        daily_loss_pct = abs(self._daily_pnl) / max(self._day_start_equity, 1) * 100
        if daily_loss_pct > 5.0:
            return 3
        if daily_loss_pct > 3.0:
            return 2
        if self._consecutive_losses >= 3:
            return 1
        return 0

    def can_open_new(self, var_95: float = 0) -> bool:
        """Check if we can open new positions."""
        if self._halted:
            return False
        s = self.status
        if s["consecutive_losses_block"]:
            return False
        if s["daily_loss_3pct_block"]:
            return False
        if var_95 > 0.04 * self._equity:
            return False
        return True

    def should_liquidate(self) -> bool:
        """Check if we should close ALL positions."""
        return self.status["daily_loss_5pct_liquidate"]

    def size_multiplier(self, var_95: float = 0) -> float:
        """Return position size multiplier based on risk state."""
        m = 1.0
        if self._consecutive_losses >= 2:
            m *= 0.7
        s = self.status
        if s["daily_loss_3pct_block"]:
            m *= 0.5
        if var_95 > 0.04 * self._equity:
            m *= 0.5
        return max(0.1, m)

    def halt(self):
        self._halted = True

    def resume(self):
        self._halted = False
        self._consecutive_losses = 0

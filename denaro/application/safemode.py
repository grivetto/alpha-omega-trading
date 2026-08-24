#!/usr/bin/env python3
"""Denaro — SafeModeGuardian (TODO punto 3): monitoraggio RAM a 3 livelli.

Livelli (percentuale RAM usata):
- CAUTION   (>70%): throttle dei calcoli non critici + log ridotti
- SAFE      (>85%): blocco NUOVI trade + svuotamento buffer storici
- EMERGENCY (>95%): cancel_all ordini + flush stato SQLite WAL +
                    shutdown controllato (prevenzione OOM)

La fonte RAM e' iniettabile (`ram_provider`), quindi il guardian e'
deterministico e testabile; default = psutil.virtual_memory().percent.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

log = logging.getLogger("denaro.safemode")


def _default_ram_provider() -> float:
    """RAM usata in percentuale (psutil); 0 se non disponibile."""
    try:
        import psutil
        return float(psutil.virtual_memory().percent)
    except Exception:
        return 0.0


class SafeModeGuardian:
    """Task asincrono che scala le misure correttive in base alla RAM."""

    def __init__(self,
                 ram_provider: Optional[Callable[[], float]] = None,
                 caution_pct: float = 70.0,
                 safe_pct: float = 85.0,
                 emergency_pct: float = 95.0,
                 interval_s: float = 10.0) -> None:
        self._ram = ram_provider or _default_ram_provider
        self.caution_pct = caution_pct
        self.safe_pct = safe_pct
        self.emergency_pct = emergency_pct
        self.interval_s = max(1.0, interval_s)

        self.level: str = "nominal"          # nominal | caution | safe | emergency
        self.trading_paused: bool = False
        self.noncritical_throttled: bool = False
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._emergency_handled = False

    # --- valutazione pura -----------------------------------------------------

    def check(self, ram_pct: Optional[float] = None) -> str:
        """Ritorna il livello per la percentuale RAM data (o letta)."""
        ram = self._ram() if ram_pct is None else ram_pct
        if ram >= self.emergency_pct:
            return "emergency"
        if ram >= self.safe_pct:
            return "safe"
        if ram >= self.caution_pct:
            return "caution"
        return "nominal"

    def apply_level(self, level: str) -> bool:
        """Applica i flag del livello; True se il livello e' cambiato."""
        changed = level != self.level
        self.level = level
        if level == "emergency":
            self.trading_paused = True
            self.noncritical_throttled = True
        elif level == "safe":
            self.trading_paused = True
            self.noncritical_throttled = True
        elif level == "caution":
            self.trading_paused = False
            self.noncritical_throttled = True
        else:  # nominal
            self.trading_paused = False
            self.noncritical_throttled = False
        return changed

    # --- loop asincrono -------------------------------------------------------

    async def run(self, on_emergency: Optional[Callable[[], Awaitable[None]]] = None,
                  on_safe: Optional[Callable[[], Awaitable[None]]] = None,
                  on_change: Optional[Callable[[], Awaitable[None]]] = None) -> None:
        """Loop di monitoraggio. Le callback di livello vengono chiamate al
        CAMBIO di livello (non a ogni poll)."""
        self._running = True
        while self._running:
            try:
                level = self.check()
                changed = self.apply_level(level)
                if changed:
                    log.warning("SafeMode -> %s (RAM %d%%)", level, self._ram())
                    if on_change:
                        await on_change()
                    if level == "emergency" and not self._emergency_handled:
                        self._emergency_handled = True
                        if on_emergency:
                            await on_emergency()
                    elif level == "safe" and on_safe:
                        await on_safe()
                    elif level == "nominal":
                        self._emergency_handled = False
            except asyncio.CancelledError:
                return
            except Exception as e:  # noqa: BLE001
                log.error("SafeMode loop error: %s", e)
            await asyncio.sleep(self.interval_s)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

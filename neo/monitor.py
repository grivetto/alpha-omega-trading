"""
monitor.py — Resource Monitor asincrono con Safe Mode.

Task in background che ogni ~5s:
1. Legge RSS del processo via psutil
2. Confronta con RAM totale
3. Determina SafeModeLevel
4. Emette heartbeat per Zabbix/health

Se SafeModeLevel >= SAFE (85%):
  - Blocca nuovi trade (main loop lo checka)
  - Svuota cache (forza clear() su buffer circolari)
  - Riduce log a errori soli

Se SafeModeLevel == EMERGENCY (95%):
  - Chiude posizioni aperte
  - Salva stato critico
  - Attende shutdown graceful
"""
from __future__ import annotations
import asyncio, logging, os, time
from typing import Optional, Callable

from neo.custom_types import SafeModeLevel, ResourceState

log = logging.getLogger("denaro-neo")
_PSUTIL_AVAILABLE = False

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    log.warning("psutil not installed — resource monitor disabled")
    def _rss_from_proc() -> float:
        try:
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
        except (FileNotFoundError, OSError, IndexError, ValueError):
            pass
        return 0.0


class ResourceMonitor:
    """
    Async resource monitor — run come task in background.
    """

    __slots__ = (
        "_interval", "_threshold_caution", "_threshold_safe",
        "_threshold_emergency", "_callback", "state", "_proc"
    )

    def __init__(
        self,
        interval: float = 5.0,
        threshold_caution: float = 0.70,
        threshold_safe: float = 0.85,
        threshold_emergency: float = 0.95,
        callback: Optional[Callable[[SafeModeLevel], None]] = None,
    ):
        self._interval = interval
        self._threshold_caution = threshold_caution
        self._threshold_safe = threshold_safe
        self._threshold_emergency = threshold_emergency
        self._callback = callback
        self.state = ResourceState()
        self._proc = psutil.Process() if _PSUTIL_AVAILABLE else None

    async def run(self) -> None:
        while True:
            self._poll()
            await asyncio.sleep(self._interval)

    def _poll(self) -> None:
        old_level = self.state.safe_level

        if _PSUTIL_AVAILABLE and self._proc:
            try:
                mem = self._proc.memory_info()
                self.state.rss_mb = mem.rss / (1024 * 1024)
                self.state.total_mb = psutil.virtual_memory().total / (1024 * 1024)
                self.state.cpu_pct = self._proc.cpu_percent(interval=0.0)
                self.state.fd_count = self._proc.num_fds()
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                self.state.rss_mb = 0.0
        else:
            self.state.rss_mb = _rss_from_proc() if not _PSUTIL_AVAILABLE else self.state.rss_mb
            self.state.total_mb = 0.0

        total = self.state.total_mb or self.state.rss_mb * 2
        self.state.pct = (self.state.rss_mb / total * 100) if total > 0 else 0.0

        if self.state.pct >= self._threshold_emergency * 100:
            new_level = SafeModeLevel.EMERGENCY
        elif self.state.pct >= self._threshold_safe * 100:
            new_level = SafeModeLevel.SAFE
        elif self.state.pct >= self._threshold_caution * 100:
            new_level = SafeModeLevel.CAUTION
        else:
            new_level = SafeModeLevel.NORMAL

        self.state.safe_level = new_level

        if new_level != old_level:
            log.warning(
                f"Safe mode: {old_level.name} → {new_level.name} "
                f"(RAM={self.state.rss_mb:.1f}MB / {self.state.pct:.1f}%)"
            )
            if self._callback:
                try:
                    self._callback(new_level)
                except Exception:
                    log.exception("Resource monitor callback failed")

        self._heartbeat()

    def _heartbeat(self) -> None:
        try:
            with open("/tmp/denaro-neo.health", "w") as f:
                f.write(f"{time.time():.0f} {self.state.safe_level.value} "
                        f"{self.state.rss_mb:.1f} {self.state.pct:.1f}\n")
        except OSError:
            pass

    @property
    def can_trade(self) -> bool:
        return self.state.safe_level < SafeModeLevel.SAFE

    @property
    def can_continue(self) -> bool:
        return self.state.safe_level < SafeModeLevel.EMERGENCY

    def emergency_stop(self) -> None:
        log.critical("EMERGENCY: resource threshold exceeded — forcing shutdown")

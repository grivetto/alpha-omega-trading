"""Denaro v3 Leader Election — Single-active failover lock.

Only ONE instance per pair is allowed to trade at any time.
Uses heartbeats to a shared lock file for leader detection.

Principle:
- Every instance writes a heartbeat every cycle
- On startup, check if another leader is alive for this pair
- If leader is dead (>90s no heartbeat), take over
- Respects the lock: never two instances trading same pair
"""

import os
import time
import json
from pathlib import Path
from typing import Optional

from loguru import logger

LOCK_DIR = os.environ.get("DENARO_LOCK_DIR", "/tmp/denaro_locks")
HEARTBEAT_TIMEOUT = 90  # seconds


class LeaderElection:
    """Distributed lock using heartbeat files.

    Usage:
        lock = LeaderElection(machine_id="mc2", pair="SOL/USDC")
        if lock.try_acquire():
            trade()
        # Every cycle:
        lock.heartbeat()
    """

    def __init__(self, machine_id: str, pair: str):
        self._machine = machine_id
        self._pair = pair.replace("/", "_")
        self._lock_file = Path(LOCK_DIR) / f"{self._pair}.lock"
        self._is_leader = False

    @property
    def is_leader(self) -> bool:
        return self._is_leader

    def get_current_leader(self) -> Optional[str]:
        """Return machine_id of current leader, or None if no leader."""
        if not self._lock_file.exists():
            return None
        try:
            data = json.loads(self._lock_file.read_text())
            last_beat = data.get("heartbeat", 0)
            if time.time() - last_beat > HEARTBEAT_TIMEOUT:
                return None  # Leader is dead
            return data.get("machine", None)
        except Exception:
            return None

    def try_acquire(self) -> bool:
        """Try to become the leader. Returns True if acquired."""
        current = self.get_current_leader()

        if current is None:
            # No leader — take the lock
            self._is_leader = True
            self.heartbeat()
            logger.info(f"Leader acquired: {self._machine} → {self._pair}")
            return True

        if current == self._machine:
            # We're already the leader — reclaim
            self._is_leader = True
            self.heartbeat()
            logger.debug(f"Leader re-acquired: {self._machine} → {self._pair}")
            return True

        # Another machine is the leader
        logger.info(f"Leader is {current} for {self._pair} — standing by")
        self._is_leader = False
        return False

    def heartbeat(self):
        """Write heartbeat to lock file. Call every cycle."""
        if not self._is_leader:
            return
        try:
            self._lock_file.parent.mkdir(parents=True, exist_ok=True)
            self._lock_file.write_text(json.dumps({
                "machine": self._machine,
                "pair": self._pair,
                "heartbeat": time.time(),
            }))
        except Exception as e:
            logger.error(f"Heartbeat write failed: {e}")

    def release(self):
        """Release leadership."""
        if self._is_leader and self._lock_file.exists():
            try:
                self._lock_file.unlink()
            except Exception:
                pass
        self._is_leader = False
        logger.info(f"Leader released: {self._machine} → {self._pair}")

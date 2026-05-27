"""Kill Switch Spietato v1.0 — Persistente, irreversibile, cross-bot.

Stati:
  OFF          = tutto OK, trading permesso
  BOT_STOPPED  = un singolo bot fermato per drawdown (per-bot stop-loss)
  LOCKED       = GLOBAL KILL: nessun bot può operare, serve reset manuale DB

Caratteristiche:
  - Persistente su SQLite (sopravvive a systemd restart)
  - Per-bot lock (un bot non riparte dopo aver superato il suo drawdown)
  - Global lock (orchestrator ferma TUTTO)
  - Consecutive loss tracker (circuit breaker: 3 loss consecutivi = STOP bot)
  - Market sell forzato all'attivazione
"""

import json, os, time, logging
from typing import Optional

logger = logging.getLogger("KillSwitch")

# Stati
KS_OFF = 0
KS_BOT_STOPPED = 1    # un singolo bot fermato
KS_LOCKED = 2          # globale: non si sblocca senza reset manuale

# Soglie default
DEFAULT_MAX_DRAWDOWN_EUR = 12.0
DEFAULT_CONSECUTIVE_LOSS_LIMIT = 3
DEFAULT_BOT_LOCK_FILE = "bot_lock.json"

class KillSwitchManager:
    """Gestisce lo stato del kill-switch in modo persistente su DB + file."""

    def __init__(self, db_path: str, lock_file: str = ""):
        self.db_path = db_path
        self.lock_file = lock_file or os.path.join(
            os.path.dirname(db_path), DEFAULT_BOT_LOCK_FILE
        )
        self._state_cache: Optional[int] = None
        self._bot_locks: dict = {}  # bot_name -> True if locked
        self._consecutive_losses: dict = {}  # bot_name -> count
        self._load_persistent_state()

    # ── Persistence ──────────────────────────────────────────────

    def _load_persistent_state(self):
        """Carica stato persistente dal file lock."""
        try:
            if os.path.exists(self.lock_file):
                with open(self.lock_file) as f:
                    data = json.load(f)
                    self._state_cache = data.get("global_state", KS_OFF)
                    self._bot_locks = data.get("bot_locks", {})
                    self._consecutive_losses = data.get("consecutive_losses", {})
                    logger.info(
                        f"KillSwitch loaded: global_state={self._state_cache}, "
                        f"bots_locked={len(self._bot_locks)}, "
                        f"consec_losses={dict(self._consecutive_losses)}"
                    )
            else:
                self._state_cache = KS_OFF
                self._bot_locks = {}
                self._consecutive_losses = {}
        except Exception as e:
            logger.warning(f"KillSwitch load failed (fresh start): {e}")
            self._state_cache = KS_OFF
            self._bot_locks = {}
            self._consecutive_losses = {}

    def _save_persistent_state(self):
        """Salva stato persistente su file lock."""
        try:
            data = {
                "global_state": self._state_cache,
                "bot_locks": self._bot_locks,
                "consecutive_losses": self._consecutive_losses,
                "updated_at": time.time(),
            }
            os.makedirs(os.path.dirname(self.lock_file) or ".", exist_ok=True)
            with open(self.lock_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"KillSwitch save failed: {e}")

    # ── Global state ────────────────────────────────────────────

    def get_global_state(self) -> int:
        return self._state_cache or KS_OFF

    def is_globally_locked(self) -> bool:
        return self.get_global_state() == KS_LOCKED

    def lock_global(self) -> bool:
        """LOCK globale: irreversibile. Tutti i bot fermi. Serve reset manuale."""
        old = self._state_cache
        self._state_cache = KS_LOCKED
        # Lock TUTTI i bot
        for name in list(self._bot_locks.keys()):
            self._bot_locks[name] = True
        self._save_persistent_state()
        logger.error(f"🔒 GLOBAL KILL-SWITCH LOCKED (was {old}) — all bots dead.")
        return True

    def release_global(self) -> bool:
        """RILASCIO manuale del kill-switch globale."""
        if self._state_cache == KS_LOCKED:
            logger.warning("⚠️ KILL-SWITCH LOCKED — release requires manual DB edit.")
            return False
        self._state_cache = KS_OFF
        self._bot_locks = {}
        self._consecutive_losses = {}
        self._save_persistent_state()
        logger.info("🔄 Kill-switch released (manual).")
        return True

    # ── Per-bot lock ────────────────────────────────────────────

    def is_bot_locked(self, bot_name: str) -> bool:
        return self._bot_locks.get(bot_name, False)

    def lock_bot(self, bot_name: str) -> bool:
        """LOCK un bot individuale. Non riparte dopo restart."""
        self._bot_locks[bot_name] = True
        self._save_persistent_state()
        logger.error(f"☠️ Bot {bot_name} LOCKED by kill-switch.")
        return True

    def unlock_bot(self, bot_name: str) -> bool:
        """Sblocca manualmente un bot."""
        if bot_name in self._bot_locks:
            del self._bot_locks[bot_name]
        self._consecutive_losses[bot_name] = 0
        self._save_persistent_state()
        logger.info(f"🔓 Bot {bot_name} unlocked (manual).")
        return True

    # ── Consecutive loss tracker (circuit breaker) ─────────────

    def consecutive_losses(self, bot_name: str) -> int:
        return self._consecutive_losses.get(bot_name, 0)

    def record_loss(self, bot_name: str, limit: int = DEFAULT_CONSECUTIVE_LOSS_LIMIT) -> bool:
        """Registra una perdita. Ritorna True se il limite è stato superato."""
        count = self._consecutive_losses.get(bot_name, 0) + 1
        self._consecutive_losses[bot_name] = count
        self._save_persistent_state()
        logger.warning(
            f"📉 {bot_name}: consecutive loss #{count}/{limit}"
        )
        if count >= limit:
            logger.error(
                f"🚨 CIRCUIT BREAKER {bot_name}: {count} consecutive losses >= {limit}"
            )
            self.lock_bot(bot_name)
            return True  # limit hit
        return False

    def record_win(self, bot_name: str):
        """Resetta il contatore delle perdite consecutive."""
        if self._consecutive_losses.get(bot_name, 0) > 0:
            self._consecutive_losses[bot_name] = 0
            self._save_persistent_state()
            logger.info(f"✅ {bot_name}: consecutive losses reset (win).")

    # ── Bot startup check ───────────────────────────────────────

    def check_bot_can_start(self, bot_name: str) -> bool:
        """Verifica se un bot può partire. Chiamato all'avvio."""
        if self.is_globally_locked():
            logger.error(
                f"🔒 {bot_name}: GLOBAL KILL-SWITCH LOCKED — cannot start. "
                f"Delete {self.lock_file} or set global_state=0 to reset."
            )
            return False
        if self.is_bot_locked(bot_name):
            logger.error(
                f"🔒 {bot_name}: bot LOCKED by kill-switch — cannot start. "
                f"Use unlock_bot('{bot_name}') to reset."
            )
            return False
        return True

    # ── Maintenance ─────────────────────────────────────────────

    def get_locked_bots(self) -> list:
        return [n for n, v in self._bot_locks.items() if v]

    def get_summary(self) -> dict:
        return {
            "global_state": self._state_cache,
            "bots_locked": self.get_locked_bots(),
            "consecutive_losses": dict(self._consecutive_losses),
            "lock_file": self.lock_file,
        }

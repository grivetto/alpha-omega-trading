#!/usr/bin/env python3
"""ATLAS Watchdog - auto-healing per atlas-engine.

Controlla ogni 15s l'health endpoint HTTP del servizio.
Se il servizio e' attivo ma NON risponde su /health per N check consecutivi
(zombie/thread bloccato) -> restart del servizio.
Se il servizio e' morto -> restart (systemd Restart=always fa gia' da backstop).
Log: /var/log/atlas-watchdog.log

Deploy: /usr/local/bin/atlas_watchdog.py  +  systemd service/timer.
"""
import datetime
import logging
import subprocess
import time
import urllib.request

HEALTH_URL = "http://127.0.0.1:8080/health"
SERVICE = "atlas-engine"
CHECK_INTERVAL = 15          # secondi
MAX_CONSECUTIVE_FAILS = 3    # restart dopo 3 health-check falliti
LOG_FILE = "/var/log/atlas-watchdog.log"

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def service_active() -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "is-active", SERVICE],
            capture_output=True, text=True, timeout=10,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


def health_ok() -> bool:
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=5) as resp:
            return resp.status == 200
    except Exception:
        return False


def restart_service() -> None:
    logging.warning("Restart di %s (health check fallito)", SERVICE)
    try:
        subprocess.run(
            ["systemctl", "restart", SERVICE],
            capture_output=True, text=True, timeout=30,
        )
        logging.info("Restart eseguito")
    except Exception as e:
        logging.error("Restart FALLITO: %s", e)


def main() -> None:
    logging.info("ATLAS Watchdog avviato (interval=%ss, max_fails=%s)", CHECK_INTERVAL, MAX_CONSECUTIVE_FAILS)
    consecutive_fails = 0
    while True:
        try:
            active = service_active()
            ok = health_ok()

            if active and not ok:
                consecutive_fails += 1
                logging.warning(
                    "Health KO (%d/%d) - servizio attivo ma non risponde",
                    consecutive_fails, MAX_CONSECUTIVE_FAILS,
                )
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    restart_service()
                    consecutive_fails = 0
            elif not active:
                consecutive_fails += 1
                if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                    logging.warning("Servizio inattivo - restart")
                    restart_service()
                    consecutive_fails = 0
            else:
                consecutive_fails = 0
        except Exception as e:
            logging.error("Errore watchdog loop: %s", e)
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()

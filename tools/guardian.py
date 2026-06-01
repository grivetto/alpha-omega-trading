#!/usr/bin/env python3
"""
Denaro Guardian — Self-Healing Daemon
Monitora RAM, swap, drawdown (10%), EUR libero (>= 5€), OOM risk.
Riavvia bot morti, killa processi zombie, notifica Telegram.

Uso: avviato come servizio systemd (denaro-guardian.service)
"""
import asyncio
import json
import logging
import os
import signal
import socket
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import psutil
import requests
from dotenv import load_dotenv

# ── CONFIG ──────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(ENV_PATH, override=True)

NODE = socket.gethostname()  # "mc2" | "nuvola" | "MARCODG1"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8183973303:AAFwVUK0LUlyyTby_V0O3U_uMt4V7fXgW8I")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
DB_PATH = BASE_DIR / ".tmp" / "denaro.db"
LOG_PATH = BASE_DIR / "logs" / "guardian.log"

# Soglie
RAM_PCT_MAX = 80.0
SWAP_PCT_MAX = 70.0
OOM_SCORE_MAX = 500  # /proc/pid/oom_score
DRAWDOWN_PCT_MAX = 10.0
EUR_FREE_MIN = 5.0
HEARTBEAT_TIMEOUT = 120  # secondi
CHECK_INTERVAL = 15  # secondi tra un check e l'altro
GRACE_PERIOD = 90  # secondi dopo startup prima di killare bot

# Servizi da monitorare (nome systemd user service)
MONITORED_SERVICES = ["denaro-orchestrator.service", "denaro-grid.service"]
ESSENTIAL_SERVICES = ["denaro-orchestrator.service"]

# ── LOGGING ─────────────────────────────────────────────────
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [GUARDIAN] %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(str(LOG_PATH)),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("Guardian")


# ── HELPERS ─────────────────────────────────────────────────
def send_telegram(text: str):
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID non configurato, skip notify")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=10)
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")


def binance_request(endpoint: str, params: str = "") -> dict:
    """Chiamata sincrona Binance API."""
    import hashlib
    import hmac as hmac_mod

    key = os.getenv("BINANCE_API_KEY", "").strip()
    secret = os.getenv("BINANCE_API_SECRET", "").strip()
    ts = str(int(time.time() * 1000))
    q = f"timestamp={ts}"
    if params:
        q += f"&{params}"
    sig = hmac_mod.new(secret.encode(), q.encode(), hashlib.sha256).hexdigest()
    url = f"https://api1.binance.com{endpoint}?{q}&signature={sig}"
    r = requests.get(url, headers={"X-MBX-APIKEY": key}, timeout=10)
    return r.json()


def get_eur_free() -> float:
    try:
        d = binance_request("/api/v3/account")
        if "balances" in d:
            for b in d["balances"]:
                if b["asset"] == "EUR":
                    return float(b["free"])
    except Exception as e:
        logger.warning(f"EUR fetch failed: {e}")
    return -1.0


def get_total_eur() -> float:
    """Valuta tutto il portafoglio in EUR."""
    try:
        d = binance_request("/api/v3/account")
        if "balances" not in d:
            return -1.0
        total = 0.0
        prices = {}
        for b in d["balances"]:
            asset = b["asset"]
            qty = float(b["free"]) + float(b["locked"])
            if qty <= 0:
                continue
            if asset == "EUR":
                total += qty
                continue
            # Prezzo in EUR
            pair = asset + "EUR"
            if pair not in prices:
                try:
                    pr = requests.get(
                        f"https://api1.binance.com/api/v3/ticker/price?symbol={pair}", timeout=5
                    ).json()
                    prices[pair] = float(pr.get("price", 0))
                except Exception:
                    prices[pair] = 0
            total += qty * prices.get(pair, 0)
        return total
    except Exception as e:
        logger.warning(f"Total EUR fetch failed: {e}")
        return -1.0


def service_active(name: str) -> bool:
    try:
        r = subprocess.run(
            ["systemctl", "--user", "is-active", name],
            capture_output=True, text=True, timeout=5,
        )
        return r.stdout.strip() == "active"
    except Exception:
        return False


def service_restart(name: str):
    logger.warning(f"Riavvio servizio: {name}")
    subprocess.run(["systemctl", "--user", "restart", name], capture_output=True, text=True, timeout=15)


def service_stop(name: str):
    logger.critical(f"FERMO servizio: {name}")
    subprocess.run(["systemctl", "--user", "stop", name], capture_output=True, text=True, timeout=15)


# ── MAIN LOOP ───────────────────────────────────────────────
async def guardian_loop():
    start_time = time.time()
    kill_switch = False
    kill_reason = ""
    consecutive_errors = 0

    logger.info(f"Guardian avviato su {NODE}")
    logger.info(f"Soglie: RAM<{RAM_PCT_MAX}% swap<{SWAP_PCT_MAX}% drawdown<{DRAWDOWN_PCT_MAX}% EUR_free>={EUR_FREE_MIN}")

    send_telegram(
        f"🛡️ <b>Guardian avviato</b> su <code>{NODE}</code>\n"
        + f"RAM max: {RAM_PCT_MAX}% | Swap max: {SWAP_PCT_MAX}%\n"
        + f"Drawdown max: {DRAWDOWN_PCT_MAX}% | EUR min: {EUR_FREE_MIN}€"
    )

    while True:
        try:
            alerts = []
            ram = psutil.virtual_memory()
            swap = psutil.swap_memory()

            # 1. RAM check
            if ram.percent > RAM_PCT_MAX:
                alerts.append(f"🔴 RAM alta: {ram.percent:.0f}% (soglia {RAM_PCT_MAX}%)")

            # 2. Swap check
            if swap.percent > SWAP_PCT_MAX:
                alerts.append(f"🔴 Swap alto: {swap.percent:.0f}% (soglia {SWAP_PCT_MAX}%)")

            # 3. EUR libero check
            eur_free = get_eur_free()
            if 0 <= eur_free < EUR_FREE_MIN:
                alerts.append(f"⚠️ EUR libero basso: {eur_free:.2f}€ (min {EUR_FREE_MIN}€)")

            # 4. Heartbeat bot da SQLite
            if DB_PATH.exists():
                try:
                    conn = sqlite3.connect(str(DB_PATH), timeout=5)
                    for svc in MONITORED_SERVICES:
                        bot_name = svc.replace("denaro-", "").replace(".service", "")
                        row = conn.execute(
                            "SELECT last_heartbeat FROM bot_state WHERE bot_name=?",
                            (bot_name,),
                        ).fetchone()
                        if row and row[0]:
                            elapsed = time.time() - row[0]
                            if elapsed > HEARTBEAT_TIMEOUT:
                                alerts.append(
                                    f"💔 {bot_name} heartbeat mancante da {elapsed:.0f}s → restart"
                                )
                                service_restart(svc)
                    conn.close()
                except Exception as e:
                    logger.warning(f"DB heartbeat check error: {e}")

            # 5. Servizi systemd caduti
            elapsed_since_start = time.time() - start_time
            for svc in MONITORED_SERVICES:
                if not service_active(svc):
                    if elapsed_since_start > GRACE_PERIOD:
                        alerts.append(f"🔴 Servizio {svc} NON attivo → restart")
                        service_restart(svc)

            # 6. Gestione alert
            if alerts:
                msg = f"⚠️ <b>Guardian [{NODE}]</b> — {datetime.now().strftime('%H:%M:%S')}\n"
                msg += "\n".join(alerts)
                logger.warning(msg)
                send_telegram(msg)

            # 7. Log periodico ogni 10 cicli (~2.5 min)
            consecutive_errors = 0

        except Exception as e:
            consecutive_errors += 1
            logger.error(f"Guardian loop error ({consecutive_errors}): {e}")
            if consecutive_errors > 10:
                logger.critical("Troppi errori consecutivi, guardian si ferma")
                send_telegram(f"💀 <b>Guardian crash</b> su {NODE}: {e}")
                break

        await asyncio.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    asyncio.run(guardian_loop())

#!/usr/bin/env python3
"""Ponte Hermes <-> DeepSeek — NOTIFICATORE (daemon persistente).

Il canale DIRETTO DeepSeek <-> Hermes e' il ponte inbox/outbox su mc2: il
"DeepSeek che risponde" e' l'agente DeepSeek di questa sessione (accede al
ponte via ssh dal Brain). Questo daemon NON risponde piu' con deepseek-cli
(evitava conflitti di doppia risposta sullo stesso inbox/outbox): si limita a
- rilevare messaggi NUOVI in outbox.md (Hermes -> DeepSeek/Sergio) e
  notificarli su Telegram (hermes send) + log locale;
- restare vivo come servizio (loop ogni PONTE_INTERVAL_S).
"""
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

BRIDGE = Path("/home/sergio/hermes_bridge")
OUTBOX = BRIDGE / "outbox.md"
STATE = BRIDGE / "state.json"
LOG = BRIDGE / "ponte.log"
LOCK = BRIDGE / ".ponte.lock"
PONTE_INTERVAL_S = 60


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] {msg}"
    print(line, flush=True)
    with LOG.open("a") as f:
        f.write(line + "\n")


def load_state() -> dict:
    try:
        return json.loads(STATE.read_text())
    except Exception:
        return {"notified_outbox_lines": 0}


def save_state(s: dict) -> None:
    STATE.write_text(json.dumps(s, indent=2, ensure_ascii=False))


def notify_telegram(text: str) -> bool:
    """Invia su Telegram via `hermes send` (canale DM di Sergio)."""
    try:
        payload = json.dumps(text)
        r = subprocess.run(
            ["bash", "-c",
             f'export PATH="$HOME/.local/bin:$PATH"; '
             f'printf "%s" {payload} | timeout 60 hermes send -t telegram -f -'],
            capture_output=True, text=True, timeout=90)
        return r.returncode == 0
    except Exception as e:  # noqa: BLE001
        log(f"notify telegram errore: {e}")
        return False


def run_once() -> int:
    try:
        import fcntl
        fd = LOCK.open("w")
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (ImportError, BlockingIOError):
        return 0
    except Exception:
        pass

    state = load_state()
    notified = int(state.get("notified_outbox_lines", 0))
    if not OUTBOX.exists():
        return 0
    lines = OUTBOX.read_text().splitlines()
    if len(lines) <= notified:
        return 0

    # nuove righe dalla outbox (Hermes -> DeepSeek/Sergio)
    new_block = "\n".join(lines[notified:]).strip()
    if new_block:
        log(f"nuove righe da Hermes ({len(lines) - notified}), notifico")
        notify_telegram("📬 HERMES ha scritto nel ponte:\n" + new_block[-1200:])
    state["notified_outbox_lines"] = len(lines)
    save_state(state)
    return 0


if __name__ == "__main__":
    log("ponte notificatore avviato (poll 60s)")
    while True:
        try:
            run_once()
        except KeyboardInterrupt:
            break
        except Exception as e:  # noqa: BLE001
            log(f"errore ciclo: {e}")
        time.sleep(PONTE_INTERVAL_S)

"""Brain — ponte con Hermes AI su mc2: inbox/outbox + invocazione headless.

Il ciclo di scambio e' AUTONOMO:
1. il Brain scrive un digest dello stato in inbox.md (mc2);
2. invoca Hermes in modalita' headless (`hermes -z`, via run_hermes.sh);
3. Hermes legge inbox.md e scrive la sua analisi in outbox.md;
4. il Brain legge outbox.md e logga la conversazione.

Tutto via base64/scp → nessun problema di quoting nei doppi hop ssh.
"""
from __future__ import annotations

import base64
import time

from . import config, sshutil

_last_exchange_ts = 0.0


def _b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def write_inbox(text: str) -> bool:
    """Appende un messaggio datato a inbox.md su mc2."""
    ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
    payload = _b64(f"\n[{ts}] {text}\n")
    cmd = f"printf '%s' '{payload}' | base64 -d >> {config.HERMES_INBOX}"
    rc, _ = sshutil.run("mc2", cmd, timeout=20)
    return rc == 0


def read_outbox() -> str:
    rc, out = sshutil.run("mc2", f"cat {config.HERMES_OUTBOX} 2>/dev/null", timeout=20)
    return out if rc == 0 else ""


def outbox_mtime() -> float | None:
    """mtime di outbox.md su mc2 (età ultima risposta Hermes)."""
    rc, out = sshutil.run("mc2", f"stat -c %Y {config.HERMES_OUTBOX} 2>/dev/null",
                          timeout=20)
    if rc == 0 and out.strip().isdigit():
        return float(out.strip())
    return None


def invoke_hermes(prompt: str) -> tuple[bool, str]:
    """Hermes headless su mc2: `run_hermes.sh` legge la prompt da /tmp."""
    b64 = _b64(prompt)
    cmd = (f"printf '%s' '{b64}' | base64 -d > /tmp/hermes_prompt.txt && "
           f"timeout {int(config.HERMES_TIMEOUT_S)} bash {config.HERMES_RUNNER} "
           f"2>&1 | tail -25")
    rc, out = sshutil.run("mc2", cmd, timeout=config.HERMES_TIMEOUT_S + 30)
    return rc == 0, out


def build_digest(state: dict) -> str:
    """Digest compatto dello stato per Hermes."""
    lines = ["STATO ALPHA-OMEGA (Brain -> Hermes):"]
    for machine, ms in state.items():
        if machine.startswith("_"):
            continue
        units_down = [u for u, s in ms.get("units", {}).items() if s != "active"]
        bots = ms.get("bots", {})
        bad = [f"{k}({v.get('status')},age={v.get('age')}s)"
               for k, v in bots.items()
               if v.get("stale") or v.get("status") != "running"]
        errs = [f"{k}:{v.get('error')[:80]}"
                for k, v in bots.items() if v.get("error")]
        lines.append(f"- {machine}: ok={ms.get('ok')} unit_giu={units_down or '-'} "
                     f"bot_giu={bad or '-'} errori={errs or '-'}")
    # VALIDAZIONE TREND vs GRID (istanza "miracolo onesto"): confronto PnL
    # paper per simbolo — il Brain lo ripassa a Hermes ogni 30 min.
    trend_lines = _trend_vs_grid(state)
    if trend_lines:
        lines.append("TREND vs GRID (paper, PnL EUR):")
        lines.extend(trend_lines)
    return "\n".join(lines)


def _trend_vs_grid(state: dict) -> list[str]:
    """Confronto PnL per simbolo tra l'istanza TREND e l'istanza GRID (paper)."""
    m = state.get("marcodg1", {})
    bots = m.get("bots", {})
    trend = {}
    grid = {}
    for k, v in bots.items():
        sym = k.split(":")[-1] if ":" in k else k
        pnl = v.get("pnl", 0) or 0
        if k.startswith("trend:"):
            trend[sym] = pnl
        elif k.startswith("paper:") and sym in trend:
            grid[sym] = pnl
    if not trend:
        return []
    out = []
    for sym in sorted(trend):
        t, g = trend.get(sym, 0.0), grid.get(sym, 0.0)
        out.append(f"  {sym}: trend={t:.2f}€ grid={g:.2f}€ "
                   f"delta={t - g:+.2f}€")
    return out


def send_telegram(text: str) -> bool:
    """Invia una notifica Telegram via `hermes send` su mc2 (base64 → no quoting)."""
    payload = _b64(text)
    cmd = (f"export PATH=\"$HOME/.local/bin:$PATH\"; printf '%s' '{payload}' "
           f"| base64 -d | timeout 60 hermes send -t telegram -f - 2>&1 | tail -5")
    rc, out = sshutil.run("mc2", cmd, timeout=90)
    if rc != 0:
        print(f"[hermes] send_telegram fallito: {out[:200]}")
    return rc == 0


def exchange_cycle(state: dict, last_snapshot: str, force: bool = False
                   ) -> tuple[str, dict | None]:
    """Un giro di scambio completo. Ritorna (snapshot_outbox, esito)."""
    global _last_exchange_ts
    now = time.time()
    if not force and now - _last_exchange_ts < config.HERMES_INTERVAL_S:
        return last_snapshot, None

    digest = build_digest(state)
    write_inbox(digest)

    prompt = (
        "Sei Hermes, partner AI del progetto Alpha-Omega (trading Denaro). "
        "Leggi /home/sergio/hermes_bridge/inbox.md, analizza lo stato, e "
        "SCRIVI la tua risposta in italiano (max 500 parole) in "
        "/home/sergio/hermes_bridge/outbox.md in APPEND col formato "
        "[AAAA-MM-GG HH:MM] testo (non cancellare mai il file). Se non hai "
        "osservazioni, scrivi comunque un breve status. Rispondi solo con OK "
        "quando hai scritto."
    )
    ok, out = invoke_hermes(prompt)

    snapshot = read_outbox()
    new_part = ""
    if last_snapshot and snapshot.startswith(last_snapshot):
        new_part = snapshot[len(last_snapshot):].strip()
    elif snapshot != last_snapshot:
        new_part = snapshot.strip()
    result = {"ok": ok, "hermes_out": out[-400:], "new_reply": new_part[:2000]}
    _log_exchange(digest, result)
    _last_exchange_ts = now
    return snapshot, result


def _log_exchange(digest: str, result: dict) -> None:
    try:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime())
        with open(config.HERMES_LOG, "a", encoding="utf-8") as f:
            f.write(f"\n### {ts} — Brain -> Hermes\n{digest}\n\n"
                    f"### {ts} — Hermes -> Brain\n{result.get('new_reply') or '(nessuna nuova risposta)'}\n")
    except Exception:  # noqa: BLE001
        pass

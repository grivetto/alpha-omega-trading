#!/usr/bin/env python3
"""Notifiche Telegram del progetto Denaro — bot dedicato agli allarmi.

Uso:
    python3 tools/notifica_tg.py "messaggio"          # invia (anche da stdin)
    python3 tools/notifica_tg.py --check              # verifica bot + invia messaggio di prova
    python3 tools/notifica_tg.py --scopri-chat        # dopo il /start sul bot: trova il chat_id

Config (in ordine di ricerca): variabili d'ambiente TELEGRAM_BOT_TOKEN /
TELEGRAM_CHAT_ID, poi i file `.env` candidati (`~/money/.env`, config del repo).
Il token non viene MAI stampato: gli errori riportano solo la classe dell'eccezione.

Exit: 0 ok | 2 config mancante | 3 invio fallito | 4 nessun update (manca il /start).
"""
from __future__ import annotations

import json
import os
import sys
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.telegram.org"
TIMEOUT = 20


def _da_file(path: Path) -> dict:
    out: dict[str, str] = {}
    try:
        testo = path.read_text(encoding="utf-8")
    except OSError:
        return out
    for riga in testo.splitlines():
        riga = riga.strip()
        if not riga or riga.startswith("#") or "=" not in riga:
            continue
        k, _, v = riga.partition("=")
        out.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return out


def _config() -> tuple[str, str]:
    candidati = [
        Path.home() / "money" / ".env",
        Path("/home/sergio/money/.env"),
        Path.home() / "alpha-omega-trading" / "config" / ".env",
    ]
    file_env: dict[str, str] = {}
    for c in candidati:
        file_env.update({k: v for k, v in _da_file(c).items() if k.startswith("TELEGRAM_")})
    tok = os.environ.get("TELEGRAM_BOT_TOKEN") or file_env.get("TELEGRAM_BOT_TOKEN") or ""
    chat = os.environ.get("TELEGRAM_CHAT_ID") or file_env.get("TELEGRAM_CHAT_ID") or ""
    return tok, chat


def _call(tok: str, metodo: str, **params):
    url = f"{API}/bot{tok}/{metodo}"
    data = urllib.parse.urlencode(params).encode() if params else None
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode())


def invia(testo: str) -> bool:
    """Invia un messaggio sul canale di progetto. False se config mancante o invio fallito."""
    tok, chat = _config()
    if not tok or not chat:
        return False
    try:
        _call(tok, "sendMessage", chat_id=chat, text=testo)
        return True
    except Exception:  # noqa: BLE001
        return False


def main(argv: list[str]) -> int:
    tok, chat = _config()

    if "--scopri-chat" in argv:
        if not tok:
            print("config mancante: TELEGRAM_BOT_TOKEN", file=sys.stderr)
            return 2
        try:
            res = _call(tok, "getUpdates")
        except Exception as e:  # noqa: BLE001
            print(f"getUpdates fallito: {e.__class__.__name__}", file=sys.stderr)
            return 3
        visti: list[tuple[int, str]] = []
        for upd in res.get("result", []):
            msg = upd.get("message") or upd.get("edited_message") or {}
            ch = msg.get("chat") or {}
            if ch.get("id"):
                visti.append((ch["id"], ch.get("username") or ch.get("first_name") or ""))
        if not visti:
            print("nessun update: apri la chat del bot su Telegram, premi START e riprova")
            return 4
        for cid, nome in visti[-3:]:
            print(f"chat_id={cid} ({nome})")
        return 0

    if "--check" in argv:
        if not tok:
            print("config mancante: TELEGRAM_BOT_TOKEN", file=sys.stderr)
            return 2
        try:
            me = (_call(tok, "getMe").get("result") or {})
        except Exception as e:  # noqa: BLE001
            print(f"getMe fallito: {e.__class__.__name__}", file=sys.stderr)
            return 3
        print(f"bot ok: @{me.get('username')}")
        if not chat:
            print("chat non configurata (dopo il /start esegui --scopri-chat)", file=sys.stderr)
            return 2
        try:
            _call(tok, "sendMessage", chat_id=chat, text="\u2705 Check notifiche Denaro: canale attivo.")
        except Exception as e:  # noqa: BLE001
            print(f"sendMessage fallito: {e.__class__.__name__}", file=sys.stderr)
            return 3
        print("messaggio di test inviato")
        return 0

    testo = " ".join(a for a in argv if not a.startswith("--")).strip()
    if not testo:
        testo = sys.stdin.read().strip()
    if not testo:
        print("uso: notifica_tg.py \"messaggio\" | --check | --scopri-chat", file=sys.stderr)
        return 2
    if not tok or not chat:
        print("config mancante: TELEGRAM_BOT_TOKEN e/o TELEGRAM_CHAT_ID", file=sys.stderr)
        return 2
    try:
        _call(tok, "sendMessage", chat_id=chat, text=testo)
    except Exception as e:  # noqa: BLE001
        print(f"sendMessage fallito: {e.__class__.__name__}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

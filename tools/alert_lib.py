#!/usr/bin/env python3
"""Libreria alert Denaro: invio Telegram robusto (anti-spam + spool di retry).

- `invia_o_spool(testo)`: invia; se fallisce, accoda in spool per il retry successivo.
- `flush_spool()`: riprova gli invii accodati (max N per giro).
- `gestisci(chiave, problema, msg_problema, msg_rientro)`: macchina a stati con
  anti-spam (un allarme per chiave per INTERVALLO_S) + messaggio di rientro.

Stato: ~/.denaro_alerts/state.json | spool: ~/.denaro_alerts/spool.jsonl
Token: come tools/notifica_tg.py (env o money/.env). Mai stampato.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

DIR = Path.home() / ".denaro_alerts"
STATE = DIR / "state.json"
SPOOL = DIR / "spool.jsonl"
INTERVALLO_S = 3600

sys.path.insert(0, str(Path(__file__).resolve().parent))
import notifica_tg  # noqa: E402


def _leggi(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _scrivi(p: Path, data) -> None:
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _registra_inviato(testo: str) -> None:
    """Audit locale: una riga per OGNI messaggio partito (timestamp + prima riga)."""
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        prima = (testo.strip().splitlines() or [""])[0][:120]
        with (DIR / "sent.log").open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%F %T')} | {prima}\n")
    except Exception:  # noqa: BLE001
        pass


def invia_o_spool(testo: str) -> bool:
    """Invia; se fallisce accoda nello spool (riprovato al prossimo giro)."""
    if notifica_tg.invia(testo):
        _registra_inviato(testo)
        return True
    try:
        DIR.mkdir(parents=True, exist_ok=True)
        with SPOOL.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"t": time.time(), "testo": testo}, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass
    return False


def flush_spool(max_n: int = 20) -> int:
    """Riprova gli invii accodati. Ritorna quanti sono partiti."""
    if not SPOOL.exists():
        return 0
    righe = [r for r in SPOOL.read_text(encoding="utf-8").splitlines() if r.strip()]
    inviati, resta = 0, []
    for i, r in enumerate(righe):
        if i < max_n:
            try:
                d = json.loads(r)
            except Exception:  # noqa: BLE001
                continue
            if d.get("testo") and notifica_tg.invia(d["testo"]):
                _registra_inviato(str(d["testo"]))
                inviati += 1
                continue
        resta.append(r)
    SPOOL.write_text("\n".join(resta) + ("\n" if resta else ""), encoding="utf-8")
    return inviati


def gestisci(chiave: str, problema: bool, msg_problema: str, msg_rientro: str,
             intervallo_s: int = INTERVALLO_S) -> bool:
    """Anti-spam per chiave. Ritorna True se ha inviato qualcosa.

    problema=True: invia max 1 volta per intervallo_s finché persiste.
    problema=False: se c'era un allarme aperto, invia il rientro e lo chiude.
    """
    stato = _leggi(STATE, {})
    ora = time.time()
    if problema:
        ultimo = float(stato.get(chiave, 0) or 0)
        if ora - ultimo > intervallo_s:
            if invia_o_spool(msg_problema):
                stato[chiave] = ora
                _scrivi(STATE, stato)
                return True
        return False
    if chiave in stato:
        if invia_o_spool(msg_rientro):
            stato.pop(chiave, None)
            _scrivi(STATE, stato)
            return True
    return False

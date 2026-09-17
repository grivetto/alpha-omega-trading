"""Stato del repo per macchina: il codice che gira e quello committato?

Perche esiste: i nodi eseguono i file del repo. Una modifica NON committata
cambia il comportamento vero senza lasciare traccia nella storia, e nessuno se
ne accorge fino al prossimo riavvio (o mai). Il 2026-09-17 e successo due volte
(tools/fetch_universe.py e tools/trend_4h_venue.py comparse modificate su mc2 e
nuvola mentre il resto del lavoro era gia committato).
"""
from __future__ import annotations

import socket
import subprocess
from pathlib import Path

CASA_MARCO = "/home/marco/alpha-omega-trading"
CASA_SERGIO = "/home/sergio/alpha-omega-trading"

# macchina -> (argomenti ssh, path del repo) oppure None se e la locale
REPO_DIRS = {
    "marcodg1": (["marco@87.106.222.123", "-p", "22"], CASA_MARCO),
    "mc2": (["sergio@127.0.0.1", "-p", "2222"], CASA_SERGIO),
    "nuvola": (["sergio@87.106.3.15", "-p", "22"], CASA_SERGIO),
}


def nome_locale() -> str:
    """Su quale macchina gira questo processo."""
    h = socket.gethostname().lower()
    if "marco" in h:
        return "marcodg1"
    if "nuvola" in h:
        return "nuvola"
    if "mc2" in h:
        return "mc2"
    return "marcodg1" if Path(CASA_MARCO).exists() else "mc2"


def _git_cmd(base: str) -> list:
    uno = "cd " + base + " && git rev-parse --short HEAD"
    due = "git status --porcelain | wc -l"
    return ["bash", "-c", uno + "; " + due]


def _ssh_cmd(ssh_args, base: str) -> list:
    remoto = "cd " + base + " && git rev-parse --short HEAD; git status --porcelain | wc -l"
    apice = chr(39)
    return ["bash", "-c", "ssh -o BatchMode=yes -o ConnectTimeout=5 "
            + " ".join(ssh_args) + " " + apice + remoto + apice]


def stato_repo() -> dict:
    """Per ogni macchina: HEAD e numero di modifiche non committate.

    "dirty" e None se la macchina non risponde (non e un falso zero).
    """
    locale = nome_locale()
    fuori = {}
    for nome, cfg in REPO_DIRS.items():
        ssh_args, base = cfg
        if nome == locale:
            cmd = _git_cmd(base)
        else:
            cmd = _ssh_cmd(ssh_args, base)
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            righe = [x.strip() for x in (r.stdout or "").splitlines() if x.strip()]
            if r.returncode == 0 and len(righe) >= 2:
                fuori[nome] = {"head": righe[0], "dirty": int(righe[1])}
            else:
                fuori[nome] = {"head": "", "dirty": None}
        except Exception:
            fuori[nome] = {"head": "", "dirty": None}
    return fuori
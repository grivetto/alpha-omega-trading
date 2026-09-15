#!/usr/bin/env python3
"""archive_stale_health.py - archivia i file di health FOSSILI (fonte di falsi allarmi CB).

Contesto (verificato 2026-09-15): su MARCODG1 i file ada.json / doge.json / eth.json / sol.json hanno
mtime 2026-09-01 23:24 e contengono errori tipo "CB OPEN: weekly_loss_-94.8%" di bot OKX dismessi:
l'aggregatore li mostra come bot attivi e genera allarmi falsi, mascherando i blocchi veri
(XRP trend in CB daily loss, SOL trend bloccato da min_notional).

Azione: sposta quei file in `health/archive_<data>/` (SPOSTA, non cancella: reversibile).
Non tocca i file vivi (trend*.json, infra_snapshot.json, *nuvola*, *mc2*).

Uso:
  python3 archive_stale_health.py --host MARCODG1 --dir /home/marco/denaro/health --dry-run
  python3 archive_stale_health.py --host MARCODG1 --dir /home/marco/denaro/health --apply
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
import time
from pathlib import Path

STALE = ["ada.json", "doge.json", "eth.json", "sol.json"]  # bot OKX dismessi, mtime 2026-09-01
KEEP_PREFIXES = ["trend", "infra_", "kraken_"]

LOG = Path("/home/sergio/hermes_bridge/stella/bridge.jsonl")


def ssh(host: str, cmd: str, timeout: int = 30) -> tuple[int, str]:
    r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", f"ConnectTimeout=8", host, cmd],
                       capture_output=True, text=True, timeout=timeout)
    return r.returncode, (r.stdout + r.stderr).strip()


def log(entry: dict) -> None:
    entry["ts"] = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="MARCODG1")
    ap.add_argument("--dir", default="/home/marco/denaro/health")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    if not a.apply and not a.dry_run:
        print("specificare --dry-run o --apply")
        return 2
    arch = f"{a.dir}/archive_{dt.datetime.now().strftime('%Y%m%d')}"

    print(f"== {a.host}:{a.dir} ==")
    rc, out = ssh(a.host, f"ls -la --time-style=long-iso {a.dir}/*.json 2>/dev/null | awk '{{print $6, $7, $9}}'")
    print("stato attuale:")
    print(out or "  (nessun file)")
    present = [f for f in STALE if f" {a.dir}/{f}" in (" " + out.replace("\n", " " + a.dir + "/").replace("  ", " "))] or STALE
    # verifica piu' robusta: esistenza per file
    to_move = []
    for f in STALE:
        rc, o = ssh(a.host, f"test -f {a.dir}/{f} && echo yes || echo no")
        if o.strip() == "yes":
            to_move.append(f)
    print("da archiviare:", to_move)
    if not to_move:
        print("niente da fare (gia' archiviati)")
        return 0
    if a.dry_run:
        rc, o = ssh(a.host, f"test -d {arch} && echo exists || echo missing")
        print(f"destinazione {arch}: {o.strip()}")
        print("DRY-RUN: nessuna modifica")
        log({"dir": "archive_stale_health", "dry_run": True, "host": a.host, "file": to_move})
        return 0

    rc, o = ssh(a.host, f"mkdir -p {arch} && mv -v " + " ".join(f"{a.dir}/{f}" for f in to_move) + f" {arch}/")
    print("esito mv:", o)
    ok = rc == 0
    rc, o2 = ssh(a.host, f"ls -la --time-style=long-iso {a.dir}/*.json 2>/dev/null | awk '{{print $6, $7, $9}}'")
    print("stato dopo:")
    print(o2 or "  (nessun file)")
    rc, o3 = ssh(a.host, f"ls -la {arch}/")
    print("contenuto archivio:")
    print(o3 or "  (vuoto)")
    log({"dir": "archive_stale_health", "dry_run": False, "host": a.host, "spostati": to_move,
         "archivio": arch, "ok": ok})
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())

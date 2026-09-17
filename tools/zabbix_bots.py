#!/usr/bin/env python3
"""Pusha le metriche dei 15 bot Denaro su Zabbix (trapper :10051).

Il registro dei bot e' UNICO (tools/denaro_bots.py), lo stesso usato dal setup
degli host Zabbix. Prima erano due elenchi separati e sono andati fuori sync: il
pusher spingeva ancora i 3 bot della generazione precedente, con file health
fermi da giorni. Zabbix segnalava "nessun dato da 5 minuti" e l'autohealing
riavviava un nodo sano OGNI 2 MINUTI.

Novita' importante: STALEZZA. Prima il contenuto di un file health vecchio
veniva pushato con status=1, quindi un nodo morto sembrava vivo e il trigger
"nodata" non poteva mai scattare (era il pusher stesso a tenere fresco l'item).
Ora un file piu' vecchio di STALE_DOPO_S viene riportato come status=0.
"""
from __future__ import annotations
import json, socket, struct, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_bots import (BOTS, MAPPA, STALE_DOPO_S, TESTUALI,  # noqa: E402
                         host_of, key_of)

ZABBIX_SERVER, ZABBIX_PORT = "127.0.0.1", 10051


def carica(src):
    """Payload del file health, o None se assente/illeggibile."""
    if src[0] == "file":
        p = Path(src[1])
        if not p.is_file():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return None
    alias, path = src[1], src[2]
    try:
        r = subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
                            alias, "cat " + path],
                           capture_output=True, text=True, timeout=15)
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout.strip().splitlines()[-1])
    except Exception:
        pass
    return None


def invia(metrics):
    if not metrics:
        return True
    payload = json.dumps({"request": "sender data", "data": metrics}).encode()
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((ZABBIX_SERVER, ZABBIX_PORT))
        s.sendall(b"ZBXD\x01" + struct.pack("<Q", len(payload)) + payload)
        s.recv(1024)
        s.close()
        return True
    except Exception as exc:
        print("zabbix_bots: invio fallito: %s" % exc, file=sys.stderr)
        return False


def metriche_di(slug, h, clock):
    """Metriche di un bot. Con h=None (irraggiungibile) si pusha solo status=0."""
    if not h:
        return [{"host": host_of(slug), "key": key_of(slug, "status"),
                 "value": 0, "clock": clock}]
    eta = clock - float(h.get("timestamp") or 0)
    h = dict(h)
    h["_status"] = 1 if (eta <= STALE_DOPO_S and h.get("status") == "running") else 0
    h["_stop_loss"] = 1 if h.get("stop_loss_triggered") else 0
    out = []
    for key, fld in MAPPA + [("status", "_status"), ("stop_loss", "_stop_loss")]:
        v = h.get(fld)
        if v is None:
            continue
        testuale = key in TESTUALI
        if v == "" and not testuale:
            continue
        if isinstance(v, str) and not testuale:
            try:
                v = float(v)
            except ValueError:
                continue
        out.append({"host": host_of(slug), "key": key_of(slug, key),
                    "value": v, "clock": clock})
    return out


def main():
    clock = int(time.time())
    metrics, fermi = [], []
    for slug, asset, mac, src in BOTS:
        h = carica(src)
        if h:
            eta = clock - float(h.get("timestamp") or 0)
            if eta > STALE_DOPO_S:
                fermi.append("%s(%.0fs)" % (slug, eta))
        else:
            fermi.append("%s(assente)" % slug)
        metrics.extend(metriche_di(slug, h, clock))
    ok = invia(metrics)
    print("zabbix_bots: %d metriche su %d bot (%s)%s"
          % (len(metrics), len(BOTS), "ok" if ok else "FALLITO",
             ("  FERMI: " + " ".join(fermi)) if fermi else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

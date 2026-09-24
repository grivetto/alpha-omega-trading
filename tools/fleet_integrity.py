#!/usr/bin/env python3
"""fleet_integrity.py — il controllo che dichiara lo stato della flotta (docs/60 §60.6).

Perche' esiste
--------------
Il 25/09/2026 tre guasti dello stesso tipo sono convissuti per giorni senza un allarme:

1. **1.486 tick saltati in silenzio** su due nodi live (conti senza capitale);
2. **553 + 560 restart** di unit systemd che puntavano a path non piu' esistenti;
3. **un miner di terzi** (utente `zabbix`) per 4 giorni su una macchina di produzione, con
   199% di CPU e meta' della RAM — causa diretta del ping-pong SafeMode del nodo live.

Nessuno dei tre era un errore di strategia. Tutti e tre erano **assenza di un controllo che
dichiara lo stato**. Questo strumento e' quel controllo: legge e basta, non modifica nulla,
e restituisce un esito binario (OK / ALLARME) con le prove.

Cosa controlla (ogni check e' indipendente e fallisce in modo esplicito)
-----------------------------------------------------------------------
- `miner`      : processi con nome kernel-like in userspace, file in /var/tmp|/tmp|/dev/shm
                 che sembrano payload, connessioni verso porte tipiche dei pool di mining.
- `crontab`    : voci che rilanciano binari da directory temporanee o con nomi ingannevoli.
- `zabbix`     : `AllowKey=system.run[*]` attiva (esecuzione comandi remoti) e regole sudo
                 verso file INESISTENTI (una regola verso un path e' root in attesa).
- `systemd`    : unit `denaro*` non attive, con contatore di restart patologico, o il cui
                 `ExecStart`/`EnvironmentFile`/`WorkingDirectory` non esiste sul disco.
- `trading`    : nodi live che **saltano ogni tick** (equity inattendibile / capitale assente).

Uso
---
    # sulla macchina locale (o dentro un nodo, via ssh)
    python tools/fleet_integrity.py
    python tools/fleet_integrity.py --json

    # su piu' host, da una macchina con le chiavi ssh (come fa l'aggregator)
    python tools/fleet_integrity.py --host nuvola --host MARCODG1 --host mc2

Esito: 0 = nessun allarme, 1 = almeno un allarme. Pensato per un timer systemd o un cron:
un controllo che non puo' fallire non e' un controllo.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional

# --- configurazione dei segnali -------------------------------------------------

#: Porte tipiche dei pool di mining (stratum). Non e' una lista esaustiva: e' la lista dei
#: valori osservati sul campo, e serve a distinguere "traffico strano" da "traffico noto".
PORTE_POOL = ("3333", "33333", "14444", "45700", "5555", "7777", "8888", "9999")

#: Nomi che imitano thread del kernel ma non hanno le parentesi quadre in `ps`.
NOMI_KERNEL_INGANNEVOLI = re.compile(
    r"(kworker|kswapd|kdevtmpfsi|kthreadd|ksoftirqd|migration)[/_]?[a-z0-9]*\s*$",
    re.IGNORECASE)

#: Directory che un payload sceglie perche' sono volatili e poco ispezionate.
DIR_TEMP = ("/var/tmp", "/tmp", "/dev/shm")

#: Pattern di file che nella quasi totalita' dei casi sono payload.
NOMI_PAYLOAD = re.compile(
    r"(^\.(kworker|kdevtmpfsi|kinsing|lpe|syslog|daemon|cron_clean)"
    r"|xmrig|\.self$|\.kworker)", re.IGNORECASE)

#: Porte in ascolto che non hanno motivo di essere raggiungibili su un nodo di questa
#: flotta. Non e' una policy completa: e' cio' che l'audit del 25/09 ha trovato esposto
#: senza che nessuno lo sapesse (postgres e agent Zabbix su interfaccia pubblica).
PORTE_DA_SEGNALARE = {
    "5432": "postgres in ascolto: su un nodo di trading non serve esposto",
    "3306": "mysql in ascolto",
    "6379": "redis in ascolto",
    "9200": "elasticsearch in ascolto",
    "10050": "agent Zabbix in ascolto: con system.run attivo e' esecuzione di comandi",
    "2375": "docker daemon in TCP non cifrato",
}


class Esito:
    """Raccoglitore di reperti. Ogni reperto ha un livello, un check e una prova."""

    def __init__(self) -> None:
        self.reperti: List[Dict[str, str]] = []

    def allarme(self, check: str, prova: str, cosa: str) -> None:
        self.reperti.append({"livello": "ALLARME", "check": check,
                             "prova": prova, "cosa": cosa})

    def nota(self, check: str, prova: str, cosa: str) -> None:
        self.reperti.append({"livello": "nota", "check": check,
                             "prova": prova, "cosa": cosa})

    @property
    def allarmi(self) -> List[Dict[str, str]]:
        return [r for r in self.reperti if r["livello"] == "ALLARME"]

    def esito(self) -> int:
        return 1 if self.allarmi else 0


# --- esecuzione comandi ---------------------------------------------------------

def _run(cmd: List[str], timeout: int = 25) -> str:
    """Esegue un comando di sola lettura. Vuoto se fallisce: il check lo dira'."""
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return out.stdout or ""
    except Exception:
        return ""


# --- check: miner ---------------------------------------------------------------

def check_miner(e: Esito) -> None:
    """Processi con nome kernel-like in userspace, payload in dir temporanee, pool."""
    ps = _run(["ps", "-eo", "pid,user,pcpu,rss,args", "--sort=-pcpu"])
    for riga in ps.splitlines()[1:]:
        parti = riga.split(None, 4)
        if len(parti) < 5:
            continue
        pid, user, pcpu, _rss, args = parti
        eseguibile = args.split()[0] if args.split() else ""
        # un thread del kernel appare come "[kworker/...]": le parentesi quadre sono la
        # differenza fra un thread vero e un processo che si spaccia per tale.
        if eseguibile.startswith("["):
            continue
        if not NOMI_KERNEL_INGANNEVOLI.search(os.path.basename(eseguibile)):
            continue
        e.allarme("miner", f"pid={pid} user={user} cpu={pcpu}% cmd={args[:90]}",
                  "processo utente che imita un thread del kernel "
                  "(nome falsificato: e' la firma del miner trovato il 25/09)")

    # payload su disco
    for d in DIR_TEMP:
        if not os.path.isdir(d):
            continue
        try:
            voci = os.listdir(d)
        except PermissionError:
            e.nota("miner", f"{d}: permesso negato",
                   "non ispezionabile senza privilegi: il check e' cieco qui")
            continue
        for v in voci:
            if NOMI_PAYLOAD.search(v):
                p = os.path.join(d, v)
                e.allarme("miner", p,
                          "file con nome da payload in directory temporanea "
                          "(verifica hash prima di cancellare)")

    # connessioni verso pool
    ss = _run(["ss", "-tnp"])
    for riga in ss.splitlines():
        for porta in PORTE_POOL:
            if f":{porta} " in riga or riga.rstrip().endswith(f":{porta}"):
                e.allarme("miner", riga.strip()[:150],
                          f"connessione verso la porta {porta} (pool di mining tipico)")
                break


# --- check: crontab -------------------------------------------------------------

def check_crontab(e: Esito) -> None:
    """Cron che rilanciano binari da directory temporanee o con `cron_clean`."""
    base = "/var/spool/cron/crontabs"
    if not os.path.isdir(base):
        return
    try:
        utenti = os.listdir(base)
    except PermissionError:
        e.nota("crontab", base, "permesso negato: esegui come root per il check completo")
        return
    for u in utenti:
        p = os.path.join(base, u)
        try:
            with open(p, encoding="utf-8", errors="replace") as f:
                testo = f.read()
        except (PermissionError, OSError):
            e.nota("crontab", p, "non leggibile senza privilegi")
            continue
        for riga in testo.splitlines():
            if not riga.strip() or riga.lstrip().startswith("#"):
                # anche i commenti di intestazione di `crontab` portano informazione:
                # `/dev/shm/.cron_clean_*` come sorgente e' la traccia di una manomissione.
                if "cron_clean" in riga or "/dev/shm" in riga:
                    e.allarme("crontab", f"{u}: {riga.strip()[:120]}",
                              "crontab installato da /dev/shm (artefatto di manomissione, "
                              "visto il 19/09 su mc2)")
                continue
            # Si giudica l'ESEGUIBILE, non la riga intera: `>> /tmp/log` e' solo una
            # redirezione e non deve diventare un allarme (falso positivo osservato il
            # 25/09 su una riga di log legittima).
            eseguibile = riga.split(">")[0]
            for d in DIR_TEMP:
                if d + "/" in eseguibile:
                    e.allarme("crontab", f"{u}: {riga.strip()[:120]}",
                              f"cron che esegue un binario da {d}: nessun servizio "
                              "legittimo vive nelle directory temporanee")
            if NOMI_PAYLOAD.search(eseguibile):
                e.allarme("crontab", f"{u}: {riga.strip()[:120]}",
                          "cron con nome di payload")


# --- check: porte esposte -------------------------------------------------------

def check_porte(e: Esito) -> None:
    """Porte in ascolto che non hanno motivo di essere raggiungibili.

    L'audit del 25/09 ha trovato `postgres` e l'agent Zabbix in ascolto su indirizzi
    non-locali con `ufw` **inactive**: nessuno lo sapeva. Non e' una policy di
    sicurezza completa: e' il promemoria che l'esposizione va **vista**, non supposta.
    """
    ss = _run(["ss", "-ltnp"])
    for riga in ss.splitlines()[1:]:
        parti = riga.split()
        if len(parti) < 4:
            continue
        locale = parti[3]
        if locale.startswith("127.") or locale.startswith("[::1]"):
            continue                      # solo loopback: non e' esposizione
        porta = locale.rsplit(":", 1)[-1]
        if porta in PORTE_DA_SEGNALARE:
            e.allarme("porte", riga.strip()[:130], PORTE_DA_SEGNALARE[porta])


# --- check: zabbix --------------------------------------------------------------

def check_zabbix(e: Esito) -> None:
    """Esecuzione comandi remoti e regole sudo verso file inesistenti."""
    conf = "/etc/zabbix/zabbix_agentd.conf"
    if os.path.exists(conf):
        try:
            with open(conf, encoding="utf-8", errors="replace") as f:
                for riga in f:
                    s = riga.strip()
                    if s.startswith("AllowKey=system.run"):
                        e.allarme("zabbix", f"{conf}: {s}",
                                  "l'agent esegue comandi arbitrari su richiesta: e' il "
                                  "vettore con cui e' entrato il miner del 19/09")
        except PermissionError:
            e.nota("zabbix", conf, "non leggibile senza privilegi")
    d = "/etc/sudoers.d"
    if os.path.isdir(d):
        try:
            for f in os.listdir(d):
                p = os.path.join(d, f)
                try:
                    with open(p, encoding="utf-8", errors="replace") as fh:
                        testo = fh.read()
                except (PermissionError, OSError):
                    continue
                for m in re.finditer(r"(/[A-Za-z0-9_./-]+\.(?:sh|py))", testo):
                    target = m.group(1)
                    if not os.path.exists(target):
                        e.allarme("zabbix" if "zabbix" in testo.lower() else "sudoers",
                                  f"{p} -> {target}",
                                  "regola sudo verso un file INESISTENTE: se quel file "
                                  "compare, l'utente ottiene root senza password")
        except PermissionError:
            pass


# --- check: systemd ------------------------------------------------------------

def check_systemd(e: Esito) -> None:
    """Unit denaro*: stato, restart patologici, path delle direttive inesistenti."""
    out = _run(["systemctl", "list-units", "denaro*", "--all", "--no-pager",
                "--plain", "--no-legend"])
    for riga in out.splitlines():
        parti = riga.split()
        if len(parti) < 4:
            continue
        unit, load, active, sub = parti[0], parti[1], parti[2], parti[3]
        if active != "active" and sub not in ("running", "exited"):
            e.allarme("systemd", f"{unit} {active}/{sub}",
                      "unita' della flotta non attiva: se e' un nodo, il trading e' fermo; "
                      "se e' telemetria, la flotta e' cieca")
        cat = _run(["systemctl", "show", "-p", "NRestarts", "--value", unit])
        try:
            n = int(cat.strip() or "0")
        except ValueError:
            n = 0
        if n >= 50:
            e.allarme("systemd", f"{unit} NRestarts={n}",
                      "restart patologico: l'unita' e' in un ciclo morto e nessuno se ne "
                      "accorge (osservati 553 e 560 restart)")
        # path delle direttive
        for prop in ("ExecStart", "EnvironmentFile", "WorkingDirectory"):
            val = _run(["systemctl", "show", "-p", prop, "--value", unit]).strip()
            if not val:
                continue
            for token in val.split():
                if not token.startswith("/"):
                    continue
                if token.startswith("-"):      # prefisso "-" = path opzionale, per systemd
                    token = token[1:]
                if not os.path.exists(token):
                    e.allarme("systemd", f"{unit} {prop}={token}",
                              "direttiva che punta a un path inesistente: e' la causa "
                              "radice dei 1.113 restart osservati il 25/09")


# --- check: trading ------------------------------------------------------------

def check_trading(e: Esito, dir_health: Optional[str] = None,
                  max_eta_s: float = 600.0) -> None:
    """Nodi live che saltano ogni tick o che non scrivono piu' health (fossili)."""
    import time
    candidati = []
    if dir_health:
        candidati.append(dir_health)
    for d in ("/home/sergio/denaro/health", "/home/marco/denaro/health"):
        if os.path.isdir(d) and d not in candidati:
            candidati.append(d)
    if not candidati:
        e.nota("trading", "nessuna dir health trovata",
               "controllo dei nodi live non eseguito su questa macchina")
        return
    ora = time.time()
    for d in candidati:
        try:
            files = [f for f in os.listdir(d) if f.endswith(".json")]
        except (PermissionError, OSError):
            continue
        for f in files:
            p = os.path.join(d, f)
            try:
                with open(p, encoding="utf-8", errors="replace") as fh:
                    h = json.load(fh)
            except Exception:
                continue
            eta = ora - os.path.getmtime(p)
            err = str(h.get("error") or "")
            blocked = h.get("blocked")
            if eta > max_eta_s:
                e.allarme("trading", f"{f} eta'={eta:.0f}s",
                          "health FOSSILE mentre il servizio risulta attivo: nessuno "
                          "scrive piu' lo stato del bot")
            elif blocked and "inattendibile" in err:
                e.allarme("trading", f"{f} equity={h.get('total_equity')} err={err[:60]}",
                          "il bot salta OGNI tick: il conto non ha il capitale che la "
                          "config dichiara (1.486 tick persi in silenzio il 25/09)")


# --- orchestrazione -------------------------------------------------------------

def esegui(host: Optional[str] = None, dir_health: Optional[str] = None) -> Dict[str, Any]:
    """Esegue i check. Con `host`, li esegue REMOTI via ssh con questo stesso file."""
    if host:
        remoto = ("python3 - " if not sys.argv[0].endswith(".py") else f"python3 {sys.argv[0]} ")
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host,
               f"{remoto}--json"]
        out = _run(cmd, timeout=90)
        try:
            dati = json.loads(out.strip().splitlines()[-1])
            dati["host"] = host
            return dati
        except Exception:
            return {"host": host, "esito": 1,
                    "reperti": [{"livello": "ALLARME", "check": "ssh",
                                 "prova": (out or "nessun output")[:200],
                                 "cosa": "controllo remoto non eseguibile: la flotta non "
                                         "e' ispezionabile (chiave ssh, path o permessi)"}]}
    e = Esito()
    check_miner(e)
    check_crontab(e)
    check_porte(e)
    check_zabbix(e)
    check_systemd(e)
    check_trading(e, dir_health=dir_health)
    return {"host": os.uname().nodename if hasattr(os, "uname") else "locale",
            "esito": e.esito(), "reperti": e.reperti}


def _stampa(ris: Dict[str, Any]) -> None:
    allarmi = [r for r in ris["reperti"] if r["livello"] == "ALLARME"]
    note = [r for r in ris["reperti"] if r["livello"] == "nota"]
    testa = "ALLARME" if allarmi else "OK"
    print(f"[{testa}] {ris['host']} — {len(allarmi)} allarmi, {len(note)} note")
    for r in allarmi:
        print(f"  ALLARME {r['check']:9s} {r['prova']}")
        print(f"          -> {r['cosa']}")
    for r in note:
        print(f"  nota    {r['check']:9s} {r['prova']}")


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Controllo d'integrita' della flotta Denaro")
    ap.add_argument("--host", action="append", default=[],
                    help="host ssh da controllare (ripetibile); senza, controlla il locale")
    ap.add_argument("--health-dir", default=None,
                    help="directory dei file health dei bot (default: i path noti)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    risultati = [esegui(h, args.health_dir) for h in args.host] if args.host \
        else [esegui(dir_health=args.health_dir)]

    if args.json:
        print(json.dumps(risultati if len(risultati) > 1 else risultati[0],
                         indent=2, ensure_ascii=False))
    else:
        for r in risultati:
            _stampa(r)
    return 1 if any(r["esito"] for r in risultati) else 0


if __name__ == "__main__":
    raise SystemExit(main())

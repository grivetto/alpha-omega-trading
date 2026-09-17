#!/usr/bin/env python3
"""Pusha le metriche dei bot Denaro su Zabbix (trapper :10051).

1 bot locale (mc2, DOGE) + 2 remoti (nuvola, MARCODG1) letti via SSH.
"""
from __future__ import annotations
import json, socket, struct, subprocess, sys, time
from pathlib import Path

ZABBIX_SERVER, ZABBIX_PORT = "127.0.0.1", 10051

BOTS = [
    ("alpha-omega-bot-okx-doge",     "okx_doge",     ("file", "/home/sergio/denaro/health/doge_mc2.json")),
    ("alpha-omega-bot-nuvola-sol",   "nuvola_sol",   ("ssh", "nuvola", "/home/sergio/denaro/health/sol_nuvola_live.json")),
    ("alpha-omega-bot-marcodg1-xrp", "marcodg1_xrp", ("ssh", "MARCODG1", "/home/marco/denaro/health/xrp_marcodg1_live.json")),
]
MAP = [("equity","total_equity"),("free","free_quote"),("pnl","pnl"),("volume","volume"),("trades","trades"),
       ("wins","wins"),("losses","losses"),("buys","buys"),("sells","sells"),("drawdown","drawdown"),
       ("uptime","uptime"),("cap_locked","cap_locked"),("cap_available","cap_available"),
       ("win_rate","win_rate_pct"),("profit_factor","profit_factor"),("sharpe","sharpe"),("sortino","sortino"),
       ("calmar","calmar"),("kelly","kelly"),("adx","adx"),("atr_pct","atr_pct"),("rsi","rsi"),
       ("ema200","ema200"),("hurst","hurst"),("strategy","strategy"),("regime","regime"),("error","error")]


def load(src):
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


def send(metrics):
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


def main():
    clock = int(time.time())
    metrics = []
    for host, prefix, src in BOTS:
        h = load(src)
        if not h:
            continue
        h["_status"] = 1 if h.get("status") == "running" else 0
        h["_stop_loss"] = 1 if h.get("stop_loss_triggered") else 0
        for key, fld in MAP + [("status", "_status"), ("stop_loss", "_stop_loss")]:
            v = h.get(fld)
            # NB: per gli item di TESTO (strategia/regime/errore) si pusha
            # anche la stringa VUOTA: serve a PULIRE il valore quando il
            # problema e' risolto. Saltandola, un errore vecchio resta
            # sull'item per sempre e il trigger continua a scattare.
            if v is None:
                continue
            if v == "" and key not in ("strategy", "regime", "error"):
                continue
            if isinstance(v, str) and key not in ("strategy", "regime", "error"):
                try:
                    v = float(v)
                except ValueError:
                    continue
            metrics.append({"host": host, "key": "bot.%s.%s" % (prefix, key),
                            "value": v, "clock": clock})
    ok = send(metrics)
    print("zabbix_bots: %d metriche inviate (%s)" % (len(metrics), "ok" if ok else "FALLITO"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

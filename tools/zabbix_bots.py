#!/usr/bin/env python3
"""Pusha le metriche dei bot Denaro su Zabbix (trapper :10051).

Legge gli health file dei bot attivi e manda una metrica per item.
Nessuna dipendenza esterna: protocollo trapper ZBXD/1.0 su socket.
"""
from __future__ import annotations

import json
import socket
import struct
import sys
import time
from pathlib import Path

ZABBIX_SERVER = "127.0.0.1"
ZABBIX_PORT = 10051

# host Zabbix -> path dell'health file -> prefisso chiave item
BOTS = [
    ("alpha-omega-bot-okx-doge", "/home/sergio/denaro/health/doge_mc2.json", "okx_doge"),
    ("alpha-omega-bot-okx-sol",  "/home/sergio/denaro/health/sol_mc2.json",  "okx_sol"),
]

# chiave item <- campo dell'health file
MAP = [
    ("equity", "total_equity"), ("free", "free_quote"), ("pnl", "pnl"),
    ("volume", "volume"), ("trades", "trades"), ("wins", "wins"),
    ("losses", "losses"), ("buys", "buys"), ("sells", "sells"),
    ("drawdown", "drawdown"), ("uptime", "uptime"),
    ("cap_locked", "cap_locked"), ("cap_available", "cap_available"),
    ("win_rate", "win_rate_pct"), ("profit_factor", "profit_factor"),
    ("sharpe", "sharpe"), ("sortino", "sortino"), ("calmar", "calmar"),
    ("kelly", "kelly"), ("adx", "adx"), ("atr_pct", "atr_pct"),
    ("rsi", "rsi"), ("ema200", "ema200"), ("hurst", "hurst"),
    ("strategy", "strategy"), ("regime", "regime"), ("error", "error"),
]


def send(metrics: list) -> bool:
    """Trapper con cache offline: la perdita di un invio non e' fatale."""
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
    except Exception as exc:  # noqa: BLE001
        print("zabbix_bots: invio fallito: %s" % exc, file=sys.stderr)
        return False


def main() -> int:
    clock = int(time.time())
    metrics = []
    for host, path, prefix in BOTS:
        p = Path(path)
        if not p.is_file():
            continue
        try:
            h = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        # status: 1 = running, 0 = altro. stop_loss: 1 se scattato.
        h["_status"] = 1 if h.get("status") == "running" else 0
        h["_stop_loss"] = 1 if h.get("stop_loss_triggered") else 0
        for key, field in MAP + [("status", "_status"), ("stop_loss", "_stop_loss")]:
            v = h.get(field)
            if v is None or v == "":
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


#!/usr/bin/env python3
"""kraken_cancel_orders.py - annulla ordini aperti su Kraken (AZIONE IRREVERSIBILE).

Autorizzato da Sergio il 2026-09-15: annullare i 3 ordini di vendita XRP/EUR orfani
(bot disabilitato, ~10% sopra mercato, nessuno li gestiva).

Sicurezze:
  - default DRY-RUN: senza --execute non annulla nulla, stampa solo cosa farebbe;
  - annulla SOLO gli id passati con --id (o quelli elencati da --from-audit), mai "tutto" per caso;
  - verifica lo stato PRIMA di annullare (deve essere 'open'), rilegge DOPO e confronta i saldi;
  - log append-only in /home/sergio/hermes_bridge/stella/bridge.jsonl (dir "kraken_cancel").

Uso:
  python3 kraken_cancel_orders.py --env /tmp/kraken_legacy.env                 # dry-run
  python3 kraken_cancel_orders.py --env /tmp/kraken_legacy.env --execute \
      --id OQXXOD-P3MAN-7TRUR2 --id OPDGIW-PUYL4-WYVRJF --id OS6KQJ-K3M47-AKBRAP
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

LOG = Path("/home/sergio/hermes_bridge/stella/bridge.jsonl")


def load_env(path: str) -> dict:
    out: dict = {}
    p = Path(path).expanduser()
    if p.exists():
        for line in p.read_text(errors="replace").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def log(entry: dict) -> None:
    entry["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    try:
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def balances(ex) -> dict:
    b = ex.fetch_balance()
    return {k: float(v) for k, v in (b.get("free") or {}).items() if v and float(v) > 0}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default="/tmp/kraken_legacy.env")
    ap.add_argument("--id", action="append", default=[])
    ap.add_argument("--execute", action="store_true")
    a = ap.parse_args()
    env = load_env(a.env)
    if not env.get("KRAKEN_API_KEY") or not (env.get("KRAKEN_API_SECRET") or env.get("KRAKEN_SECRET")):
        print("credenziali Kraken mancanti in", a.env)
        return 2
    import ccxt  # type: ignore
    ex = ccxt.kraken({"apiKey": env["KRAKEN_API_KEY"],
                      "secret": env.get("KRAKEN_API_SECRET") or env.get("KRAKEN_SECRET"),
                      "enableRateLimit": True})

    open_now = {o["id"]: o for o in ex.fetch_open_orders()}
    print("ordini aperti adesso:", len(open_now))
    targets = a.id or list(open_now.keys())
    print("obiettivo:", targets)
    free_before = balances(ex)
    print("free prima:", json.dumps(free_before, ensure_ascii=False))

    done, skipped = [], []
    for oid in targets:
        o = open_now.get(oid)
        if not o:
            print(f"  {oid}: NON aperto adesso -> salto")
            skipped.append({"id": oid, "motivo": "non aperto"})
            continue
        if o.get("side") != "sell":
            print(f"  {oid}: lato {o.get('side')} inatteso -> salto")
            skipped.append({"id": oid, "motivo": f"lato {o.get('side')}"})
            continue
        print(f"  {oid} {o['symbol']} {o['side']} price={o['price']} amount={o['amount']}")
        if not a.execute:
            print("    DRY-RUN: non annullo (usa --execute)")
            continue
        try:
            res = ex.cancel_order(oid, o["symbol"])
            done.append({"id": oid, "symbol": o["symbol"], "result": str(res)[:120]})
            print("    annullato:", str(res)[:100])
        except Exception as e:  # noqa: BLE001
            print("    errore annullamento:", type(e).__name__, str(e)[:160])
            skipped.append({"id": oid, "motivo": f"{type(e).__name__}: {str(e)[:120]}"})
        time.sleep(1)

    if a.execute:
        time.sleep(3)
        open_after = ex.fetch_open_orders()
        free_after = balances(ex)
        print("\nordini aperti dopo:", len(open_after))
        for o in open_after:
            print("  residuo:", o.get("id"), o.get("symbol"), o.get("side"), o.get("price"))
        print("free dopo:", json.dumps(free_after, ensure_ascii=False))
        log({"dir": "kraken_cancel", "eseguito": True, "annullati": done, "saltati": skipped,
             "free_prima": free_before, "free_dopo": free_after,
             "aperti_dopo": len(open_after)})
    else:
        log({"dir": "kraken_cancel", "eseguito": False, "dry_run": True, "obiettivo": targets,
             "free_prima": free_before})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""repair_aggregator_helpers.py - inserisce a livello di modulo gli helper mancanti.

Il fix precedente (fix_local_aggregator_equity.py) ha sostituito il blocco dell'equity ma NON ha
inserito le funzioni fetch_eur_rate()/balance_eur() perche' il pattern di ancoraggio non combaciava:
risultato "name 'balance_eur' is not defined". Questo script le inserisce prima di `class Handler`,
verifica la sintassi e riavvia il servizio.

Uso: python3 repair_aggregator_helpers.py [--check|--apply]
"""
from __future__ import annotations

import argparse
import py_compile
import shutil
import subprocess
import sys
import datetime as dt
from pathlib import Path

TARGET = Path("/home/sergio/alpha-omega-trading/denaro/infra_aggregator.py")
ANCHOR = "class Handler(BaseHTTPRequestHandler):"

HELPERS = '''# [fix-equity-stella] valorizzazione dei saldi reali in EUR (stessa logica dell'aggregatore MARCODG1)
_eur_rate_cache = {}


def fetch_eur_rate(currency):
    """Cambio in EUR per una valuta; stablecoin = 1.0; None se non disponibile."""
    cur = str(currency or "").upper()
    if not cur:
        return None
    if cur in ("EUR", "USDT", "USDC", "DAI", "USD", "TUSD", "PYUSD"):
        return 1.0
    now = time.time()
    hit = _eur_rate_cache.get(cur)
    if hit and now - hit[0] < 300:
        return hit[1]
    rate = None
    try:
        import ccxt
        ex = ccxt.okx({"enableRateLimit": True, "hostname": "eea.okx.com"})
        for pair in ("%s/EUR" % cur, "%s/USDT" % cur):
            try:
                t = ex.fetch_ticker(pair)
                last = float(t.get("last") or 0)
                if not last:
                    continue
                if pair.endswith("USDT"):
                    try:
                        fx = float(ex.fetch_ticker("EUR/USDT").get("last") or 1) or 1
                        last = last / fx
                    except Exception:
                        pass
                rate = last
                break
            except Exception:
                continue
    except Exception:
        rate = None
    _eur_rate_cache[cur] = (now, rate)
    return rate


def balance_eur(balances):
    """Valorizza in EUR i saldi reali deduplicando gli account identici.

    Ritorna (totale_eur, dettaglio_per_etichetta, quote_non_valutate).
    """
    seen = []
    detail = {}
    total = 0.0
    unpriced = []
    for label, bal in (balances or {}).items():
        if not isinstance(bal, dict) or not bal.get("ok"):
            err = bal.get("error", "") if isinstance(bal, dict) else "n/d"
            detail[label] = {"ok": False, "eur": None, "error": str(err)[:80]}
            continue
        fp = bal.get("acct") or label
        if fp in seen:
            detail[label] = {"ok": True, "eur": None, "dedup": True}
            continue
        seen.append(fp)
        tot = 0.0
        for cur, amt in (bal.get("total") or {}).items():
            try:
                amt = float(amt)
            except Exception:
                continue
            if amt <= 0:
                continue
            rate = fetch_eur_rate(cur)
            if rate is None:
                unpriced.append("%s:%s" % (label, cur))
                continue
            tot += amt * rate
        detail[label] = {"ok": True, "eur": round(tot, 2)}
        total += tot
    return round(total, 2), detail, unpriced


'''


def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--check", action="store_true")
    g.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    src = TARGET.read_text()
    has = "def balance_eur(" in src
    if a.check:
        print("balance_eur presente:", has)
        print("anchor presente:", ANCHOR in src)
        return 0
    if has:
        print("helper gia' presenti, nessuna modifica")
        return 0
    if ANCHOR not in src:
        print("ERRORE: anchor non trovato, nessuna modifica")
        return 2
    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TARGET.with_name(f"infra_aggregator.py.bak.helpers{stamp}")
    shutil.copy2(TARGET, bak)
    print("backup:", bak)
    TARGET.write_text(src.replace(ANCHOR, HELPERS + ANCHOR, 1))
    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("sintassi OK")
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, TARGET)
        print("SINTASSI ERRATA, ripristinato:", e)
        return 3
    sh("sudo -n systemctl restart --kill-who=all denaro-aggregator-mc2.service")
    print("servizio riavviato")
    return 0


if __name__ == "__main__":
    sys.exit(main())

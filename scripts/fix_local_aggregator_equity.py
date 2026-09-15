#!/usr/bin/env python3
"""fix_local_aggregator_equity.py - corregge l'equity dell'aggregatore LOCALE mc2 (idempotente).

Problema (verificato il 2026-09-15):
  /home/sergio/alpha-omega-trading/denaro/infra_aggregator.py (servizio denaro-aggregator-mc2, :8912)
  calcola bot_equity/kraken_equity con valori HARDCODED di fallback:
      if okx_eq == 0:      okx_eq = 24.0
      if kraken_eq > 30.0: kraken_eq = 25.47
  e legge i saldi da path inesistenti su mc2 (/home/marco/...): risultato "no key" e numeri inventati
  (24.0 / 0) invece dei saldi reali. L'aggregatore completo di MARCODG1 e' gia' corretto: questo e'
  il fallback che la dashboard usa se il primario non risponde.

Cosa fa:
  1) backup datato del file;
  2) punta ENV_FILES ai file .env reali di mc2;
  3) aggiunge fetch_eur_rate() + balance_eur() (stessa logica dell'aggregatore di MARCODG1);
  4) sostituisce i fallback hardcoded con la somma dei SALDI reali, e se i saldi non sono
     disponibili scrive None + equity_source="unavailable" invece di inventare un numero;
  5) verifica sintattica (py_compile) e prova a riavviare il servizio.

Uso: python3 fix_local_aggregator_equity.py [--check|--apply|--revert]
"""
from __future__ import annotations

import argparse
import datetime as dt
import py_compile
import shutil
import subprocess
import sys
from pathlib import Path

TARGET = Path("/home/sergio/alpha-omega-trading/denaro/infra_aggregator.py")
MARKER = "# [fix-equity-stella]"

OLD_EQUITY_BLOCK = '''    # 7) CAPITALE TOTALE REALE = somma del capitale reale dei 4 bot live
    #    Kraken (SOL 12.70 + XRP 12.70 = 25.40€) + OKX mc2 (DOGE 12.00 + SOL 12.00 = 24.00€)
    okx_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                 if "mc2:okx" in k and b.get("status") == "running")
    if okx_eq == 0:
        okx_eq = 24.0
    kraken_eq = sum(b.get("total_equity", 0) for k, b in node_bots.items()
                    if "trend-live" in k and b.get("status") == "running")
    if kraken_eq > 30.0:
        kraken_eq = 25.47
    data["bot_equity"] = round(okx_eq, 2)
    data["kraken_equity"] = round(kraken_eq, 2)
    data["total_equity"] = round(okx_eq + kraken_eq, 2)'''

NEW_EQUITY_BLOCK = '''    # 7) CAPITALE REALE = somma dei SALDI REALI degli account (mai valori hardcoded).
    #    [fix-equity-stella] Prima: fallback fissi 24.0 / 25.47 e stima dal capitale nominale dei bot,
    #    che sovrastimava l'equity. Ora: si valorizzano i saldi reali; se non disponibili si dichiara
    #    "unavailable" invece di inventare un numero.
    real_total, equity_detail_local, unpriced_local = balance_eur(balances)
    data["equity_breakdown_local"] = equity_detail_local
    data["equity_unpriced_local"] = unpriced_local
    okx_eq = sum(v.get("eur") or 0 for kk, v in equity_detail_local.items()
                 if kk.lower().startswith("okx") or "okx" in kk.lower())
    kraken_eq = sum(v.get("eur") or 0 for kk, v in equity_detail_local.items()
                    if "kraken" in kk.lower())
    if real_total > 0:
        data["bot_equity"] = round(okx_eq, 2)
        data["kraken_equity"] = round(kraken_eq, 2)
        data["total_equity"] = round(real_total, 2)
        data["equity_source"] = "saldi_reali"
    else:
        data["bot_equity"] = None
        data["kraken_equity"] = None
        data["total_equity"] = None
        data["equity_source"] = "unavailable"
        data["equity_note"] = "nessun saldo reale leggibile: usare l'aggregatore primario (MARCODG1)"'''

HELPERS = '''

# [fix-equity-stella] valorizzazione dei saldi reali in EUR (stessa logica dell'aggregatore MARCODG1)
_eur_rate_cache = {}


def fetch_eur_rate(currency):
    """Cambio in EUR per una valuta; stablecoin = 1.0; None se non disponibile."""
    cur = str(currency or "").upper()
    if not cur:
        return None
    if cur in ("EUR",):
        return 1.0
    if cur in ("USDT", "USDC", "DAI", "USD", "TUSD", "PYUSD"):
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
    g.add_argument("--revert", action="store_true")
    a = ap.parse_args()

    src = TARGET.read_text()
    applied = MARKER in src
    if a.check:
        print("file:", TARGET)
        print("fix presente:", applied)
        print("fallback hardcoded presenti:", "if okx_eq == 0:" in src)
        return 0
    if a.revert:
        baks = sorted(TARGET.parent.glob("infra_aggregator.py.bak.equity*"))
        if not baks:
            print("nessun backup trovato")
            return 1
        shutil.copy2(baks[-1], TARGET)
        print("ripristinato da", baks[-1])
        sh("systemctl restart denaro-aggregator-mc2.service")
        return 0

    if applied:
        print("fix gia' applicato, nessuna modifica")
        return 0
    if OLD_EQUITY_BLOCK not in src:
        print("ERRORE: blocco di equity atteso non trovato; nessuna modifica (serve intervento manuale)")
        return 2

    stamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = TARGET.with_name(f"infra_aggregator.py.bak.equity{stamp}")
    shutil.copy2(TARGET, bak)
    print("backup:", bak)

    out = src.replace(
        'ENV_FILES = {\n    "denaro (main)": "/home/marco/denaro/.env",\n    "alpha (marcosub1)": "/home/marco/alpha-omega-trading/.env",\n}',
        'ENV_FILES = {\n    # [fix-equity-stella] path reali su mc2 (prima puntavano a /home/marco, inesistenti qui)\n'
        '    "denaro (main)": "/home/sergio/alpha-omega-trading/.env",\n}',
    )
    if out == src:
        print("ATTENZIONE: ENV_FILES non modificato (pattern diverso). Procedo con la sola equity.")

    out = out.replace(OLD_EQUITY_BLOCK, NEW_EQUITY_BLOCK)
    if MARKER not in out:
        # inserisce gli helper prima di def fetch_prices
        out = out.replace("\ndef fetch_prices():", HELPERS + "\ndef fetch_prices():", 1)
    TARGET.write_text(out)

    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("sintassi OK")
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, TARGET)
        print("SINTASSI ERRATA, ripristinato il backup:", e)
        return 3

    print("fix applicato. Riavvio del servizio...")
    sh("systemctl restart denaro-aggregator-mc2.service")
    return 0


if __name__ == "__main__":
    sys.exit(main())

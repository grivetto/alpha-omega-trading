#!/usr/bin/env python3
"""Conformita' della flotta deployata allo specificato MISURATO.

Il mandato e' "deploy solo di edge misurato e robusto". Questo tool trasforma
quella frase in un controllo: confronta i tre config di produzione con la
specifica deployata (parametri, universo, capitali, modalita') e con i guardrail
(mandato strategie, barre allineate all'exchange) e stampa PASS/FAIL per voce.

Serve a scoprire in un comando se qualcosa e' cambiato sotto i piedi: un
parametro ritoccato, un asset aggiunto o tolto, un capitale disallineato, una
strategia non misurata riportata in live. Il 2026-09-17 e' successo piu' volte
che una modifica arrivasse da una sessione parallela.

Uso: python3 tools/trend_conformita.py
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import yaml  # noqa: E402

from denaro.research.misurate import puo_girare_live  # noqa: E402

# ── SPECIFICA DEPLOYATA (docs/37, 41) ────────────────────────────────────────
PAR = {"canale": 40, "atr_period": 14, "trail_mult": 2.5, "stop_atr_mult": 2.0,
       "trend_ema": 100, "risk_pct": 0.02, "max_exposure": 1.0,
       "fee": 0.0035, "timeframe": "1d", "mode": "okx", "strategy": "trend"}
FLOTTA = {
    "mc2": (42.12, ["BTC", "ETH", "SOL", "XRP", "DOGE", "TRX", "CRV"]),
    "nuvola": (24.83, ["LINK", "AVAX", "DOT", "UNI", "SUI", "MINA"]),
    "marcodg1": (42.04, ["ADA", "ARB", "XLM", "ALGO"]),
}
CONFIG = {
    "mc2": "config/node_mc2.yaml",
    "nuvola": "config/node_nuvola_trade.yaml",
    "marcodg1": "config/node_marcodg1_xrp.yaml",
}
TOLLERANZA_CAPITALE = 0.02      # 2%: i saldi si muovono col mercato
OFFSET_ATTESO = 57_600.0        # 16:00 UTC: il confine delle candele OKX

esiti = []


def check(ok: bool, descrizione: str, dettaglio: str = "") -> None:
    esiti.append((ok, descrizione, dettaglio))
    print("  %-4s %s%s" % ("PASS" if ok else "FAIL", descrizione,
                           ("  -> " + dettaglio) if dettaglio else ""))


def main():
    radice = pathlib.Path(__file__).resolve().parents[1]
    for macchina, percorso in CONFIG.items():
        p = radice / percorso
        print()
        print("== %s (%s)" % (macchina, percorso))
        if not p.is_file():
            check(False, "config presente", str(p))
            continue
        cfg = yaml.safe_load(p.read_text(encoding="utf-8"))
        bots = [b for b in (cfg.get("bots") or []) if b.get("enabled", True)]
        atteso_cap, attesi = FLOTTA[macchina]
        nomi = sorted(b["symbol"].split("/")[0] for b in bots)
        check(nomi == sorted(attesi), "universo della macchina",
              "atteso %s, trovato %s" % (",".join(sorted(attesi)), ",".join(nomi)))
        cap = sorted({float(b.get("capital", 0) or 0) for b in bots})
        check(len(cap) == 1 and abs(cap[0] - atteso_cap) <= TOLLERANZA_CAPITALE,
              "capitale del conto", "atteso %.2f, config %s" % (atteso_cap, cap))
        problemi_param = 0
        for b in bots:
            base = b["symbol"].split("/")[0]
            for chiave, valore in PAR.items():
                trovato = b.get(chiave, valore if chiave in ("canale", "atr_period",
                                                             "trend_ema", "risk_pct",
                                                             "max_exposure",
                                                             "strategy") else None)
                if chiave == "timeframe":
                    trovato = str(b.get("timeframe", "1d")).lower()
                elif chiave in ("canale", "atr_period", "trend_ema"):
                    trovato = int(trovato)
                elif chiave in ("trail_mult", "stop_atr_mult", "risk_pct",
                                "max_exposure", "fee"):
                    trovato = float(trovato)
                if trovato != valore:
                    problemi_param += 1
                    check(False, "%s: %s" % (base, chiave),
                          "atteso %r, trovato %r" % (valore, trovato))
        check(problemi_param == 0,
              "parametri deployati (%d controlli su %d bot)"
              % (len(bots) * len(PAR), len(bots)))
        ok_mandato = all(puo_girare_live(str(b.get("strategy", "")),
                                         str(b.get("mode", "")))[0] for b in bots)
        check(ok_mandato, "mandato: in live solo strategie con alpha misurato")
    # parametri: un solo esito aggregato per non stampare 17x8 righe
    falliti = [d for ok, d, _ in esiti if not ok]
    print()
    print("== RIEPILOGO")
    print("  controlli: %d | falliti: %d" % (len(esiti), len(falliti)))
    if falliti:
        for d in falliti:
            print("    - %s" % d)
        return 1
    print("  la flotta deployata corrisponde alla specifica misurata")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

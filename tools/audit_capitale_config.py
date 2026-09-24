#!/usr/bin/env python3
"""audit_capitale_config.py - il capitale per bot e' la QUOTA del conto o l'intero conto?

Problema (trovato il 2026-09-23 leggendo `config/node_*.yaml`): ogni bot di una
macchina dichiara `capital:` uguale al totale del sub-account. Con N bot, il
rischio per trade del 2% e' quindi il 2% dell'INTERO conto per OGNI bot: la
somma dei rischi diventa N x 2%, non 2%.

Effetto: su mc2 (7 bot) il rischio aggregato e' il 14% del conto, non il 2%.
La quota corretta e' `totale / N`.

Questo strumento e' di SOLA LETTURA: non scrive nulla in `config/` (che non e'
nel perimetro di [dsh]). Stampa la tabella e lo snippet YAML corretto, perche'
la patch la applica chi possiede quella cartella.

Uso:
    python tools/audit_capitale_config.py
    python tools/audit_capitale_config.py --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover
    print("serve pyyaml: pip install pyyaml", file=sys.stderr)
    raise SystemExit(2)

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"


def _cifra(x: float) -> str:
    return f"{x:.2f}"


def analizza(path: Path) -> dict:
    """Ritorna {macchina, bot, totale_implicito, quota, sovradichiarazione}."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    bots = [b for b in (doc.get("bots") or []) if isinstance(b, dict)]
    attivi = [b for b in bots if b.get("enabled", True)]
    capitali = [float(b.get("capital") or 0.0) for b in attivi]
    simboli = [str(b.get("symbol") or "?") for b in attivi]

    # Il totale del conto non e' dichiarato da nessuna parte: se tutti i bot
    # portano lo stesso valore, quel valore E' il totale del conto (ed e' anche
    # la sovradichiarazione). Se differiscono, il massimo e' la stima prudente.
    totale = max(capitali) if capitali else 0.0
    n = len(attivi)
    quota = totale / n if n else 0.0
    somma = sum(capitali)

    return {
        "file": path.name,
        "n_bot": n,
        "simboli": simboli,
        "capitali": capitali,
        "valori_distinti": sorted({round(c, 2) for c in capitali}),
        "totale_conto_stimato": round(totale, 2),
        "somma_dichiarata": round(somma, 2),
        "quota_corretta": round(quota, 2),
        "sovradichiarazione": round(somma / totale, 2) if totale else 0.0,
        "tutti_uguali": len({round(c, 2) for c in capitali}) == 1,
    }


def _tabella(righe: list[dict]) -> str:
    out = []
    out.append(f"{'config':<34}{'bot':>4}{'dichiarato':>12}{'conto stim.':>13}"
               f"{'quota giusta':>14}{'fattore':>9}")
    out.append("-" * 86)
    for r in righe:
        out.append(f"{r['file']:<34}{r['n_bot']:>4}{r['somma_dichiarata']:>12.2f}"
                   f"{r['totale_conto_stimato']:>13.2f}{r['quota_corretta']:>14.2f}"
                   f"{r['sovradichiarazione']:>8.1f}x")
    tot_dich = sum(r["somma_dichiarata"] for r in righe)
    tot_conto = sum(r["totale_conto_stimato"] for r in righe)
    tot_bot = sum(r["n_bot"] for r in righe)
    out.append("-" * 86)
    out.append(f"{'TOTALE':<34}{tot_bot:>4}{tot_dich:>12.2f}{tot_conto:>13.2f}"
               f"{(tot_conto / tot_bot if tot_bot else 0):>14.2f}"
               f"{(tot_dich / tot_conto if tot_conto else 0):>8.1f}x")
    return "\n".join(out)


def _rischio(righe: list[dict], risk_pct: float = 0.02) -> str:
    """Il punto vero: cosa diventa il rischio aggregato."""
    out = ["", "RISCHIO AGGREGATO (risk_pct = %.0f%% per bot)" % (risk_pct * 100)]
    for r in righe:
        n = r["n_bot"]
        out.append(
            f"  {r['file']:<34} dichiarato: {n} x {risk_pct:.0%} = "
            f"{n * risk_pct:.0%} del conto   ->   corretto: {risk_pct:.0%} del conto")
    return "\n".join(out)


def _snippet(righe: list[dict]) -> str:
    out = ["", "PATCH PROPOSTA (da applicare in config/, non lo fa questo strumento):"]
    for r in righe:
        out.append(f"  # {r['file']}: sostituire il valore di `capital:` in TUTTI "
                   f"i {r['n_bot']} bot con {_cifra(r['quota_corretta'])} "
                   f"(= {_cifra(r['totale_conto_stimato'])} / {r['n_bot']})")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", action="store_true", help="output machine-readable")
    ap.add_argument("--config-dir", default=str(CONFIG_DIR))
    args = ap.parse_args()

    cdir = Path(args.config_dir)
    files = sorted(cdir.glob("node_*.yaml"))
    if not files:
        print(f"nessun config node_*.yaml in {cdir}", file=sys.stderr)
        return 1

    righe = [analizza(p) for p in files]

    if args.json:
        print(json.dumps(righe, indent=2, ensure_ascii=False))
    else:
        print(_tabella(righe))
        print(_rischio(righe))
        print(_snippet(righe))
        problemi = [r for r in righe if r["tutti_uguali"] and r["n_bot"] > 1]
        print()
        if problemi:
            print(f"ESITO: {len(problemi)} config su {len(righe)} sovradichiarano "
                  f"il capitale. Ogni bot rischia la percentuale dell'intero conto.")
            return 1
        print("ESITO: nessuna sovradichiarazione rilevata.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

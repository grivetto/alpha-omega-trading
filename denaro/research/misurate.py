#!/usr/bin/env python3
"""Quali strategie hanno un alpha MISURATO e possono girare in LIVE.

Il mandato del progetto e' "deploy solo di edge misurato e robusto". Questo
modulo e' quel mandato in forma eseguibile: il Node consulta `puo_girare_live`
prima di costruire un bot, e in modalita' live rifiuta tutto cio' che non ha una
misura alle spalle.

Censimento del 2026-09-17 (`tools/strategie_censimento.py`, fee taker reale
0.35%/lato dello spot OKX EEA, 17 asset della flotta, 5 finestre):

  trend     storia +13.08%, positiva in 5/5 finestre   -> DEPLOYABILE
  pullback  storia  -4.19%, positiva in 3/5 finestre   -> solo ricerca
  grid      -58.08%  -43.67%  -50.75%  -26.26%   -4.67% -> 0/5, ELIMINATA
  momentum  -78.89%  -56.73%  -37.73%  -35.19%  -21.40% -> 0/5, ELIMINATA
  meanrev     0 trade con i default: motore morto      -> ELIMINATA

Le eliminazioni non sono un'opinione: grid e momentum fanno 743 e 2328 giri sui
17 asset in 2.4 anni, e a 0.70% di round trip la fee da sola vale molte volte il
capitale. Il segnale puo' anche esistere, ma su spot a fee taker e' il costo a
decidere il risultato (docs/17, docs/31).
"""
from __future__ import annotations

from typing import Dict, Tuple

RIFERIMENTO = "docs/31_censimento_strategie_2026-09-17.md"

# strategia -> note della misura che la giustifica
MISURATE: Dict[str, str] = {
    "trend": "storia +13.08%, positiva in 5/5 finestre (17 asset, fee 0.35%)",
}

# strategie con alpha misurato NEGATIVO: eliminate
ELIMINATE: Dict[str, str] = {
    "grid": "storia -58.08%, 0/5 finestre positive (743 giri)",
    "momentum": "storia -78.89%, 0/5 finestre positive (2328 giri)",
    "meanrev": "0 trade con i default: nessun alpha misurabile",
}

# policy presenti nel dominio ma SENZA motore di backtest: non deployabili
NON_MISURATE = (
    "adaptive", "adaptive_vol_grid", "irmr", "vagr", "mincapture_grid",
    "flowgate_grid", "cycle_phase_grid", "asymvol_anchor", "circular",
    "pullback",
)

MODALITA_PAPER = ("paper",)


def puo_girare_live(strategia: str, modalita: str) -> Tuple[bool, str]:
    """(ammessa, motivo). In paper tutto e' ammesso: e' il banco di prova."""
    strat = (strategia or "").strip().lower()
    modo = (modalita or "paper").strip().lower()
    if modo in MODALITA_PAPER:
        return True, ""
    if strat in MISURATE:
        return True, ""
    if strat in ELIMINATE:
        return False, ("strategia %s ELIMINATA dal censimento alpha del "
                       "2026-09-17 (%s: %s): in live non parte"
                       % (strat, RIFERIMENTO, ELIMINATE[strat]))
    if strat in NON_MISURATE:
        return False, ("strategia %s NON MISURATA: nessun motore di backtest in "
                       "denaro/research/eval.py, quindi nessun edge da "
                       "difendere (%s)" % (strat, RIFERIMENTO))
    return False, ("strategia %s sconosciuta al registro delle misure (%s): in "
                   "live non parte" % (strat, RIFERIMENTO))

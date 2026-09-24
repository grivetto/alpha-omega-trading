#!/usr/bin/env python3
"""Denaro — stato di FINANZIAMENTO del conto (difetto A, P0).

PERCHE' ESISTE (difetto osservato in produzione): il nodo live su nuvola
(`denaro-node-nuvola-trade.service`, 6 bot trend su OKX) girava da ore senza
piazzare NULLA. Il conto conteneva 0,0003 EUR di dust, la config dichiarava
`capital: 24.83` per bot, e `BotTask._guard_equity` classifica OGNI lettura
fuori dal range [5%, 30x] del capitale come "inattendibile". Il journal
ripeteva ogni 30 secondi, per tutti e 6 i bot:

    [WARNING] denaro.bot: equity inattendibile 0.0003 per LINK/EUR:
              tick saltato (nessun valore sostitutivo)

Nessuna transizione di stato, nessun allarme, nessuna traccia di "il conto non
e' finanziato". Due situazioni DIVERSE erano collassate in un unico ramo:

- **non finanziato**: il conto non ha denaro sufficiente nemmeno a rispettare
  il minimo d'ordine dell'exchange. E' uno stato OPERATIVO stabile: va
  dichiarato UNA volta, esposto in health, e ricalcolato quando il saldo
  cambia (se arrivano fondi si esce da soli, senza restart);
- **illeggibile**: la lettura del saldo e' fallita o e' incoerente. E' un
  guasto TRANSITORIO: si salta il tick e si riprova.

Questo modulo e' PURO: nessun I/O, nessuna rete, nessuna conoscenza
dell'exchange, quindi si testa in millisecondi. La soglia operativa gliela
porta il chiamante, che legge il `min_notional` REALE dall'adapter; qui si
decide solo lo stato e lo si motiva.

Contratto:
- `classifica_capitale(...) -> ClassificazioneCapitale` (mai eccezioni: input
  sporchi diventano `illeggibile`, non un crash del tick);
- `ok` e `sottocapitalizzato` possono operare, `non_finanziato` e `illeggibile`
  no (`puo_operare` / `blocca_tick`);
- `capitale_reale` non viene mai inventato: se la lettura non produce un numero
  finito e non negativo, il campo resta `None` e lo stato e' `illeggibile`.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

# --- stati -------------------------------------------------------------------
# Stringhe, non Enum: finiscono in health JSON, nel journal e nei log, e devono
# restare leggibili da Zabbix/dashboard senza un decoder.

STATO_OK: str = "ok"
STATO_SOTTOCAPITALIZZATO: str = "sottocapitalizzato"
STATO_NON_FINANZIATO: str = "non_finanziato"
STATO_ILLEGGIBILE: str = "illeggibile"

STATI: tuple = (STATO_OK, STATO_SOTTOCAPITALIZZATO, STATO_NON_FINANZIATO,
                STATO_ILLEGGIBILE)

# --- soglia operativa --------------------------------------------------------

# Default PRUDENTE, usato solo quando ne' l'adapter ne' la config sanno dire il
# minimo d'ordine. 1 EUR e' l'ordine di grandezza dei minimi reali delle coppie
# /EUR usate da questa flotta (le config di produzione dichiarano
# `min_notional: 1.0` per ogni bot live). Non e' un numero magico nascosto:
# l'origine della soglia finisce in health (`capitale_soglia_origine`).
SOGLIA_OPERATIVA_DEFAULT: float = 1.0

ORIGINE_EXCHANGE: str = "exchange"   # min_notional(symbol) dell'adapter
ORIGINE_CONFIG: str = "config"       # min_notional dichiarato nella config del bot
ORIGINE_DEFAULT: str = "default"     # fallback prudente, dichiarato

# Sotto questa frazione del capitale CONFIGURATO il bot non puo' dispiegare il
# sizing che dichiara (la griglia e' dimensionata sul capitale di config):
# 25% = meno di un livello pieno su una griglia a 4 livelli, o meta' del rischio
# per trade che il trend calcola sul capitale dichiarato. E' un avviso, non un
# blocco: il bot riduce da solo (`risk_sized_capital`) e continua a gestire.
FRAZIONE_OPERATIVA_DEFAULT: float = 0.25


def _numero_finito(x) -> Optional[float]:
    """`float(x)` se e' un numero finito, altrimenti None (mai eccezioni).

    NaN e inf NON sono letture: sono l'assenza di una lettura. Vanno trattati
    come `illeggibile`, non come "saldo basso".
    """
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def risolvi_soglia(min_notional_exchange: Optional[float] = None,
                   min_notional_config: Optional[float] = None,
                   default: float = SOGLIA_OPERATIVA_DEFAULT) -> "tuple[float, str]":
    """(soglia minima operativa, origine) — la soglia NON si inventa.

    Ordine di fiducia:
    1. `min_notional(symbol)` dell'adapter (`ORIGINE_EXCHANGE`): e' il vincolo
       VERO della sede, quello che fa rifiutare l'ordine con "order value below
       minimum";
    2. `min_notional` dichiarato nella config del bot (`ORIGINE_CONFIG`): stessa
       grandezza, scritta a mano, usata quando l'adapter non sa rispondere
       (markets non caricate, venue senza filtro `cost.min`);
    3. default prudente (`ORIGINE_DEFAULT`), dichiarato e visibile in health.

    Un valore <= 0 significa "non disponibile" e non viene mai usato come
    soglia: una soglia 0 classificherebbe come finanziato anche un conto a zero.
    """
    for valore, origine in ((min_notional_exchange, ORIGINE_EXCHANGE),
                            (min_notional_config, ORIGINE_CONFIG)):
        v = _numero_finito(valore)
        if v is not None and v > 0:
            return v, origine
    d = _numero_finito(default)
    if d is None or d <= 0:
        d = SOGLIA_OPERATIVA_DEFAULT
    return d, ORIGINE_DEFAULT


@dataclass(frozen=True)
class ClassificazioneCapitale:
    """Esito della classificazione: stato + i numeri che lo giustificano.

    Immutabile: e' una fotografia del tick, non uno stato mutabile che qualcuno
    puo' alterare a meta' ciclo.
    """

    stato: str
    capitale_configurato: float
    capitale_reale: Optional[float]
    soglia_operativa: float
    origine_soglia: str = ORIGINE_DEFAULT
    motivo: str = ""

    # --- semantica operativa ------------------------------------------------

    @property
    def puo_operare(self) -> bool:
        """True se il bot puo' piazzare ordini.

        `sottocapitalizzato` puo' operare: il capitale c'e' (sopra il minimo
        d'ordine), e' solo sotto il sizing dichiarato — e il bot riduce da solo
        (`RiskManager.risk_sized_capital`). Bloccare anche questo stato
        immobilizzerebbe un conto che puo' ancora gestire e chiudere posizioni.
        """
        return self.stato in (STATO_OK, STATO_SOTTOCAPITALIZZATO)

    @property
    def blocca_tick(self) -> bool:
        """True se il tick va saltato (nessun ordine, nessuna baseline)."""
        return not self.puo_operare

    @property
    def non_finanziato(self) -> bool:
        """Scorciatoia per il ramo rumoroso del tick (difetto A)."""
        return self.stato == STATO_NON_FINANZIATO

    # --- serializzazione ----------------------------------------------------

    def messaggio(self) -> str:
        """Una riga autoportante per `_last_error`/health (mai un numero nudo)."""
        if self.stato == STATO_NON_FINANZIATO:
            return (f"NON FINANZIATO: capitale reale "
                    f"{self.capitale_reale:.4f} EUR < soglia operativa "
                    f"{self.soglia_operativa:.4f} EUR (configurato "
                    f"{self.capitale_configurato:.2f})")
        if self.stato == STATO_ILLEGGIBILE:
            return ("capitale ILLEGGIBILE: saldo non leggibile o incoerente "
                    f"(configurato {self.capitale_configurato:.2f}, "
                    f"soglia operativa {self.soglia_operativa:.4f})")
        if self.stato == STATO_SOTTOCAPITALIZZATO:
            return (f"SOTTOCAPITALIZZATO: capitale reale "
                    f"{self.capitale_reale:.4f} EUR < "
                    f"{FRAZIONE_OPERATIVA_DEFAULT:.0%} del configurato "
                    f"{self.capitale_configurato:.2f}")
        return (f"capitale ok: {self.capitale_reale:.4f} EUR (soglia operativa "
                f"{self.soglia_operativa:.4f} EUR, origine {self.origine_soglia})")

    def to_dict(self) -> dict:
        """Campi di health: ESPLICITI, come richiesto dal difetto A.

        `capitale_reale` puo' essere None (illeggibile): si dichiara l'ignoto
        invece di mettere uno zero che verrebbe letto come "conto vuoto".
        """
        return {
            "capitale_stato": self.stato,
            "capitale_reale": (None if self.capitale_reale is None
                               else round(self.capitale_reale, 4)),
            "capitale_configurato": round(self.capitale_configurato, 4),
            "capitale_soglia_operativa": round(self.soglia_operativa, 4),
            "capitale_soglia_origine": self.origine_soglia,
            "capitale_motivo": self.motivo,
        }


def classifica_capitale(capitale_configurato: float,
                        capitale_reale: Optional[float],
                        soglia_operativa: Optional[float] = None,
                        origine_soglia: str = ORIGINE_DEFAULT,
                        frazione_operativa: float = FRAZIONE_OPERATIVA_DEFAULT,
                        ) -> ClassificazioneCapitale:
    """Classifica il finanziamento del conto in uno dei quattro stati.

    Regole, in ordine:
    1. `capitale_reale` non e' un numero finito e non negativo → `illeggibile`
       (lettura fallita o incoerente: caso TRANSITORIO, si salta il tick);
    2. `capitale_reale < soglia_operativa` → `non_finanziato`: sotto questa
       soglia un ordine non puo' nemmeno rispettare il minimo dell'exchange,
       quindi il bot non puo' fare NULLA di utile — ed e' esattamente la
       situazione del conto a 0,0003 EUR con `capital: 24.83`;
    3. `capitale_reale < capitale_configurato * frazione_operativa` →
       `sottocapitalizzato`: si puo' ordinare, ma non col sizing dichiarato;
    4. altrimenti `ok`.

    NB su 0.0: uno ZERO che arriva da una lettura RIUSCITA e' un conto vuoto →
    `non_finanziato`. Una lettura FALLITA non produce un numero: produce None o
    un'eccezione, che qui e' `illeggibile`. La distinzione e' voluta: e' il
    cuore del difetto A.
    """
    configurato = _numero_finito(capitale_configurato)
    configurato = 0.0 if configurato is None else max(0.0, configurato)

    soglia = _numero_finito(soglia_operativa)
    if soglia is None or soglia <= 0:
        soglia = SOGLIA_OPERATIVA_DEFAULT
        origine_soglia = ORIGINE_DEFAULT

    reale = _numero_finito(capitale_reale)
    if reale is None or reale < 0:
        return ClassificazioneCapitale(
            stato=STATO_ILLEGGIBILE, capitale_configurato=configurato,
            capitale_reale=None, soglia_operativa=soglia,
            origine_soglia=origine_soglia,
            motivo="saldo non leggibile o incoerente (None/NaN/negativo)")

    if reale < soglia:
        return ClassificazioneCapitale(
            stato=STATO_NON_FINANZIATO, capitale_configurato=configurato,
            capitale_reale=reale, soglia_operativa=soglia,
            origine_soglia=origine_soglia,
            motivo=(f"{reale:.4f} EUR sotto la soglia operativa "
                    f"{soglia:.4f} EUR (origine {origine_soglia}): nessun "
                    f"ordine puo' rispettare il minimo dell'exchange"))

    frazione = _numero_finito(frazione_operativa)
    frazione = (FRAZIONE_OPERATIVA_DEFAULT if frazione is None
                else max(0.0, frazione))
    if configurato > 0 and reale < configurato * frazione:
        return ClassificazioneCapitale(
            stato=STATO_SOTTOCAPITALIZZATO, capitale_configurato=configurato,
            capitale_reale=reale, soglia_operativa=soglia,
            origine_soglia=origine_soglia,
            motivo=(f"{reale:.4f} EUR < {frazione:.0%} del capitale "
                    f"configurato {configurato:.2f} EUR: si opera con sizing "
                    f"ridotto, non con quello dichiarato"))

    return ClassificazioneCapitale(
        stato=STATO_OK, capitale_configurato=configurato, capitale_reale=reale,
        soglia_operativa=soglia, origine_soglia=origine_soglia,
        motivo=f"{reale:.4f} EUR >= soglia operativa {soglia:.4f} EUR")

# ruff: noqa: TRY004  # REQ F2: ogni violazione di input, anche di tipo, -> ValueError
"""Carry Fase 2 — pianificatore multi-coppia (modulo PURO, nessun I/O).

Spec: ``docs/63_carry_fase2_impl_2026-10-03.md`` (REQ-20261002-234000-F2CARRY).
Esecutore di riferimento (fase 1, singola coppia): ``carry/canary_carry.py``.

Garanzie
--------
* solo ``stdlib``: nessun import di ``ccxt``/rete/socket/chiavi e nessun I/O;
* funzioni pure + dataclass ``frozen``: stessi input -> stessi output;
* input malformati (non numerici, non finiti, non positivi, NaN) -> ``ValueError``;
* i rifiuti di sizing/budget NON sono eccezioni: sono piani con
  ``operabile=False`` e ``motivo`` valorizzato, con le quantita' azzerate.
  Non si clampa MAI un piano per farlo entrare: si rifiuta e si motiva.

Convenzioni
-----------
* coppia = spot-long + X-Perp-short 1x isolated;
* ``contratti`` = contratti del X-Perp; ``spot_qty`` = unita' base sullo spot;
* ``ct_val`` = unita' base per contratto; i valori monetari sono in valuta di
  quotazione (USDC).

Regole numeriche applicate (dichiarate, non negoziabili)
--------------------------------------------------------
1. ``contratti`` sono quantizzati a ``ct_step`` per difetto (floor): il
   nozionale perp non supera mai il target richiesto.
2. ``spot_qty = contratti * ct_val`` arrotondata a ``spot_step`` per eccesso,
   cosi' il delta residuo e' sempre >= 0 (nessun output negativo) e mai sotto
   ``spot_min``.
3. ``contratti < min_ct`` oppure ``costo > budget`` -> coppia rifiutata con
   motivo; il nozionale non viene ridotto per rientrare.
4. Delta atteso ~ 0; tolleranza = 1 ct equivalente (``ct_val`` unita' base sullo
   spot, 1 contratto sul perp). Oltre tolleranza il piano viene rifiutato.
5. L'apertura e' in sequenza sull'ordine ricevuto (payback crescente); quando il
   capitale non basta piu' il pianificatore si ferma e motiva le coppie residue.
"""

from __future__ import annotations

import math
import numbers
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

__all__ = [
    "AzioneChiusura",
    "Diff",
    "InstrumentSpec",
    "PairPlan",
    "PortafoglioPlan",
    "StatoCoppia",
    "calcola_delta",
    "entro_tolleranza",
    "pianifica_chiusura",
    "pianifica_coppia",
    "pianifica_portafoglio",
    "riconcilia",
    "riepilogo",
    "verdetto_riconciliazione",
]

_EPS_REL = 1e-9
_EPS_MONETA = 1e-9


# --------------------------------------------------------------------------- #
# validatori interni (nessun I/O)
# --------------------------------------------------------------------------- #
def _e_numero(x) -> bool:
    """True se x e' un numero reale e non un bool (True/False non sono importi)."""
    return isinstance(x, numbers.Real) and not isinstance(x, bool)


def _valida_finito(valore, nome: str) -> float:
    if not _e_numero(valore):
        raise ValueError(f"{nome} deve essere un numero, ricevuto {type(valore).__name__}")
    v = float(valore)
    if not math.isfinite(v):
        raise ValueError(f"{nome} non finito: {valore!r}")
    return v


def _valida_positivo(valore, nome: str) -> float:
    v = _valida_finito(valore, nome)
    if v <= 0.0:
        raise ValueError(f"{nome} deve essere > 0, ricevuto {v!r}")
    return v


def _valida_non_negativo(valore, nome: str) -> float:
    v = _valida_finito(valore, nome)
    if v < 0.0:
        raise ValueError(f"{nome} deve essere >= 0, ricevuto {v!r}")
    return v


def _pulisci(x) -> float:
    """Toglie la polvere floating-point dalle uscite (determinismo sui confronti)."""
    return round(float(x), 12)


def _multiplo(a: float, b: float) -> bool:
    k = a / b
    return abs(k - round(k)) <= _EPS_REL * max(1.0, abs(k))


def _chiudi(a: float, b: float) -> bool:
    return abs(a - b) <= _EPS_REL * max(1.0, abs(a), abs(b))


def _floor_step(valore: float, step: float) -> float:
    """Quantizza per difetto a un multiplo di step (mai sopra il valore dato)."""
    q = valore / step
    n = math.floor(q + _EPS_REL * max(1.0, abs(q)))
    return _pulisci(n * step)


def _ceil_step(valore: float, step: float) -> float:
    """Quantizza per eccesso a un multiplo di step (mai sotto il valore dato)."""
    q = valore / step
    n = math.ceil(q - _EPS_REL * max(1.0, abs(q)))
    return _pulisci(n * step)


# --------------------------------------------------------------------------- #
# modello dati
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class InstrumentSpec:
    """Specifica statica di una coppia spot/X-Perp.

    ``ct_val``  unita' base per contratto perp.
    ``min_ct``  contratti minimi negoziabili (multiplo di ``ct_step``).
    ``ct_step`` passo dei contratti.
    ``spot_min``/``spot_step``  minimo e passo dello spot (unita' base).
    """

    base: str
    ct_val: float
    min_ct: float
    ct_step: float
    spot_min: float
    spot_step: float

    def __post_init__(self) -> None:
        if not isinstance(self.base, str) or not self.base.strip():
            raise ValueError("InstrumentSpec.base deve essere una stringa non vuota")
        object.__setattr__(self, "base", self.base.strip())
        ct_val = _valida_positivo(self.ct_val, "ct_val")
        min_ct = _valida_positivo(self.min_ct, "min_ct")
        ct_step = _valida_positivo(self.ct_step, "ct_step")
        spot_min = _valida_positivo(self.spot_min, "spot_min")
        spot_step = _valida_positivo(self.spot_step, "spot_step")
        object.__setattr__(self, "ct_val", ct_val)
        object.__setattr__(self, "min_ct", min_ct)
        object.__setattr__(self, "ct_step", ct_step)
        object.__setattr__(self, "spot_min", spot_min)
        object.__setattr__(self, "spot_step", spot_step)
        if not _multiplo(min_ct, ct_step):
            raise ValueError(
                f"ct_step violato per {self.base}: min_ct={min_ct:g} non e' multiplo di ct_step={ct_step:g}"
            )
        if not _multiplo(spot_min, spot_step):
            raise ValueError(
                f"spot_step violato per {self.base}: spot_min={spot_min:g} non e' multiplo di spot_step={spot_step:g}"
            )


@dataclass(frozen=True)
class PairPlan:
    """Piano di una singola coppia (operabile o rifiutato con motivo).

    Un piano rifiutato ha ``operabile=False``, ``motivo`` non vuoto e TUTTE le
    quantita'/importi a 0: non e' eseguibile per costruzione.
    """

    base: str
    contratti: float
    spot_qty: float
    nozionale_stimato: float
    costo_spot: float
    margine_stimato: float
    delta_residuo: float
    prezzo_spot: float = 0.0
    prezzo_perp: float = 0.0
    operabile: bool = True
    motivo: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.base, str) or not self.base.strip():
            raise ValueError("PairPlan.base deve essere una stringa non vuota")
        object.__setattr__(self, "base", self.base.strip())
        for nome in (
            "contratti",
            "spot_qty",
            "nozionale_stimato",
            "costo_spot",
            "margine_stimato",
            "delta_residuo",
            "prezzo_spot",
            "prezzo_perp",
        ):
            object.__setattr__(self, nome, _valida_non_negativo(getattr(self, nome), nome))
        if not isinstance(self.operabile, bool):
            raise ValueError("PairPlan.operabile deve essere bool")
        if not isinstance(self.motivo, str):
            raise ValueError("PairPlan.motivo deve essere una stringa")
        if self.operabile:
            if self.motivo:
                raise ValueError("piano operabile: motivo deve essere vuoto")
            if self.contratti > 0.0 and self.prezzo_perp <= 0.0:
                raise ValueError("piano operabile: prezzo_perp mancante")
            if self.spot_qty > 0.0 and self.prezzo_spot <= 0.0:
                raise ValueError("piano operabile: prezzo_spot mancante")
        else:
            if self.contratti != 0.0 or self.spot_qty != 0.0:
                raise ValueError("piano rifiutato: contratti e spot_qty devono essere 0")
            if not self.motivo:
                raise ValueError("piano rifiutato: motivo obbligatorio")


@dataclass(frozen=True)
class PortafoglioPlan:
    """Esito della pianificazione multi-coppia.

    ``piani``    solo le coppie operabili, nell'ordine di apertura.
    ``scartate`` coppie rifiutate come tuple ``(base, motivo)``.
    ``note``     annotazioni operative (es. stop per capitale esaurito).
    """

    piani: tuple
    scartate: tuple
    commit_totale: float
    note: tuple = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "piani", tuple(self.piani))
        object.__setattr__(self, "scartate", tuple(tuple(s) for s in self.scartate))
        object.__setattr__(self, "note", tuple(self.note))
        for piano in self.piani:
            if not isinstance(piano, PairPlan) or not piano.operabile:
                raise ValueError("PortafoglioPlan.piani deve contenere solo PairPlan operabili")
        for voce in self.scartate:
            if len(voce) != 2 or not all(isinstance(x, str) for x in voce):
                raise ValueError("PortafoglioPlan.scartate deve contenere tuple (base, motivo)")
        object.__setattr__(self, "commit_totale", _valida_non_negativo(self.commit_totale, "commit_totale"))


@dataclass(frozen=True)
class StatoCoppia:
    """Istantanea di una coppia: quantita' spot, contratti perp, ``ct_val`` e prezzi."""

    base: str
    spot_qty: float
    contratti: float
    ct_val: float
    prezzo_spot: float = 0.0
    prezzo_perp: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.base, str) or not self.base.strip():
            raise ValueError("StatoCoppia.base deve essere una stringa non vuota")
        object.__setattr__(self, "base", self.base.strip())
        object.__setattr__(self, "spot_qty", _valida_non_negativo(self.spot_qty, "spot_qty"))
        object.__setattr__(self, "contratti", _valida_non_negativo(self.contratti, "contratti"))
        object.__setattr__(self, "ct_val", _valida_positivo(self.ct_val, "ct_val"))
        object.__setattr__(self, "prezzo_spot", _valida_non_negativo(self.prezzo_spot, "prezzo_spot"))
        object.__setattr__(self, "prezzo_perp", _valida_non_negativo(self.prezzo_perp, "prezzo_perp"))


@dataclass(frozen=True)
class Diff:
    """Scostamento rilevato in riconciliazione su un campo (spot o contratti)."""

    base: str
    campo: str
    atteso: float
    rilevato: float
    delta: float
    ok: bool

    def __post_init__(self) -> None:
        if self.campo not in ("spot", "contratti"):
            raise ValueError(f"Diff.campo non valido: {self.campo!r}")
        if not isinstance(self.ok, bool):
            raise ValueError("Diff.ok deve essere bool")


@dataclass(frozen=True)
class AzioneChiusura:
    """Azione di chiusura atomica: perp reduceOnly (buy) oppure spot sell."""

    base: str
    mercato: str
    lato: str
    quantita: float
    reduce_only: bool

    def __post_init__(self) -> None:
        if not isinstance(self.base, str) or not self.base.strip():
            raise ValueError("AzioneChiusura.base deve essere una stringa non vuota")
        object.__setattr__(self, "base", self.base.strip())
        object.__setattr__(self, "quantita", _valida_positivo(self.quantita, "quantita"))
        if not isinstance(self.reduce_only, bool):
            raise ValueError("AzioneChiusura.reduce_only deve essere bool")
        if self.mercato == "perp":
            if self.lato != "buy" or not self.reduce_only:
                raise ValueError("chiusura perp: atteso lato 'buy' e reduce_only=True")
        elif self.mercato == "spot":
            if self.lato != "sell" or self.reduce_only:
                raise ValueError("chiusura spot: atteso lato 'sell' e reduce_only=False")
        else:
            raise ValueError(f"AzioneChiusura.mercato non valido: {self.mercato!r}")


# --------------------------------------------------------------------------- #
# sizing
# --------------------------------------------------------------------------- #
def calcola_delta(spot_qty: float, contratti: float, ct_val: float) -> float:
    """Delta residuo in unita' base: ``spot_qty - contratti * ct_val``.

    Puo' essere negativo solo se chiamato a mano con input incoerenti; il
    pianificatore produce sempre delta >= 0 (spot arrotondato per eccesso).
    """
    s = _valida_non_negativo(spot_qty, "spot_qty")
    c = _valida_non_negativo(contratti, "contratti")
    cv = _valida_positivo(ct_val, "ct_val")
    return _pulisci(s - c * cv)


def entro_tolleranza(delta: float, ct_val: float, tolleranza_ct: float = 1.0) -> bool:
    """True se ``|delta| <= tolleranza_ct`` contratti equivalenti (bordo incluso)."""
    d = _valida_finito(delta, "delta")
    cv = _valida_positivo(ct_val, "ct_val")
    tc = _valida_positivo(tolleranza_ct, "tolleranza_ct")
    limite = tc * cv
    return abs(d) <= limite + _EPS_REL * max(1.0, abs(limite))


def _rifiuta(spec: InstrumentSpec, motivo: str, prezzo_spot: float, prezzo_perp: float) -> PairPlan:
    return PairPlan(
        base=spec.base,
        contratti=0.0,
        spot_qty=0.0,
        nozionale_stimato=0.0,
        costo_spot=0.0,
        margine_stimato=0.0,
        delta_residuo=0.0,
        prezzo_spot=prezzo_spot,
        prezzo_perp=prezzo_perp,
        operabile=False,
        motivo=motivo,
    )


def pianifica_coppia(
    spec: InstrumentSpec,
    nozionale_target: float,
    prezzo_spot: float,
    prezzo_perp: float,
    *,
    capitale_disponibile: float | None = None,
) -> PairPlan:
    """Piano deterministico per una coppia (spot-long + X-Perp-short 1x isolated).

    Quantizza i contratti a ``ct_step`` per difetto e lo spot a ``spot_step``
    per eccesso. Rifiuta con motivo (senza clampare) se: sotto ``min_ct``,
    sotto ``spot_min``, delta oltre 1 ct, oppure costo (spot + margine) oltre
    ``capitale_disponibile`` quando fornito.
    """
    if not isinstance(spec, InstrumentSpec):
        raise ValueError("spec deve essere un InstrumentSpec")
    target = _valida_positivo(nozionale_target, "nozionale_target")
    p_spot = _valida_positivo(prezzo_spot, "prezzo_spot")
    p_perp = _valida_positivo(prezzo_perp, "prezzo_perp")
    capitale = None
    if capitale_disponibile is not None:
        capitale = _valida_positivo(capitale_disponibile, "capitale_disponibile")

    valore_contratto = spec.ct_val * p_perp
    contratti = _floor_step(target / valore_contratto, spec.ct_step)

    if contratti < spec.min_ct and not _chiudi(contratti, spec.min_ct):
        return _rifiuta(
            spec,
            f"sotto minimo strumento: {contratti:g} ct < min_ct {spec.min_ct:g} ct (target {target:g} troppo piccolo)",
            p_spot,
            p_perp,
        )

    spot_raw = _pulisci(contratti * spec.ct_val)
    spot_qty = _ceil_step(spot_raw, spec.spot_step)
    if spot_qty < spec.spot_min and not _chiudi(spot_qty, spec.spot_min):
        return _rifiuta(
            spec,
            f"spot sotto minimo: {spot_qty:g} < spot_min {spec.spot_min:g}",
            p_spot,
            p_perp,
        )

    delta = _pulisci(spot_qty - spot_raw)
    if not entro_tolleranza(delta, spec.ct_val, 1.0):
        return _rifiuta(
            spec,
            f"delta oltre tolleranza 1 ct: {delta:g} (spot_step {spec.spot_step:g} "
            f"troppo grosso rispetto a ct_val {spec.ct_val:g})",
            p_spot,
            p_perp,
        )

    nozionale = _pulisci(spot_raw * p_perp)
    costo_spot = _pulisci(spot_qty * p_spot)
    margine = _pulisci(spot_raw * p_perp)  # 1x isolated: margine = nozionale perp
    if capitale is not None and _pulisci(costo_spot + margine) > capitale + _EPS_MONETA:
        return _rifiuta(
            spec,
            f"costo oltre capitale: serve {_pulisci(costo_spot + margine):.8g}, disponibile {capitale:.8g}",
            p_spot,
            p_perp,
        )

    return PairPlan(
        base=spec.base,
        contratti=contratti,
        spot_qty=spot_qty,
        nozionale_stimato=nozionale,
        costo_spot=costo_spot,
        margine_stimato=margine,
        delta_residuo=delta,
        prezzo_spot=p_spot,
        prezzo_perp=p_perp,
    )


def _target_per_base(base: str, nozionale_per_coppia) -> float:
    if _e_numero(nozionale_per_coppia):
        return _valida_positivo(nozionale_per_coppia, "nozionale_per_coppia")
    if isinstance(nozionale_per_coppia, Mapping):
        if base not in nozionale_per_coppia:
            raise ValueError(f"nozionale_per_coppia: manca il target per {base}")
        return _valida_positivo(nozionale_per_coppia[base], f"nozionale_per_coppia[{base}]")
    raise ValueError("nozionale_per_coppia deve essere un numero oppure una mappa base -> target")


def _prezzi_per_base(base: str, prezzi: Mapping) -> tuple[float, float]:
    if not isinstance(prezzi, Mapping):
        raise ValueError("prezzi deve essere una mappa base -> (prezzo_spot, prezzo_perp)")
    if base not in prezzi:
        raise ValueError(f"prezzi: manca il prezzo per {base}")
    voce = prezzi[base]
    if isinstance(voce, Mapping):
        if "spot" not in voce or "perp" not in voce:
            raise ValueError(f"prezzi[{base}]: attesi i campi 'spot' e 'perp'")
        return voce["spot"], voce["perp"]
    if isinstance(voce, (str, bytes)):
        raise ValueError(f"prezzi[{base}]: attesa coppia (spot, perp), ricevuto testo")
    try:
        valori = tuple(voce)
    except TypeError as exc:
        raise ValueError(f"prezzi[{base}]: attesa coppia (spot, perp)") from exc
    if len(valori) != 2:
        raise ValueError(f"prezzi[{base}]: attesi 2 valori (spot, perp), ricevuti {len(valori)}")
    return valori[0], valori[1]


def pianifica_portafoglio(
    specs_ordinate: Iterable[InstrumentSpec],
    capitale_commit: float,
    nozionale_per_coppia,
    prezzi: Mapping,
) -> PortafoglioPlan:
    """Pianifica N coppie in sequenza, senza mai eccedere ``capitale_commit``.

    ``specs_ordinate`` e' l'ordine di apertura (payback crescente). Per ogni
    coppia il commit e' ``costo_spot + margine_stimato`` (~2x nozionale). I
    rifiuti di sizing finiscono in ``scartate`` con motivo; al primo commit che
    non entra, la pianificazione si FERMA e le coppie residue sono marcate.
    """
    capitale = _valida_positivo(capitale_commit, "capitale_commit")
    specs = tuple(specs_ordinate)
    for spec in specs:
        if not isinstance(spec, InstrumentSpec):
            raise ValueError("specs_ordinate deve contenere solo InstrumentSpec")
    if not (isinstance(nozionale_per_coppia, Mapping) or _e_numero(nozionale_per_coppia)):
        raise ValueError("nozionale_per_coppia deve essere un numero oppure una mappa base -> target")
    if not isinstance(prezzi, Mapping):
        raise ValueError("prezzi deve essere una mappa base -> (prezzo_spot, prezzo_perp)")

    piani: list[PairPlan] = []
    scartate: list[tuple[str, str]] = []
    note: list[str] = []
    residuo = capitale
    fermato = False

    for spec in specs:
        if fermato:
            scartate.append((spec.base, "capitale esaurito: pianificazione fermata in sequenza"))
            continue
        target = _target_per_base(spec.base, nozionale_per_coppia)
        p_spot, p_perp = _prezzi_per_base(spec.base, prezzi)
        piano = pianifica_coppia(spec, target, p_spot, p_perp)
        if not piano.operabile:
            scartate.append((spec.base, piano.motivo))
            continue
        commit = _pulisci(piano.costo_spot + piano.margine_stimato)
        if commit > residuo + _EPS_MONETA:
            scartate.append((spec.base, f"capitale insufficiente: serve {commit:.8g}, residuo {residuo:.8g}"))
            fermato = True
            continue
        residuo = _pulisci(residuo - commit)
        piani.append(piano)

    if not piani and scartate:
        note.append("nessuna coppia pianificata")
    if fermato:
        note.append("stop in sequenza: capitale esaurito (nessun clamp di nozionale)")

    commit_totale = _pulisci(sum(p.costo_spot + p.margine_stimato for p in piani))
    return PortafoglioPlan(
        piani=tuple(piani),
        scartate=tuple(scartate),
        commit_totale=commit_totale,
        note=tuple(note),
    )


# --------------------------------------------------------------------------- #
# riconciliazione
# --------------------------------------------------------------------------- #
def _richiedi_stato(stato, nome: str) -> StatoCoppia:
    if not isinstance(stato, StatoCoppia):
        raise ValueError(f"{nome} deve essere uno StatoCoppia")
    return stato


def riconcilia(
    stato_atteso: StatoCoppia,
    istantanea: StatoCoppia,
    *,
    tolleranza_ct: float = 1.0,
) -> list[Diff]:
    """Confronta atteso vs rilevato su spot e contratti.

    Tolleranza = ``tolleranza_ct`` contratti equivalenti: ``tolleranza_ct *
    ct_val`` unita' base sullo spot e ``tolleranza_ct`` contratti sul perp.
    Ritorna due ``Diff`` (spot, contratti); verdetto complessivo con
    :func:`verdetto_riconciliazione`.
    """
    atteso = _richiedi_stato(stato_atteso, "stato_atteso")
    rilevato = _richiedi_stato(istantanea, "istantanea")
    tc = _valida_positivo(tolleranza_ct, "tolleranza_ct")
    if atteso.base != rilevato.base:
        raise ValueError(f"base diversa: {atteso.base!r} vs {rilevato.base!r}")
    if not _chiudi(atteso.ct_val, rilevato.ct_val):
        raise ValueError(f"ct_val diverso: {atteso.ct_val!r} vs {rilevato.ct_val!r}")

    coppie = (
        ("spot", atteso.spot_qty, rilevato.spot_qty, tc * atteso.ct_val),
        ("contratti", atteso.contratti, rilevato.contratti, tc),
    )
    out: list[Diff] = []
    for campo, va, vb, limite in coppie:
        delta = _pulisci(vb - va)
        ok = abs(delta) <= limite + _EPS_REL * max(1.0, abs(limite))
        out.append(Diff(base=atteso.base, campo=campo, atteso=va, rilevato=vb, delta=delta, ok=ok))
    return out


def verdetto_riconciliazione(diffs: Iterable[Diff]) -> str:
    """``"ok"`` se tutti i diff sono entro tolleranza, altrimenti ``"ko"``."""
    return "ok" if all(d.ok for d in diffs) else "ko"


# --------------------------------------------------------------------------- #
# chiusura e riepilogo
# --------------------------------------------------------------------------- #
def pianifica_chiusura(stato) -> list[AzioneChiusura]:
    """Piano di chiusura: perp reduceOnly (buy) PRIMA, poi spot sell.

    Accetta uno ``StatoCoppia`` o un iterabile di stati. Stato gia' chiuso
    (spot e contratti a 0) -> lista vuota. Spot senza perp -> solo sell.
    """
    if isinstance(stato, StatoCoppia):
        stati = [stato]
    elif isinstance(stato, Iterable) and not isinstance(stato, (str, bytes, Mapping)):
        stati = list(stato)
    else:
        raise ValueError("pianifica_chiusura: atteso StatoCoppia o iterabile di stati")
    for s in stati:
        if not isinstance(s, StatoCoppia):
            raise ValueError("pianifica_chiusura: elementi attesi StatoCoppia")
    azioni: list[AzioneChiusura] = []
    for s in stati:
        if s.contratti > 0.0:
            azioni.append(
                AzioneChiusura(
                    base=s.base,
                    mercato="perp",
                    lato="buy",
                    quantita=_pulisci(s.contratti),
                    reduce_only=True,
                )
            )
        if s.spot_qty > 0.0:
            azioni.append(
                AzioneChiusura(
                    base=s.base,
                    mercato="spot",
                    lato="sell",
                    quantita=_pulisci(s.spot_qty),
                    reduce_only=False,
                )
            )
    return azioni


def _riga_da_elemento(el) -> tuple[float, float, float, float]:
    if isinstance(el, PairPlan):
        return el.costo_spot, el.margine_stimato, el.nozionale_stimato, el.delta_residuo
    if isinstance(el, StatoCoppia):
        nozionale = _pulisci(el.contratti * el.ct_val * el.prezzo_perp)
        costo = _pulisci(el.spot_qty * el.prezzo_spot)
        delta = calcola_delta(el.spot_qty, el.contratti, el.ct_val)
        return costo, nozionale, nozionale, delta
    raise ValueError("riepilogo: elementi attesi PairPlan o StatoCoppia")


def riepilogo(piani_o_stato) -> dict:
    """Totali per dashboard/alert (spot, margine, nozionale, delta).

    Accetta un ``PortafoglioPlan``, un ``PairPlan``, uno ``StatoCoppia`` oppure
    un iterabile di ``PairPlan``/``StatoCoppia``. Tutte le uscite sono finite e
    non negative.
    """
    if isinstance(piani_o_stato, PortafoglioPlan):
        elementi = list(piani_o_stato.piani)
        scartate = list(piani_o_stato.scartate)
    elif isinstance(piani_o_stato, (PairPlan, StatoCoppia)):
        elementi = [piani_o_stato]
        scartate = []
    elif isinstance(piani_o_stato, Iterable) and not isinstance(piani_o_stato, (str, bytes, Mapping)):
        elementi = list(piani_o_stato)
        scartate = []
    else:
        raise ValueError("riepilogo: atteso PortafoglioPlan, PairPlan, StatoCoppia o iterabile degli stessi")

    spot = margine = nozionale = delta = 0.0
    delta_max = 0.0
    for el in elementi:
        costo, marg, noz, dlt = _riga_da_elemento(el)
        spot += costo
        margine += marg
        nozionale += noz
        delta += dlt
        delta_max = max(delta_max, abs(dlt))

    return {
        "n_coppie": len(elementi),
        "n_scartate": len(scartate),
        "spot_totale": _pulisci(spot),
        "margine_totale": _pulisci(margine),
        "nozionale_totale": _pulisci(nozionale),
        "delta_totale": _pulisci(delta),
        "delta_max": _pulisci(delta_max),
        "commit_totale": _pulisci(spot + margine),
        "scartate": scartate,
    }

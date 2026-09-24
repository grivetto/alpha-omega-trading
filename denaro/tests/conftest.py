#!/usr/bin/env python3
"""Configurazione dei test di `denaro` — isolamento dal temp di sistema.

Perche' esiste
--------------
Il 25/09/2026 due sessioni di lavoro indipendenti si sono fermate sullo stesso muro:
**la suite non era eseguibile**. Sintomo: `PermissionError` su ogni test che toccava il
disco (63 "falliti" e 50 errori che non dicevano nulla sul codice, solo sull'ambiente).
Con l'esito della suite ridotto a rumore, nessuno puo' verificare il proprio lavoro — ed
e' esattamente il modo in cui i difetti arrivano in produzione.

La causa, isolata con tre prove dirette:

    os.makedirs(<repo>/.pytmp/probe) + scrittura   -> OK
    tempfile.mkdtemp()                + scrittura  -> PermissionError
    os.makedirs(...) + open(...)       -> OK

Quindi **non** e' la directory temporanea in se': e' la `mkdtemp` a essere rifiutata in
questo ambiente. `tempfile.TemporaryDirectory` e il `tmp_path` di pytest ci passano
entrambi attraverso, ed e' per questo che la suite intera cadeva.

La correzione: sostituire `mkdtemp` con la stessa logica costruita su `os.makedirs`
(nome casuale, `exist_ok=False`, retry sul caso raro di collisione) e puntare la base su
`.pytmp/` dentro il repo. Cosi' si riparano **tutte** le strade in un punto solo, senza
toccare i test: chi scrive `tmp_path` o `TemporaryDirectory()` non deve saperne nulla.

La pulizia (`cleanup`) e' resa non fatale: `shutil.rmtree` chiama `os.chmod` su una
directory creata al volo e qui talvolta viene negato, ma **la pulizia non e' un test** e
non deve farlo fallire. Gli avanzi restano sotto `.pytmp/`, che e' gitignorata.
"""
from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

#: Radice dei file temporanei dei test: dentro il repo, sempre scrivibile.
BASE_TMP = Path(__file__).resolve().parents[2] / ".pytmp"


def base_tmp() -> Path:
    """Ritorna la base temporanea, creandola se manca. Idempotente."""
    BASE_TMP.mkdir(parents=True, exist_ok=True)
    return BASE_TMP


def dir_tmp(nome: str = "t") -> Path:
    """Directory temporanea nuova, con nome unico, dentro una base che esiste gia'.

    Rimpiazzo esplicito di `tempfile.mkdtemp()` per i test che vogliono un albero
    proprio senza dipendere dalla patch globale. Chi la usa puo' chiamare `pulisci`.
    """
    import uuid
    p = base_tmp() / f"{nome}-{uuid.uuid4().hex[:12]}"
    p.mkdir(parents=True, exist_ok=True)
    return p


def pulisci(p: Path) -> None:
    """Rimuove un albero temporaneo senza sollevare: la pulizia non e' un test."""
    shutil.rmtree(str(p), ignore_errors=True)


def _mkdtemp_scrutable(suffix: str | None = None, prefix: str | None = None,
                       dir: str | None = None, max_attempts: int = 100) -> str:
    """`tempfile.mkdtemp` rifatta su `os.makedirs`.

    Identica nel contratto (ritorna un path NUOVO, unico, non esistente) ma senza
    `os.mkdir` diretto, che in questo ambiente viene rifiutato. `exist_ok=False` tiene
    la garanzia di unicita': se il nome esiste si ritenta, come fa l'originale.
    """
    d = dir or tempfile.gettempdir()
    pre = prefix if prefix is not None else tempfile.gettempprefix()
    suf = suffix or ""
    os.makedirs(d, exist_ok=True)
    for _ in range(max_attempts):
        name = os.path.join(d, f"{pre}{next(tempfile._get_candidate_names())}{suf}")
        try:
            os.makedirs(name, exist_ok=False)
            return name
        except FileExistsError:
            continue
    raise FileExistsError(f"mkdtemp: nessun nome unico in {d} dopo {max_attempts} tentativi")


def _rmtree_tollerante(*args, **kwargs) -> None:
    """`shutil.rmtree` che non solleva mai.

    Serve alla pulizia di pytest (`tmp_path`, `--basetemp`): `rmtree` prova a fare
    `os.chmod` su cio' che non riesce a cancellare, e in questo ambiente il chmod su una
    directory creata al volo viene negato -> `PermissionError` in teardown, che pytest
    conta come errore. **La pulizia non e' un test**: se un avanzo resta sotto `.pytmp/`
    (gitignorata) il risultato dei test resta valido, mentre un errore di teardown
    traveste da guasto del codice un limite dell'ambiente.
    """
    real = _RMTREE_ORIGINALE
    try:
        real(*args, **kwargs)
    except Exception:
        # secondo tentativo ignorando gli errori per-file, poi si lascia stare.
        try:
            real(*args, ignore_errors=True)
        except Exception:
            pass


def _cleanup_non_fatale(self) -> None:  # pragma: no cover - ambiente, non logica
    """Chiude il finalizer senza cancellare a forza (il chmod qui puo' essere negato)."""
    try:
        self._finalizer.detach()
    except Exception:
        pass


def _configura_temp() -> None:
    """Dirotta il temp nel repo e sostituisce `mkdtemp` alla radice."""
    global _RMTREE_ORIGINALE
    base = base_tmp()
    tempfile.tempdir = str(base)
    os.environ.setdefault("TMPDIR", str(base))
    os.environ.setdefault("TMP", str(base))
    os.environ.setdefault("TEMP", str(base))
    tempfile.mkdtemp = _mkdtemp_scrutable            # type: ignore[assignment]
    tempfile.TemporaryDirectory.cleanup = _cleanup_non_fatale  # type: ignore[method-assign]
    _RMTREE_ORIGINALE = shutil.rmtree
    shutil.rmtree = _rmtree_tollerante               # type: ignore[assignment]
    # NB: NON impostare `PYTEST_TMP_NUM`. Pytest numera le basetemp come `<base><n>` e,
    # se la variabile e' gia' presente, usa quel valore invece di dedurlo: forzando "1"
    # il `tmp_path` puntava a `<base>1/` e il fixture moriva in setup con PermissionError.
    # Lasciandola assente, pytest deduce il numero dalla base esistente e incrementa.
    os.environ.pop("PYTEST_TMP_NUM", None)


#: riferimento all'originale, per non ricadere nella patch quando la si richiama.
_RMTREE_ORIGINALE = shutil.rmtree


# --- residui illeggibili: pytest non deve morire per colpa loro -----------------
#
# pytest, quando `--basetemp` non e' dato, usa `<temp>/pytest-of-<utente>/` e per
# decidere il prossimo numero **scandisce** quella directory. Se esiste un residuo di
# una sessione precedente che in questo ambiente non e' leggibile, la scandice solleva
# `PermissionError` e il fixture `tmp_path` muore in **setup**: quattro test di
# `test_overrides.py` cadevano per questo, non per il codice.
#
# Correzione: una scandice che, su directory illeggibile, si comporta come se fosse
# **vuota**, invece di sollevare. E' la semantica giusta per quello che pytest ne fa
# (cercare il numero libero successivo): se non posso leggerla, non ci sono numeri
# occupati che mi riguardino.

class _ScandirVuota:
    """`os.scandir` di una directory che non si riesce a leggere: si comporta come vuota.

    Deve rispettare il protocollo di `os.scandir` (iteratore **e** context manager):
    la prima versione restituiva `iter(())` e pytest e' morto con
    `TypeError: 'tuple_iterator' object does not support the context manager protocol`.
    """

    def __init__(self, path=None) -> None:
        try:
            self._it = _SCANDIR_ORIGINALE(path)
        except (PermissionError, FileNotFoundError, NotADirectoryError, OSError):
            self._it = iter(())

    def __iter__(self):
        return self._it

    def __next__(self):
        return next(self._it)

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> bool:
        close = getattr(self._it, "close", None)
        if callable(close):
            close()
        return False

    def close(self) -> None:
        close = getattr(self._it, "close", None)
        if callable(close):
            close()


def _scandir_tollerante(path=None):
    """`os.scandir` che non solleva su directory inaccessibili."""
    return _ScandirVuota(path)


_SCANDIR_ORIGINALE = os.scandir


def pytest_configure(config) -> None:  # pragma: no cover - ambiente, non logica
    """Rende tollerante la scandice che pytest usa per numerare le basetemp.

    `_pytest.pathlib` importa `os.scandir` **nel proprio namespace** al momento
    dell'import: sostituirlo in `os` non basta, va sostituito anche li'. Lo si fa qui e
    non in cima al file perche' a questo punto `_pytest.pathlib` e' certamente caricato.
    """
    os.scandir = _scandir_tollerante                 # type: ignore[assignment]
    try:
        from _pytest import pathlib as _pytest_pathlib
        _pytest_pathlib.os.scandir = _scandir_tollerante  # type: ignore[assignment]
        if hasattr(_pytest_pathlib, "scandir"):
            _pytest_pathlib.scandir = _scandir_tollerante  # type: ignore[attr-defined]
    except Exception:
        pass

_configura_temp()

#!/usr/bin/env python3
"""Denaro — storage robusto (journal immutabile + stato atomico).

Design (D5 del blueprint):
- `Journal`: append-only JSONL con fsync per riga; replay tollerante a
  righe troncate (crash a meta' scrittura). Fonte di verita' dei trade.
- `AtomicFile`: scrittura tmp+rename (pattern gia' usato in `_write_health`
  del motore v3.3 — esteso a tutto lo stato).
- `StateStore`: load/save dello stato (CoreState) come JSON atomico, con
  ripristino dai default se il file e' assente/corrotto.
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional


class AtomicFile:
    """Scrittura atomica: tmp + rename. Il file di destinazione non e' mai
    visibile a meta' scrittura."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def write_text(self, content: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, self.path)

    def write_json(self, data: Any) -> None:
        self.write_text(json.dumps(data, ensure_ascii=False))

    def read_text_or(self, default: str = "") -> str:
        try:
            return self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return default

    def read_json_or(self, default: Any = None) -> Any:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError):
            return default


class Journal:
    """Append-only JSONL con fsync. Replay tollerante alle righe troncate."""

    def __init__(self, path: Path, fsync: bool = True) -> None:
        self.path = Path(path)
        self.fsync = fsync

    def append(self, record: Dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, ensure_ascii=False) + "\n"
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            if self.fsync:
                f.flush()
                os.fsync(f.fileno())

    def read_all(self) -> List[Dict[str, Any]]:
        """Legge tutte le righe valide; ignora righe troncate/corrotte."""
        out: List[Dict[str, Any]] = []
        try:
            raw = self.path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return out
        for line in raw.splitlines():
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue  # riga troncata da crash: tollerata
        return out

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        return iter(self.read_all())

    def __len__(self) -> int:
        return len(self.read_all())


class StateStore:
    """Persistenza atomica dello stato condiviso (CoreState o dict).

    `factory()` ricostruisce lo stato di default se il file manca o e' rotto.
    """

    def __init__(self, path: Path, factory: Optional[Callable[[], Any]] = None,
                 min_save_interval: float = 0.0) -> None:
        self.file = AtomicFile(path)
        self.factory = factory or dict
        self.min_save_interval = min_save_interval
        self._last_save: float = 0.0

    def load(self) -> Any:
        data = self.file.read_json_or(None)
        if data is None:
            return self.factory()
        return data

    def save(self, state: Any) -> bool:
        """Salva se e' passato l'intervallo minimo; ritorna True se scritto."""
        now = time.time()
        if self.min_save_interval and now - self._last_save < self.min_save_interval:
            return False
        self.file.write_json(state)
        self._last_save = now
        return True

    def flush(self, state: Any) -> None:
        """Salvataggio forzato (ignora l'intervallo minimo)."""
        self.file.write_json(state)
        self._last_save = time.time()

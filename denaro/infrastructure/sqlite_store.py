#!/usr/bin/env python3
"""Denaro — SQLite state store (WAL mode) per il flush di emergenza (TODO p.3).

Usato dal SafeModeGuardian in EMERGENCY: flush dello stato su SQLite WAL
prima dello shutdown controllato (piu' robusto del JSON per scritture
frequenti e atomiche).
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional


class SqliteStateStore:
    """Key-value su SQLite con WAL. Thread-safe per uso da to_thread.

    Connessione LAZY: il file viene creato solo al primo uso (save/load),
    cosi' istanziare lo store non tocca il filesystem (es. nei test).
    """

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._conn: Optional[sqlite3.Connection] = None

    def _connect(self) -> sqlite3.Connection:
        if self._conn is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS state (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            self._conn.commit()
        return self._conn

    def save(self, key: str, data: Any) -> None:
        conn = self._connect()
        conn.execute(
            "INSERT OR REPLACE INTO state (key, value) VALUES (?, ?)",
            (key, json.dumps(data, ensure_ascii=False)))
        conn.commit()

    def load(self, key: str) -> Optional[Any]:
        conn = self._connect()
        row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        try:
            return json.loads(row[0])
        except json.JSONDecodeError:
            return None

    def keys(self) -> list:
        conn = self._connect()
        return [r[0] for r in conn.execute("SELECT key FROM state ORDER BY key")]

    def journal_mode(self) -> str:
        conn = self._connect()
        row = conn.execute("PRAGMA journal_mode").fetchone()
        return row[0] if row else ""

    def close(self) -> None:
        if self._conn is not None:
            try:
                self._conn.close()
            except Exception:
                pass
            self._conn = None

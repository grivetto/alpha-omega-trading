#!/usr/bin/env python3
"""Test storage: journal immutabile, atomicita', ripristino stato."""
import json
import os
import tempfile
import unittest
from pathlib import Path

from denaro.infrastructure.storage import AtomicFile, Journal, StateStore


class TestAtomicFile(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_write_e_read(self):
        f = AtomicFile(self.dir / "state.json")
        f.write_json({"a": 1})
        self.assertEqual(f.read_json_or(), {"a": 1})

    def test_nessun_file_tmp_residuo(self):
        f = AtomicFile(self.dir / "state.json")
        f.write_json({"a": 1})
        residui = [p for p in self.dir.iterdir() if p.suffix == ".tmp"]
        self.assertEqual(residui, [])

    def test_read_corrotto_ritorna_default(self):
        p = self.dir / "state.json"
        p.write_text("{rotto")
        f = AtomicFile(p)
        self.assertIsNone(f.read_json_or(None))
        self.assertEqual(f.read_json_or(42), 42)


class TestJournal(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.j = Journal(self.dir / "trades.jsonl")

    def tearDown(self):
        self._tmp.cleanup()

    def test_append_e_replay(self):
        self.j.append({"event": "buy", "n": 1})
        self.j.append({"event": "sell", "n": 2})
        records = self.j.read_all()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["n"], 1)
        self.assertEqual(records[1]["event"], "sell")

    def test_riga_troncata_tollerata(self):
        """Crash a meta' scrittura: l'ultima riga e' troncata, il replay la ignora."""
        self.j.append({"event": "buy", "n": 1})
        with open(self.j.path, "a") as f:
            f.write('{"event": "sell", "n": 2')  # troncato (niente newline/close)
        records = self.j.read_all()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["n"], 1)

    def test_len(self):
        self.j.append({"a": 1})
        self.j.append({"a": 2})
        self.assertEqual(len(self.j), 2)

    def test_file_mancante(self):
        self.assertEqual(Journal(self.dir / "nope.jsonl").read_all(), [])


class TestStateStore(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_default_factory_se_manca(self):
        s = StateStore(self.dir / "s.json", factory=lambda: {"fresh": True})
        self.assertEqual(s.load(), {"fresh": True})

    def test_save_e_load(self):
        s = StateStore(self.dir / "s.json")
        s.flush({"x": 1})
        self.assertEqual(StateStore(self.dir / "s.json").load(), {"x": 1})

    def test_min_interval(self):
        import time
        s = StateStore(self.dir / "s.json", min_save_interval=100.0)
        self.assertTrue(s.save({"a": 1}))
        self.assertFalse(s.save({"a": 2}))  # dentro l'intervallo → non salva
        s.flush({"a": 3})                    # flush forza (nessun return)
        self.assertEqual(s.load(), {"a": 3})


if __name__ == "__main__":
    unittest.main()

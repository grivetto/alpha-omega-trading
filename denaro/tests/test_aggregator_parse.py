#!/usr/bin/env python3
"""Il dump ssh dei health non deve perdere bot per una virgola (round 33).

Prima i bot live "extra" erano letti con UNA ssh per bot: bastava che una
fallisse per far sparire la card dalla dashboard per un ciclo (visto su
nuvola/AVAX il 2026-09-17). Ora la lettura e' raggruppata per host e il parsing
e' in una funzione pura, testabile senza rete.
"""
from __future__ import annotations

from denaro.infra_aggregator import _parse_dump


def test_una_riga_per_file():
    dump = ("===FILE===" + chr(10) + '{"symbol": "AVAX/EUR", "x": 1}' + chr(10)
            + "===FILE===" + chr(10) + '{"symbol": "DOT/EUR"}' + chr(10))
    assert _parse_dump(dump) == ['{"symbol": "AVAX/EUR", "x": 1}',
                                 '{"symbol": "DOT/EUR"}']


def test_json_multiriga():
    dump = "===FILE===" + chr(10) + "{" + chr(10) + ' "symbol": "UNI/EUR"' + chr(10) + "}" + chr(10)
    fuori = _parse_dump(dump)
    assert len(fuori) == 1 and fuori[0].startswith("{") and fuori[0].endswith("}")


def test_dump_vuoto_o_sporco():
    assert _parse_dump("") == []
    assert _parse_dump("nessun file") == []
    assert _parse_dump("===FILE===" + chr(10) + "troncato") == [""]


def test_ordine_preservato():
    """L'ordine dei blocchi deve seguire quello dei path richiesti."""
    dump = "".join("===FILE===" + chr(10) + '{"n": %d}' % i + chr(10) for i in range(5))
    assert _parse_dump(dump) == ['{"n": %d}' % i for i in range(5)]
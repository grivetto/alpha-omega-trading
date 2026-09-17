#!/usr/bin/env python3
"""19 contro 16 su finestre SCORREVOLI: la potatura regge ovunque?

La potatura e' stata decisa con un criterio INDIPENDENTE (alpha per-asset su 48
set): qui si controlla solo che il miglioramento non sia concentrato. Se il 16
batte il 19 nella maggioranza delle finestre, e' solido.

Uso: python3 tools/trend_potatura_finestre.py
"""
from __future__ import annotations
import importlib.util
import sys
from pathlib import Path

BASE_T = Path("/home/sergio/alpha-omega-trading/tools")
sp = importlib.util.spec_from_file_location("pt", str(BASE_T / "trend_potatura_test.py"))
pt = importlib.util.module_from_spec(sp)
sp.loader.exec_module(pt)

FINESTRE = [720, 630, 540, 450, 365, 300, 270, 220, 180, 150]


def main():
    print("  %-8s %10s %10s %8s" % ("barre", "19 asset", "16 asset", "delta"))
    vinte = {19: 0, 16: 0}
    for b in FINESTRE:
        r19, _, _, _ = pt.prova([], b)
        r16, _, _, _ = pt.prova(["LTC", "AAVE", "ATOM"], b)
        d = r16 - r19
        if d > 0:
            vinte[16] += 1
        else:
            vinte[19] += 1
        print("  %-8d %+9.2f%% %+9.2f%% %+7.2fpp" % (b, r19 * 100, r16 * 100, d * 100))
    print()
    print("  il 16 asset batte il 19 in %d finestre su %d" % (vinte[16], len(FINESTRE)))
    print("  il 19 asset batte il 16 in %d finestre su %d" % (vinte[19], len(FINESTRE)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Denaro v6 — `python -m denaro` entry point."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from denaro.launcher import run_main

if __name__ == "__main__":
    raise SystemExit(run_main())

#!/usr/bin/env python3
"""Smoke: mock_runner compat + entry points."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_runner import run_mock_test
r = run_mock_test(cycles=40, verbose=False)
print(f"SMOKE_MOCK cycles={r['cycles']} trades={r['total_trades']} "
      f"pnl={r['final_pnl_pct']:+.3f}% win={r['win_rate']*100:.1f}% "
      f"kelly={r['final_kelly']*100:.0f}%")

import main
print(f"SMOKE_MAIN {main.SYMBOL} cap={main.CAPITAL} levels={main.LEVELS} "
      f"cooldown={main.COOLDOWN} shadow={main.SHADOW_MODE}")

import denaro
print(f"SMOKE_DENARO v{denaro.__version__} "
      f"core={denaro.DenaroCore.__name__} orch={denaro.DenaroOrchestrator.__name__}")

import denaro_core
print(f"SMOKE_SHIM {denaro_core.DenaroCore is denaro.DenaroCore}")

import importlib
spec = importlib.util.find_spec("denaro.__main__")
print(f"SMOKE_MAINMODULE {'ok' if spec else 'missing'}")

#!/usr/bin/env python3
"""Smoke mock: 100-cycle mock_runner compatibility check."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from mock_runner import run_mock_test
r = run_mock_test(cycles=100, verbose=False)
print(f"cycles={r['cycles']} trades={r['total_trades']} "
      f"pnl={r['final_pnl_pct']:+.3f}% win={r['win_rate']*100:.1f}% "
      f"kelly={r['final_kelly']*100:.0f}% levels_last={r['cycle_log'][-1]['levels']}")
ok = r["total_trades"] >= 5
print("MOCK_OK" if ok else "MOCK_WARN: <5 trades in 100 cycles")
sys.exit(0 if ok else 2)

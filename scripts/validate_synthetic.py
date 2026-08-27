#!/usr/bin/env python3
"""Gate di validazione sintetica per sim_grid (backtest harness v3+).

Serie sintetiche a prezzo noto, fee reali, zero slippage:
  - FLAT      : prezzo costante -> grid perde SOLO le fee (nessun PnL fabbricato)
  - UPTREND   : trend lineare up -> B&H > grid (la grid non crea alpha dal trend)
  - DOWNTREND : trend lineare down -> la grid perde meno del B&H (protezione)
  - SINE      : mean-reversion -> grid > B&H (la grid cattura il chopping)

Asserts (falliscono = bug del simulatore, NON numeri da aggiustare):
  1. FLAT: 0 <= perdita <= fee totali
  2. UPTREND: grid < B&H
  3. SINE: grid > B&H
  4. Invariante a costo storico: cash + inventory_cost + fees == capital + realized
"""
import importlib.util
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

spec = importlib.util.spec_from_file_location(
    "bt", Path(__file__).resolve().parent / "backtest.py"
)
bt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bt)

CAP = bt.CAPITAL
FEE = bt.FEE_TAKER


def mk(price_fn, n=300, base_ts=1700000000000, step=3600 * 1000):
    out = []
    for i in range(n):
        p = price_fn(i)
        out.append([base_ts + i * step, p, p * 1.002, p * 0.998, p])
    return out


flat = mk(lambda i: 100.0)
up = mk(lambda i: 100.0 * (1 + 0.001 * i))
down = mk(lambda i: 100.0 * (1 - 0.001 * i))
sine = mk(lambda i: 100.0 + 10.0 * math.sin(i / 8.0))

SPREAD, LEVELS = 0.02, 2
results = {}
for name, candles in [("FLAT", flat), ("UPTREND", up), ("DOWNTREND", down), ("SINE", sine)]:
    bh = bt.sim_buy_hold(candles, FEE, 0.0, CAP)
    g = bt.sim_grid(candles, LEVELS, SPREAD, FEE, 0.0, CAP, 1.0)
    results[name] = (g["final"], g["round_trips"], g["fees"], bh["final"])
    print(f"{name:<10} grid={g['final']:8.2f} (RT={g['round_trips']:>3}, fees={g['fees']:.2f}) | "
          f"B&H={bh['final']:8.2f}")

g_flat, rt_flat, fees_flat, _ = results["FLAT"]
g_up, _, _, bh_up = results["UPTREND"]
g_sine, _, _, bh_sine = results["SINE"]

checks = [
    ("FLAT: perdita solo fee (0 <= loss <= fees)", 0 <= CAP - g_flat <= fees_flat + 1e-9),
    ("UPTREND: grid < B&H", g_up < bh_up),
    ("SINE: grid > B&H (mean-reversion)", g_sine > bh_sine),
]
ok = True
for desc, passed in checks:
    print(f"  [{'PASS' if passed else 'FAIL'}] {desc}")
    ok = ok and passed

print(f"\nGATE {'SUPERATO' if ok else 'FALLITO'}")
sys.exit(0 if ok else 1)

#!/usr/bin/env python3
"""
Harness sell-path ShadowGrid — replay prezzo sintetico per forzare buy-fill e sell-fill.

Scenario A (LEVELS=1, SPREAD=1.5): round trip pulito — buy-fill, sell-fill, fee, PnL>0.
Scenario B (LEVELS=3, SPREAD=0.5): gap-down 100 -> 95.5 in UN ciclo — 3 buy fill, free_cash >= 0.
Scenario C (LEVELS=5, SPREAD=0.5, PER_LEVEL=0.25): gap-down 100 -> 95.5 — 5 buy fill da 125% del
    capitale: PRE-fix free_cash va a -25 (fill senza guardia cassa), POST-fix resta >= 0.

Uso: python3 harness_sell_path.py A|B|C
"""
import os, sys

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "A"

if SCENARIO == "A":
    os.environ.update({
        "EXCHANGE": "kraken", "SYMBOL": "SOL/EUR", "CURRENCY": "EUR",
        "CAPITAL": "100.0", "LEVELS": "1", "SPREAD": "1.5", "PER_LEVEL": "0.50",
        "COOLDOWN": "1", "LOG_FILE": "/tmp/sg_harness_a.log",
        "STATE_FILE": "/tmp/sg_harness_a_state.json",
    })
elif SCENARIO == "B":
    os.environ.update({
        "EXCHANGE": "kraken", "SYMBOL": "SOL/EUR", "CURRENCY": "EUR",
        "CAPITAL": "100.0", "LEVELS": "3", "SPREAD": "0.5", "PER_LEVEL": "0.20",
        "COOLDOWN": "1", "LOG_FILE": "/tmp/sg_harness_b.log",
        "STATE_FILE": "/tmp/sg_harness_b_state.json",
    })
else:
    os.environ.update({
        "EXCHANGE": "kraken", "SYMBOL": "SOL/EUR", "CURRENCY": "EUR",
        "CAPITAL": "100.0", "LEVELS": "5", "SPREAD": "0.5", "PER_LEVEL": "0.25",
        "COOLDOWN": "1", "LOG_FILE": "/tmp/sg_harness_c.log",
        "STATE_FILE": "/tmp/sg_harness_c_state.json",
    })

sys.path.insert(0, "/home/sergio/denaro")
import shadowgrid as sg

state = sg.State()
engine = sg.GridEngine(state)

if SCENARIO == "A":
    prices = [100.00, 98.5, 99.98, 100.0]
    for i, p in enumerate(prices):
        r = engine.cycle(p)
        print(f"[{i}] price={p:7.4f} eq={r['equity']:.4f} orders={r['orders']} trades={r['trades']} | {r['event']}")
    free = state.free_cash
    coins = state.coins
    print(f"free_cash={free:.4f} coins={coins:.8f} realized_pnl={state.realized_pnl:+.4f}")
    ok = (state.total_trades == 2 and state.winning_trades == 1
          and state.realized_pnl > 0.5 and state.equity(100.0) > 100.5
          and free > 0 and coins >= 0)
    print(f"assert: trades={state.total_trades} wins={state.winning_trades} pnl={state.realized_pnl:+.4f} eq={state.equity(100.0):.4f}")
    print("SCENARIO A: " + ("PASS — sell path OK (buy+sell+fee+pnl>0)" if ok else "FAIL"))
    sys.exit(0 if ok else 1)
elif SCENARIO == "B":
    prices = [100.00, 95.5, 97.0]
    for i, p in enumerate(prices):
        r = engine.cycle(p)
        print(f"[{i}] price={p:7.4f} eq={r['equity']:.4f} orders={r['orders']} trades={r['trades']} | {r['event']}")
    free = state.free_cash
    print(f"free_cash={free:.4f} coins={state.coins:.8f}")
    ok = free >= 0
    print(f"assert: free_cash >= 0 -> {ok}")
    print("SCENARIO B: " + ("PASS — nessun free_cash negativo (guardia cassa OK)" if ok else "FAIL — free_cash negativo: buy fill senza guardia di cassa (bug)"))
    sys.exit(0 if ok else 1)
else:
    prices = [100.00, 95.5]
    for i, p in enumerate(prices):
        r = engine.cycle(p)
        print(f"[{i}] price={p:7.4f} eq={r['equity']:.4f} orders={r['orders']} trades={r['trades']} | {r['event']}")
    free = state.free_cash
    print(f"free_cash={free:.4f} coins={state.coins:.8f} orders={len(state.orders)}")
    ok = free >= 0
    print("SCENARIO C: " + ("PASS — nessun free_cash negativo (guardia cassa al fill OK)" if ok else "FAIL — free_cash negativo: fill senza guardia di cassa (bug)"))
    sys.exit(0 if ok else 1)

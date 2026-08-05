#!/usr/bin/env python3
"""
ShadowGrid — verifica persistenza dopo round-trip (gap mai testato).
1. Round-trip completo col modulo REALE (md5 548a4fae): buy fill -> sell fill.
2. state.save() -> sg.State() (auto-_load) -> stato coerente (trades/pnl/free/ordini).
3. Secondo round-trip post-reload: il libro restaurato CONTINUA a tradare (restart-safe).
Zero rete, zero chiavi (solo GridEngine.cycle con prezzi sintetici).
"""
import json, os, sys

os.environ.update({
    "EXCHANGE": "kraken", "SYMBOL": "SOL/EUR", "CURRENCY": "EUR",
    "CAPITAL": "100.0", "LEVELS": "1", "SPREAD": "1.5", "PER_LEVEL": "0.50",
    "COOLDOWN": "1", "FEE_PCT": "0.25",
    "LOG_FILE": "/tmp/sg_persist.log", "STATE_FILE": "/tmp/sg_persist_state.json",
})
if os.path.exists("/tmp/sg_persist_state.json"):
    os.remove("/tmp/sg_persist_state.json")

sys.path.insert(0, "/home/sergio/denaro")
import shadowgrid as sg

ok = True
def check(name, cond, detail=""):
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")
    if not cond:
        ok = False

# ── 1. Round-trip (sequenza scenario A: 100 -> 98.5 -> 99.98 -> 100) ─────
state = sg.State()
engine = sg.GridEngine(state)
for p in [100.00, 98.5, 99.98, 100.0]:
    r = engine.cycle(p)
    print(f"[{p:7.4f}] eq={r['equity']:.4f} orders={r['orders']} trades={r['trades']} | {r['event']}")

print(f"pre-save: trades={state.total_trades} wins={state.winning_trades} "
      f"pnl={state.realized_pnl:+.4f} free={state.free_cash:.4f} coins={state.coins:.8f} orders={len(state.orders)}")
check("round-trip completo", state.total_trades == 2 and state.winning_trades == 1
      and state.realized_pnl > 0.5 and state.free_cash > 0,
      f"trades={state.total_trades} pnl={state.realized_pnl:+.4f}")
state.save()

# ── 2. Reload da disco (simula restart del servizio) ─────────────────────
state2 = sg.State()  # __init__ -> _load() legge STATE_FILE
print(f"post-load: trades={state2.total_trades} wins={state2.winning_trades} "
      f"pnl={state2.realized_pnl:+.4f} free={state2.free_cash:.4f} coins={state2.coins:.8f} orders={len(state2.orders)}")
for o in state2.orders:
    print(f"  restored order: {o['side']} @ {o['price']} amt={o['amount']:.6f} cost={o['cost']:.2f}")
check("persistenza completa", state2.total_trades == 2 and state2.winning_trades == 1
      and state2.realized_pnl > 0.5 and state2.free_cash > 0
      and len(state2.orders) == 1 and state2.orders[0]["side"] == "buy",
      f"trades={state2.total_trades} pnl={state2.realized_pnl:+.4f} orders={len(state2.orders)}")

# ── 3. Secondo round-trip post-reload: il libro restaurato continua ──────
engine2 = sg.GridEngine(state2)
r = engine2.cycle(97.0)   # <= 97.0225 (buy restaurato) -> deve fillare
print(f"[post-reload 97.0000] eq={r['equity']:.4f} orders={r['orders']} trades={r['trades']} | {r['event']}")
check("restart-safe trading", state2.total_trades == 3 and "BUY filled" in r["event"],
      f"trades={state2.total_trades} event={r['event']}")

print("\n" + ("SG PERSISTENCE: ALL PASS" if ok else "SG PERSISTENCE: FAILURES"))
sys.exit(0 if ok else 1)

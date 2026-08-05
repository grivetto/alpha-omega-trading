#!/usr/bin/env python3
"""
Harness Scalper v2 — replay prezzo sintetico, zero rete, zero chiavi.

Scenario A (entry drop -> target): round-trip completo, PnL > 0, fee incluse.
Scenario B (entry drop -> stop):  perdita limitata, stop -1% rispettato.
Scenario C (guardia cassa):       SIZE_FRAC>1 -> cost > cash -> ENTRY skipped (no cash).
Scenario D (persistenza):         save -> reload -> stato posizione ripristinato.

Uso: python3 harness_scalper_v2.py [A|B|C|D|ALL]
"""
import os, sys

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "ALL"

COMMON = {
    "EXCHANGE": "kraken", "SYMBOL": "DOGE/EUR", "CURRENCY": "EUR",
    "CAPITAL": "100.0", "ENTRY_DROP": "1.0", "TARGET_PCT": "1.5", "STOP_PCT": "1.0",
    "COOLDOWN": "1", "FEE_PCT": "0.25", "HEALTH_PORT": "18913",
}


def run(scenario: str) -> int:
    os.environ.clear()
    os.environ.update(COMMON)
    state_file = f"/tmp/sg_scalper_harness_{scenario.lower()}_state.json"
    log_file = f"/tmp/sg_scalper_harness_{scenario.lower()}.log"
    os.environ["STATE_FILE"] = state_file
    os.environ["LOG_FILE"] = log_file
    if os.path.exists(state_file):
        os.remove(state_file)

    if scenario == "C":
        os.environ["SIZE_FRAC"] = "1.5"   # forza cost > cash -> guardia cassa

    # CRITICO: senza il purge, in modalita' ALL Python riusa il modulo cachato
    # in sys.modules con le env del PRIMO scenario (STATE_FILE incluso) ->
    # gli assert dei successivi girerebbero sullo stato sbagliato (falsi PASS).
    sys.modules.pop("scalper_v2", None)
    sys.path.insert(0, "/home/sergio/denaro")
    import scalper_v2 as sp

    state = sp.State()
    engine = sp.ScalperEngine(state)
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")
        if not cond:
            ok = False

    if scenario == "A":
        # 100 (peak) -> 99.0 (drop 1% -> entry) -> 100.5 (target +1.5%)
        for p in [100.00, 99.0, 100.5]:
            r = engine.cycle(p)
            print(f"[{p:7.4f}] eq={r['equity']:.4f} pos={r['in_position']} trades={r['trades']} | {r['event']}")
        check("A: entry su drop", state.in_position() is False and state.total_trades == 1
              and state.realized_pnl > 0,
              f"pnl={state.realized_pnl:+.4f} trades={state.total_trades}")
        check("A: no cash negativo", state.free_cash >= 0, f"free={state.free_cash:.4f}")
    elif scenario == "B":
        for p in [100.00, 99.0, 97.5]:
            r = engine.cycle(p)
            print(f"[{p:7.4f}] eq={r['equity']:.4f} pos={r['in_position']} trades={r['trades']} | {r['event']}")
        # 99 -> 97.5 = -1.52% <= -1% -> stop exit
        check("B: exit stop", state.in_position() is False and state.total_trades == 1
              and state.realized_pnl < 0,
              f"pnl={state.realized_pnl:+.4f} trades={state.total_trades}")
        check("B: perdita limitata", state.realized_pnl > -5.0, f"pnl={state.realized_pnl:+.4f}")
    elif scenario == "C":
        for p in [100.00, 99.0]:
            r = engine.cycle(p)
            print(f"[{p:7.4f}] eq={r['equity']:.4f} pos={r['in_position']} trades={r['trades']} | {r['event']}")
        check("C: entry bloccata (no cash)", state.in_position() is False and state.total_trades == 0
              and "no cash" in r["event"],
              f"event={r['event']}")
    elif scenario == "D":
        # entry + save + reload + continua
        for p in [100.00, 99.0]:
            engine.cycle(p)
        print(f"pre-save: pos={state.in_position()} entry={state.entry_price:.4f} coins={state.coins:.8f}")
        state.save()
        state2 = sp.State()
        print(f"post-load: pos={state2.in_position()} entry={state2.entry_price:.4f} coins={state2.coins:.8f}")
        check("D: persistenza posizione", state2.in_position() and state2.entry_price > 0
              and abs(state2.entry_price - state.entry_price) < 1e-6,
              f"entry={state2.entry_price:.4f}")
        # il reload continua a tradare: 100.5 -> target exit
        engine2 = sp.ScalperEngine(state2)
        r = engine2.cycle(100.5)
        check("D: restart-safe trading", state2.total_trades == 1 and "EXIT" in r["event"],
              f"event={r['event']}")

    print(f"\nSCALPER v2 scenario {scenario}: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if SCENARIO == "ALL":
    rc = 0
    for s in ["A", "B", "C", "D"]:
        rc |= run(s)
    print("\n════ SCALPER V2 HARNESS: " + ("ALL PASS" if rc == 0 else "FAILURES") + " ════")
    sys.exit(rc)
else:
    sys.exit(run(SCENARIO))

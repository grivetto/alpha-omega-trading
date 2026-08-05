#!/usr/bin/env python3
"""
Harness offline strategie v6 (neo/) — ZERO rete, ZERO chiavi.
Verifica: GridStrategy, DCAStrategy, ScalpStrategy, StrategySelector,
StateStore (SQLite WAL, path fix executemany) con db temporaneo.
"""
import asyncio, os, sys, tempfile

sys.path.insert(0, "/home/sergio/denaro")

from neo.types import SafeModeLevel
from neo.memory import OhlcvBuffer
from neo.strategies import GridStrategy, DCAStrategy, ScalpStrategy, StrategySelector
from neo.state import StateStore

ok = True
def check(name, cond, detail=""):
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")
    if not cond:
        ok = False

# ── 1. Buffer OHLCV sintetico (24 candele) ──────────────────────────────
buf = OhlcvBuffer(maxlen=100)
for i in range(24):
    buf.append(1700000000 + i * 3600, 100.0, 101.0, 99.0, 100.0, 10.0)

# ── 2. GridStrategy — passiva, nessun segnale, nessuna eccezione ────────
async def t_grid():
    g = GridStrategy("SOL/EUR", levels=5, spread=0.025)
    sig = await g.analyze(100.0, buf, 99.9, 100.1, SafeModeLevel.NORMAL)
    return sig
sig = asyncio.run(t_grid())
check("GridStrategy.analyze", sig is None, f"(passiva, segnale={sig})")

# ── 3. DCAStrategy — bear dump >3% → buy ────────────────────────────────
buf_dca = OhlcvBuffer(maxlen=100)
for i in range(24):
    c = 104.0 - i * (4.0 / 23.0)  # 104 -> 100
    buf_dca.append(1700000000 + i * 3600, c, c, c, c, 10.0)
async def t_dca():
    d = DCAStrategy("SOL/EUR", max_entries=5, entry_spacing=0.03)
    return await d.analyze(100.0, buf_dca, 0, 0, SafeModeLevel.NORMAL)
sig = asyncio.run(t_dca())
check("DCAStrategy.analyze", sig is not None and sig.action == "buy",
      f"reason={sig.reason if sig else None}")

# ── 4. ScalpStrategy — spread stretto → buy ─────────────────────────────
async def t_scalp():
    s = ScalpStrategy("SOL/EUR", spread_threshold=0.002)
    return await s.analyze(1.0, buf, 0.999, 1.000, SafeModeLevel.NORMAL)
sig = asyncio.run(t_scalp())
check("ScalpStrategy.analyze", sig is not None and sig.action == "buy",
      f"reason={sig.reason if sig else None}")

# ── 5. StrategySelector — transizioni regime ────────────────────────────
import neo.strategies as ns
counter = [0]
def fake_monotonic():
    counter[0] += 400  # > 300s lock anti-switch
    return counter[0]
ns.time.monotonic = fake_monotonic
sel = StrategySelector()
r1 = sel.select(0.04, 0.0, 0.0)     # ATR alto -> cooldown
r2 = sel.select(0.01, 0.0, 0.6)     # trend forte -> dca
r3 = sel.select(0.01, 0.0, 0.0)     # ATR basso -> scalp
r4 = sel.select(0.02, 0.0, 0.0)     # medio -> grid
print(f"selector: atr4%={r1} trend0.6={r2} atr1%={r3} atr2%={r4}")
check("StrategySelector", r1 == "cooldown" and r2 == "dca" and r3 == "scalp" and r4 == "grid",
      f"got {r1}/{r2}/{r3}/{r4}")

# ── 6. StateStore SQLite WAL — path fix executemany (runtime) ───────────
async def t_state():
    db = os.path.join(tempfile.mkdtemp(), "t.db")
    store = await StateStore.create(db)
    # DML su trades + state (il path che prima andava in errore)
    await store.execute("INSERT INTO trades (symbol, side, entry_price, amount, entry_ts, status, strategy) VALUES (?,?,?,?,?,?,?)",
                        ("SOL/EUR", "buy", 100.0, 0.5, 1, "open", "grid"))
    await store.execute("INSERT OR REPLACE INTO state (key, value, updated_ts) VALUES (?,?,?)",
                        ("k", "v", 1))
    await store._flush()
    v = await store.get_state("k")
    trades = await store.fetch_all("SELECT * FROM trades")
    wal = await store.fetch_one("PRAGMA journal_mode")
    await store.close()
    return v, len(trades), wal["journal_mode"] if wal else None
v, ntr, jm = asyncio.run(t_state())
check("StateStore", v == "v" and ntr == 1 and jm == "wal",
      f"state={v} trades={ntr} journal_mode={jm}")

print("\n" + ("HARNESS V6: ALL PASS" if ok else "HARNESS V6: FAILURES"))
sys.exit(0 if ok else 1)

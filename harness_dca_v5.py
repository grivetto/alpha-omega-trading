#!/usr/bin/env python3
"""
Harness DCA v5 (denaro_core.py:753-815) — unico motore mai esercitato.
ZERO rete, ZERO chiavi. Stato sintetico via SimpleNamespace (nessun file di stato).

Scenari: 1-4 entry (nuovo, none, drop, max_entries), 5 open_position,
6 exit target, 7 trailing (FINDING: ramo irraggiungibile), 8 stop, 9 close+reset.
"""
import sys, types

sys.path.insert(0, "/home/sergio/denaro")
from denaro_core import DenaroCore, Trend

def mk_state():
    dca = types.SimpleNamespace(
        active=False, entry_price=0.0, avg_entry_price=0.0, total_size=0.0,
        total_cost=0.0, num_entries=0, max_entries=5, entry_spacing_pct=0.03,
        last_entry_price=0.0, target_pnl_pct=0.03,
        trailing_activation=0.0, trailing_stop_pct=0.015)
    regime = types.SimpleNamespace(momentum_24h=0.0, volume_regime="normal",
                                   trend=Trend.RANGING, volatility_regime="normal")
    micro = types.SimpleNamespace(bid_ask_imbalance=1.0)
    return types.SimpleNamespace(dca=dca, regime=regime, micro=micro)

core = object.__new__(DenaroCore)
core.state = mk_state()
core.state.kelly_fraction = 1.0     # via state (kelly_fraction è property read-only su DenaroCore)
core.state.sizing_multiplier = 1.0  # necessario dalla property kelly_fraction

ok = True
def check(name, cond, detail=""):
    global ok
    print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")
    if not cond:
        ok = False

EQ = 100.0

# ── 1. Entry nuova posizione: bear dump + volume spike + imbalance basso ──
st = core.state
st.regime.momentum_24h = -0.05
st.regime.volume_regime = "spike"
st.micro.bid_ask_imbalance = 0.5
ent = core.dca_should_enter(100.0, EQ)
check("dca entry (nuova)", ent[0] and abs(ent[1] - 10.0) < 1e-9 and ent[2].startswith("dca_entry"),
      f"size={ent[1]:.2f} reason={ent[2]}")

# ── 2. Nessun dump -> nessun segnale ─────────────────────────────────────
st.regime.momentum_24h = -0.02
ent = core.dca_should_enter(100.0, EQ)
check("dca nessun segnale", not ent[0] and ent[2] == "none", f"reason={ent[2]}")

# ── 3. Apri posizione + entry aggiuntiva su drop ─────────────────────────
core.dca_open_position(100.0, 1.0, 100.0)
d = core.state.dca
check("dca_open_position", d.active and d.num_entries == 1 and d.total_size == 1.0
      and abs(d.avg_entry_price - 100.0) < 1e-9, f"size={d.total_size} avg={d.avg_entry_price}")
# drop 5% >= spacing 3% -> nuova entry
ent = core.dca_should_enter(95.0, EQ)
check("dca drop entry", ent[0] and abs(ent[1] - 3.0) < 1e-9 and ent[2].startswith("dca_drop"),
      f"size={ent[1]:.2f} reason={ent[2]}")

# ── 4. max_entries raggiunto -> blocco ───────────────────────────────────
d.num_entries = d.max_entries
ent = core.dca_should_enter(90.0, EQ)
check("dca max_entries", not ent[0] and ent[2] == "max_entries", f"reason={ent[2]}")
d.num_entries = 1

# ── 5. Exit su target +3% ────────────────────────────────────────────────
core.state.dca.avg_entry_price = 100.0
core.state.dca.total_size = 1.0
ex = core.dca_should_exit(105.0)
check("dca exit target", ex[0] and ex[2].startswith("target"), f"reason={ex[2]}")

# ── 6. TRAILING (fix 2026-08-05: ramo ora raggiungibile) ─────────────────
# salita a +1.5% (sotto target 3%) -> ratchet activation=101.5; poi -1.67% dal picco -> exit trailing
core.state.dca.avg_entry_price = 100.0
core.state.dca.total_size = 1.0
core.state.dca.trailing_activation = 0.0
ex = core.dca_should_exit(101.5)
act = core.state.dca.trailing_activation
check("dca trailing ratchet", not ex[0] and abs(act - 101.5) < 1e-9,
      f"activation={act:.1f}")
ex = core.dca_should_exit(99.8)   # trail=-1.67% < -1.5% -> exit trailing
check("dca trailing exit", ex[0] and ex[2].startswith("trailing"), f"reason={ex[2]}")
print("FIX: ramo trailing (era irraggiungibile) — ora ratchet-then-trail; exit reale su -1.5% dal picco.")

# ── 7. Stop loss -10% (stato ripulito: niente trailing_activation residua) ──
core.state.dca.trailing_activation = 0.0
core.state.dca.avg_entry_price = 100.0
core.state.dca.total_size = 1.0
ex = core.dca_should_exit(89.0)
check("dca exit stop", ex[0] and ex[2].startswith("stop"), f"reason={ex[2]}")

# ── 8. Close: PnL reale (fix v4.1: usa exit_price passato) + reset ──────
core.state.dca.avg_entry_price = 100.0
core.state.dca.total_size = 2.0
core.state.dca.total_cost = 200.0
core.state.dca.trailing_activation = 101.5   # residuo picco (sanity: deve essere azzerato)
pnl = core.dca_close_position(exit_price=105.0)
exp = (105.0 * 2.0 - 200.0) / 200.0  # +5.0%
check("dca close pnl+reset", abs(pnl - exp) < 1e-9 and not d.active and d.num_entries == 0
      and d.total_size == 0 and d.total_cost == 0
      and d.trailing_activation == 0.0,   # Fix: trailing_activation azzerata in close
      f"pnl={pnl*100:.1f}% atteso {exp*100:.1f}% trail_act={d.trailing_activation}")

print("\n" + ("HARNESS DCA V5: ALL PASS" if ok else "HARNESS DCA V5: FAILURES"))
sys.exit(0 if ok else 1)

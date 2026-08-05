#!/usr/bin/env python3
"""
Harness LIVE shadowgrid — exchange mockato, ZERO rete, ZERO chiavi.

A: paper invariato (LIVE_MODE=0) — la simulazione locale resta identica.
B: live placement — piazza 5 buy reali (mock), zero sell (no coins), cash intatto.
C: min-cost guard — cost < min del mercato -> ordine saltato.
D: fill reale rilevato -> coins aggiornati dal balance + paired sell piazzato.
E: drift -> cancel-all + rebuild della griglia attorno al nuovo prezzo.

Uso: python3 harness_sg_live.py [A|B|C|D|E|ALL]
"""
import os, sys

SCENARIO = sys.argv[1] if len(sys.argv) > 1 else "ALL"

COMMON = {
    "EXCHANGE": "kraken", "SYMBOL": "SOL/EUR", "CURRENCY": "EUR",
    "CAPITAL": "100.0", "LEVELS": "5", "SPREAD": "0.5", "PER_LEVEL": "0.20",
    "COOLDOWN": "1", "FEE_PCT": "0.25", "HEALTH_PORT": "18991",
}


class MockExchange:
    """Finto exchange ccxt: libro ordini + balance, tutto in memoria."""

    def __init__(self, balances=None, min_cost=5.0, min_amount=0.01):
        self.book = []
        self.closed = []
        self.balances = balances or {"EUR": 100.0, "SOL": 0.0}
        self.min_cost = min_cost
        self.min_amount = min_amount
        self._seq = 0

    def market(self, symbol):
        return {"limits": {"cost": {"min": self.min_cost},
                           "amount": {"min": self.min_amount}}}

    def fetch_balance(self):
        return {"free": dict(self.balances)}

    def fetch_open_orders(self, symbol=None):
        return list(self.book)

    def create_limit_order(self, symbol, side, amount, price):
        self._seq += 1
        o = {"id": f"mock{self._seq}", "symbol": symbol, "side": side,
             "amount": amount, "price": price, "status": "open"}
        self.book.append(o)
        return o

    def cancel_order(self, oid, symbol=None):
        self.book = [o for o in self.book if str(o["id"]) != str(oid)]

    def fetch_order(self, oid, symbol=None):
        for o in self.closed:
            if str(o["id"]) == str(oid):
                return o
        for o in self.book:
            if str(o["id"]) == str(oid):
                return o
        raise Exception(f"order {oid} not found")

    def fill(self, oid, avg=None):
        """Simula un fill reale: sposta da open a closed e aggiorna i balance."""
        for o in self.book:
            if str(o["id"]) == str(oid):
                avg = avg or o["price"]
                self.book.remove(o)
                closed = dict(o)
                closed.update({"status": "closed", "filled": o["amount"], "average": avg})
                self.closed.append(closed)
                if o["side"] == "buy":
                    self.balances["EUR"] -= o["amount"] * avg
                    self.balances["SOL"] += o["amount"]
                else:
                    self.balances["EUR"] += o["amount"] * avg
                    self.balances["SOL"] -= o["amount"]
                return closed
        raise Exception(f"{oid} not open")


def run(scenario: str) -> int:
    os.environ.clear()
    os.environ.update(COMMON)
    os.environ["LIVE_MODE"] = "0" if scenario == "A" else "1"
    os.environ["STATE_FILE"] = f"/tmp/sg_live_{scenario.lower()}_state.json"
    os.environ["LOG_FILE"] = f"/tmp/sg_live_{scenario.lower()}.log"
    for p in (os.environ["STATE_FILE"], os.environ["LOG_FILE"]):
        if os.path.exists(p):
            os.remove(p)

    sys.modules.pop("shadowgrid", None)
    sys.path.insert(0, "/home/sergio/denaro")
    import shadowgrid as sg

    state = sg.State()
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        print(f"{'PASS' if cond else 'FAIL'}  {name} {detail}")
        if not cond:
            ok = False

    if scenario == "A":
        eng = sg.GridEngine(state, ex=None, live=False)
        r = eng.cycle(100.0)
        check("A: paper invariato (5 ordini simulati)", r["orders"] == 5, f"orders={r['orders']}")
        check("A: nessuna chiamata exchange", eng.ex is None and state.free_cash == 100.0,
              f"cash={state.free_cash}")
    elif scenario == "B":
        ex = MockExchange()
        eng = sg.GridEngine(state, ex=ex, live=True)
        r = eng.cycle(100.0)
        buys = [o for o in ex.book if o["side"] == "buy"]
        sells = [o for o in ex.book if o["side"] == "sell"]
        check("B: 5 buy piazzati", len(buys) == 5, f"book={len(ex.book)}")
        check("B: zero sell (no coins)", len(sells) == 0)
        check("B: cash intatto", abs(state.free_cash - 100.0) < 1e-9, f"cash={state.free_cash}")
        check("B: id reali dal mock", all(str(o["id"]).startswith("mock") for o in state.orders))
    elif scenario == "C":
        ex = MockExchange(min_cost=50.0)
        eng = sg.GridEngine(state, ex=ex, live=True)
        r = eng.cycle(100.0)
        check("C: min-cost guard (cost 20 < min 50 -> skip)", len(ex.book) == 0
              and "skip (cost" in r["event"], r["event"][:90])
    elif scenario == "D":
        ex = MockExchange()
        eng = sg.GridEngine(state, ex=ex, live=True)
        eng.cycle(100.0)
        low = min((o for o in ex.book if o["side"] == "buy"), key=lambda o: o["price"])
        ex.fill(low["id"])
        r = eng.cycle(100.0)
        sells = [o for o in ex.book if o["side"] == "sell"]
        check("D: buy fill rilevato", state.total_trades >= 1, f"trades={state.total_trades}")
        check("D: coins dal balance", state.coins > 0, f"coins={state.coins:.6f}")
        check("D: paired sell piazzato", len(sells) == 1, f"sells={len(sells)}")
    elif scenario == "E":
        ex = MockExchange()
        eng = sg.GridEngine(state, ex=ex, live=True)
        eng.cycle(100.0)
        old_ids = {o["id"] for o in ex.book}
        r = eng.cycle(110.0)  # drift 10% >> soglia 1%
        new_ids = {o["id"] for o in ex.book}
        check("E: rebuild cancella i vecchi", old_ids.isdisjoint(new_ids),
              f"old={len(old_ids)} new={len(new_ids)}")
        prices = [o["price"] for o in ex.book]
        # 5 livelli a 0.5% sotto 110 -> buy piu' basso a 107.25 (2.75 dal mid)
        check("E: livelli vicini al nuovo prezzo", all(abs(p - 110) <= 2.76 for p in prices),
              f"prices={sorted(prices)}")

    print(f"\nSHADOWGRID LIVE scenario {scenario}: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if SCENARIO == "ALL":
    rc = 0
    for s in ["A", "B", "C", "D", "E"]:
        rc |= run(s)
    print("\n════ SHADOWGRID LIVE HARNESS: " + ("ALL PASS" if rc == 0 else "FAILURES") + " ════")
    sys.exit(rc)
else:
    sys.exit(run(SCENARIO))

"""Whale Tracker — Order book imbalance detection."""
import time
from engine import WarEngine

class WhaleTracker:
    def __init__(self, eng: WarEngine, sym: str, capital: float, cfg: dict):
        self.eng = eng; self.sym = sym; self.cap = capital; self.cfg = cfg
        self.entry_price = 0.0; self.trades = 0; self.pnl = 0.0; self.cooldown = 0

    def run(self) -> dict:
        p = self.eng.price(self.sym)
        if p <= 0 or time.time() < self.cooldown:
            return {}

        orders = self.eng.open_orders(self.sym)
        if any(o["side"] == "SELL" for o in orders):
            return {}  # Already in position

        imb = self.eng.imbalance(self.sym)
        threshold = self.cfg["imbalance_threshold"]

        if imb >= threshold:
            # Whale on bid side — buy pressure
            amt = min(self.cap * 0.3, self.cfg["max_order"])
            if self.eng.balance("USDC") >= amt:
                r = self.eng.market_buy(self.sym, amt)
                if "executedQty" in r:
                    qty = float(r["executedQty"])
                    cost = float(r["cummulativeQuoteQty"])
                    self.entry_price = cost / qty
                    tp = self.entry_price * (1 + self.cfg["take_profit"])
                    self.eng.limit_sell(self.sym, qty * 0.998, tp)
                    self.trades += 1
                    self.cooldown = time.time() + self.cfg["cooldown"]
                    return {"action": "BUY", "imbalance": imb, "qty": qty, "price": self.entry_price}

        elif imb <= 1.0 / threshold:
            # Whale on ask side — sell pressure (rare, alert only)
            return {"alert": "BEAR_WHALE", "imbalance": imb}

        return {"price": p, "imbalance": imb, "pnl": self.pnl, "trades": self.trades}

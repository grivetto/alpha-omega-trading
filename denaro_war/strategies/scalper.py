"""Scalper — ATR spike entry, fast exit. The bread and butter."""
import time
from engine import WarEngine

class Scalper:
    def __init__(self, eng: WarEngine, sym: str, capital: float, cfg: dict):
        self.eng = eng; self.sym = sym; self.cap = capital; self.cfg = cfg
        self.entry_price = 0.0; self.high = 0.0; self.trades = 0; self.pnl = 0.0
        self.baseline_atr = 0.0

    def run(self) -> dict:
        p = self.eng.price(self.sym)
        if p <= 0: return {}
        self.high = max(self.high, p)

        # Detect ATR spike
        atr = self.eng.atr(self.sym, self.cfg["atr_period"])
        if not self.baseline_atr:
            self.baseline_atr = atr
        spike = atr / max(self.baseline_atr, 0.0001)

        orders = self.eng.open_orders(self.sym)
        sell_orders = [o for o in orders if o["side"] == "SELL"]

        if sell_orders:
            # Already in position
            if p <= self.entry_price * self.cfg["stop_loss"]:
                sol = self.eng.balance(self.sym.replace("USDC", ""))
                if sol > 0:
                    self.eng.cancel_all(self.sym)
                    r = self.eng.market_sell(self.sym, sol)
                    loss = self.entry_price * sol - float(r.get("cummulativeQuoteQty", 0))
                    self.pnl -= loss
                    self.trades += 1
                    self.entry_price = 0.0; self.high = p
            return {}

        # No position — look for entry
        drop = (self.high - p) / self.high if self.high else 0
        entry_signal = drop >= self.cfg["entry_drop"] and spike > self.cfg["atr_spike_threshold"]

        if entry_signal and self.eng.balance("USDC") >= self.cfg["min_order"]:
            amt = min(self.cap * 0.4, self.cfg["max_order"])
            r = self.eng.market_buy(self.sym, amt)
            if "executedQty" in r:
                qty = float(r["executedQty"])
                cost = float(r["cummulativeQuoteQty"])
                self.entry_price = cost / qty
                tp = self.entry_price * (1 + self.cfg["take_profit"])
                self.eng.limit_sell(self.sym, qty * 0.998, tp)
                self.high = p
                self.trades += 1
                return {"action": "BUY", "qty": qty, "price": self.entry_price,
                        "drop_pct": drop * 100, "atr_spike": spike}

        self.baseline_atr = self.baseline_atr * 0.95 + atr * 0.05  # EMA smooth
        return {"price": p, "drop": drop * 100, "atr": atr, "spike": spike,
                "pnl": self.pnl, "trades": self.trades}

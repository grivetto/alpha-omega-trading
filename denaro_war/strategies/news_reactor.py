"""News Reactor — Keyword-based sentiment proxy via volatility spikes."""
import time
from engine import WarEngine

class NewsReactor:
    """Simulates news detection via volatility proxy until X API is integrated.
    When ATR spikes 5x above baseline + price moves >1% in 1 minute → news event."""
    
    def __init__(self, eng: WarEngine, sym: str, capital: float, cfg: dict):
        self.eng = eng; self.sym = sym; self.cap = capital; self.cfg = cfg
        self.entry_price = 0.0; self.trades = 0; self.pnl = 0.0
        self.baseline_atr = 0.0; self.last_price = 0.0; self.last_check = 0.0
        self.cooldown = 0

    def run(self) -> dict:
        if time.time() < self.cooldown:
            return {}
        p = self.eng.price(self.sym)
        if p <= 0: return {}

        orders = self.eng.open_orders(self.sym)
        if any(o["side"] == "SELL" for o in orders):
            return {}

        atr = self.eng.atr(self.sym)
        if not self.baseline_atr:
            self.baseline_atr = atr
            self.last_price = p
            self.last_check = time.time()
            return {}

        spike = atr / max(self.baseline_atr, 0.0001)
        price_change = (p - self.last_price) / self.last_price if self.last_price else 0
        elapsed = time.time() - self.last_check

        # News event: ATR 5x + price moved >1% in under 2 minutes
        news_event = (spike > self.cfg["volatility_threshold"] and 
                      abs(price_change) > self.cfg["price_move_threshold"] and
                      elapsed < 120)

        if news_event and self.eng.balance("USDC") >= self.cfg["min_order"]:
            amt = min(self.cap * 0.5, self.cfg["max_order"])
            side = "BUY" if price_change > 0 else "SELL"
            r = self.eng.market_buy(self.sym, amt)
            if "executedQty" in r:
                qty = float(r["executedQty"])
                cost = float(r["cummulativeQuoteQty"])
                self.entry_price = cost / qty
                tp = self.entry_price * (1 + self.cfg["take_profit"])
                self.eng.limit_sell(self.sym, qty * 0.998, tp)
                self.trades += 1
                self.cooldown = time.time() + self.cfg["cooldown"]
                return {"action": "NEWS_BUY", "atr_spike": spike, "price_change": price_change,
                        "qty": qty, "price": self.entry_price}

        self.baseline_atr = self.baseline_atr * 0.98 + atr * 0.02
        self.last_price = p
        self.last_check = time.time()
        return {"price": p, "atr_spike": spike, "price_change": price_change,
                "pnl": self.pnl, "trades": self.trades}

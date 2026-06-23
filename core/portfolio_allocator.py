"""Portfolio Allocator — 3 strategies coordinated, Kelly-based rebalancing."""
import hashlib, hmac, requests, time, json
from datetime import datetime
from risk_modules.performance_analytics import PerformanceAnalytics

class StrategyRunner:
    """Execute a single strategy on the allocated capital."""
    
    def __init__(self, name, engine, capital_usdc):
        self.name = name
        self.eng = engine
        self.capital = capital_usdc
        self.trades = []
        self.active = True
        self.last_entry = None  # (side, price, amount)
    
    def buy(self, amount_usdc):
        r = self.eng.market_buy(amount_usdc)
        if "executedQty" in r:
            qty = float(r["executedQty"])
            cost = float(r["cummulativeQuoteQty"])
            self.last_entry = ("BUY", cost / qty, qty)
            return qty, cost / qty
        return 0, 0

    def sell(self, amount_sol):
        r = self.eng.market_sell(amount_sol)
        if "executedQty" in r:
            qty = float(r["executedQty"])
            revenue = float(r["cummulativeQuoteQty"])
            if self.last_entry:
                entry_cost = self.last_entry[1] * qty
                profit = revenue - entry_cost
                self.trades.append({
                    "time": datetime.utcnow().isoformat(),
                    "profit": profit,
                    "capital": self.capital,
                    "strategy": self.name,
                })
                return profit
        return 0


class GridStrategy(StrategyRunner):
    def run(self, price: float, portfolio_daily_loss_eur: float, max_daily_loss_eur: float):
        if len(self.eng.open_orders()) > 0:
            return None  # Already has orders
        if portfolio_daily_loss_eur >= max_daily_loss_eur:
            return None
        # Grid: 2 BUY levels, with 2 corresponding SELL levels
        spacing = 0.012
        cap = min(self.capital * 0.4, 5.0)  # Max €5 per trade
        for i in range(2):
            bp = round(price * (1 - spacing * (i + 1) / 2), 2)
            sp = round(bp * (1 + spacing), 2)
            amt = round(cap / bp, 4)
            if amt * bp >= 5.1:
                self.eng.limit_buy(amt, bp)
                time.sleep(0.2)
                self.eng.limit_sell(amt * 0.998, sp)
                time.sleep(0.2)
        return {"type": "grid", "levels": 2, "capital": cap * 2}


class MeanReversionRSI(StrategyRunner):
    def run(self, ohlcv: list, portfolio_daily_loss_eur: float, max_daily_loss_eur: float):
        if self.last_entry:
            return None
        if portfolio_daily_loss_eur >= max_daily_loss_eur:
            return None
        if len(ohlcv) < 15:
            return None
        closes = [float(k[4]) for k in ohlcv]
        # RSI calculation
        gains = losses = 0
        for i in range(-14, 0):
            d = closes[i] - closes[i - 1]
            if d > 0:
                gains += d
            else:
                losses -= d
        avg_gain = gains / 14
        avg_loss = losses / 14
        rsi = 100 - 100 / (1 + avg_gain / avg_loss) if avg_loss else 100
        price = closes[-1]
        if rsi < 25:
            cap = min(self.capital * 0.3, 5.0)
            qty, bp = self.buy(cap)
            if qty:
                self.eng.limit_sell(qty, round(bp * 1.008, 2))  # +0.8% TP
        return {"type": "rsi", "rsi": rsi, "action": "buy" if rsi < 25 else "hold"}


class MomentumTrend(StrategyRunner):
    def run(self, ohlcv: list, portfolio_daily_loss_eur: float, max_daily_loss_eur: float):
        if self.last_entry:
            return None
        if portfolio_daily_loss_eur >= max_daily_loss_eur:
            return None
        if len(ohlcv) < 21:
            return None
        closes = [float(k[4]) for k in ohlcv]
        volumes = [float(k[5]) for k in ohlcv]
        # EMA 8 and EMA 21 (approximate)
        ema8 = sum(closes[-8:]) / 8
        ema21 = sum(closes[-21:]) / 21
        vol_ratio = sum(volumes[-3:]) / max(sum(volumes[-24:-3]), 0.01)
        if ema8 > ema21 and vol_ratio > 2.0:
            cap = min(self.capital * 0.3, 5.0)
            qty, bp = self.buy(cap)
            if qty:
                self.eng.limit_sell(qty, round(bp * 1.01, 2))
        return {"type": "momentum", "ema8_cross": ema8 > ema21, "vol_ratio": vol_ratio}


class PortfolioOrchestrator:
    """Central allocator managing 3 strategies with Kelly rebalancing."""

    def __init__(self, engine, total_capital=200, max_daily_drawdown=6.0):
        self.eng = engine
        self.total = total_capital
        self.max_dd = max_daily_drawdown
        self.analytics = PerformanceAnalytics()
        self.alloc = {
            "grid":       {"pct": 0.40, "capital": total_capital * 0.40},
            "rsi":        {"pct": 0.30, "capital": total_capital * 0.30},
            "momentum":   {"pct": 0.30, "capital": total_capital * 0.30},
        }
        self.daily_pnl = 0.0
        self.day = ""
        self.grid = GridStrategy("grid", engine, self.alloc["grid"]["capital"])
        self.rsi = MeanReversionRSI("rsi", engine, self.alloc["rsi"]["capital"])
        self.momentum = MomentumTrend("momentum", engine, self.alloc["momentum"]["capital"])

    def rebalance(self):
        """Daily Kelly-based rebalancing."""
        strategies = {
            "grid": {"sharpe": self._sharpe(self.grid.trades), "win_rate": self._wr(self.grid.trades),
                     "trade_count": len(self.grid.trades)},
            "rsi": {"sharpe": self._sharpe(self.rsi.trades), "win_rate": self._wr(self.rsi.trades),
                    "trade_count": len(self.rsi.trades)},
            "momentum": {"sharpe": self._sharpe(self.momentum.trades), "win_rate": self._wr(self.momentum.trades),
                         "trade_count": len(self.momentum.trades)},
        }
        best = self.analytics.optimize_sharpe(strategies)
        worst = min(strategies, key=lambda s: strategies[s]["sharpe"])
        if best != worst and strategies[worst]["trade_count"] > 5:
            self.alloc[best]["pct"] += 0.05
            self.alloc[worst]["pct"] -= 0.05
            for s in self.alloc:
                self.alloc[s]["pct"] = max(0.15, min(0.50, self.alloc[s]["pct"]))
                self.alloc[s]["capital"] = self.total * self.alloc[s]["pct"]
            print(f"  🔄 Rebalance: +{best} -{worst}")

    def _sharpe(self, trades):
        if not trades:
            return 0
        returns = [t["profit"] / t["capital"] for t in trades if t["capital"] > 0]
        if len(returns) < 5:
            return 0
        avg = sum(returns) / len(returns)
        var = sum((r - avg) ** 2 for r in returns) / len(returns)
        return avg / (var ** 0.5) if var > 0 and avg != 0 else 0

    def _wr(self, trades):
        if not trades:
            return 0
        return sum(1 for t in trades if t["profit"] > 0) / len(trades)

    def run_cycle(self, price: float, ohlcv: list):
        today = datetime.utcnow().strftime("%Y-%m-%d")
        if today != self.day:
            self.rebalance()
            self.day = today
            self.daily_pnl = 0

        # Capitals with max per-trade €5
        for s in [self.grid, self.rsi, self.momentum]:
            s.capital = self.alloc[s.name]["capital"]
        if self.daily_pnl < -self.max_dd:
            return {"status": "halted", "reason": "daily_drawdown"}

        results = {}
        for s, run_fn in [(self.grid, lambda: s.run(price, abs(self.daily_pnl), self.max_dd)),
                           (self.rsi, lambda: s.run(ohlcv, abs(self.daily_pnl), self.max_dd)),
                           (self.momentum, lambda: s.run(ohlcv, abs(self.daily_pnl), self.max_dd))]:
            try:
                r = run_fn()
                if r:
                    results[s.name] = r
            except Exception as e:
                print(f"  ❌ {s.name}: {str(e)[:60]}")

        return {"status": "ok", "results": results, "daily_pnl": self.daily_pnl,
                "allocation": {k: round(v["pct"], 2) for k, v in self.alloc.items()}}

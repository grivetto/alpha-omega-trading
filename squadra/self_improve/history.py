"""
TradeHistory — registra trade completati per la riflessione.
I bot chiamano record_trade() al completamento di ogni trade.
L'orchestrator chiama get_recent() per l'analisi.
"""
import os, json, time, logging

logger = logging.getLogger("SelfImprove.History")


class TradeHistory:
    def __init__(self, db_path: str = None):
        # Usa un file JSON per persistenza tra riavvii
        if db_path is None:
            db_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "trade_history.json"
            )
        self.path = db_path
        self._cache: dict = self._load()

    def _load(self) -> dict:
        if os.path.exists(self.path):
            try:
                with open(self.path) as f:
                    return json.load(f)
            except (json.JSONDecodeError, Exception):
                return {}
        return {}

    def _save(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with open(self.path, "w") as f:
            json.dump(self._cache, f, indent=2)

    def record_trade(self, bot_name: str, pnl_pct: float, duration_sec: float = 0, reason: str = ""):
        """Registra un trade completato."""
        if bot_name not in self._cache:
            self._cache[bot_name] = {
                "trades": [],
                "reflections": [],
                "total_trades": 0,
            }
        entry = {
            "ts": time.time(),
            "pnl_pct": round(pnl_pct, 4),
            "duration_sec": round(duration_sec, 1),
            "reason": reason,
        }
        self._cache[bot_name]["trades"].append(entry)
        self._cache[bot_name]["total_trades"] = len(self._cache[bot_name]["trades"])
        # Keep last 100 trades per bot (memory cap)
        if len(self._cache[bot_name]["trades"]) > 100:
            self._cache[bot_name]["trades"] = self._cache[bot_name]["trades"][-100:]
        self._save()

    def get_recent_trades(self, bot_name: str, n: int = 10) -> list:
        """Restituisce gli ultimi N trade di un bot."""
        bot_data = self._cache.get(bot_name, {})
        return bot_data.get("trades", [])[-n:]

    def get_trade_count(self, bot_name: str) -> int:
        bot_data = self._cache.get(bot_name, {})
        return bot_data.get("total_trades", 0)

    def record_reflection(self, bot_name: str, reflection: dict):
        """Registra un ciclo di riflessione/ottimizzazione."""
        if bot_name not in self._cache:
            self._cache[bot_name] = {"trades": [], "reflections": [], "total_trades": 0}
        reflection["ts"] = time.time()
        self._cache[bot_name]["reflections"].append(reflection)
        if len(self._cache[bot_name]["reflections"]) > 50:
            self._cache[bot_name]["reflections"] = self._cache[bot_name]["reflections"][-50:]
        self._save()

    def get_reflections(self, bot_name: str, n: int = 5) -> list:
        bot_data = self._cache.get(bot_name, {})
        return bot_data.get("reflections", [])[-n:]

    def get_stats_summary(self, bot_name: str) -> dict:
        """Calcola metriche aggregate sugli ultimi trade."""
        trades = self.get_recent_trades(bot_name, 20)
        if not trades:
            return {"total_trades": 0, "win_rate": 0, "avg_pnl": 0, "sharpe": 0}
        pnls = [t["pnl_pct"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p < 0]
        win_rate = len(wins) / len(pnls) if pnls else 0
        avg_pnl = sum(pnls) / len(pnls) if pnls else 0
        avg_win = sum(wins) / len(wins) if wins else 0
        avg_loss = sum(losses) / len(losses) if losses else 0
        # Sharpe-like: mean / std (annualized approssimato)
        if len(pnls) >= 2:
            mean_pnl = sum(pnls) / len(pnls)
            var = sum((p - mean_pnl) ** 2 for p in pnls) / (len(pnls) - 1)
            std = var ** 0.5
            sharpe = (mean_pnl / std) * (252 * 6) ** 0.5 if std > 0 else 0  # ~6 trades/giorno
        else:
            sharpe = 0
        return {
            "total_trades": len(trades),
            "win_rate": round(win_rate, 3),
            "avg_pnl_pct": round(avg_pnl, 4),
            "avg_win_pct": round(avg_win, 4),
            "avg_loss_pct": round(avg_loss, 4),
            "sharpe": round(sharpe, 2),
            "consecutive_losses": self._consecutive_losses(pnls),
        }

    def _consecutive_losses(self, pnls: list) -> int:
        count = 0
        max_count = 0
        for p in reversed(pnls):
            if p < 0:
                count += 1
                max_count = max(max_count, count)
            else:
                count = 0
        return max_count

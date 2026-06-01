"""
GoalManager — carica e valida goal.yaml per ogni bot.
"""
import os, yaml, logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GOAL_PATH = os.path.join(SCRIPT_DIR, "goal.yaml")

logger = logging.getLogger("SelfImprove.Goal")


class GoalManager:
    def __init__(self, goal_path: str = GOAL_PATH):
        self.path = goal_path
        self._data = None

    def load(self) -> dict:
        if not os.path.exists(self.path):
            logger.warning(f"goal.yaml non trovato: {self.path}")
            self._data = {"global": {}, "bots": {}}
            return self._data
        with open(self.path) as f:
            self._data = yaml.safe_load(f)
        logger.info(f"✅ goal.yaml caricato: {len(self._data.get('bots', {}))} bot configurati")
        return self._data

    def get_global(self, key: str, default=None):
        if self._data is None:
            self.load()
        return self._data.get("global", {}).get(key, default)

    def get_bot_goal(self, bot_name: str) -> dict:
        if self._data is None:
            self.load()
        return self._data.get("bots", {}).get(bot_name, {})

    def get_var_ranges(self, bot_name: str) -> dict:
        """Ritorna i range per ogni variabile ottimizzabile."""
        goal = self.get_bot_goal(bot_name)
        vars_raw = goal.get("variables", [])
        ranges = {}
        for v in vars_raw:
            if isinstance(v, str):
                ranges[v] = None
            elif isinstance(v, dict):
                name = list(v.keys())[0]
                ranges[name] = v[name]
        return ranges

    def reflection_cadence(self, bot_name: str) -> int:
        goal = self.get_bot_goal(bot_name)
        return goal.get("reflection_every_trades", 5)

    def max_drawdown_pct(self, bot_name: str) -> float:
        """Drawdown massimo percentuale per questo bot (default 5%)."""
        goal = self.get_bot_goal(bot_name)
        return goal.get("max_drawdown_pct", 5.0)

    def global_max_drawdown_pct(self) -> float:
        return self.get_global("max_portfolio_drawdown_pct", 5.0)

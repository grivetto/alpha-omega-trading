"""
StrategyReflector — motore di riflessione scientifica.
Dopo N trade chiusi, analizza performance, formula ipotesi,
cambia UNA variabile alla volta nel config del bot.

Principi dal video (Lewis Jackson / Zero-One Self-Improving Agent):
  1. ACCURATE — dati reali, non assunti
  2. RELIABLE — non rimane bloccato, auto-recupera
  3. WELL-DEFINED GOAL — metriche chiare
  4. SELF-IMPROVING — esplorazione vs sfruttamento:
     - exploration_rate: probabilità di provare qualcosa di nuovo vs exploitare
     - Dopo 5+ reflection senza miglioramento → esplora parametri non toccati
     - Dopo 10+ → considera switch strategia (timeframe, ecc.)
"""
import os, json, copy, logging, random, time
from .goal import GoalManager
from .history import TradeHistory

logger = logging.getLogger("SelfImprove.Reflector")

# Range validi per ogni variabile ottimizzabile
VAR_RANGES = {
    "base_order_eur": (5.0, 30.0),        # range più largo per riduzione drawdown
    "take_profit_pct": (0.003, 0.035),
    "stop_loss_pct": (0.002, 0.020),
    "atr_sl_multiplier": (1.0, 3.5),
    "atr_tp_multiplier": (1.5, 5.0),
    "fast_sma": (3, 15),
    "slow_sma": (10, 60),
    "buy_threshold": (0.1, 0.8),
    "grid_spread_pct": (0.002, 0.020),
    "grid_levels": (2, 15),
    "max_investment_eur": (10.0, 50.0),
    "lookback_period": (10, 40),
    "entry_zscore": (1.0, 3.0),
    "interval_sec": (30, 300),
}

# Delta di modifica per ogni variabile (frazione o valore assoluto)
VAR_DELTAS = {
    "base_order_eur": 2.0,           # ±2€
    "take_profit_pct": 0.002,        # ±0.2%
    "stop_loss_pct": 0.001,          # ±0.1%
    "atr_sl_multiplier": 0.25,
    "atr_tp_multiplier": 0.5,
    "fast_sma": 1,                   # ±1 periodo
    "slow_sma": 2,                   # ±2 periodi
    "buy_threshold": 0.05,
    "grid_spread_pct": 0.001,
    "grid_levels": 1,
    "max_investment_eur": 5.0,
    "lookback_period": 2,
    "entry_zscore": 0.2,
    "interval_sec": 15,
}


class StrategyReflector:
    def __init__(self, goal_mgr: GoalManager, history: TradeHistory):
        self.goal = goal_mgr
        self.history = history

    def _get_config_path(self, bot_name: str) -> str:
        config_file = f"{bot_name.lower()}.json"
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "config",
            config_file
        )

    def _load_config(self, bot_name: str) -> dict:
        path = self._get_config_path(bot_name)
        if not os.path.exists(path):
            logger.warning(f"Config non trovato per {bot_name}: {path}")
            return {}
        with open(path) as f:
            return json.load(f)

    def _save_config(self, bot_name: str, config: dict):
        path = self._get_config_path(bot_name)
        with open(path, "w") as f:
            json.dump(config, f, indent=4)
        logger.info(f"📝 {bot_name}: config salvata -> {path}")

    def _validate_change(self, var_name: str, new_value: float) -> bool:
        """Verifica che il nuovo valore sia entro i range sicuri."""
        if var_name not in VAR_RANGES:
            return True  # variabile sconosciuta, permetti comunque
        lo, hi = VAR_RANGES[var_name]
        if not (lo <= new_value <= hi):
            logger.warning(f"🚫 {var_name}: {new_value} fuori range [{lo}, {hi}]")
            return False
        return True

    def reflect(self, bot_name: str) -> dict:
        """
        Ciclo di riflessione principale.
        1. Carica goal e stats
        2. Valuta performance vs goal
        3. Propone UNA modifica
        4. Applica al config JSON
        Ritorna il reflection report.
        """
        goal = self.goal.get_bot_goal(bot_name)
        stats = self.history.get_stats_summary(bot_name)
        config = self._load_config(bot_name)

        if not config:
            return {"bot": bot_name, "error": "config non trovata", "changed": False}

        if stats["total_trades"] == 0:
            logger.info(f"{bot_name}: nessun trade per la riflessione, salto")
            return {"bot": bot_name, "changed": False, "reason": "no trades yet"}

        # --- Diagnostica ---
        target_return = goal.get("target_return_30d_pct", 5.0) / 100.0
        target_sharpe = goal.get("min_sharpe", 0.5)
        max_dd = goal.get("max_drawdown_pct", 5.0) / 100.0

        win_rate = stats["win_rate"]
        avg_pnl = stats["avg_pnl_pct"]
        sharpe = stats["sharpe"]
        avg_win = stats["avg_win_pct"]
        avg_loss = stats["avg_loss_pct"]

        logger.info(
            f"🔍 {bot_name}: WR={win_rate:.1%} avgP&L={avg_pnl:.2%} "
            f"Sharpe={sharpe:.2f} wins={avg_win:.2%} losses={avg_loss:.2%}"
        )

        # --- Decisione: UNA variabile per volta ---
        var_name = None
        delta = 0.0
        direction = 0  # +1 = increase, -1 = decrease
        reason = ""

        # ── Principio 4: EXPLORATION vs EXPLOITATION ──
        # Quante reflection recenti senza miglioramento?
        reflections = self.history.get_reflections(bot_name, 10)
        stagnation_count = 0
        for r in reflections:
            if not r.get("changed"):
                stagnation_count += 1
            elif r.get("stats", {}).get("avg_pnl_pct", 0) <= 0:
                stagnation_count += 1

        # exploration rate cresce con la stagnazione (10% base → 80% a 10 stagnation)
        exploration_rate = min(0.1 + stagnation_count * 0.07, 0.8)

        # Regole di aggiustamento (una alla volta, priorità decrescente)

        # 1. Drawdown troppo alto o perdite consecutive → riduci posizione
        consecutive_losses = stats.get("consecutive_losses", 0)
        if consecutive_losses >= 3:
            var_name = "base_order_eur"
            delta = -VAR_DELTAS.get(var_name, 2.0)
            direction = -1
            reason = f"{consecutive_losses} perdite consecutive → riduco posizione"
        elif avg_pnl < -0.01:  # P&L medio negativo
            # Peggiora la stop-loss o riduci posizione
            if avg_loss < -0.02:  # perdite singole troppo grandi
                var_name = "stop_loss_pct"
                delta = -VAR_DELTAS.get(var_name, 0.001)
                direction = -1
                reason = f"avg loss {avg_loss:.2%} troppo grande → tight SL"
            else:
                var_name = "base_order_eur"
                delta = -VAR_DELTAS.get(var_name, 2.0)
                direction = -1
                reason = f"P&L medio negativo ({avg_pnl:.2%}) → riduco posizione"
        elif win_rate < 0.35:
            # Win rate basso: aumenta TP o rendi SL più stretto
            var_name = "take_profit_pct"
            delta = -VAR_DELTAS.get(var_name, 0.002)  # TP più stretto = più piccoli profitti
            direction = -1
            reason = f"WR basso ({win_rate:.1%}) → tight TP"
        elif avg_win < 0.005:
            # Win troppo piccoli: allarga TP
            var_name = "take_profit_pct"
            delta = VAR_DELTAS.get(var_name, 0.002)
            direction = 1
            reason = f"avg win {avg_win:.2%} troppo piccolo → allargo TP"
        elif sharpe < target_sharpe:
            # Sharpe basso: regola holding period (interval)
            if "interval_sec" in config:
                var_name = "interval_sec"
                delta = VAR_DELTAS.get(var_name, 15)
                direction = 1  # più lento = meno noise
                reason = f"Sharpe {sharpe:.2f} sotto target {target_sharpe} → rallento"
            else:
                var_name = "atr_tp_multiplier"
                delta = VAR_DELTAS.get(var_name, 0.5)
                direction = 1
                reason = f"Sharpe {sharpe:.2f} sotto target → allargo TP/ATR"
        elif win_rate > 0.65 and avg_win > 0.01:
            # Sta andando bene: prova ad aumentare la posizione
            var_name = "base_order_eur"
            delta = VAR_DELTAS.get(var_name, 2.0)
            direction = 1
            reason = f"performance buona (WR={win_rate:.1%}) → aumento posizione"
        elif random.random() < exploration_rate and stagnation_count >= 3:
            # ── EXPLORATION MODE ──
            # Il sistema è stagnante → provo variabili non toccate di recente
            recently_touched = set()
            for r in reflections[:3]:
                recently_touched.add(r.get("variable", ""))

            # Variabili esplorabili ordinandole per rilevanza
            explorables = [v for v in VAR_RANGES if v in config and v not in recently_touched]
            if not explorables:
                explorables = [v for v in VAR_RANGES if v in config]

            if explorables:
                var_name = random.choice(explorables)
                delta = VAR_DELTAS.get(var_name, 1.0)
                # Direzione casuale ma biased verso riduzione del rischio
                direction = -1 if random.random() < 0.6 else 1
                delta = delta * direction
                reason = f"EXPLORATION (stagnation={stagnation_count}, rate={exploration_rate:.0%}) → provo {var_name}"
                logger.info(f"🧭 {bot_name}: EXPLORATION mode — provo {var_name}")
            else:
                return {
                    "bot": bot_name,
                    "changed": False,
                    "reason": "niente da esplorare",
                    "stats": stats,
                }
        elif stagnation_count >= 8:
            # ── RADICAL EXPLORATION ──
            # 8+ reflection senza miglioramento → cambio timeframe o grid spacing
            if "timeframe" in config and config["timeframe"] != "15m":
                old_tf = config["timeframe"]
                # Prova timeframe diverso
                tf_options = {"1m": "5m", "5m": "15m", "15m": "5m", "1h": "15m", "1d": "1h"}
                new_tf = tf_options.get(old_tf, "5m")
                config["timeframe"] = new_tf
                self._save_config(bot_name, config)
                report = {
                    "bot": bot_name,
                    "changed": True,
                    "variable": "timeframe",
                    "old_value": old_tf,
                    "new_value": new_tf,
                    "delta": 0,
                    "direction": "radical",
                    "reason": f"RADICAL EXPLORATION (stagnation={stagnation_count}) → switch timeframe",
                    "stats": stats,
                    "ts": time.time(),
                }
                self.history.record_reflection(bot_name, report)
                return report
            elif "grid_spread_pct" in config:
                var_name = "grid_spread_pct"
                # Prova spread molto diverso
                delta = VAR_DELTAS.get(var_name, 0.001) * 3  # 3x il delta normale
                direction = 1 if config.get(var_name, 0.01) < 0.01 else -1
                delta = delta * direction
                reason = f"RADICAL (stagnation={stagnation_count}) → cambio grid_spread"
            else:
                return {
                    "bot": bot_name,
                    "changed": False,
                    "reason": "radical exploration non applicabile",
                    "stats": stats,
                }
        else:
            # Default: aggiusta slow_sma o fast_sma se disponibile
            if "fast_sma" in config:
                var_name = "fast_sma"
                delta = 1
                direction = -1  # accelera
                reason = "ottimizzazione fine → fast SMA -1"
            else:
                return {
                    "bot": bot_name,
                    "changed": False,
                    "reason": "performance nella norma, nessuna modifica",
                    "stats": stats,
                }

        if var_name is None or var_name not in config:
            logger.info(f"{bot_name}: {var_name} non nel config, salto")
            return {"bot": bot_name, "changed": False, "reason": f"{var_name} non trovato"}

        # Costruisci lista di tentativi: prima la scelta, poi fallback
        fallback_vars = ["base_order_eur", "stop_loss_pct", "take_profit_pct"]
        if var_name in fallback_vars:
            fallback_vars.remove(var_name)
        attempts = [var_name] + fallback_vars[:2]  # max 3 tentativi

        for attempt_var in attempts:
            if attempt_var not in config:
                continue
            old_value = config.get(attempt_var)
            if old_value is None:
                continue

            # Calcola delta per questo tentativo
            attempt_delta = delta
            if attempt_var != var_name:
                # Fallback: default delta
                attempt_delta = VAR_DELTAS.get(attempt_var, 0)
                if attempt_delta == 0:
                    attempt_delta = -VAR_DELTAS.get("base_order_eur", 2.0)

            new_value = old_value + attempt_delta

            # Validazione range
            if not self._validate_change(attempt_var, new_value):
                logger.info(f"{bot_name}: tentativo {attempt_var}={new_value} fuori range, provo altro")
                continue

            # Arrotonda
            if isinstance(old_value, int):
                new_value = int(round(new_value))
            else:
                new_value = round(new_value, 6)

            if new_value == old_value:
                continue

            # --- APPLICA ---
            config[attempt_var] = new_value
            self._save_config(bot_name, config)

            report = {
                "bot": bot_name,
                "changed": True,
                "variable": attempt_var,
                "old_value": old_value,
                "new_value": new_value,
                "delta": attempt_delta,
                "direction": "up" if attempt_delta > 0 else "down",
                "reason": f"{reason} (fallback: {attempt_var})" if attempt_var != var_name else reason,
                "stats": stats,
                "ts": __import__("time").time(),
            }

            self.history.record_reflection(bot_name, report)
            logger.info(f"🧬 {bot_name}: {attempt_var} {old_value} → {new_value} ({reason})")
            return report

        # Nessun tentativo riuscito
        return {
            "bot": bot_name,
            "changed": False,
            "reason": "tutti i tentativi falliti (range esauriti o valori invariati)",
            "stats": stats,
        }

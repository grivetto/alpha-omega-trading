#!/usr/bin/env python3
"""
DENARO KRAKEN BOT v2 — Enhanced grid with Kelly, Circuit Breaker, ATR, Compounding.
DOGE/EUR — Kraken spot. SHADOW_MODE safe default (10% sizing).
"""
import os, sys, time, json, signal, logging
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Dict, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from kraken_engine import KrakenEngine, SYMBOL, _fix_base64_secret
from denaro_core import DenaroCore, CBState

# ─── CONFIG ──────────────────────────────────────────────
SYMBOL = os.environ.get("SYMBOL", "DOGE/EUR")
CAPITAL = float(os.environ.get("CAPITAL", "100.0"))
LEVELS = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN = int(os.environ.get("COOLDOWN", "30"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
DRY_RUN = os.environ.get("DRY_RUN", "0") == "1"
LOG_FILE = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "kraken_bot.log")))
STATE_FILE = Path(os.environ.get("STATE_FILE", str(Path(__file__).parent / "kraken_state.json")))

# ─── LOGGING ─────────────────────────────────────────────
log = logging.getLogger("kraken_v2")
log.setLevel(logging.INFO)
fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
sh = logging.StreamHandler(sys.stdout); sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.handlers = [fh, sh]

# ─── HELPERS ─────────────────────────────────────────────
def load_env(env_path: str) -> Dict[str, str]:
    result = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    result[k.strip()] = v.strip().strip('"').strip("'")
    return result

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"levels": [], "total_pnl": 0.0, "initial_capital": CAPITAL}

def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))

def health_write():
    try:
        Path("/tmp/denaro.health").write_text(f"{time.time():.1f}\n")
    except OSError:
        pass

# ─── ENHANCED GRID STRATEGY ──────────────────────────────
class EnhancedGrid:
    def __init__(self, engine: KrakenEngine, core: DenaroCore):
        self.eng = engine
        self.core = core
        self.state = load_state()
        self._last_ohlcv_fetch = 0.0

    def run(self):
        now = time.time()
        price = self.eng.fetch_ticker(SYMBOL)

        # ── ATR update (every 5 min) ──
        if now - self._last_ohlcv_fetch > 300:
            try:
                ohlcv = self.eng.ex.fetch_ohlcv(SYMBOL, "1h", limit=15)
                self.core.calculate_atr(ohlcv)
                self._last_ohlcv_fetch = now
            except Exception:
                pass

        # ── Equity ──
        eur = self.eng.fetch_balance("EUR")
        try:
            bal = self.eng.ex.fetch_balance()
            doge = float(bal.get("total", {}).get("DOGE", 0) or 0)
        except Exception as e:
            log.warning(f"balance failed: {e}")
            doge = 0.0
        equity = eur + doge * price

        # ── Circuit Breaker ──
        blocked = self.core.check_circuit_breaker(equity)
        if blocked:
            log.critical(f"CB OPEN: {self.core.state.cb.reason} — halted until recovery")
            return

        # ── Compounding check ──
        self.core.compound_profits(equity)

        # ── Position sizing (Kelly) ──
        pos_capital = self.core.position_size(equity, 1.0)
        if SHADOW_MODE:
            pos_capital *= SHADOW_FACTOR

        # ── Reconcile open orders ──
        open_orders = self.eng.fetch_open_orders(SYMBOL)
        levels = self.state.get("levels", [])
        active_levels = []

        for lvl in levels:
            matched = any(
                abs(float(o.get("price", 0)) - lvl["buy_price"]) < 0.0001 or
                abs(float(o.get("price", 0)) - lvl["sell_price"]) < 0.0001
                for o in open_orders
            )
            if matched:
                active_levels.append(lvl)
            else:
                # Order filled — place counter-order
                if doge >= lvl["amount"] * 0.5:
                    self.eng.create_limit_sell_order(
                        SYMBOL,
                        self.eng.round_amount(lvl["amount"]),
                        self.eng.round_price(lvl["sell_price"])
                    )
                    active_levels.append(lvl)

        self.state["levels"] = active_levels

        # ── ATR-adaptive spread ──
        atr_pct = self.core.state.adaptive.atr_pct
        spread = max(BASE_SPREAD * 0.5, min(atr_pct * 0.8, BASE_SPREAD * 3)) if atr_pct > 0 else BASE_SPREAD
        adaptive_tp = TAKE_PROFIT

        # ── Deploy new grid levels ──
        active_count = len(active_levels)
        per_level_eur = pos_capital / LEVELS if pos_capital > 0 else CAPITAL / LEVELS

        if active_count < LEVELS and eur >= per_level_eur:
            base_price = price * 0.98
            for i in range(active_count, LEVELS):
                buy_price = self.eng.round_price(base_price * (1 - spread * i))
                sell_price = self.eng.round_price(buy_price * (1 + adaptive_tp))
                amount = self.eng.round_amount(per_level_eur / buy_price)

                if DRY_RUN:
                    order = {"id": f"dry-run-buy-{i}", "symbol": SYMBOL, "side": "buy",
                             "amount": amount, "price": buy_price}
                else:
                    try:
                        order = self.eng.create_limit_buy_order(SYMBOL, amount, buy_price)
                    except Exception as e:
                        log.error(f"BUY failed @ {buy_price}: {e}")
                        continue

                if order:
                    self.state["levels"].append({
                        "buy_price": buy_price, "sell_price": sell_price,
                        "amount": amount, "order_id": order.get("id"),
                        "time": datetime.now().isoformat(),
                    })
                    log.info(f"GRID {'[SHADOW]' if SHADOW_MODE else ''} BUY {amount} @ €{buy_price} (spread={spread*100:.2f}%)")
                    if not DRY_RUN:
                        time.sleep(1)

        save_state(self.state)

        # ── Status ──
        pnl_pct = (equity - self.state.get("initial_capital", CAPITAL)) / self.state.get("initial_capital", CAPITAL) * 100
        mode = "SHADOW" if SHADOW_MODE else ("DRY" if DRY_RUN else "LIVE")
        log.info(f"Eq:€{equity:.2f} | PnL:{pnl_pct:+.1f}% | Grid:{len(active_levels)}/{LEVELS} | "
                 f"CB:{self.core.state.cb.state.value} | Kelly:{self.core.kelly_fraction*100:.0f}% | "
                 f"ATR:{atr_pct*100:.2f}% | {mode}")

        # ── Save trade if any fill closed ──
        self.core._save_state()

# ─── MAIN ────────────────────────────────────────────────
def main():
    env_paths = [
        Path(__file__).parent / ".env",
        Path.home() / "denaro" / ".env",
        Path(".env"),
    ]
    env = {}
    for p in env_paths:
        env = load_env(str(p))
        if env:
            break

    api_key = os.environ.get("KRAKEN_API") or env.get("KRAKEN_API", "")
    api_secret = os.environ.get("KRAKEN_SECRET") or env.get("KRAKEN_SECRET", "")

    if not api_key or not api_secret:
        log.critical("KRAKEN_API or KRAKEN_SECRET not found")
        sys.exit(1)

    log.info("=" * 55)
    log.info(f"DENARO KRAKEN BOT v2 — {SYMBOL} | Capital: €{CAPITAL}")
    log.info(f"Mode: {'SHADOW' if SHADOW_MODE else ('DRY' if DRY_RUN else 'LIVE')} | "
             f"Grid: {LEVELS} lvls | Spread: {BASE_SPREAD*100:.1f}% | CB: active")
    log.info("=" * 55)

    # SIGTERM handler
    shutdown = {"flag": False}
    def _handle(sig, frame):
        log.info("SIGTERM — graceful shutdown...")
        shutdown["flag"] = True
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    try:
        engine = KrakenEngine(api_key, api_secret)
    except Exception as e:
        log.critical(f"Engine init failed: {e}")
        sys.exit(1)

    core = DenaroCore(initial_capital=CAPITAL, state_path=Path("/tmp/denaro_cb_state.json"))

    # Cancel orphans
    log.info("Cancelling orphaned orders...")
    engine.cancel_all_orders(SYMBOL)

    grid = EnhancedGrid(engine, core)
    cycle = 0

    while not shutdown["flag"]:
        try:
            cycle += 1
            grid.run()
            if cycle % 30 == 0:
                health_write()
            time.sleep(COOLDOWN)
        except KeyboardInterrupt:
            break
        except Exception as e:
            log.error(f"Cycle {cycle}: {type(e).__name__}: {e}")
            time.sleep(30)

    # Shutdown
    log.info("Shutting down — cancelling orders...")
    try:
        engine.cancel_all_orders(SYMBOL)
    except Exception:
        pass
    core._save_state()
    log.info("Done.")

if __name__ == "__main__":
    main()

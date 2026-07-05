#!/usr/bin/env python3
"""
DENARO v3 — Orchestratore strategico: Grid adattivo + DCA + microstructure.
Macchina a profitto autonoma: sceglie strategia in base al regime di mercato.
"""
from __future__ import annotations

import json, logging, os, signal, sys, time, traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import DenaroCore, CBState, Trend, StrategyMode

def _get_kraken_engine():
    from kraken_engine import KrakenEngine, SYMBOL, _fix_base64_secret
    return KrakenEngine, SYMBOL, _fix_base64_secret

# ─── .env loader ──────────────────────────────────────────────────────────

def _load_dotenv() -> None:
    for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env", Path(".env")]:
        if p.exists():
            with open(p) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        v = v.strip().strip('"').strip("'")
                        if k not in os.environ:
                            os.environ[k] = v
            break
_load_dotenv()

SYMBOL      = os.environ.get("SYMBOL", "DOGE/EUR")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
DRY_RUN     = os.environ.get("DRY_RUN", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "kraken_bot.log")))
STATE_FILE  = Path(os.environ.get("STATE_FILE", str(Path(__file__).parent / "kraken_state.json")))
CORE_STATE_FILE = Path(os.environ.get("CORE_STATE_FILE", str(Path(__file__).parent / "denaro_core_state.json")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8909"))

# ─── LOGGING ─────────────────────────────────────────────────────────────

log = logging.getLogger("kraken_v2")
log.setLevel(os.environ.get("LOG_LEVEL", "INFO"))
fh = RotatingFileHandler(LOG_FILE, maxBytes=5*1024*1024, backupCount=3)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.handlers = [fh, sh]

def load_env(env_path: str) -> dict:
    r = {}
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    r[k.strip()] = v.strip().strip('"').strip("'")
    return r

def load_state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {"levels": [], "total_pnl": 0.0, "initial_capital": CAPITAL}

def save_state(s: dict) -> None:
    STATE_FILE.write_text(json.dumps(s, indent=2))

def health_write() -> None:
    try:
        Path("/tmp/denaro.health").write_text(f"{time.time():.1f}\n")
    except OSError:
        pass

def mode_label() -> str:
    return "SHADOW" if SHADOW_MODE else "DRY" if DRY_RUN else "MOCK" if MOCK_MODE else "LIVE"

def validate_config() -> list:
    w = []
    if CAPITAL <= 0:
        log.critical(f"CAPITAL={CAPITAL} must be > 0"); sys.exit(1)
    if LEVELS < 1 or LEVELS > 20:
        w.append(f"LEVELS={LEVELS} outside [1,20]")
    if BASE_SPREAD < 0.001 or BASE_SPREAD > 0.5:
        w.append(f"SPREAD={BASE_SPREAD} outside [0.001,0.5]")
    if COOLDOWN < 5 or COOLDOWN > 300:
        w.append(f"COOLDOWN={COOLDOWN}s outside [5,300]")
    if SHADOW_FACTOR < 0.01 or SHADOW_FACTOR > 1.0:
        w.append(f"SHADOW_FACTOR={SHADOW_FACTOR} outside [0.01,1.0]")
    return w


# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED GRID + DCA ENGINE
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    def __init__(self, engine, core: DenaroCore):
        self.eng = engine
        self.core = core
        self.state = load_state()
        self._last_ohlcv_fetch = 0.0
        self._error_count = 0
        self._started_at = time.time()
        self._last_perf_log = 0.0

    @property
    def error_count(self) -> int:
        return self._error_count

    def _log_perf(self) -> None:
        """Log performance metrics every 50 cycles."""
        now = time.time()
        if now - self._last_perf_log < 300:
            return
        self._last_perf_log = now
        p = self.core.state.perf
        r = self.core.state.regime
        log.info("─" * 60)
        log.info(f"PERF: Trades={p.total_trades} WR={p.win_rate*100:.0f}% "
                 f"Sharpe={p.sharpe_ratio:.2f} Sortino={p.sortino_ratio:.2f} "
                 f"PF={p.profit_factor:.2f}")
        log.info(f"PERF: Kelly={self.core.state.kelly_fraction*100:.0f}% "
                 f"SizeMult={self.core.state.sizing_multiplier:.2f} "
                 f"VaR95={self.core.state.var.var_95_1h*100:.2f}%")
        log.info(f"REGIME: {r.trend.value} strength={r.trend_strength:.2f} "
                 f"vol={r.volatility_regime} vol_r={r.volume_ratio:.1f}")
        log.info(f"STRAT: {self.core.state.exec.active_strategy.value} "
                 f"DCA={self.core.state.dca.active}")
        log.info("─" * 60)

    def run(self) -> None:
        now = time.time()
        eur = doge = price = equity = 0.0

        # ── Price + microstructure ──
        try:
            price = self.eng.fetch_ticker(SYMBOL)
            micro = self.eng.get_microstructure()
            self.core.update_microstructure(
                micro["bid"], micro["ask"], micro["bid_vol"], micro["ask_vol"],
                micro["cum_bid"], micro["cum_ask"], micro["price"])
        except Exception as e:
            self._error_count += 1
            log.error(f"ticker/micro failed: {e}")
            return

        # ── ATR + regime update ──
        if now - self._last_ohlcv_fetch > 300:
            try:
                ohlcv = self.eng.ex.fetch_ohlcv(SYMBOL, "1h", limit=24)
                self.core.calculate_atr(ohlcv)
                self.core.update_regime(ohlcv)
                self.core.update_var(price)
                self._last_ohlcv_fetch = now
            except Exception as e:
                log.debug(f"OHLCV/regime fetch: {e}")

        # ── Equity ──
        try:
            eur = self.eng.fetch_balance("EUR")
            bal = self.eng.ex.fetch_balance()
            doge = float(bal.get("total", {}).get("DOGE", 0) or 0)
        except Exception as e:
            self._error_count += 1
            log.warning(f"balance: {e}")
        equity = eur + doge * price

        # ── Circuit Breaker ──
        blocked = self.core.check_circuit_breaker(equity)
        if blocked:
            from notifier import notify_cb_open
            log.critical(f"CB OPEN: {self.core.state.cb.reason}")
            notify_cb_open(self.core.state.cb.reason, equity)
            return

        # ── Compounding ──
        self.core.compound_profits(equity)

        # ── Strategy selection ──
        strategy = self.core.select_strategy()
        self.core.state.exec.active_strategy = strategy

        # ── DCA operations (if HYBRID or DCA mode) ──
        if strategy in (StrategyMode.DCA, StrategyMode.HYBRID):
            self._run_dca(price, equity, doge)

        # ── Grid operations (if GRID or HYBRID) ──
        if strategy in (StrategyMode.GRID, StrategyMode.HYBRID):
            self._run_grid(price, equity, eur, doge)
        elif strategy == StrategyMode.COOLDOWN:
            log.info(f"COOLDOWN: extreme volatility — skipping grid")

        # ── Status ──
        self._log_status(price, equity, eur)

        # ── Save ──
        save_state(self.state)
        self.core._save_state()

        # ── Perf log ──
        self._log_perf()

    def _run_grid(self, price: float, equity: float, eur: float, doge: float) -> None:
        """Adaptive grid strategy."""
        grid_params = self.core.get_grid_params()
        spread = grid_params["spread"]
        levels = grid_params["levels"]
        atr_pct = self.core.state.regime.atr_pct

        pos_capital = self.core.position_size(equity, 1.0)
        if SHADOW_MODE:
            pos_capital *= SHADOW_FACTOR

        # ── Reconcile open orders ──
        open_orders = []
        try:
            open_orders = self.eng.fetch_open_orders(SYMBOL)
        except Exception as e:
            self._error_count += 1
            log.warning(f"fetch_open_orders: {e}")
        open_ids = {o["id"] for o in open_orders if o.get("id")}
        levels_data = self.state.get("levels", [])
        active_levels = []

        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            stage = lvl.get("stage", "buy")
            b_open = bid and bid in open_ids
            s_open = sid and sid in open_ids

            if stage == "buy" and not b_open and bid:
                if SHADOW_MODE or DRY_RUN or doge >= lvl["amount"] * 0.5:
                    try:
                        so = {"id": f"dry-run-sell-{len(levels_data)}"} if DRY_RUN else \
                             self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(lvl["amount"]), self.eng.round_price(lvl["sell_price"]))
                        if so:
                            lvl["sell_order_id"] = so.get("id")
                            lvl["stage"] = "sell"
                            log.info(f"FILL BUY EUR {lvl['buy_price']} -> SELL {lvl['amount']} EUR {lvl['sell_price']}")
                            if not DRY_RUN:
                                time.sleep(0.5)
                    except Exception as e:
                        self._error_count += 1
                        log.error(f"SELL failed: {e}")
                active_levels.append(lvl)
            elif stage == "sell" and not b_open and not s_open:
                # Round complete
                cb = lvl.get("actual_cost", lvl["amount"] * lvl["buy_price"])
                pp = lvl["amount"] * lvl["sell_price"]
                pnl = (pp - cb) / cb
                self.core.update_kelly(pnl)
                log.info(f"ROUND: EUR {lvl['buy_price']} -> EUR {lvl['sell_price']} = {pnl*100:+.2f}%  Kelly:{self.core.kelly_fraction*100:.0f}%")
            elif b_open or s_open:
                lvl["stage"] = "sell" if s_open else "buy"
                active_levels.append(lvl)

        self.state["levels"] = active_levels

        # ── Deploy new grid levels ──
        active_count = len(active_levels)
        per_level = pos_capital / levels if pos_capital > 0 else CAPITAL / levels

        if active_count < levels and eur >= per_level:
            bb = price * 0.98
            for i in range(active_count, levels):
                bp = self.eng.round_price(bb * (1 - spread * i))
                sp = self.eng.round_price(bp * (1 + TAKE_PROFIT * grid_params.get("take_profit_mult", 1.0)))
                amt = self.eng.round_amount(per_level / bp)
                order = {"id": f"dry-run-buy-{i}"} if DRY_RUN else None
                if not DRY_RUN:
                    try:
                        order = self.eng.create_limit_buy_order(SYMBOL, amt, bp)
                    except Exception as e:
                        self._error_count += 1
                        log.error(f"BUY failed EUR {bp}: {e}")
                        continue
                if order:
                    self.state["levels"].append({
                        "buy_price": bp, "sell_price": sp, "amount": amt,
                        "buy_order_id": order.get("id"), "stage": "buy",
                        "time": datetime.now().isoformat(),
                    })
                    log.info(f"GRID {'[SHADOW]' if SHADOW_MODE else ''} BUY {amt} EUR {bp} spread={spread*100:.2f}%")
                    if not DRY_RUN:
                        time.sleep(1)

    def _run_dca(self, price: float, equity: float, doge: float) -> None:
        """Dollar-cost averaging operations."""
        dca = self.core.state.dca

        # Check entry
        should_enter, enter_amount, reason = self.core.dca_should_enter(price, equity)
        if should_enter and enter_amount > 0:
            buy_doge = enter_amount / price
            try:
                if DRY_RUN:
                    self.core.dca_open_position(price, buy_doge, enter_amount)
                    log.info(f"DCA ENTER [DRY] {buy_doge:.2f} @ EUR {price:.6f} reason={reason}")
                else:
                    order = self.eng.create_limit_buy_order(SYMBOL, self.eng.round_amount(buy_doge),
                                                            self.eng.round_price(price * 0.998))
                    if order:
                        self.core.dca_open_position(price, buy_doge, enter_amount)
                        log.info(f"DCA ENTER {buy_doge:.2f} @ EUR {price:.6f} reason={reason}")
                        time.sleep(0.5)
            except Exception as e:
                log.error(f"DCA entry failed: {e}")

        # Check exit
        if dca.active:
            should_exit, exit_size, exit_reason = self.core.dca_should_exit(price)
            if should_exit:
                try:
                    if DRY_RUN:
                        pnl = self.core.dca_close_position()
                        log.info(f"DCA EXIT [DRY] {exit_size:.2f} @ EUR {price:.6f} +{pnl:.4f} reason={exit_reason}")
                    else:
                        # Sell via limit order
                        if doge >= exit_size * 0.5:
                            sell_price = self.eng.round_price(price * 1.002)
                            order = self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(exit_size), sell_price)
                            if order:
                                pnl = self.core.dca_close_position()
                                log.info(f"DCA EXIT {exit_size:.2f} @ EUR {sell_price:.6f} reason={exit_reason}")
                except Exception as e:
                    log.error(f"DCA exit failed: {e}")

    def _log_status(self, price: float, equity: float, eur: float) -> None:
        pnl_pct = (equity - self.state.get("initial_capital", CAPITAL)) / max(1e-10, self.state.get("initial_capital", CAPITAL)) * 100
        atr = self.core.state.regime.atr_pct
        active = len(self.state.get("levels", []))
        log.info(f"Eq:EUR {equity:.2f} PnL:{pnl_pct:+.1f}% "
                 f"Grid:{active}/{self.core.state.exec.grid_target_levels} "
                 f"Strat:{self.core.state.exec.active_strategy.value} "
                 f"CB:{self.core.state.cb.state.value} "
                 f"Kelly:{self.core.kelly_fraction*100:.0f}% "
                 f"ATR:{atr*100:.2f}% "
                 f"VaR:{self.core.state.var.var_95_1h*100:.2f}% "
                 f"WS:{'OK' if getattr(self.eng, 'ws_connected', False) else 'POLL'} "
                 f"Trend:{self.core.state.regime.trend.value} "
                 f"DCA:{'ACTIVE' if self.core.state.dca.active else 'IDLE'} "
                 f"{mode_label()}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

    for w in validate_config():
        log.warning(f"Config: {w}")

    mode = mode_label()
    log.info(f"Mode: {mode} | Grid: {LEVELS} | Spread: {BASE_SPREAD*100:.1f}%")

    # ── Health server ──
    health = None
    try:
        from enhanced.health_server import start_default
        health = start_default(port=HEALTH_PORT)
        health.update(mode=mode, max_levels=LEVELS, symbol=SYMBOL)
        health.set_degraded("starting")
    except Exception as e:
        log.warning(f"Health server: {e}")

    notify_startup(SYMBOL, mode, CAPITAL)

    # ── Credentials ──
    env = {}
    for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env", Path(".env")]:
        if p.exists():
            env = load_env(str(p))
            if env:
                break
    api_key = os.environ.get("KRAKEN_API") or env.get("KRAKEN_API", "")
    api_secret = os.environ.get("KRAKEN_SECRET") or env.get("KRAKEN_SECRET", "")
    if not api_key or not api_secret:
        log.critical("KRAKEN_API or KRAKEN_SECRET not found"); sys.exit(1)

    # ── Engine ──
    if MOCK_MODE:
        from mock_runner import MockKrakenEngine
        engine = MockKrakenEngine(initial_eur=CAPITAL)
        log.info("MOCK_MODE enabled")
    else:
        try:
            Ke, _, _ = _get_kraken_engine()
            engine = Ke(api_key, api_secret)
        except Exception as e:
            log.critical(f"Engine init: {e}"); sys.exit(1)

    core = DenaroCore(initial_capital=CAPITAL, state_path=CORE_STATE_FILE)
    log.info(f"Core loaded: {CORE_STATE_FILE}")

    if not DRY_RUN and not MOCK_MODE:
        log.info("Cancelling orphan orders...")
        try:
            engine.cancel_all_orders(SYMBOL)
        except Exception as e:
            log.warning(f"Cancel orphans: {e}")

    grid = TradingEngine(engine, core)
    cycle = 0

    shutdown = {"flag": False}
    def _handle(sig, frame):
        if shutdown["flag"]:
            log.warning("Second signal — force exit"); sys.exit(1)
        log.info(f"Signal {sig} — graceful shutdown...")
        shutdown["flag"] = True
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    degraded = False

    while not shutdown["flag"]:
        cycle += 1
        cycle_ok = False
        try:
            grid.run()
            cycle_ok = True
            grid._error_count = 0

            if health and cycle % 5 == 0:
                eq = core.state.current_capital
                initial = core.state.initial_capital
                pnl = (eq - initial) / initial * 100 if initial > 0 else 0
                health.update(
                    status="ok", equity=eq, pnl_pct=pnl,
                    grid_levels=len(grid.state.get("levels", [])),
                    cb_state=core.state.cb.state.value,
                    kelly_pct=core.kelly_fraction * 100,
                    atr_pct=core.state.regime.atr_pct,
                    last_cycle_ts=time.time(), last_cycle_ok=True,
                    uptime_sec=time.time() - grid._started_at,
                    ws_connected=getattr(engine, "ws_connected", False),
                    error_count=0,
                    strategy=core.state.exec.active_strategy.value,
                    trend=core.state.regime.trend.value,
                    dca_active=core.state.dca.active,
                )
            if degraded and cycle_ok:
                degraded = False
                log.info("Recovered — normal cycle")
        except KeyboardInterrupt:
            break
        except Exception as e:
            grid._error_count += 1
            log.error(f"Cycle {cycle}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            if health:
                health.update(status="degraded" if grid._error_count < 5 else "down",
                              last_cycle_ok=False, error_count=grid._error_count)
            if grid._error_count >= 3:
                if not degraded:
                    degraded = True
                    log.warning(f"Degradation: {grid._error_count} errors — backing off")
                time.sleep(min(COOLDOWN * 3, 120))
                continue

        if cycle % 30 == 0:
            health_write()

        sleep_sec = COOLDOWN * (3 if degraded else 1)
        if shutdown["flag"]:
            break
        for _ in range(int(min(sleep_sec, 5))):
            if shutdown["flag"]:
                break
            time.sleep(1)

    # ── Shutdown ──
    tg_notify(f"Shutting down | {SYMBOL}")
    log.info("Shutdown — cancelling orders...")
    try:
        engine.cancel_all_orders(SYMBOL)
    except Exception:
        pass
    try:
        core._save_state()
    except Exception:
        pass
    if health:
        health.set_down("shutdown"); health.stop()
    if hasattr(engine, "close"):
        try:
            engine.close()
        except Exception:
            pass
    log.info("Denaro shut down.")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
DENARO v5 — Bybit Spot Grid Trading.
Stessa architettura di v4 (denaro_core.py) ma su Bybit (USDT pairs).

Differenze da v4/Kraken:
  - Bybit spot pairs in USDT (default DOGE/USDT)
  - Health server su porta 8911 (per non collidere con Kraken su 8909)
  - Stato persistente su bybit_core_state.json
  - Logger separato "bybit_v5"
"""
from __future__ import annotations

import logging
import os
import signal
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import DenaroCore, CBState, StrategyMode
from bybit_engine import SYMBOL as _DEFAULT_SYMBOL
from notifier import notify as tg_notify, notify_startup, notify_cb_open

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

SYMBOL      = os.environ.get("SYMBOL", _DEFAULT_SYMBOL)
CURRENCY    = os.environ.get("CURRENCY", "USDT")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "bybit_bot.log")))
CORE_STATE_FILE = Path(os.environ.get("CORE_STATE_FILE", str(Path(__file__).parent / "bybit_core_state.json")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8911"))

# ─── LOGGING ─────────────────────────────────────────────────────────────

log = logging.getLogger("bybit_v5")
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

def health_write() -> None:
    try:
        Path("/tmp/bybit.health").write_text(f"{time.time():.1f}\n")
    except OSError:
        pass

def mode_label() -> str:
    return "SHADOW" if SHADOW_MODE else "MOCK" if MOCK_MODE else "LIVE"

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
# TRADING ENGINE v5 — Grid + DCA adattivo (Bybit)
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    def __init__(self, engine, core: DenaroCore):
        self.eng = engine
        self.core = core
        self._last_known_equity: float = core.state.current_capital
        self._last_ohlcv_fetch = 0.0
        self._error_count = 0
        self._started_at = time.time()
        self._last_perf_log = 0.0

    @property
    def error_count(self) -> int:
        return self._error_count

    def _log_perf(self) -> None:
        now = time.time()
        if now - self._last_perf_log < 300:
            return
        self._last_perf_log = now
        p = self.core.state.perf
        r = self.core.state.regime
        log.info("-" * 60)
        log.info(f"PERF: Trades={p.total_trades} WR={p.win_rate*100:.0f}% "
                 f"Sharpe={p.sharpe_ratio:.2f} Sortino={p.sortino_ratio:.2f} "
                 f"PF={p.profit_factor:.2f}")
        log.info(f"PERF: Kelly={self.core.kelly_fraction*100:.0f}% "
                 f"SizeMult={self.core.state.sizing_multiplier:.2f} "
                 f"VaR95={self.core.state.var.var_95_1h*100:.2f}%")
        log.info(f"REGIME: {r.trend.value} strength={r.trend_strength:.2f} "
                 f"vol={r.volatility_regime} vol_r={r.volume_ratio:.1f}")
        log.info(f"STRAT: {self.core.state.exec.active_strategy.value} "
                 f"DCA={self.core.state.dca.active}")
        log.info("-" * 60)

    def run(self) -> None:
        now = time.time()
        usdt = price = equity = 0.0

        # ── Price + microstructure ──
        try:
            price = self.eng.fetch_ticker(SYMBOL)
            micro = self.eng.get_microstructure()
            self.core.update_microstructure(
                bid_ask_spread_pct=micro.get("bid_ask_spread_pct", 0.001),
                bid_ask_imbalance=micro.get("bid_ask_imbalance", 1.0),
                order_book_slope=micro.get("order_book_slope", 0.0),
                cum_bid_depth=micro.get("cum_bid_depth_1pct", 0.0),
                cum_ask_depth=micro.get("cum_ask_depth_1pct", 0.0),
            )
        except Exception as e:
            log.warning(f"Price/micro fetch failed: {e}")
            return

        # ── Balance + Equity ──
        try:
            usdt = self.eng.fetch_balance(CURRENCY)
            base_asset = SYMBOL.split("/")[0]
            base_bal_total = 0.0
            try:
                bal = self.eng.ex.fetch_balance()
                base_bal_total = float(bal.get("total", {}).get(base_asset, 0) or 0)
            except Exception:
                pass
            equity = usdt + (base_bal_total * price)
        except Exception as e:
            log.warning(f"Balance fetch failed: {e}")
            return

        # ── Regime / ATR ──
        try:
            ticker_info = self.eng.ex.fetch_ticker(SYMBOL)
            self.core.compute_atr(price, ticker_info)
            self.core.update_regime(price, ticker_info)
        except Exception as e:
            log.warning(f"ATR/regime failed: {e}")
            pass  # atr_pct stays at last known value

        # ── OHLCV (ogni 5 min) ──
        if now - self._last_ohlcv_fetch > 300:
            try:
                ohlcv = self.eng.ex.fetch_ohlcv(SYMBOL, "5m", limit=96)
                if ohlcv:
                    self.core.update_ohlcv(ohlcv)
                    self._last_ohlcv_fetch = now
            except Exception as e:
                log.warning(f"OHLCV fetch: {e}")

        # ── Circuit Breaker ──
        cb_reason, should_stop = self.core.circuit_breaker_check(price, equity, base_bal_total)
        if cb_reason:
            if self.core.state.cb.state == CBState.CLOSED:
                log.warning(f"CB OPEN: {cb_reason}")
                notify_cb_open(cb_reason, equity - CORE_STATE_FILE)
                self.core.state.cb.state = CBState.OPEN
                self.core.state.cb.open_time = time.time()
            if should_stop:
                self._cancel_all()
                self.core.flush_state()
                return

        # ── Strategy selection ──
        strategy = self.core.select_strategy()
        if strategy == StrategyMode.COOLDOWN:
            if self.core.state.exec.active_strategy != StrategyMode.COOLDOWN:
                log.info("COOLDOWN — extreme volatility, skipping cycle")
                self.core.state.exec.active_strategy = StrategyMode.COOLDOWN
            return

        self.core.state.exec.active_strategy = strategy

        # ── Kelly sizing ──
        self.core.compute_kelly()

        # ── Operations ──
        self._run_grid(price, equity, usdt)
        self._run_dca(price, equity, base_bal_total)

        # ── Compounding ──
        self.core.compound_profits(equity)
        self.core.state.current_capital = equity

        # ── Save state (throttled) ──
        try:
            self.core.save_state()
        except Exception:
            pass

        # ── Logging ──
        self._log_perf()
        self._log_status(price, equity, usdt)

    # ── Grid ──────────────────────────────────────────────────────────────

    def _cancel_all(self) -> None:
        try:
            cancelled = self.eng.cancel_all_orders(SYMBOL)
            if cancelled:
                log.info(f"Cancelled {len(cancelled)} orders")
        except Exception:
            pass

    def _sync_grid(self, price: float, equity: float) -> None:
        grid = self.core.state.grid_levels
        active = [lv for lv in grid if lv.get("stage") in ("buy", "sell")]
        max_grid = self.core.state.exec.grid_target_levels or LEVELS

        # Remove filled sell orders
        active = [lv for lv in active if lv.get("stage") != "sell_complete"]

        # Remove filled buy orders (become sell orders)
        for lvl in active:
            if lvl.get("stage") == "buy" and lvl.get("buy_order_id", "0") == "0":
                # Buy filled — place sell
                try:
                    amt = self.eng.round_amount(lvl["amount"] * 0.998)  # -fee
                    sp = self.eng.round_price(lvl["sell_price"])
                    if SHADOW_MODE:
                        lvl["stage"] = "sell"
                        lvl["sell_order_id"] = f"shadow-sell-{active.index(lvl)}"
                    elif MOCK_MODE:
                        lvl["stage"] = "sell"
                        lvl["sell_order_id"] = f"mock-sell-{active.index(lvl)}"
                    else:
                        so = self.eng.create_limit_sell_order(SYMBOL, amt, sp)
                        if so:
                            lvl["stage"] = "sell"
                            lvl["sell_order_id"] = so.get("id")
                            lvl["sell_price_exec"] = sp
                        else:
                            log.warning(f"Sell order failed for {lvl}")
                except Exception as e:
                    log.error(f"SELL fill detection error: {e}")

        self.core.state.grid_levels = active

        # Check if we need new levels
        if len(active) >= max_grid:
            return

        params = self.core.get_grid_params()
        base_spread = params.get("spread", BASE_SPREAD)
        grid_levels = min(params.get("levels", LEVELS), max_grid)
        take_profit_mult = params.get("take_profit_mult", 1.0)

        per_level = equity * 0.85 / max(grid_levels, 1)
        low_price = price * (1 - base_spread)
        high_price = price * (1 + base_spread)
        step = (high_price - low_price) / max(grid_levels, 1)

        current = len(active)
        to_place = grid_levels - current
        for i in range(to_place):
            bp = self.eng.round_price(low_price + (current + i + 0.5) * step)
            sp = self.eng.round_price(bp * (1 + base_spread * take_profit_mult))
            amt = self.eng.round_amount(per_level / bp)
            if amt <= 0:
                continue
            try:
                if SHADOW_MODE or MOCK_MODE:
                    bo = {"id": f"shadow-buy-{i}"} if SHADOW_MODE else {"id": f"mock-buy-{i}"}
                else:
                    bo = self.eng.create_limit_buy_order(SYMBOL, amt, bp)
                if bo:
                    lvl = {
                        "buy_order_id": bo.get("id"), "order_id": bo.get("id"),
                        "buy_price": bp, "sell_price": sp, "amount": amt,
                        "stage": "buy", "time": datetime.now().isoformat(),
                    }
                    self.core.state.grid_levels.append(lvl)
                    log.info(f"GRID BUY {len(self.core.state.grid_levels)}/{grid_levels} USDT {bp} amt {amt} ({per_level:.2f} USDT)")
                    if not SHADOW_MODE and not MOCK_MODE:
                        time.sleep(0.5)
            except Exception as e:
                self._error_count += 1
                log.error(f"BUY failed (level {i}): {e}")

    def _run_grid(self, price: float, equity: float, usdt: float) -> None:
        self._sync_grid(price, equity)

        # Check sell fills for active sell orders
        grid = self.core.state.grid_levels
        for lvl in grid:
            if lvl.get("stage") != "sell":
                continue
            sid = lvl.get("sell_order_id", "")
            if not sid or sid.startswith("shadow-") or sid.startswith("mock-"):
                lvl["stage"] = "sell_complete"
                continue
            try:
                orders = self.eng.fetch_open_orders(SYMBOL)
                still_open = any(o["id"] == sid for o in orders)
                if not still_open:
                    lvl["stage"] = "sell_complete"
                    log.info(f"SELL FILLED: {lvl.get('amount',0):.4f} @ {lvl.get('sell_price', 0):.6f}")
            except Exception:
                pass

        # Clean completed levels
        self.core.state.grid_levels = [
            lv for lv in grid if lv.get("stage") != "sell_complete"
        ]

    def _run_dca(self, price: float, equity: float, base_bal: float) -> None:
        dca = self.core.state.dca
        if not dca.active:
            should, size, reason = self.core.dca_should_enter(price, equity)
            if should:
                if SHADOW_MODE or MOCK_MODE:
                    log.info(f"DCA ENTER (shadow) {reason} size={size:.2f} USDT")
                    self.core.dca_open_position(price, size / price, size)
                else:
                    try:
                        amt = self.eng.round_amount(size / price)
                        bo = self.eng.create_limit_buy_order(SYMBOL, amt, price)
                        if bo:
                            self.core.dca_open_position(price, amt, size)
                            log.info(f"DCA BUY {amt} @ USDT {price} = USDT {size:.2f}")
                    except Exception as e:
                        log.error(f"DCA buy order failed: {e}")

        should_exit, amount, reason = self.core.dca_should_exit(price)
        if should_exit:
            if SHADOW_MODE or MOCK_MODE:
                pnl = self.core.dca_close_position()
                log.info(f"DCA EXIT (shadow) {reason} size={amount:.2f} PnL={pnl:.4f}")
            else:
                try:
                    so = self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(amount), self.eng.round_price(price))
                    if so:
                        pnl = self.core.dca_close_position()
                        log.info(f"DCA EXIT {reason} size={amount:.2f} PnL={pnl:.4f}")
                except Exception as e:
                    log.error(f"DCA sell order failed: {e}")

    def _log_status(self, price: float, equity: float, usdt: float) -> None:
        cs = self.core.state
        pnl = (equity - cs.initial_capital) / cs.initial_capital * 100 if cs.initial_capital > 0 else 0
        log.info(f"DENARO v5 STATUS | {SYMBOL} price={price:.6f} equity={equity:.2f} "
                 f"USDT={usdt:.2f} PnL={pnl:+.2f}% grid={len(cs.grid_levels)}/{cs.exec.grid_target_levels} "
                 f"CB={cs.cb.state.value} mode={mode_label()}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    for w in validate_config():
        log.warning(f"Config warning: {w}")
    log.info(f"Starting Denaro v5 | {SYMBOL} | {mode_label()} | CAPITAL={CAPITAL} {CURRENCY}")

    # ── Health server ──
    health = None
    try:
        from enhanced.health_server import HealthServer
        health = HealthServer(port=HEALTH_PORT)
        health.start()
        health.update(mode=mode_label(), max_levels=LEVELS, symbol=SYMBOL)
        health.set_degraded("starting")
    except Exception as e:
        log.warning(f"Health server: {e}")

    notify_startup(SYMBOL, f"v5-{mode_label()}", CAPITAL)

    # ── Credentials ──
    env = {}
    for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env", Path(".env")]:
        if p.exists():
            env = load_env(str(p))
            if env:
                break
    api_key = os.environ.get("BYBIT_API_KEY") or env.get("BYBIT_API_KEY", "")
    api_secret = os.environ.get("BYBIT_API_SECRET") or env.get("BYBIT_API_SECRET", "")
    if not api_key or not api_secret:
        log.critical("BYBIT_API_KEY or BYBIT_API_SECRET not found"); sys.exit(1)

    # ── Engine ──
    if MOCK_MODE:
        log.info("MOCK_MODE — using MockBybitEngine placeholder")
        log.warning("Mock mode: create mock_runner_v5.py or reuse mock_runner.py")
        from bybit_engine import BybitEngine
        engine = BybitEngine(api_key, api_secret)
    else:
        try:
            engine = BybitEngine(api_key, api_secret, SYMBOL)
        except Exception as e:
            log.critical(f"Engine init: {e}"); sys.exit(1)

    core = DenaroCore(initial_capital=CAPITAL, state_path=CORE_STATE_FILE)
    log.info(f"Core loaded: {CORE_STATE_FILE}")

    if not MOCK_MODE:
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
                    grid_levels=len(grid.core.state.grid_levels),
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
    tg_notify(f"Denaro v5 shutting down | {SYMBOL}")
    log.info("Shutdown — cancelling orders...")
    try:
        engine.cancel_all_orders(SYMBOL)
    except Exception:
        pass
    try:
        core.flush_state()
    except Exception:
        pass
    if health:
        health.set_down("shutdown"); health.stop()
    if hasattr(engine, "close"):
        try:
            engine.close()
        except Exception:
            pass
    log.info("Denaro v5 shut down.")

if __name__ == "__main__":
    main()

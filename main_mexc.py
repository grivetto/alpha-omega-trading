#!/usr/bin/env python3
"""
DENARO MEXC v5 — Orchestratore strategico adattivo per MEXC spot.
Grid Trading + DCA + regime detection.

v5 fixes (stessa pattern di main.py v5):
  - Cache-aware balance + orders
  - Lockout mode + deep sleep
  - Permanent error detection → shutdown
  - Graceful degradation
  - EUR+DOGE tracking separato
"""
from __future__ import annotations

import json, logging, os, signal, sys, time, traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import DenaroCore, CBState, Trend, StrategyMode
from mexc_engine import MexcEngine, SYMBOL as _DEF_SYM, MexcPermanentError
from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

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

SYMBOL      = os.environ.get("SYMBOL", _DEF_SYM)
CURRENCY    = os.environ.get("CURRENCY", "USDT")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
MAX_DEPLOYED = float(os.environ.get("MAX_DEPLOYED", "0.50"))
MIN_ORDER_USDT = float(os.environ.get("MIN_ORDER_USDT", "5.0"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "mexc_bot.log")))
CORE_STATE_FILE = Path(os.environ.get("CORE_STATE_FILE", str(Path(__file__).parent / "mexc_core_state.json")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8911"))

# v5 cache config
BALANCE_CACHE_TTL = float(os.environ.get("BALANCE_CACHE_TTL", "15"))
ORDERS_CACHE_TTL = float(os.environ.get("ORDERS_CACHE_TTL", "10"))
LOCKOUT_RETRY_INTERVAL = float(os.environ.get("LOCKOUT_RETRY_INTERVAL", "60"))
DEEP_SLEEP_CYCLES = int(os.environ.get("DEEP_SLEEP_CYCLES", "5"))

log = logging.getLogger("mexc_v5")
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
        Path("/tmp/mexc.health").write_text(f"{time.time():.1f}\n")
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
    return w

class TradingEngine:
    def __init__(self, engine: MexcEngine, core: DenaroCore):
        self.eng = engine
        self.core = core
        self._last_known_equity: float = core.state.current_capital
        self._last_ohlcv_fetch = 0.0
        self._error_count = 0
        self._started_at = time.time()
        self._last_perf_log = 0.0
        self._consecutive_api_failures = 0
        self._last_deploy_attempt = 0.0
        self._deploy_cooldown = 10.0

    def run(self) -> None:
        now = time.time()
        price = base_bal = equity = quote_bal = 0.0

        if hasattr(self.eng, 'in_lockout') and self.eng.in_lockout:
            remaining = self.eng.lockout_remaining
            if remaining > 0:
                log.warning(f"LOCKOUT: {remaining:.0f}s remaining")
                self.core.flush_state()
                return
            log.info("LOCKOUT: backoff expired")

        try:
            price = self.eng.fetch_ticker(SYMBOL)
            micro = self.eng.get_microstructure()
            self.core.update_microstructure(
                micro["bid"], micro["ask"], micro["bid_vol"], micro["ask_vol"],
                micro["cum_bid"], micro["cum_ask"], micro["price"])
            self._consecutive_api_failures = 0
        except MexcPermanentError as e:
            log.critical(f"PERMANENT ERROR (ticker): {e}")
            raise
        except Exception as e:
            self._error_count += 1
            self._consecutive_api_failures += 1
            log.error(f"ticker/micro failed: {e}")
            return

        if now - self._last_ohlcv_fetch > 300:
            try:
                ohlcv = self.eng.ex.fetch_ohlcv(SYMBOL, "1h", limit=24)
                self.core.calculate_atr(ohlcv)
                self.core.update_regime(ohlcv)
                self.core.update_var(price)
                self._last_ohlcv_fetch = now
            except Exception as e:
                log.debug(f"OHLCV fetch: {e}")

        try:
            full_bal = self.eng.fetch_balance("FULL")
        except MexcPermanentError as e:
            log.critical(f"PERMANENT ERROR (balance): {e}")
            raise
        except Exception as e:
            self._error_count += 1
            log.warning(f"balance fetch failed: {e}")
            equity = self._last_known_equity
            quote_bal = 0.0; base_bal = 0.0
        else:
            if SHADOW_MODE:
                # In shadow mode, use virtual equity from core state
                quote_bal = 0.0
                base_bal = 0.0
                equity = self.core.state.current_capital
            else:
                quote_bal = full_bal.get(CURRENCY, 0.0)
                base_asset = SYMBOL.split("/")[0]
                base_bal = full_bal.get(base_asset, 0.0)
                equity = quote_bal + base_bal * price
            self._last_known_equity = equity
            self._error_count = max(0, self._error_count - 1)
            self._consecutive_api_failures = 0

        cs = self.core.state
        day_pnl = (equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
        if cs.exec.cycle_count < 3 and day_pnl < -self.core._daily_loss_limit:
            old = cs.day_start_capital
            cs.day_start_capital = equity
            log.warning(f"Day capital realigned: {old:.2f} -> {equity:.2f}")

        blocked = self.core.check_circuit_breaker(equity)
        if blocked:
            log.critical(f"CB OPEN: {self.core.state.cb.reason}")
            notify_cb_open(self.core.state.cb.reason, equity)
            return

        self.core.compound_profits(equity)
        strategy = self.core.select_strategy()
        self.core.state.exec.active_strategy = strategy

        if strategy in (StrategyMode.GRID, StrategyMode.HYBRID):
            self._run_grid(price, equity, quote_bal, base_bal)
        elif strategy == StrategyMode.COOLDOWN:
            log.info(f"COOLDOWN: skipping grid")

        self._log_status(price, equity, quote_bal, base_bal)
        self.core._save_state()
        self._log_perf()

    def _log_status(self, price: float, equity: float, quote: float, base: float) -> None:
        cs = self.core.state
        pnl = (equity - cs.initial_capital) / cs.initial_capital * 100 if cs.initial_capital > 0 else 0
        ws = "[WS]" if (hasattr(self.eng, 'ws_connected') and self.eng.ws_connected) else "[!WS]"
        log.info(f"MEXC STATUS | {ws} {SYMBOL} price={price:.4f} equity={equity:.2f} "
                 f"{CURRENCY}={quote:.2f} {base=:.2f} PnL={pnl:+.2f}% "
                 f"grid={len(cs.grid_levels)}/{cs.exec.grid_target_levels} "
                 f"CB={cs.cb.state.value} mode={mode_label()}")

    def _run_grid(self, price: float, equity: float, quote: float, base_bal: float) -> None:
        if price <= 0:
            log.error(f"INVALID PRICE {price}")
            return

        grid_params = self.core.get_grid_params()
        spread = grid_params["spread"]
        levels = grid_params["levels"]
        atr_pct = self.core.state.regime.atr_pct
        tp_mult = grid_params.get("take_profit_mult", 1.2)
        effective_tp = max(0.01, atr_pct * 1.5) * tp_mult
        effective_tp = max(TAKE_PROFIT * 0.5, min(TAKE_PROFIT * 2.0, effective_tp))

        open_orders = []
        try:
            open_orders = self.eng.fetch_open_orders(SYMBOL)
        except MexcPermanentError as e:
            log.critical(f"PERMANENT ERROR (orders): {e}")
            return
        except Exception as e:
            log.warning(f"fetch_open_orders: {e}")
            return

        open_ids = {o["id"] for o in open_orders if o.get("id")}
        levels_data = self.core.state.grid_levels
        active_levels = []
        filled_updates = []
        deployed = 0.0

        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            stage = lvl.get("stage", "buy")
            b_open = bid and bid in open_ids
            s_open = sid and sid in open_ids
            cost = lvl.get("actual_cost", lvl["amount"] * lvl["buy_price"])
            deployed += cost

            if stage == "buy" and not b_open and bid:
                filled = False
                try:
                    if not SHADOW_MODE and not MOCK_MODE:
                        info = self.eng.fetch_order(bid, SYMBOL)
                        filled = info.get("status") == "closed" and float(info.get("filled", 0)) > 0
                        if info.get("status") == "canceled":
                            continue
                except MexcPermanentError:
                    continue
                except Exception:
                    filled = True
                if filled:
                    try:
                        so = {"id": f"shadow-sell-{len(levels_data)}"} if SHADOW_MODE else \
                             self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(lvl["amount"]), self.eng.round_price(lvl["sell_price"]))
                        if so:
                            lvl["sell_order_id"] = so.get("id")
                            lvl["stage"] = "sell"
                            lvl["actual_cost"] = cost
                            log.info(f"FILL BUY USDT {lvl['buy_price']} -> SELL {lvl['amount']} @ USDT {lvl['sell_price']}")
                    except MexcPermanentError:
                        return
                    except Exception as e:
                        log.error(f"SELL failed: {e}")
                    active_levels.append(lvl)
            elif stage == "sell" and not b_open and not s_open:
                sp = lvl.get("sell_price", 0)
                pp = lvl["amount"] * sp
                pnl = (pp - cost) / cost if cost > 0 else 0
                filled_updates.append(pnl)
                log.info(f"ROUND: USDT {lvl['buy_price']} -> USDT {sp} = {pnl*100:+.2f}%")
            elif b_open or s_open:
                lvl["stage"] = "sell" if s_open else "buy"
                active_levels.append(lvl)

        self.core.state.grid_levels = active_levels
        for pnl in filled_updates:
            self.core.update_kelly(pnl)

        active_count = len(active_levels)
        max_grid = equity * MAX_DEPLOYED
        remaining = max(0, max_grid - deployed)
        avail = min(remaining, quote)
        per_level = avail / levels if levels > 0 else 0

        if SHADOW_MODE:
            per_level *= SHADOW_FACTOR

        if active_count < levels and per_level >= MIN_ORDER_USDT and quote >= per_level:
            bb = price * (1 - spread)
            for i in range(active_count, levels):
                bp = self.eng.round_price(bb * (1 - spread * i))
                if bp <= 0:
                    continue
                sp = self.eng.round_price(bp * (1 + spread + effective_tp))
                amt = self.eng.round_amount(per_level / bp)
                if amt <= 0:
                    continue
                notional = amt * bp
                if notional < MIN_ORDER_USDT:
                    continue
                try:
                    bo = {"id": f"shadow-buy-{i}"} if SHADOW_MODE else \
                         self.eng.create_limit_buy_order(SYMBOL, amt, bp)
                    if bo:
                        lvl = {
                            "buy_order_id": bo.get("id"), "order_id": bo.get("id"),
                            "buy_price": bp, "sell_price": sp, "amount": amt,
                            "stage": "buy", "time": datetime.now().isoformat(),
                            "actual_cost": notional,
                        }
                        self.core.state.grid_levels.append(lvl)
                        log.info(f"GRID BUY {len(self.core.state.grid_levels)}/{levels} USDT {bp} amt {amt} ({notional:.2f}) TP={effective_tp*100:.1f}%")
                except MexcPermanentError:
                    return
                except Exception as e:
                    log.error(f"BUY failed (level {i}): {e}")

    def _log_perf(self) -> None:
        now = time.time()
        if now - self._last_perf_log < 300:
            return
        self._last_perf_log = now
        p = self.core.state.perf
        log.info("-" * 60)
        log.info(f"PERF: Trades={p.total_trades} WR={p.win_rate*100:.0f}% "
                 f"Sharpe={p.sharpe_ratio:.2f} Sortino={p.sortino_ratio:.2f}")
        log.info(f"PERF: Kelly={self.core.kelly_fraction*100:.0f}% "
                 f"SizeMult={self.core.state.sizing_multiplier:.2f}")
        log.info("-" * 60)


def main() -> None:
    for w in validate_config():
        log.warning(f"Config warning: {w}")
    log.info(f"Starting Denaro MEXC v5 | {SYMBOL} | {mode_label()} | CAPITAL={CAPITAL} | LEVELS={LEVELS}")

    notify_startup(SYMBOL, mode_label(), CAPITAL)

    env = {}
    for p in [Path(__file__).parent / ".env", Path.home() / "denaro" / ".env", Path(".env")]:
        if p.exists():
            env = load_env(str(p))
            if env:
                break
    api_key = os.environ.get("MEXC_API_KEY") or env.get("MEXC_API_KEY", "")
    api_secret = os.environ.get("MEXC_API_SECRET") or env.get("MEXC_API_SECRET", "")
    if not api_key or not api_secret:
        log.critical("MEXC_API or MEXC_SECRET not found"); sys.exit(1)

    if MOCK_MODE:
        from mock_runner import MockKrakenEngine
        engine = MockKrakenEngine(initial_eur=CAPITAL)
        log.info("MOCK_MODE enabled")
    else:
        try:
            engine = MexcEngine(api_key, api_secret, symbol=SYMBOL)
        except MexcPermanentError as e:
            log.critical(f"MEXC credentials invalid: {e}")
            sys.exit(1)
        except Exception as e:
            log.critical(f"Engine init: {e}"); sys.exit(1)

    max_dd = float(os.environ.get("MAX_DRAWDOWN_PCT", "15.0")) / 100.0
    max_dl = float(os.environ.get("MAX_DAILY_LOSS_PCT", "5.0")) / 100.0
    max_cl = int(os.environ.get("MAX_CONSECUTIVE_LOSSES", "4"))
    compound = float(os.environ.get("COMPOUND_RATIO", "0.5"))
    core = DenaroCore(
        initial_capital=CAPITAL,
        daily_loss_limit=max_dl,
        max_drawdown_limit=max_dd,
        max_consecutive_losses=max_cl,
        compound_ratio=compound,
        state_path=CORE_STATE_FILE,
    )
    log.info(f"Core loaded: {CORE_STATE_FILE} | DD={max_dd*100:.0f}% DL={max_dl*100:.0f}% CL={max_cl}")

    if not MOCK_MODE:
        try:
            engine.cancel_all_orders(SYMBOL)
            log.info("Orphan orders cancelled")
        except Exception as e:
            log.warning(f"Cancel orphans: {e}")

    # VaR Hydration (Task 1.2)
    try:
        ohlcv = engine.fetch_ohlcv(SYMBOL, timeframe="1m", limit=50)
        closes = [c[4] for c in ohlcv if isinstance(c, (list, tuple)) and len(c) > 4]
        core.hydrate_var_buffer(closes)
        log.info(f"VaR buffer hydrated with {len(closes)} historical prices")
    except Exception as e:
        log.warning(f"VaR hydration skipped: {e}")

    grid = TradingEngine(engine, core)
    cycle = 0
    deep_sleep = False
    shutdown = {"flag": False}

    def _handle(sig, frame):
        if shutdown["flag"]:
            sys.exit(1)
        log.info(f"Signal {sig} — shutdown...")
        shutdown["flag"] = True
    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, _handle)

    while not shutdown["flag"]:
        cycle += 1
        cycle_ok = False

        if deep_sleep:
            log.info(f"DEEP SLEEP — checking every {LOCKOUT_RETRY_INTERVAL}s")
            for _ in range(int(LOCKOUT_RETRY_INTERVAL)):
                if shutdown["flag"]:
                    break
                time.sleep(1)
            try:
                price = engine.fetch_ticker(SYMBOL)
                if price > 0:
                    deep_sleep = False
                    log.info("DEEP SLEEP: exchange responsive")
            except Exception:
                continue
            health_write()
            continue

        try:
            grid.run()
            cycle_ok = True
            grid._error_count = 0
            grid._consecutive_api_failures = 0
        except MexcPermanentError as e:
            log.critical(f"PERMANENT ERROR: {e} — shutdown")
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            grid._error_count += 1
            grid._consecutive_api_failures += 1
            log.error(f"Cycle {cycle}: {e}")
            if grid._error_count >= 3:
                if grid._consecutive_api_failures >= DEEP_SLEEP_CYCLES:
                    deep_sleep = True
                    log.warning(f"Entering DEEP SLEEP")
                time.sleep(min(COOLDOWN * 3, 120))
                continue

        for _ in range(int(min(COOLDOWN, 5))):
            if shutdown["flag"]:
                break
            time.sleep(1)

    try:
        engine.cancel_all_orders(SYMBOL)
    except Exception:
        pass
    try:
        core.flush_state()
    except Exception:
        pass
    if hasattr(engine, "close"):
        engine.close()
    log.info("MEXC Denaro shut down.")

if __name__ == "__main__":
    main()

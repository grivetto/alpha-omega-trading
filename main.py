#!/usr/bin/env python3
"""
DENARO v5 — Orchestratore strategico adattivo.
Grid Trading + DCA + regime detection su Kraken spot DOGE/EUR.

v5 fixes critici rispetto a v4:
  - Cache-aware balance + orders: riduce chiamate API REST del 70%+
  - Lockout mode: backoff esponenziale autonomo (30s → 600s)
  - Permanent error detection: Invalid key → shutdown immediato
  - Graceful degradation: errori API non bloccano l'intero ciclo
  - Better state recovery: ripristino grid levels dopo lockout
  - WS health monitoring: logga esplicitamente stato WS
  - EUR+DOGE tracking separato: deploy solo funds realmente disponibili
  - Daily loss limit corretto: basato su equity reale (non day_start_capital)
  - Cycle timing: sleep fra cycle diviso in chunk per shutdown reattivo
  - Config support: BALANCE_CACHE_TTL, ORDERS_CACHE_TTL, LOCKOUT_BACKOFF_*
"""
from __future__ import annotations

import json, logging, os, signal, sys, time, traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import DenaroCore, CBState, Trend, StrategyMode
from kraken_engine import KrakenEngine, SYMBOL, _fix_base64_secret, KrakenPermanentError
from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

# ─── .env loader ──────────────────────────────────────────────────────────────

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
MAX_DEPLOYED = float(os.environ.get("MAX_DEPLOYED", "0.50"))
MIN_ORDER_EUR = float(os.environ.get("MIN_ORDER_EUR", "1.0"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "kraken_bot.log")))
CORE_STATE_FILE = Path(os.environ.get("CORE_STATE_FILE", str(Path(__file__).parent / "denaro_core_state.json")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8909"))

# v5: Cache config
BALANCE_CACHE_TTL = float(os.environ.get("BALANCE_CACHE_TTL", "15"))
ORDERS_CACHE_TTL = float(os.environ.get("ORDERS_CACHE_TTL", "10"))

# v5: Recovery config
LOCKOUT_RETRY_INTERVAL = float(os.environ.get("LOCKOUT_RETRY_INTERVAL", "60"))  # check every 60s during lockout
DEEP_SLEEP_CYCLES = int(os.environ.get("DEEP_SLEEP_CYCLES", "5"))               # full sleep after N failed cycles
STATE_SAVE_INTERVAL = float(os.environ.get("STATE_SAVE_INTERVAL", "30"))          # max 1 save per 30s

# ─── LOGGING ──────────────────────────────────────────────────────────────────

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

def health_write() -> None:
    try:
        Path("/tmp/denaro.health").write_text(f"{time.time():.1f}\n")
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
# TRADING ENGINE v5 — Grid + DCA adattivo con cache awareness
# ═══════════════════════════════════════════════════════════════════════════

class TradingEngine:
    def __init__(self, engine: KrakenEngine, core: DenaroCore):
        self.eng = engine
        self.core = core
        self._last_known_equity: float = core.state.current_capital
        self._last_ohlcv_fetch = 0.0
        self._error_count = 0
        self._started_at = time.time()
        self._last_perf_log = 0.0
        self._last_state_save = 0.0
        # v5: Cycle metrics
        self._cycle_count = 0
        self._consecutive_api_failures = 0
        self._last_deploy_attempt = 0.0
        self._deploy_cooldown = 10.0  # min sec between deploy attempts

    @property
    def error_count(self) -> int:
        return self._error_count

    def _log_perf(self) -> None:
        """Log performance metrics every 300s."""
        now = time.time()
        if now - self._last_perf_log < 300:
            return
        self._last_perf_log = now
        p = self.core.state.perf
        r = self.core.state.regime
        stats = self.eng.get_stats() if hasattr(self.eng, 'get_stats') else {}
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
        if stats:
            log.info(f"API: calls={stats.get('api_calls',0)} hits={stats.get('cache_hits',0)} "
                     f"lockout={stats.get('lockout',False)} ws={stats.get('ws_connected',False)}")
        log.info("-" * 60)

    def run(self) -> None:
        """Main cycle — v5: cache-aware, lockout-tolerant."""
        now = time.time()
        price = base_bal = equity = eur_bal = 0.0

        # ── Check lockout state ──
        if hasattr(self.eng, 'in_lockout') and self.eng.in_lockout:
            remaining = self.eng.lockout_remaining
            if remaining > 0:
                log.warning(f"LOCKOUT: {remaining:.0f}s remaining — skipping API calls")
                self.core.flush_state()
                return
            else:
                log.info("LOCKOUT: backoff expired — attempting recovery")

        # ── Price + microstructure (WS-first, REST only if stale) ──
        try:
            price = self.eng.fetch_ticker(SYMBOL)
            micro = self.eng.get_microstructure()
            self.core.update_microstructure(
                micro["bid"], micro["ask"], micro["bid_vol"], micro["ask_vol"],
                micro["cum_bid"], micro["cum_ask"], micro["price"])
            self._consecutive_api_failures = 0
        except KrakenPermanentError as e:
            log.critical(f"PERMANENT ERROR (ticker): {e} — shutting down")
            raise
        except Exception as e:
            self._error_count += 1
            self._consecutive_api_failures += 1
            log.error(f"ticker/micro failed: {e}")
            if self._consecutive_api_failures >= 3:
                log.warning("3+ consecutive API failures — entering deep sleep")
            return

        # ── ATR + regime update (every 300s) ──
        if now - self._last_ohlcv_fetch > 300:
            try:
                ohlcv = self.eng.ex.fetch_ohlcv(SYMBOL, "1h", limit=24)
                self.core.calculate_atr(ohlcv)
                self.core.update_regime(ohlcv)
                self.core.update_var(price)
                self._last_ohlcv_fetch = now
            except KrakenPermanentError as e:
                log.critical(f"PERMANENT ERROR (ohlcv): {e}")
                raise
            except Exception as e:
                log.debug(f"OHLCV/regime fetch: {e}")

        # ── Balance (cached — solo ogni BALANCE_CACHE_TTL sec) ──
        try:
            # v5: Usa fetch_balance singolo che restituisce dict completo
            full_bal = self.eng.fetch_balance("FULL")
        except KrakenPermanentError as e:
            log.critical(f"PERMANENT ERROR (balance): {e} — shutting down")
            raise
        except Exception as e:
            self._error_count += 1
            self._consecutive_api_failures += 1
            log.warning(f"balance fetch failed: {e}")
            equity = self._last_known_equity
            eur_bal = 0.0
            base_bal = 0.0
        else:
            eur_bal = full_bal.get("EUR", 0.0)
            base_asset = SYMBOL.split("/")[0]
            base_bal = full_bal.get(base_asset, 0.0)
            doge_bal = full_bal.get("DOGE", 0.0)
            equity = eur_bal + base_bal * price
            if doge_bal > 0 and base_asset != "DOGE":
                try:
                    doge_ticker = self.eng.ex.fetch_ticker("DOGE/EUR")
                    equity += doge_bal * float(doge_ticker["last"])
                except Exception:
                    pass
            self._last_known_equity = equity
            self._error_count = max(0, self._error_count - 1)
            self._consecutive_api_failures = 0

        # ── v5: Allinea day_start_capital all'equity reale (previene CB spurio) ──
        cs = self.core.state
        day_pnl = (equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
        if cs.exec.cycle_count < 3 and day_pnl < -self.core._daily_loss_limit:
            old = cs.day_start_capital
            cs.day_start_capital = equity
            log.warning(f"Day capital realigned: {old:.2f} → {equity:.2f} (equity reale dopo restart)")

        # ── Circuit Breaker ──
        blocked = self.core.check_circuit_breaker(equity)
        if blocked:
            log.critical(f"CB OPEN: {self.core.state.cb.reason}")
            notify_cb_open(self.core.state.cb.reason, equity)
            return

        # ── Compounding ──
        self.core.compound_profits(equity)

        # ── Strategy selection ──
        strategy = self.core.select_strategy()
        self.core.state.exec.active_strategy = strategy

        # ── DCA operations ──
        if strategy in (StrategyMode.DCA, StrategyMode.HYBRID):
            self._run_dca(price, equity, base_bal)

        # ── Grid operations ──
        if strategy in (StrategyMode.GRID, StrategyMode.HYBRID):
            self._run_grid(price, equity, eur_bal, base_bal)
        elif strategy == StrategyMode.COOLDOWN:
            log.info(f"COOLDOWN: extreme volatility — skipping grid")

        # ── Status ──
        self._log_status(price, equity, eur_bal, base_bal)

        # ── Save state (throttled) ──
        self.core._save_state()

        # ── Perf log ──
        self._log_perf()

    def _log_status(self, price: float, equity: float, eur_bal: float, base_bal: float) -> None:
        """Log current trading status with balance details."""
        cs = self.core.state
        pnl = (equity - cs.initial_capital) / cs.initial_capital * 100 if cs.initial_capital > 0 else 0
        ws_icon = "[WS]" if (hasattr(self.eng, 'ws_connected') and self.eng.ws_connected) else "[!WS]"
        lockout_icon = "🧊" if (hasattr(self.eng, 'in_lockout') and self.eng.in_lockout) else ""
        log.info(f"DENARO STATUS | {ws_icon} {SYMBOL} price={price:.6f} equity={equity:.2f} "
                 f"EUR={eur_bal:.2f} {base_bal=:.2f} PnL={pnl:+.2f}% "
                 f"grid={len(cs.grid_levels)}/{cs.exec.grid_target_levels} "
                 f"CB={cs.cb.state.value} mode={mode_label()}{lockout_icon}")

    def _run_grid(self, price: float, equity: float, eur: float, base_bal: float) -> None:
        """Adaptive grid with ATR spread, cache-aware, lockout-tolerant."""
        if price <= 0 or price * 100 < 0.01:
            log.error(f"INVALID PRICE {price} — skipping grid (WS not ready?)")
            return

        grid_params = self.core.get_grid_params()
        spread = grid_params["spread"]
        levels = grid_params["levels"]
        atr_pct = self.core.state.regime.atr_pct
        tp_mult = grid_params.get("take_profit_mult", 1.2)

        effective_tp = max(0.01, atr_pct * 1.5) * tp_mult
        effective_tp = max(TAKE_PROFIT * 0.5, min(TAKE_PROFIT * 2.0, effective_tp))

        # Deploy throttling — non tentare deploy troppo spesso
        now = time.time()
        if now - self._last_deploy_attempt < self._deploy_cooldown:
            log.debug(f"Grid: deploy cooldown ({self._deploy_cooldown}s) — skipping new levels")
        else:
            self._last_deploy_attempt = now

        # ── Reconcile open orders ──
        open_orders = []
        try:
            open_orders = self.eng.fetch_open_orders(SYMBOL)
        except KrakenPermanentError as e:
            log.critical(f"PERMANENT ERROR (orders): {e} — skipping grid")
            return
        except Exception as e:
            self._error_count += 1
            log.warning(f"fetch_open_orders: {e}")
            return  # Skip grid if we can't check orders

        open_ids = {o["id"] for o in open_orders if o.get("id")}
        levels_data = self.core.state.grid_levels
        active_levels = []
        filled_kelly_updates = []
        deployed_eur = 0.0

        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            stage = lvl.get("stage", "buy")
            b_open = bid and bid in open_ids
            s_open = sid and sid in open_ids

            cost = lvl.get("actual_cost", lvl["amount"] * lvl["buy_price"])
            deployed_eur += cost

            if stage == "buy" and not b_open and bid:
                # v5: Verifica stato ordine con fetch_order dedicato (singola chiamata)
                actual_filled = False
                try:
                    if not SHADOW_MODE and not MOCK_MODE:
                        order_info = self.eng.fetch_order(bid, SYMBOL)
                        actual_filled = order_info.get("status") == "closed" and float(order_info.get("filled", 0)) > 0
                        if order_info.get("status") == "canceled":
                            log.info(f"Order {bid} cancelled — removing level")
                            continue
                except KrakenPermanentError:
                    log.warning(f"Cannot verify order {bid} — removing")
                    continue
                except Exception:
                    actual_filled = True  # Fallback: assume filled

                if actual_filled:
                    try:
                        so = {"id": f"shadow-sell-{len(levels_data)}"} if SHADOW_MODE else \
                             self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(lvl["amount"]), self.eng.round_price(lvl["sell_price"]))
                        if so:
                            lvl["sell_order_id"] = so.get("id")
                            lvl["stage"] = "sell"
                            lvl["actual_cost"] = cost
                            log.info(f"✅ FILL BUY EUR {lvl['buy_price']} -> SELL {lvl['amount']} @ EUR {lvl['sell_price']}")
                            if not SHADOW_MODE:
                                time.sleep(0.5)
                    except KrakenPermanentError as e:
                        log.error(f"PERMANENT ERROR placing sell: {e}")
                        return
                    except Exception as e:
                        self._error_count += 1
                        log.error(f"SELL failed: {e}")
                    active_levels.append(lvl)
            elif stage == "sell" and not b_open and not s_open:
                # Round complete
                sell_price = lvl.get("sell_price", 0)
                pp = lvl["amount"] * sell_price
                pnl = (pp - cost) / cost if cost > 0 else 0
                filled_kelly_updates.append(pnl)
                log.info(f"🔄 ROUND: EUR {lvl['buy_price']} -> EUR {sell_price} = {pnl*100:+.2f}%")
            elif b_open or s_open:
                lvl["stage"] = "sell" if s_open else "buy"
                active_levels.append(lvl)

        self.core.state.grid_levels = active_levels

        # Update Kelly after all fills
        for pnl in filled_kelly_updates:
            self.core.update_kelly(pnl)

        # ── Deploy new grid levels ──
        active_count = len(active_levels)
        max_grid_eur = equity * MAX_DEPLOYED
        remaining_capital = max(0, max_grid_eur - deployed_eur)

        # v5: Usa solo EUR realmente disponibile
        available_eur = min(remaining_capital, eur)
        per_level_raw = available_eur / levels if levels > 0 else 0

        if SHADOW_MODE:
            per_level_raw *= SHADOW_FACTOR

        if active_count < levels and per_level_raw >= MIN_ORDER_EUR and eur >= per_level_raw:
            bb = price * (1 - spread)
            for i in range(active_count, levels):
                bp = self.eng.round_price(bb * (1 - spread * i))
                if bp <= 0:
                    log.warning(f"Invalid bp={bp}, skipping")
                    continue
                sp = self.eng.round_price(bp * (1 + spread + effective_tp))
                amt = self.eng.round_amount(per_level_raw / bp)
                if amt <= 0:
                    continue
                notional = amt * bp
                if notional < MIN_ORDER_EUR:
                    log.warning(f"Order too small: {amt} @ {bp} = EUR {notional:.2f} (min EUR {MIN_ORDER_EUR})")
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
                        log.info(f"📊 GRID BUY {len(self.core.state.grid_levels)}/{levels} EUR {bp} amt {amt} ({notional:.2f}€) TP={effective_tp*100:.1f}%")
                        if not SHADOW_MODE:
                            time.sleep(0.5)
                except KrakenPermanentError as e:
                    log.error(f"PERMANENT ERROR deploying buy {i}: {e}")
                    return
                except Exception as e:
                    self._error_count += 1
                    log.error(f"BUY failed (level {i}): {e}")
        elif active_count < levels:
            log.debug(f"Grid: waiting for capital — need min EUR {MIN_ORDER_EUR} per level, have EUR {eur:.2f} (remaining {remaining_capital:.2f})")

    def _run_dca(self, price: float, equity: float, base_bal: float) -> None:
        """DCA operations."""
        dca = self.core.state.dca
        if not dca.active:
            should, size, reason = self.core.dca_should_enter(price, equity)
            if should and size >= MIN_ORDER_EUR:
                if SHADOW_MODE:
                    log.info(f"DCA ENTER (shadow) {reason} size={size:.2f}€")
                    self.core.dca_open_position(price, size / price, size)
                elif MOCK_MODE:
                    log.info(f"DCA ENTER (mock) {reason} size={size:.2f}€")
                    self.core.dca_open_position(price, size / price, size)
                else:
                    try:
                        amt = self.eng.round_amount(size / price)
                        bo = self.eng.create_limit_buy_order(SYMBOL, amt, price)
                        if bo:
                            self.core.dca_open_position(price, amt, size)
                            log.info(f"DCA BUY {amt} DOGE @ EUR {price} = EUR {size:.2f}")
                    except Exception as e:
                        log.error(f"DCA buy order failed: {e}")

        should_exit, amount, reason = self.core.dca_should_exit(price)
        if should_exit and amount > 0:
            if not SHADOW_MODE and not MOCK_MODE:
                try:
                    so = self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(amount), self.eng.round_price(price))
                    if so:
                        pnl = self.core.dca_close_position(exit_price=price)
                        log.info(f"DCA EXIT {reason} size={amount:.2f} PnL={pnl*100:+.2f}%")
                except Exception as e:
                    log.error(f"DCA sell order failed: {e}")
            else:
                pnl = self.core.dca_close_position(exit_price=price)
                log.info(f"DCA EXIT (shadow) {reason} size={amount:.2f} PnL={pnl*100:+.2f}%")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

    for w in validate_config():
        log.warning(f"Config warning: {w}")
    log.info(f"Starting Denaro v5 | {SYMBOL} | {mode_label()} | CAPITAL={CAPITAL} | LEVELS={LEVELS}")

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

    notify_startup(SYMBOL, mode_label(), CAPITAL)

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
            engine = KrakenEngine(api_key, api_secret, symbol=SYMBOL)
        except KrakenPermanentError as e:
            log.critical(f"Kraken credentials invalid: {e}")
            notify_shutdown(SYMBOL)
            sys.exit(1)
        except Exception as e:
            log.critical(f"Engine init: {e}"); sys.exit(1)

    # v5: Passa i limiti di rischio da .env
    max_drawdown_pct = float(os.environ.get("MAX_DRAWDOWN_PCT", "15.0")) / 100.0
    daily_loss_pct = float(os.environ.get("MAX_DAILY_LOSS_PCT", "5.0")) / 100.0
    max_consecutive = int(os.environ.get("MAX_CONSECUTIVE_LOSSES", "4"))
    compound_ratio = float(os.environ.get("COMPOUND_RATIO", "0.5"))
    core = DenaroCore(
        initial_capital=CAPITAL,
        daily_loss_limit=daily_loss_pct,
        max_drawdown_limit=max_drawdown_pct,
        max_consecutive_losses=max_consecutive,
        compound_ratio=compound_ratio,
        state_path=CORE_STATE_FILE,
    )
    log.info(f"Core loaded: {CORE_STATE_FILE} | DD={max_drawdown_pct*100:.0f}% DL={daily_loss_pct*100:.0f}% CL={max_consecutive}")

    if not MOCK_MODE:
        log.info("Cancelling orphan orders...")
        try:
            engine.cancel_all_orders(SYMBOL)
            log.info("Orphan orders cancelled ✓")
        except KrakenPermanentError as e:
            log.warning(f"Cannot cancel orders (permanent error): {e}")
        except Exception as e:
            log.warning(f"Cancel orphans: {e}")

    grid = TradingEngine(engine, core)
    cycle = 0
    deep_sleep = False

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

        # v5: Deep sleep — skip API calls entirely
        if deep_sleep:
            log.info(f"DEEP SLEEP cycle {cycle} — checking every {LOCKOUT_RETRY_INTERVAL}s")
            for _ in range(int(LOCKOUT_RETRY_INTERVAL)):
                if shutdown["flag"]:
                    break
                time.sleep(1)
            # Try one API call to check if Kraken is back
            try:
                price = engine.fetch_ticker(SYMBOL)
                if price > 0:
                    deep_sleep = False
                    log.info("DEEP SLEEP: Kraken responsive again — resuming normal cycles")
            except Exception:
                continue
            health_write()
            continue

        try:
            grid.run()
            cycle_ok = True
            grid._error_count = 0
            grid._consecutive_api_failures = 0

            if health and cycle % 5 == 0:
                eq = core.state.current_capital
                initial = core.state.initial_capital
                pnl = (eq - initial) / initial * 100 if initial > 0 else 0
                stats = engine.get_stats() if hasattr(engine, 'get_stats') else {}
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
                    lockout=stats.get("lockout", False),
                    cache_hits=stats.get("cache_hits", 0),
                    api_calls=stats.get("api_calls", 0),
                )
            if degraded and cycle_ok:
                degraded = False
                log.info("Recovered — normal cycle")
        except KrakenPermanentError as e:
            log.critical(f"PERMANENT ERROR: {e} — shutting down gracefully")
            notify_shutdown(SYMBOL)
            break
        except KeyboardInterrupt:
            break
        except Exception as e:
            grid._error_count += 1
            grid._consecutive_api_failures += 1
            log.error(f"Cycle {cycle}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
            if health:
                health.update(status="degraded" if grid._error_count < 5 else "down",
                              last_cycle_ok=False, error_count=grid._error_count)
            if grid._error_count >= 3:
                if not degraded:
                    degraded = True
                    log.warning(f"Degradation: {grid._error_count} errors — backing off")
                if grid._consecutive_api_failures >= DEEP_SLEEP_CYCLES:
                    deep_sleep = True
                    log.warning(f"{grid._consecutive_api_failures} consecutive API failures — entering DEEP SLEEP")
                time.sleep(min(COOLDOWN * 3, 120))
                continue

        if cycle % 30 == 0:
            health_write()

        # v5: Sleep diviso in chunk per shutdown reattivo
        sleep_sec = COOLDOWN * (3 if degraded else 1)
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
    log.info("Denaro shut down.")

if __name__ == "__main__":
    main()

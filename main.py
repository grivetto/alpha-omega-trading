#!/usr/bin/env python3
"""
DENARO v4 — Orchestratore strategico adattivo.
Grid Trading + DCA + regime detection su Kraken spot DOGE/EUR.

v4 rispetto a v3:
  - Grid buy base usa spread ATR (non hardcoded 2%)
  - Import tutti in testa (zero lazy import nel loop)
  - Config reading centralizzato
  - _save_state throttled (max 1x/30s)
  - Gestione errori più pulita
"""
from __future__ import annotations

import json, logging, os, signal, sys, time, traceback
from datetime import datetime
from pathlib import Path
from logging.handlers import RotatingFileHandler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from denaro_core import DenaroCore, CBState, Trend, StrategyMode
from kraken_engine import KrakenEngine, SYMBOL, _fix_base64_secret
from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

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
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))  # v4.1: overridden by ATR scaling below
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
MAX_DEPLOYED = float(os.environ.get("MAX_DEPLOYED", "0.50"))  # v4.1: max 50% of capital in grid
MIN_ORDER_EUR = float(os.environ.get("MIN_ORDER_EUR", "1.0")) # Kraken min notional ~1 EUR
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
SHADOW_FACTOR = float(os.environ.get("SHADOW_FACTOR", "0.10"))
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "kraken_bot.log")))
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
# TRADING ENGINE v4 — Grid + DCA adattivo
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
        """Log performance metrics every 300s."""
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
        eur = base_bal = price = equity = 0.0

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

        # ── Equity (totale: EUR + DOGE residue + asset corrente) ──
        try:
            eur = self.eng.fetch_balance("EUR")
            bal = self.eng.ex.fetch_balance()
            base_asset = SYMBOL.split("/")[0]
            base_bal = float(bal.get("total", {}).get(base_asset, 0) or 0)
            # Conta anche asset residui (es. DOGE rimasto da swap precedente)
            doge = float(bal.get("total", {}).get("DOGE", 0) or 0)
            equity = eur + base_bal * price
            if doge > 0 and base_asset != "DOGE":
                try:
                    doge_ticker = self.eng.ex.fetch_ticker("DOGE/EUR")
                    equity += doge * float(doge_ticker["last"])
                except Exception:
                    pass
            self._last_known_equity = equity
            self._error_count = max(0, self._error_count - 1)
        except Exception as e:
            self._error_count += 1
            equity = self._last_known_equity
            log.warning(f"balance fetch failed: {e} — using last known equity EUR {equity:.2f}")

        # ── v4.1: Allinea day_start_capital all'equity reale al primo ciclo ──
        # Previene CB spurio dopo restart con stato vecchio
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

        # ── DCA operations (if HYBRID or DCA mode) ──
        if strategy in (StrategyMode.DCA, StrategyMode.HYBRID):
            self._run_dca(price, equity, base_bal)

        # ── Grid operations (if GRID or HYBRID) ──
        if strategy in (StrategyMode.GRID, StrategyMode.HYBRID):
            self._run_grid(price, equity, eur, base_bal)
        elif strategy == StrategyMode.COOLDOWN:
            log.info(f"COOLDOWN: extreme volatility — skipping grid")

        # ── Status ──
        self._log_status(price, equity, eur)

        # ── Save unified state ──
        self.core._save_state()

        # ── Perf log ──
        self._log_perf()

    def _run_grid(self, price: float, equity: float, eur: float, base_bal: float) -> None:
        """Adaptive grid strategy with ATR-based spread (v4.1 fix: prezzo valido, ATR TP, min notional)."""
        # ── v4.1: Price validation ──
        if price <= 0 or price * 100 < 0.01:  # Prezzo realistico (non 0, non 2.4e-06)
            log.error(f"INVALID PRICE {price} — skipping grid deployment (probably WS not ready)")
            return

        grid_params = self.core.get_grid_params()
        spread = grid_params["spread"]
        levels = grid_params["levels"]
        atr_pct = self.core.state.regime.atr_pct
        tp_mult = grid_params.get("take_profit_mult", 1.2)

        # v4.1: ATR-scaled take-profit (non hardcoded 3%)
        effective_tp = max(0.01, atr_pct * 1.5) * tp_mult
        effective_tp = max(TAKE_PROFIT * 0.5, min(TAKE_PROFIT * 2.0, effective_tp))
        log.debug(f"Grid: price={price:.6f} spread={spread*100:.2f}% TP={effective_tp*100:.2f}% levels={levels}")

        # v4.1: Max deployed capital
        deployed_eur = sum(
            lvl.get("amount", 0) * lvl.get("buy_price", 0)
            for lvl in self.core.state.grid_levels
        )
        max_grid_eur = equity * MAX_DEPLOYED
        remaining_capital = max(0, max_grid_eur - deployed_eur)

        # v4.1: Grid usa allocazione diretta (non Kelly/CB sizing).
        # I limit order grid NON sono posizioni aperte — si riempiono solo se
        # il mercato li raggiunge. Kelly/CB sizing è per posizioni market/entry.
        per_level_raw = remaining_capital / levels
        if SHADOW_MODE:
            per_level_raw *= SHADOW_FACTOR

        # ── Reconcile open orders ──
        open_orders = []
        try:
            open_orders = self.eng.fetch_open_orders(SYMBOL)
        except Exception as e:
            self._error_count += 1
            log.warning(f"fetch_open_orders: {e}")
        open_ids = {o["id"] for o in open_orders if o.get("id")}
        levels_data = self.core.state.grid_levels
        active_levels = []

        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            stage = lvl.get("stage", "buy")
            b_open = bid and bid in open_ids
            s_open = sid and sid in open_ids

            if stage == "buy" and not b_open and bid:
                # Buy was filled — place sell
                if SHADOW_MODE or base_bal >= lvl["amount"] * 0.5:
                    try:
                        so = {"id": f"shadow-sell-{len(levels_data)}"} if SHADOW_MODE else \
                             self.eng.create_limit_sell_order(SYMBOL, self.eng.round_amount(lvl["amount"]), self.eng.round_price(lvl["sell_price"]))
                        if so:
                            lvl["sell_order_id"] = so.get("id")
                            lvl["stage"] = "sell"
                            log.info(f"FILL BUY EUR {lvl['buy_price']} -> SELL {lvl['amount']} @ EUR {lvl['sell_price']}")
                            if not SHADOW_MODE:
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
                # v4.1: Update grid deployed capital
                remaining_capital += cb
            elif b_open or s_open:
                lvl["stage"] = "sell" if s_open else "buy"
                active_levels.append(lvl)

        self.core.state.grid_levels = active_levels

        # ── Deploy new grid levels ──
        active_count = len(active_levels)
        per_level = per_level_raw if per_level_raw > 0 else (CAPITAL * MAX_DEPLOYED) / levels

        if active_count < levels and eur >= per_level and remaining_capital > MIN_ORDER_EUR:
            bb = price * (1 - spread)
            for i in range(active_count, levels):
                bp = self.eng.round_price(bb * (1 - spread * i))
                if bp <= 0:
                    log.warning(f"Invalid bp={bp} (price={price}, spread={spread}, i={i}), skipping grid level")
                    continue
                sp = self.eng.round_price(bp * (1 + spread + effective_tp))
                amt = self.eng.round_amount(per_level / bp)
                if amt <= 0:
                    continue
                # v4.1: Min notional check (Kraken ~1 EUR)
                notional = amt * bp
                if notional < MIN_ORDER_EUR:
                    log.warning(f"Order too small: {amt} @ {bp} = EUR {notional:.2f} (min EUR {MIN_ORDER_EUR}), skipping")
                    continue
                try:
                    bo = {"id": f"shadow-buy-{i}"} if SHADOW_MODE else \
                         self.eng.create_limit_buy_order(SYMBOL, amt, bp)
                    if bo:
                        lvl = {
                            "buy_order_id": bo.get("id"), "order_id": bo.get("id"),
                            "buy_price": bp, "sell_price": sp, "amount": amt,
                            "stage": "buy", "time": datetime.now().isoformat(),
                        }
                        self.core.state.grid_levels.append(lvl)
                        log.info(f"GRID BUY {len(self.core.state.grid_levels)}/{levels} EUR {bp} amt {amt} ({per_level:.2f}€) TP={effective_tp*100:.1f}%")
                        if not SHADOW_MODE:
                            time.sleep(0.5)
                except Exception as e:
                    self._error_count += 1
                    log.error(f"BUY failed (level {i}): {e}")

    def _run_dca(self, price: float, equity: float, base_bal: float) -> None:
        """DCA operations."""
        dca = self.core.state.dca
        if not dca.active:
            should, size, reason = self.core.dca_should_enter(price, equity)
            if should:
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
        if should_exit:
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

    def _log_status(self, price: float, equity: float, eur: float) -> None:
        """Log current trading status."""
        cs = self.core.state
        pnl = (equity - cs.initial_capital) / cs.initial_capital * 100 if cs.initial_capital > 0 else 0
        log.info(f"DENARO STATUS | {SYMBOL} price={price:.6f} equity={equity:.2f} "
                 f"EUR={eur:.2f} PnL={pnl:+.2f}% grid={len(cs.grid_levels)}/{cs.exec.grid_target_levels} "
                 f"CB={cs.cb.state.value} mode={mode_label()}")


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main() -> None:
    from notifier import notify as tg_notify, notify_startup, notify_shutdown, notify_cb_open, notify_cb_close

    for w in validate_config():
        log.warning(f"Config warning: {w}")
    log.info(f"Starting Denaro v4 | {SYMBOL} | {mode_label()} | CAPITAL={CAPITAL}")

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

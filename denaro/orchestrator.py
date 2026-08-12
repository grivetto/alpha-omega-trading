#!/usr/bin/env python3
"""Denaro v6 — zero-touch orchestrator.

One-cycle engine (`run()`) plus the resilient supervisor loop (`run_forever()`).

Cycle pipeline (v6):
  lockout → price/micro → regime (every OHLCV_INTERVAL) → balance → CB →
  compounding → dump-defense → strategy → DCA → grid (reconcile + retarget +
  deploy) → rebalance → status/health/state.

Supervisor: deep-sleep on API blackout, exponential error backoff, watchdog
(3 consecutive slow cycles → exit for systemd restart), graceful signals.
"""
from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime
from typing import Any, Dict, Optional

from .config import DenaroConfig
from .core import DenaroCore
from .exchange import ExchangeAdapter
from .grid import GridPolicy
from .rebalancer import Rebalancer
from .types import StrategyMode

log = logging.getLogger("kraken_v2")


def _is_permanent(e: Exception) -> bool:
    """Duck-typed permanent-error detection (exchange-agnostic)."""
    return type(e).__name__.endswith("PermanentError")


class DenaroOrchestrator:
    """Adaptive grid + DCA execution with zero-touch resilience."""

    def __init__(self, engine: Any, core: DenaroCore,
                 config: Optional[DenaroConfig] = None) -> None:
        self.eng = engine
        self.core = core
        self.cfg = config if config is not None else self._detect_config(engine)

        self.adapter = ExchangeAdapter(
            engine, self.cfg.symbol,
            shadow_mode=self.cfg.shadow_mode,
            mock_mode=self.cfg.mock_mode,
            min_order_eur=self.cfg.min_order_eur,
        )
        self.grid_policy = GridPolicy()
        self.rebalancer = Rebalancer(
            tolerance=self.cfg.rebalance_tolerance,
            interval_cycles=self.cfg.rebalance_interval,
            max_rebalance_pct=self.cfg.rebalance_max_pct,
            min_order_eur=self.cfg.min_order_eur,
        )

        # Cycle bookkeeping
        self._last_known_equity: float = core.state.current_capital
        self._last_ohlcv_fetch: float = 0.0
        self._error_count: int = 0
        self._started_at: float = time.time()
        self._last_perf_log: float = 0.0
        self._last_state_save: float = 0.0
        self._consecutive_api_failures: int = 0
        self._last_deploy_attempt: float = 0.0
        self._deploy_cooldown: float = 10.0
        self._dump_armed: bool = False
        self._last_cb_state: str = core.state.cb.state.value
        self._watchdog_trips: int = 0

    @staticmethod
    def _detect_config(engine: Any) -> DenaroConfig:
        """Config fallback: auto-detect mock engines so MOCK_MODE needs no env."""
        cfg = DenaroConfig.from_env()
        if type(engine).__name__ == "MockKrakenEngine" or hasattr(engine, "eur_balance"):
            cfg.mock_mode = True
            cfg.shadow_mode = False
        return cfg

    # ═══════════════════════════════════════════════════════════════════════
    # ONE CYCLE
    # ═══════════════════════════════════════════════════════════════════════

    def run(self) -> None:
        """Execute a single adaptive trading cycle (no-arg → mock_runner compat)."""
        t0 = time.perf_counter()
        now = time.time()
        cfg = self.cfg
        price = eur_bal = base_bal = equity = 0.0

        # ── Lockout protection ──
        if self.adapter.in_lockout:
            remaining = self.adapter.lockout_remaining
            if remaining > 0:
                log.warning(f"LOCKOUT: {remaining:.0f}s remaining — skipping API calls")
                self.core.flush_state()
                return
            log.info("LOCKOUT: backoff expired — attempting recovery")

        # ── Price + microstructure (WS-first, REST fallback) ──
        try:
            price = self.adapter.fetch_price()
            micro = self.adapter.fetch_microstructure()
            self.core.update_microstructure(
                micro.get("bid", 0), micro.get("ask", 0),
                micro.get("bid_vol", 0), micro.get("ask_vol", 0),
                micro.get("cum_bid", 0), micro.get("cum_ask", 0),
                micro.get("price", 0) or price)
            self._consecutive_api_failures = 0
        except Exception as e:
            if _is_permanent(e):
                log.critical(f"PERMANENT ERROR (ticker): {e}")
                raise
            self._error_count += 1
            self._consecutive_api_failures += 1
            log.error(f"ticker/micro failed: {e}")
            return

        # ── Regime refresh (throttled) ──
        if now - self._last_ohlcv_fetch >= cfg.ohlcv_interval:
            try:
                ohlcv = self.adapter.fetch_ohlcv("1h", limit=24)
                if ohlcv:
                    self.core.calculate_atr(ohlcv)
                    self.core.update_regime(ohlcv)
                    self.core.update_var(price)
                    self._last_ohlcv_fetch = now
            except Exception as e:
                if _is_permanent(e):
                    raise
                log.debug(f"OHLCV/regime fetch: {e}")

        # ── Balance (cached) ──
        try:
            full = self.adapter.fetch_full_balance()
            eur_bal = float(full.get("EUR", 0.0) or 0.0)
            base_bal = float(full.get(self.adapter.base_asset, 0.0) or 0.0)
            equity = eur_bal + base_bal * price
            self._last_known_equity = equity
            self._error_count = max(0, self._error_count - 1)
            self._consecutive_api_failures = 0
        except Exception as e:
            if _is_permanent(e):
                log.critical(f"PERMANENT ERROR (balance): {e}")
                raise
            self._error_count += 1
            self._consecutive_api_failures += 1
            log.warning(f"balance fetch failed: {e}")
            equity = self._last_known_equity

        # ── Realign day capital right after restart (prevents spurious CB) ──
        cs = self.core.state
        if cs.exec.cycle_count < 3 and equity > 0:
            day_pnl = (equity - cs.day_start_capital) / max(1e-10, cs.day_start_capital)
            if day_pnl < -self.core.risk.daily_loss_limit_effective(cs.regime):
                old = cs.day_start_capital
                cs.day_start_capital = equity
                log.warning(f"Day capital realigned: {old:.2f} → {equity:.2f} (post-restart equity)")

        # ── Circuit breaker + compounding ──
        blocked = self.core.check_circuit_breaker(equity)
        cb_state = cs.cb.state.value
        if cb_state != self._last_cb_state:
            self._notify_cb_transition(cb_state, cs.cb.reason, equity)
            self._last_cb_state = cb_state
        if blocked:
            log.critical(f"CB OPEN: {cs.cb.reason}")
            return

        self.core.compound_profits(equity)

        # ── Dump defense (cancel buys on dump entry) ──
        self._dump_defense()

        # ── Strategy selection ──
        strategy = self.core.select_strategy()
        cs.exec.active_strategy = strategy

        # ── DCA ──
        if strategy in (StrategyMode.DCA, StrategyMode.HYBRID):
            self._run_dca(price, equity)

        # ── Grid ──
        if strategy in (StrategyMode.GRID, StrategyMode.HYBRID):
            self._run_grid(price, equity, eur_bal)
        elif strategy == StrategyMode.COOLDOWN:
            log.info(f"COOLDOWN: extreme volatility or dump — grid frozen")

        # ── Rebalancing (zero-touch) ──
        self._maybe_rebalance(price, eur_bal, base_bal, equity)

        # ── Status / persistence ──
        self._log_status(price, equity, eur_bal, base_bal)
        self.core._save_state()
        self._log_perf()

        cs.exec.cycle_count += 1
        cs.exec.last_cycle_ms = (time.perf_counter() - t0) * 1000.0

    # ═══════════════════════════════════════════════════════════════════════
    # DCA
    # ═══════════════════════════════════════════════════════════════════════

    def _run_dca(self, price: float, equity: float) -> None:
        cfg = self.cfg
        dca = self.core.state.dca
        if not dca.active:
            should, size, reason = self.core.dca_should_enter(price, equity)
            if should and size >= cfg.min_order_eur:
                if cfg.shadow_mode or cfg.mock_mode:
                    log.info(f"DCA ENTER (sim) {reason} size={size:.2f}€")
                    self.core.dca_open_position(price, size / price, size)
                else:
                    try:
                        amt = self.adapter.round_amount(size / price)
                        bo = self.adapter.place_limit_buy(amt, self.adapter.round_price(price))
                        if bo:
                            self.core.dca_open_position(price, amt, size)
                            log.info(f"DCA BUY {amt} {self.cfg.symbol.split('/')[0]} @ EUR {price:.6f} = EUR {size:.2f}")
                    except Exception as e:
                        if _is_permanent(e):
                            raise
                        log.error(f"DCA buy order failed: {e}")

        should_exit, amount, reason = self.core.dca_should_exit(price)
        if should_exit and amount > 0:
            if cfg.shadow_mode or cfg.mock_mode:
                pnl = self.core.dca_close_position(exit_price=price)
                log.info(f"DCA EXIT (sim) {reason} size={amount:.2f} PnL={pnl * 100:+.2f}%")
            else:
                try:
                    so = self.adapter.place_limit_sell(
                        self.adapter.round_amount(amount), self.adapter.round_price(price))
                    if so:
                        pnl = self.core.dca_close_position(exit_price=price)
                        log.info(f"DCA EXIT {reason} size={amount:.2f} PnL={pnl * 100:+.2f}%")
                except Exception as e:
                    if _is_permanent(e):
                        raise
                    log.error(f"DCA sell order failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # GRID — reconcile → retarget → deploy
    # ═══════════════════════════════════════════════════════════════════════

    def _run_grid(self, price: float, equity: float, eur: float) -> None:
        cfg = self.cfg
        if price <= 0:
            log.error(f"INVALID PRICE {price} — skipping grid (WS not ready?)")
            return

        gp = self.core.get_grid_params()
        spread = gp["spread"]
        levels = gp["levels"]
        tp = gp["tp"]
        center = gp["center"] or price
        max_spend = gp["max_spend_pct"]

        # ── Reconcile open orders ──
        try:
            open_orders = self.adapter.fetch_open_orders()
        except Exception as e:
            if _is_permanent(e):
                raise
            self._error_count += 1
            log.warning(f"fetch_open_orders: {e}")
            return

        # Zero-touch: kill exchange orders we no longer track
        self.adapter.reconcile_orphans(self.core.state.grid_levels, open_orders)

        open_ids = {o.get("id") for o in open_orders if o.get("id")}
        levels_data = self.core.state.grid_levels
        active_levels: list = []
        filled_kelly_updates: list = []
        deployed_eur = 0.0
        retarget_ids: set = set()

        for lvl in levels_data:
            bid = lvl.get("buy_order_id") or lvl.get("order_id")
            sid = lvl.get("sell_order_id")
            stage = lvl.get("stage", "buy")
            b_open = bool(bid and bid in open_ids)
            s_open = bool(sid and sid in open_ids)

            cost = lvl.get("actual_cost", lvl.get("amount", 0.0) * lvl.get("buy_price", 0.0))
            deployed_eur += cost

            # Buy level drifted too far below price → retarget (re-deploy closer)
            if stage == "buy" and b_open and self.core.should_retarget_level(lvl, price, gp):
                retarget_ids.add(bid)
                try:
                    self.adapter.cancel_order(bid)
                    log.info(f"🎯 RETARGET: buy {bid} @ {lvl['buy_price']:.6f} stale — re-placing")
                except Exception as e:
                    log.warning(f"Retarget cancel failed {bid}: {e}")
                continue

            if stage == "buy" and not b_open and bid:
                # Verify fill (live only; sim assumes immediate fill)
                actual_filled = True
                if not cfg.shadow_mode and not cfg.mock_mode:
                    try:
                        info = self.adapter.fetch_order(bid)
                        actual_filled = (info.get("status") == "closed"
                                         and float(info.get("filled", 0)) > 0)
                        if info.get("status") == "canceled":
                            log.info(f"Order {bid} cancelled — removing level")
                            continue
                    except Exception as e:
                        if _is_permanent(e):
                            raise
                        log.warning(f"Cannot verify order {bid} — removing")
                        continue
                if actual_filled:
                    try:
                        so = self.adapter.place_limit_sell(
                            self.adapter.round_amount(lvl["amount"]),
                            self.adapter.round_price(lvl["sell_price"]))
                        if so:
                            lvl["sell_order_id"] = so.get("id")
                            lvl["stage"] = "sell"
                            lvl["actual_cost"] = cost
                            log.info(f"✅ FILL BUY EUR {lvl['buy_price']:.6f} -> SELL "
                                     f"{lvl['amount']} @ EUR {lvl['sell_price']:.6f}")
                            if not cfg.shadow_mode:
                                time.sleep(0.5)
                    except Exception as e:
                        if _is_permanent(e):
                            raise
                        self._error_count += 1
                        log.error(f"SELL failed: {e}")
                    active_levels.append(lvl)
            elif stage == "sell" and not b_open and not s_open:
                # Round complete
                sell_price = lvl.get("sell_price", 0)
                pp = lvl.get("amount", 0) * sell_price
                pnl = (pp - cost) / cost if cost > 0 else 0
                filled_kelly_updates.append(pnl)
                log.info(f"🔄 ROUND: EUR {lvl['buy_price']} -> EUR {sell_price} = {pnl * 100:+.2f}%")
            elif b_open or s_open:
                lvl["stage"] = "sell" if s_open else "buy"
                active_levels.append(lvl)

        self.core.state.grid_levels = active_levels

        for pnl in filled_kelly_updates:
            self.core.update_kelly(pnl)

        # ── Deploy new levels (vol-scaled budget, adaptive geometry) ──
        self._deploy_grid(price, equity, eur, gp, len(active_levels), deployed_eur, retarget_ids)

    def _deploy_grid(self, price: float, equity: float, eur: float, gp: dict,
                     active_count: int, deployed_eur: float, retarget_ids: set) -> None:
        cfg = self.cfg
        now = time.time()
        if now - self._last_deploy_attempt < self._deploy_cooldown:
            log.debug(f"Grid: deploy cooldown ({self._deploy_cooldown}s) — skipping new levels")
            return
        self._last_deploy_attempt = now

        levels = gp["levels"]
        spread = gp["spread"]
        tp = gp["tp"]
        center = gp["center"] or price
        max_spend = gp["max_spend_pct"]

        # Budget: vol-scaled exposure cap, only real available EUR, minus retargets
        max_grid_eur = equity * max_spend
        available_eur = min(max(0.0, max_grid_eur - deployed_eur), eur)
        per_level_raw = available_eur / levels if levels > 0 else 0.0
        if cfg.shadow_mode:
            per_level_raw *= cfg.shadow_factor

        need = levels - active_count
        if need <= 0 or per_level_raw < cfg.min_order_eur:
            log.debug(f"Grid: waiting for capital (need={need} per_level={per_level_raw:.2f}€)")
            return

        bb = center * (1 - spread)
        for i in range(active_count, levels):
            bp = self.adapter.round_price(bb * (1 - spread * (i - active_count)))
            if bp <= 0:
                log.warning(f"Invalid bp={bp}, skipping")
                continue
            sp = self.adapter.round_price(bp * (1 + spread + tp))
            amt = self.adapter.round_amount(per_level_raw / bp)
            if amt <= 0:
                continue
            notional = amt * bp
            if notional < cfg.min_order_eur:
                log.warning(f"Order too small: {amt} @ {bp} = EUR {notional:.2f} (min {cfg.min_order_eur}€)")
                continue
            try:
                bo = self.adapter.place_limit_buy(amt, bp)
                if bo:
                    lvl = {
                        "buy_order_id": bo.get("id"), "order_id": bo.get("id"),
                        "buy_price": bp, "sell_price": sp, "amount": amt,
                        "stage": "buy", "time": datetime.now().isoformat(),
                        "actual_cost": notional,
                    }
                    self.core.state.grid_levels.append(lvl)
                    self.core.state.exec.redeploy_count += 1
                    log.info(f"📊 GRID BUY {len(self.core.state.grid_levels)}/{levels} "
                             f"EUR {bp} amt {amt} ({notional:.2f}€) TP={tp * 100:.1f}%")
                    if not cfg.shadow_mode:
                        time.sleep(0.5)
            except Exception as e:
                if _is_permanent(e):
                    raise
                self._error_count += 1
                log.error(f"BUY failed (level {i}): {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # DUMP DEFENSE + REBALANCE
    # ═══════════════════════════════════════════════════════════════════════

    def _dump_defense(self) -> None:
        r = self.core.state.regime
        if r.dump_mode and not self._dump_armed:
            self._dump_armed = True
            self.core.state.exec.dump_events += 1
            cancelled = []
            for lvl in self.core.state.grid_levels:
                if lvl.get("stage", "buy") != "buy":
                    continue
                oid = lvl.get("buy_order_id") or lvl.get("order_id")
                if oid:
                    try:
                        self.adapter.cancel_order(oid)
                        cancelled.append(oid)
                    except Exception as e:
                        log.warning(f"Dump cancel failed {oid}: {e}")
            # Drop the dead buy levels from state (sell-side inventory survives)
            self.core.state.grid_levels = [
                lvl for lvl in self.core.state.grid_levels
                if lvl.get("stage", "buy") != "buy"]
            self.core._save_state()
            log.warning(f"🚨 DUMP MODE: cancelled {len(cancelled)} buy orders ({r.dump_reason})")
            self._notify(f"🚨 DUMP MODE: buy orders cancelled ({len(cancelled)}) — {r.dump_reason}")
        elif not r.dump_mode and self._dump_armed:
            self._dump_armed = False
            log.info("✅ DUMP MODE cleared — grid deployment re-enabled")
            self._notify("✅ DUMP MODE cleared — grid deployment re-enabled")

    def _maybe_rebalance(self, price: float, eur: float, base_bal: float, equity: float) -> None:
        if equity <= 0:
            return
        should, delta_eur, reason = self.rebalancer.compute(
            self.core.state, price, eur, base_bal, self.core.state.exec.cycle_count)
        if not should:
            return
        try:
            side = "buy" if reason.startswith("buy") else "sell"
            amt = self.adapter.round_amount(delta_eur / price)
            if amt <= 0:
                return
            self.adapter.rebalance_market(amt, side, price)
            self.core.state.exec.rebalance_count += 1
            self.core.state.exec.last_rebalance_ts = time.time()
            log.info(f"⚖️ REBALANCE {side} {amt} ({delta_eur:.2f}€) — {reason}")
            self._notify(f"⚖️ REBALANCE {side} {delta_eur:.2f}€ — {reason}")
        except Exception as e:
            if _is_permanent(e):
                raise
            log.warning(f"REBALANCE failed: {e}")

    # ═══════════════════════════════════════════════════════════════════════
    # SUPERVISOR LOOP
    # ═══════════════════════════════════════════════════════════════════════

    def run_forever(self, shutdown: dict, health: Any = None) -> bool:
        """Resilient loop. Returns True on graceful stop, False when the
        watchdog requests a restart (systemd picks it up)."""
        cfg = self.cfg
        cycle = 0
        deep_sleep = False
        degraded = False

        while not shutdown["flag"]:
            cycle += 1

            if deep_sleep:
                if self._deep_sleep_probe(shutdown, cfg.lockout_retry_interval):
                    deep_sleep = False
                continue

            t_start = time.perf_counter()
            try:
                self.run()
                self._watchdog_trips = 0
                if health and cycle % 5 == 0:
                    self._health_update(health, degraded=False)
                if degraded:
                    degraded = False
                    log.info("Recovered — normal cycle")
            except KeyboardInterrupt:
                break
            except Exception as e:
                if _is_permanent(e):
                    log.critical(f"PERMANENT ERROR: {e} — shutting down gracefully")
                    self._notify(f"Shutting down (permanent error): {e}")
                    return False
                self._error_count += 1
                self._consecutive_api_failures += 1
                log.error(f"Cycle {cycle}: {type(e).__name__}: {e}\n{traceback.format_exc()}")
                if health:
                    health.update(status="degraded" if self._error_count < 5 else "down",
                                  last_cycle_ok=False, error_count=self._error_count)
                if self._error_count >= 3:
                    if not degraded:
                        degraded = True
                        log.warning(f"Degradation: {self._error_count} errors — backing off")
                    if self._consecutive_api_failures >= cfg.deep_sleep_cycles:
                        deep_sleep = True
                        log.warning(f"{self._consecutive_api_failures} consecutive API failures — DEEP SLEEP")
                    time.sleep(min(cfg.cooldown * 3, 120))
                    continue

            # Watchdog: a single cycle must never hang the process
            elapsed = time.perf_counter() - t_start
            if elapsed > cfg.watchdog_cycle_s:
                self._watchdog_trips += 1
                log.error(f"WATCHDOG: cycle took {elapsed:.0f}s "
                          f"(trip {self._watchdog_trips}/3)")
                if self._watchdog_trips >= 3:
                    log.critical("WATCHDOG: 3 slow cycles — requesting restart")
                    return False
            else:
                self._watchdog_trips = 0

            sleep_sec = cfg.cooldown * (3 if degraded else 1)
            for _ in range(int(min(sleep_sec, 5))):
                if shutdown["flag"]:
                    break
                time.sleep(1)
        return True

    def _deep_sleep_probe(self, shutdown: dict, interval: float) -> bool:
        """Probe the exchange during deep sleep. True → recovered, resume."""
        log.info(f"DEEP SLEEP — probing every {interval:.0f}s")
        for _ in range(int(interval)):
            if shutdown["flag"]:
                return False
            time.sleep(1)
        try:
            price = self.adapter.fetch_price()
            if price > 0:
                self._consecutive_api_failures = 0
                self._error_count = 0
                log.info("DEEP SLEEP: exchange responsive again — resuming")
                return True
        except Exception:
            pass
        return False

    # ═══════════════════════════════════════════════════════════════════════
    # TEARDOWN
    # ═══════════════════════════════════════════════════════════════════════

    def shutdown(self) -> None:
        self._notify(f"Shutting down | {self.cfg.symbol}")
        log.info("Shutdown — cancelling orders...")
        try:
            self.adapter.cancel_all()
        except Exception:
            pass
        try:
            self.core.flush_state()
        except Exception:
            pass
        try:
            self.adapter.close()
        except Exception:
            pass
        log.info("Denaro v6 shut down.")

    # ═══════════════════════════════════════════════════════════════════════
    # OBSERVABILITY
    # ═══════════════════════════════════════════════════════════════════════

    def _log_status(self, price: float, equity: float, eur_bal: float, base_bal: float) -> None:
        cs = self.core.state
        pnl = (equity - cs.initial_capital) / cs.initial_capital * 100 if cs.initial_capital > 0 else 0
        ws = "[WS]" if self.adapter.ws_connected else "[!WS]"
        lock = "🧊" if self.adapter.in_lockout else ""
        dump = "🚨" if cs.regime.dump_mode else ""
        log.info(f"DENARO v6 STATUS | {ws}{dump} {self.cfg.symbol} price={price:.6f} "
                 f"equity={equity:.2f} EUR={eur_bal:.2f} {self.adapter.base_asset}={base_bal:.2f} "
                 f"PnL={pnl:+.2f}% grid={len(cs.grid_levels)}/{cs.exec.grid_target_levels} "
                 f"CB={cs.cb.state.value} mode={self._mode_label()}{lock}")

    def _log_perf(self) -> None:
        now = time.time()
        if now - self._last_perf_log < 300:
            return
        self._last_perf_log = now
        p = self.core.state.perf
        r = self.core.state.regime
        stats = self.adapter.stats
        log.info("-" * 60)
        log.info(f"PERF: Trades={p.total_trades} WR={p.win_rate * 100:.0f}% "
                 f"Sharpe={p.sharpe_ratio:.2f} Sortino={p.sortino_ratio:.2f} PF={p.profit_factor:.2f}")
        log.info(f"PERF: Kelly={self.core.kelly_fraction * 100:.0f}% "
                 f"SizeMult={self.core.state.sizing_multiplier:.2f} "
                 f"VaR95={self.core.state.var.var_95_1h * 100:.2f}%")
        log.info(f"REGIME: {r.trend.value} strength={r.trend_strength:.2f} "
                 f"vol={r.volatility_regime} vol_r={r.volume_ratio:.1f} dump={r.dump_mode}")
        log.info(f"STRAT: {self.core.state.exec.active_strategy.value} "
                 f"DCA={self.core.state.dca.active} rebal={self.core.state.exec.rebalance_count}")
        if stats:
            log.info(f"API: calls={stats.get('api_calls', 0)} hits={stats.get('cache_hits', 0)} "
                     f"lockout={stats.get('lockout', False)} ws={stats.get('ws_connected', False)}")
        log.info("-" * 60)

    def _health_update(self, health: Any, degraded: bool) -> None:
        cs = self.core.state
        eq = cs.current_capital
        initial = cs.initial_capital
        pnl = (eq - initial) / initial * 100 if initial > 0 else 0
        stats = self.adapter.stats
        try:
            health.update(
                status="ok" if not degraded else "degraded",
                equity=eq, pnl_pct=pnl,
                grid_levels=len(cs.grid_levels),
                cb_state=cs.cb.state.value,
                kelly_pct=self.core.kelly_fraction * 100,
                atr_pct=cs.regime.atr_pct,
                last_cycle_ts=time.time(), last_cycle_ok=True,
                uptime_sec=time.time() - self._started_at,
                ws_connected=self.adapter.ws_connected,
                error_count=self._error_count,
                strategy=cs.exec.active_strategy.value,
                trend=cs.regime.trend.value,
                dca_active=cs.dca.active,
                dump_mode=cs.regime.dump_mode,
                lockout=stats.get("lockout", False),
                cache_hits=stats.get("cache_hits", 0),
                api_calls=stats.get("api_calls", 0),
            )
        except Exception as e:
            log.debug(f"health update: {e}")

    def _notify_cb_transition(self, new_state: str, reason: str, equity: float) -> None:
        if new_state == "OPEN":
            self._notify(f"🚨 CB OPEN: {reason} — equity {equity:.2f}€")
        elif new_state == "HALF_OPEN":
            self._notify(f"⚠️ CB HALF_OPEN: {reason} — equity {equity:.2f}€")
        elif new_state == "CLOSED" and self._last_cb_state in ("OPEN", "HALF_OPEN"):
            self._notify(f"✅ CB CLOSED — trading resumed, equity {equity:.2f}€")

    def _notify(self, text: str) -> None:
        try:
            from notifier import notify
            notify(text)
        except Exception:
            pass

    def _mode_label(self) -> str:
        if self.cfg.shadow_mode:
            return "SHADOW"
        if self.cfg.mock_mode:
            return "MOCK"
        return "LIVE"

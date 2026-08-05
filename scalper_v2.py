#!/usr/bin/env python3
"""
Scalper v2.0 — Paper scalping mean-reversion su micro-struttura.
Zero capitale richiesto. Track record reale su dati di mercato live (ticker ccxt pubblico).

Strategia (diversa da ShadowGrid, complementare):
  - Entry: il prezzo scende >= ENTRY_DROP% dal massimo recente (mean-reversion
    verso il rimbalzo). Non usa griglia: una posizione alla volta (MAX_POSITIONS).
  - Exit: TARGET_PCT% sopra l'entry (take-profit) OPPURE STOP_PCT% sotto l'entry.
  - Il massimo recente segue il prezzo solo al rialzo (ratchet), cosi' si entra
    sui dip che vengono dal "tetto" del movimento.
  - Guardia cassa: mai comprare se il cash non copre il costo (no leverage).

Pattern riusato da shadowgrid.py: env-driven, ccxt pubblico (nessuna API key),
Health server, state file atomico, FEE_PCT parametrizzato, shutdown graceful.

Uso:
    python3 scalper_v2.py                          # kraken, DOGE/EUR, default
    EXCHANGE=mexc SYMBOL=SOL/USDT ... python3 scalper_v2.py

Test: python3 harness_scalper_v2.py                # scenari A/B/C/D
"""
from __future__ import annotations
import json, logging, os, signal, sys, time
from datetime import datetime, timezone
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

import ccxt

# ─── Config da env ────────────────────────────────────────────────────────
EXCHANGE    = os.environ.get("EXCHANGE", "kraken")
SYMBOL      = os.environ.get("SYMBOL", "DOGE/EUR")
CURRENCY    = os.environ.get("CURRENCY", "EUR")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
ENTRY_DROP  = float(os.environ.get("ENTRY_DROP", "1.0"))    # % ribasso dal max recente
TARGET_PCT  = float(os.environ.get("TARGET_PCT", "1.5"))    # % take-profit dall'entry
STOP_PCT    = float(os.environ.get("STOP_PCT", "1.0"))      # % stop-loss dall'entry
SIZE_FRAC   = float(os.environ.get("SIZE_FRAC", "0.30"))    # % del capitale per trade
MAX_POSITIONS = int(os.environ.get("MAX_POSITIONS", "1"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
FEE_PCT     = float(os.environ.get("FEE_PCT", "0.25"))      # fee % per lato (Kraken maker 0.25, MEXC ~0.10)
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8913"))
LOG_FILE    = os.environ.get("LOG_FILE", f"/tmp/scalper_v2_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}.log")
STATE_FILE  = os.environ.get("STATE_FILE", f"/tmp/scalper_v2_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}_state.json")

# ─── Logging ──────────────────────────────────────────────────────────────
log = logging.getLogger("scalper_v2")
log.setLevel(logging.INFO)
fh = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.handlers = [fh, sh]


# ─── Exchange (ccxt pubblico, zero chiavi) ────────────────────────────────
def _make_exchange():
    cls = getattr(ccxt, EXCHANGE.lower())
    return cls({"enableRateLimit": True})


# ─── State ────────────────────────────────────────────────────────────────
class State:
    def __init__(self):
        self.free_cash = CAPITAL
        self.coins = 0.0
        self.realized_pnl = 0.0
        self.total_trades = 0
        self.winning_trades = 0
        self.equity_peak = CAPITAL
        self.entry_price = 0.0
        self.entry_fee = 0.0
        self.high_since_entry = 0.0
        self.trade_high = 0.0          # ratchet del massimo (persistito)
        self.last_price = 0.0
        self.start_ts = time.time()
        self.last_save = 0
        self._load()

    def _load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    d = json.load(f)
                self.free_cash = d.get("free_cash", CAPITAL)
                self.coins = d.get("coins", 0.0)
                self.realized_pnl = d.get("realized_pnl", 0.0)
                self.total_trades = d.get("total_trades", 0)
                self.winning_trades = d.get("winning_trades", 0)
                self.equity_peak = d.get("equity_peak", CAPITAL)
                self.entry_price = d.get("entry_price", 0.0)
                self.entry_fee = d.get("entry_fee", 0.0)
                self.high_since_entry = d.get("high_since_entry", 0.0)
                self.trade_high = d.get("trade_high", 0.0)   # Fix: ratchet persistito -> restart-safe
                log.info(f"State loaded: equity={self.equity():.2f} trades={self.total_trades}")
            except Exception:
                log.warning("State file corrupt, starting fresh")

    def equity(self, price: float = 0) -> float:
        return self.free_cash + self.coins * (price if price > 0 else self.last_price)

    def in_position(self) -> bool:
        return self.entry_price > 0 and self.coins > 1e-12

    def save(self):
        now = time.time()
        if now - self.last_save < 5:
            return
        self.last_save = now
        try:
            d = {
                "free_cash": round(self.free_cash, 4),
                "coins": round(self.coins, 8),
                "realized_pnl": round(self.realized_pnl, 4),
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "equity_peak": round(self.equity_peak, 4),
                "entry_price": round(self.entry_price, 6),
                "entry_fee": round(self.entry_fee, 4),
                "high_since_entry": round(self.high_since_entry, 6),
                "trade_high": round(self.trade_high, 6),
            }
            with open(STATE_FILE, "w") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            log.error(f"Save state failed: {e}")


# ─── Scalper Logic ────────────────────────────────────────────────────────
class ScalperEngine:
    def __init__(self, state: State):
        self.state = state
        self.cycle_count = 0
        self.ccxt_errors = 0
        self.trade_high = state.trade_high   # Fix: ratchet riletto dallo state (restart-safe)
        self.entry_drop_pct = ENTRY_DROP / 100.0
        self.target_pct = TARGET_PCT / 100.0
        self.stop_pct = STOP_PCT / 100.0
        self.size_frac = SIZE_FRAC
        self.max_positions = MAX_POSITIONS

    def _buy_cost(self, price: float) -> float:
        """Quanto cash serve per il trade (entry + fee)."""
        amount = (CAPITAL * self.size_frac) / price
        return amount * price * (1.0 + FEE_PCT / 100.0)

    def cycle(self, price: float) -> dict:
        """Un ciclo: aggiorna massimo, decide entry/exit, calcola equity."""
        self.cycle_count += 1
        self.state.last_price = price
        events = []

        # Ratchet del massimo recente (solo al rialzo) — fuori posizione
        if not self.state.in_position():
            if price > self.trade_high:
                self.trade_high = price
                self.state.trade_high = price   # sync con lo state (persistenza)
            drop = (self.trade_high - price) / self.trade_high if self.trade_high > 0 else 0
            if drop >= self.entry_drop_pct:
                cost = self._buy_cost(price)
                if self.state.free_cash < cost:
                    events.append(f"ENTRY skipped (no cash: {self.state.free_cash:.2f} < {cost:.2f})")
                else:
                    amount = (CAPITAL * self.size_frac) / price
                    fee = amount * price * (FEE_PCT / 100.0)
                    self.state.free_cash -= amount * price + fee
                    self.state.coins += amount
                    self.state.entry_price = price
                    self.state.entry_fee = fee
                    self.state.high_since_entry = price
                    events.append(f"ENTRY @ {price:.6f} x{amount:.6f} (drop {drop*100:.2f}%)")
        else:
            # Aggiorna max da entry (per trailing di fatto via target/stop fissi)
            if price > self.state.high_since_entry:
                self.state.high_since_entry = price
            ep = self.state.entry_price
            pnl_pct = (price - ep) / ep * 100.0 if ep > 0 else 0
            if pnl_pct >= self.target_pct * 100.0:
                self._close(price, "target", pnl_pct, events)
            elif pnl_pct <= -self.stop_pct * 100.0:
                self._close(price, "stop", pnl_pct, events)

        # Equity + peak
        eq = self.state.equity(price)
        if eq > self.state.equity_peak:
            self.state.equity_peak = eq

        return {
            "event": " | ".join(events) if events else "idle",
            "price": price,
            "equity": eq,
            "drawdown_pct": (1.0 - eq / self.state.equity_peak) * 100 if self.state.equity_peak > 0 else 0,
            "trades": self.state.total_trades,
            "in_position": self.state.in_position(),
        }

    def _close(self, price: float, reason: str, pnl_pct: float, events: list) -> None:
        """Vende tutto e registra il trade."""
        amt = self.state.coins
        revenue = amt * price * (1.0 - FEE_PCT / 100.0)
        cost_basis = amt * self.state.entry_price + self.state.entry_fee
        pnl = revenue - cost_basis
        self.state.free_cash += revenue
        self.state.coins = 0.0
        self.state.realized_pnl += pnl
        self.state.total_trades += 1
        if pnl > 0:
            self.state.winning_trades += 1
        events.append(f"EXIT {reason} @ {price:.6f} PnL={pnl:+.4f} ({pnl_pct:+.2f}%)")
        log.info(f"EXIT {reason}: pnl={pnl:+.4f} total={self.state.realized_pnl:+.4f}")
        # Reset posizione
        self.state.entry_price = 0.0
        self.state.entry_fee = 0.0
        self.state.high_since_entry = 0.0
        self.state.trade_high = price   # sync: nuovo riferimento post-exit (persistenza)
        self.trade_high = price


# ─── Health Server ────────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    engine_ref: Optional[ScalperEngine] = None
    state_ref: Optional[State] = None

    def do_GET(self):
        engine = self.__class__.engine_ref
        state = self.__class__.state_ref
        price = state.last_price if state else 0
        equity = state.equity(price) if state else 0
        if self.path == "/health":
            body = json.dumps({
                "status": "healthy",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "exchange": EXCHANGE,
                "symbol": SYMBOL,
                "equity": round(equity, 2),
                "drawdown_pct": round((1.0 - equity / state.equity_peak) * 100, 2) if state and state.equity_peak > 0 else 0,
                "total_trades": state.total_trades if state else 0,
                "realized_pnl": round(state.realized_pnl, 4) if state else 0,
                "win_rate": round(state.winning_trades / state.total_trades * 100, 1) if state and state.total_trades > 0 else 0,
                "in_position": state.in_position() if state else False,
                "uptime_hours": round((time.time() - state.start_ts) / 3600, 1) if state else 0,
                "port": HEALTH_PORT,
            }, indent=2).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silenzia log HTTP


# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    log.info(f"=== Scalper v2.0 ===")
    log.info(f"Exchange: {EXCHANGE} | Symbol: {SYMBOL} | Capital: {CAPITAL} {CURRENCY}")
    log.info(f"Entry: drop>={ENTRY_DROP}% dal max | TP {TARGET_PCT}% | Stop {STOP_PCT}% | Size {SIZE_FRAC*100:.0f}% | Fee {FEE_PCT}%")
    log.info(f"Health: :{HEALTH_PORT} | State: {STATE_FILE}")

    ex = _make_exchange()
    state = State()
    engine = ScalperEngine(state)

    HealthHandler.engine_ref = engine
    HealthHandler.state_ref = state
    health = HTTPServer(("0.0.0.0", HEALTH_PORT), HealthHandler)
    hthread = threading.Thread(target=health.serve_forever, daemon=True)
    hthread.start()
    log.info(f"Health server on :{HEALTH_PORT}")

    shutdown_flag = False

    def graceful(sig, frame):
        nonlocal shutdown_flag
        log.warning(f"Signal {sig} — graceful shutdown...")
        shutdown_flag = True

    signal.signal(signal.SIGINT, graceful)
    signal.signal(signal.SIGTERM, graceful)

    while not shutdown_flag:
        try:
            ticker = ex.fetch_ticker(SYMBOL)
            price = ticker.get("last") or ticker.get("close")
            if not price or price <= 0:
                log.warning("Prezzo invalido, skip")
                engine.ccxt_errors += 1
                time.sleep(COOLDOWN * max(1, min(engine.ccxt_errors, 5)))
                continue

            engine.ccxt_errors = 0
            result = engine.cycle(price)

            if result["event"] != "idle" or engine.cycle_count % 10 == 0:
                log.info(f"[{engine.cycle_count:>6d}] price={price:.6f} equity={result['equity']:.2f} "
                         f"dd={result['drawdown_pct']:.1f}% trades={result['trades']} "
                         f"{'POS' if result['in_position'] else 'flat'} {result['event']}")

            if engine.cycle_count % 60 == 0:
                state.save()
                log.info(f"Snapshot | equity={state.equity(price):.2f} PnL={state.realized_pnl:+.4f} "
                         f"trades={state.total_trades} win_rate={(state.winning_trades/max(1,state.total_trades))*100:.1f}%")

        except Exception as e:
            engine.ccxt_errors += 1
            log.error(f"Cycle error: {e}")
            if engine.ccxt_errors >= 5:
                log.critical(f"{engine.ccxt_errors} errori consecutivi — backoff 5 min")
                state.save()
                time.sleep(300)
                engine.ccxt_errors = 0

        for _ in range(int(min(COOLDOWN, 5))):
            if shutdown_flag:
                break
            time.sleep(1)

    state.save()
    health.shutdown()
    log.info("Scalper v2 stopped.")


if __name__ == "__main__":
    main()

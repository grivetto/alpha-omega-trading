#!/usr/bin/env python3
"""
ShadowGrid v1.0 — Paper trading grid bot.
Zero capitale richiesto. Accumula track record reale su dati di mercato live.

Strategia: griglia di limit order equidistanti. Compra al livello N, vende a N+1.
Funziona su qualsiasi exchange ccxt (candele OHLCV pubbliche, niente API key).
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
LEVELS      = int(os.environ.get("LEVELS", "5"))
SPREAD_PCT  = float(os.environ.get("SPREAD", "0.5"))    # distanza % tra livelli
PER_LEVEL   = float(os.environ.get("PER_LEVEL", "0.20"))  # 20% del capitale per livello
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
FEE_PCT     = float(os.environ.get("FEE_PCT", "0.25"))  # fee % per lato (Kraken maker 0.25, MEXC spot ~0.10)
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8911"))
LOG_FILE    = os.environ.get("LOG_FILE", f"/tmp/shadowgrid_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}.log")
STATE_FILE  = os.environ.get("STATE_FILE", f"/tmp/shadowgrid_{EXCHANGE.lower()}_{SYMBOL.replace('/', '_').lower()}_state.json")

# ─── Logging ──────────────────────────────────────────────────────────────
log = logging.getLogger("shadowgrid")
log.setLevel(logging.INFO)
fh = RotatingFileHandler(LOG_FILE, maxBytes=2*1024*1024, backupCount=2)
fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
log.handlers = [fh, sh]

# ─── Exchange ─────────────────────────────────────────────────────────────
def _make_exchange():
    cls = getattr(ccxt, EXCHANGE.lower())
    return cls({"enableRateLimit": True})

# ─── State ────────────────────────────────────────────────────────────────
class State:
    def __init__(self):
        self.free_cash = CAPITAL
        self.locked_cash = 0.0
        self.coins = 0.0
        self.orders: list[dict] = []
        self.equity_peak = CAPITAL
        self.total_trades = 0
        self.winning_trades = 0
        self.realized_pnl = 0.0
        self.start_ts = time.time()
        self.last_save = 0
        self._load()

    def _load(self):
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE) as f:
                    d = json.load(f)
                self.free_cash = d.get("free_cash", CAPITAL)
                self.locked_cash = d.get("locked_cash", 0)
                self.coins = d.get("coins", 0)
                self.equity_peak = d.get("equity_peak", CAPITAL)
                self.total_trades = d.get("total_trades", 0)
                self.winning_trades = d.get("winning_trades", 0)
                self.realized_pnl = d.get("realized_pnl", 0)
                self.orders = d.get("orders", [])
                log.info(f"State loaded: equity={self.equity():.2f}, trades={self.total_trades}")
            except Exception:
                log.warning("State file corrupt, starting fresh")

    def equity(self, price: float = 0) -> float:
        # Fix 2026-08-05: realized_pnl NON va sommato — free_cash contiene gia'
        # i ricavi netti dei sell; sommarlo duplicava il PnL e gonfiava
        # equity/drawdown del track record.
        return self.free_cash + self.locked_cash + self.coins * price

    def save(self):
        now = time.time()
        if now - self.last_save < 5:
            return
        self.last_save = now
        try:
            d = {
                "free_cash": round(self.free_cash, 4),
                "locked_cash": round(self.locked_cash, 4),
                "coins": round(self.coins, 8),
                "equity_peak": round(self.equity_peak, 4),
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "realized_pnl": round(self.realized_pnl, 4),
                "orders": [{
                    "id": o["id"],
                    "side": o["side"],
                    "price": o["price"],
                    "amount": o["amount"],
                    "cost": o["cost"],
                } for o in self.orders],
            }
            with open(STATE_FILE, "w") as f:
                json.dump(d, f, indent=2)
        except Exception as e:
            log.error(f"Save state failed: {e}")

# ─── Grid Logic ───────────────────────────────────────────────────────────
class GridEngine:
    def __init__(self, state: State):
        self.state = state
        self.last_price: float = 0.0
        self.cycle_count = 0
        self.ccxt_errors = 0

    def _build_levels(self, price: float) -> list[dict]:
        """Costruisce N livelli sopra e sotto il prezzo corrente."""
        levels = []
        spread = SPREAD_PCT / 100.0
        per_level_cash = CAPITAL * PER_LEVEL

        # Livelli di BUY sotto il prezzo
        for i in range(LEVELS):
            lvl_price = price * (1.0 - spread * (i + 1))
            amount = per_level_cash / lvl_price if lvl_price > 0 else 0
            levels.append({"side": "buy", "price": lvl_price, "amount": amount, "cost": per_level_cash})

        # Livelli di SELL sopra il prezzo
        for i in range(LEVELS):
            lvl_price = price * (1.0 + spread * (i + 1))
            amount = per_level_cash / price if price > 0 else 0  # base amount calcolato sul mid
            levels.append({"side": "sell", "price": lvl_price, "amount": amount, "cost": per_level_cash})

        return levels

    def cycle(self, price: float) -> dict:
        """Un ciclo di grid: controlla fill, piazza/cancella ordini, calcola PnL."""
        self.last_price = price
        self.cycle_count += 1

        events = []

        # 1. Controlla fill sugli ordini esistenti
        filled = []
        for i, o in enumerate(self.state.orders):
            if o["side"] == "buy" and price <= o["price"]:
                # Guardia cassa AL FILL (fix 2026-08-05): se il cash non copre il cost,
                # NON fillare — altrimenti gap-down su griglia 5x25% -> free_cash negativo.
                # L'ordine resta pending e il placement non lo rimpiazza (gia' presente).
                if self.state.free_cash < o["cost"]:
                    events.append(f"BUY skipped @ {o['price']:.6f} (no cash)")
                    continue
                # BUY filled
                self.state.free_cash -= o["cost"]
                self.state.coins += o["amount"]
                self.state.total_trades += 1
                events.append(f"BUY filled @ {o['price']:.6f} x{o['amount']:.6f}")
                filled.append(i)
                # Piazza un ordine SELL corrispondente
                sell_price = o["price"] * (1.0 + SPREAD_PCT / 100.0)
                self.state.orders.append({
                    "id": f"s{self.cycle_count}_{len(self.state.orders)}",
                    "side": "sell",
                    "price": sell_price,
                    "amount": o["amount"] * (1.0 - FEE_PCT / 100.0),  # meno fee (FEE_PCT %)
                    "cost": o["amount"] * (1.0 - FEE_PCT / 100.0) * sell_price,
                })

            elif o["side"] == "sell" and price >= o["price"]:
                # SELL filled
                if self.state.coins >= o["amount"]:
                    revenue = o["amount"] * o["price"]
                    self.state.coins -= o["amount"]
                    self.state.free_cash += revenue
                    # Calcola PnL: il costo originale del buy abbinato
                    # Semplificazione: PnL = (sell_price - buy_price) * amount
                    # Prendiamo il buy price dal livello corrispondente
                    buy_price = o["price"] / (1.0 + SPREAD_PCT / 100.0)
                    pnl = revenue - o["amount"] * buy_price
                    self.state.realized_pnl += pnl
                    self.state.total_trades += 1
                    if pnl > 0:
                        self.state.winning_trades += 1
                    events.append(f"SELL filled @ {o['price']:.6f} PnL={pnl:+.6f}")
                    filled.append(i)

        # Rimuovi ordini filled (in ordine inverso)
        for i in reversed(filled):
            self.state.orders.pop(i)

        # 2. Ricostruisci griglia se ordini insufficienti
        target_buys = LEVELS - sum(1 for o in self.state.orders if o["side"] == "buy")
        target_sells = LEVELS - sum(1 for o in self.state.orders if o["side"] == "sell")

        if target_buys > 0 or target_sells > 0:
            levels = self._build_levels(price)
            existing_prices = {(o["side"], o["price"]) for o in self.state.orders}

            for lvl in levels:
                key = (lvl["side"], lvl["price"])
                if key not in existing_prices:
                    if lvl["side"] == "buy" and target_buys > 0 and self.state.free_cash >= lvl["cost"]:
                        self.state.orders.append({
                            "id": f"b{self.cycle_count}_{len(self.state.orders)}",
                            "side": lvl["side"],
                            "price": lvl["price"],
                            "amount": lvl["amount"],
                            "cost": lvl["cost"],
                        })
                        target_buys -= 1
                    elif lvl["side"] == "sell" and target_sells > 0 and self.state.coins >= lvl["amount"]:
                        self.state.orders.append({
                            "id": f"s{self.cycle_count}_{len(self.state.orders)}",
                            "side": lvl["side"],
                            "price": lvl["price"],
                            "amount": lvl["amount"],
                            "cost": lvl["cost"],
                        })
                        target_sells -= 1

        # 3. Calcola equity corrente
        equity = self.state.equity(price)
        if equity > self.state.equity_peak:
            self.state.equity_peak = equity

        return {
            "event": " | ".join(events) if events else "idle",
            "price": price,
            "equity": equity,
            "drawdown_pct": (1.0 - equity / self.state.equity_peak) * 100 if self.state.equity_peak > 0 else 0,
            "orders": len(self.state.orders),
            "trades": self.state.total_trades,
        }

# ─── Health Server ────────────────────────────────────────────────────────
class HealthHandler(BaseHTTPRequestHandler):
    engine_ref = None
    state_ref = None

    def do_GET(self):
        engine = self.__class__.engine_ref
        state = self.__class__.state_ref
        price = engine.last_price if engine else 0
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

    def log_message(self, fmt, *args):
        pass  # silenzia log HTTP

# ─── Main ─────────────────────────────────────────────────────────────────
def main():
    log.info(f"=== ShadowGrid v1.0 ===")
    log.info(f"Exchange: {EXCHANGE} | Symbol: {SYMBOL} | Capital: {CAPITAL} {CURRENCY}")
    log.info(f"Grid: {LEVELS} livelli, spread {SPREAD_PCT}%, {PER_LEVEL*100:.0f}% capitale/livello")
    log.info(f"Health: :{HEALTH_PORT} | State: {STATE_FILE}")

    ex = _make_exchange()
    state = State()
    engine = GridEngine(state)

    # Health server
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
                         f"dd={result['drawdown_pct']:.1f}% orders={result['orders']} trades={result['trades']} "
                         f"{result['event']}")

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
    log.info("ShadowGrid stopped.")

if __name__ == "__main__":
    main()
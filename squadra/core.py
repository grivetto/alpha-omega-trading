"""
DenaroOpportunisticCore v3.0 — Base asincrona per la Squadra Denaro Opportunistico.
v3.0: + test_mode (fake OHLCV, log-only orders), strategie separate in strategies/
Legge .env dalla directory padre (denaro/), fornisce exchange + OHLCV + logging.
"""
import os, json, logging, asyncio, time, random, math
import ccxt.async_support as ccxt
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PARENT_DIR, ".env")
load_dotenv(ENV_PATH)

import sys
sys.path.insert(0, PARENT_DIR)
from trade_db import TradeDB
from utils.risk_engine import RiskManager
from risk.kill_switch import (
    KillSwitchManager, KS_OFF, KS_BOT_STOPPED, KS_LOCKED,
    DEFAULT_MAX_DRAWDOWN_EUR, DEFAULT_CONSECUTIVE_LOSS_LIMIT,
)

# ── Cost Model ────────────────────────────────────────────────
BINANCE_MAKER_FEE = 0.00075   # 0.075% con BNB
BINANCE_TAKER_FEE = 0.001     # 0.1% senza BNB
ESTIMATED_SLIPPAGE = 0.001    # 0.1% per ordine market
ROUND_TRIP_COST_PCT = (BINANCE_TAKER_FEE + ESTIMATED_SLIPPAGE) * 2  # ~0.4%

def cost_model(symbol: str, amount: float, price: float, is_buy: bool = True) -> dict:
    """Calcola costi espliciti per un trade: fee + slippage stimato."""
    notional = amount * price
    fee = notional * BINANCE_TAKER_FEE
    slippage = notional * ESTIMATED_SLIPPAGE
    return {
        "notional_eur": notional,
        "fee_eur": fee,
        "slippage_eur": slippage,
        "total_cost_eur": fee + slippage,
        "total_cost_pct": BINANCE_TAKER_FEE + ESTIMATED_SLIPPAGE,
    }

def cost_filter(expected_profit_pct: float) -> bool:
    """Filtra trade con profitto netto negativo dopo fee e slippage."""
    return expected_profit_pct > ROUND_TRIP_COST_PCT


# ── Fake OHLCV generator ──────────────────────────────────────────
# Persistent state per symbol: prezzo base + direzione drift
_fake_state: dict = {}

def _generate_fake_ohlcv(symbol: str, timeframe: str = "1m", limit: int = 50) -> list:
    """
    Genera candele OHLCV fittizie per test_mode.
    Prezzi base realistici per simboli noti, random walk con mean reversion.
    """
    now = int(time.time() * 1000)
    interval_ms = {"1m": 60_000, "5m": 300_000, "15m": 900_000}.get(timeframe, 60_000)

    # Prezzi base per simbolo
    base_prices = {
        "ETH/EUR": 1800.0, "BTC/EUR": 55000.0, "SOL/EUR": 90.0,
        "ETH/USDT": 1900.0, "BTC/USDT": 58000.0, "SOL/USDT": 95.0,
    }
    base_price = base_prices.get(symbol, 100.0)

    # Inizializza o recupera stato persistente
    if symbol not in _fake_state:
        _fake_state[symbol] = {
            "price": base_price,
            "drift": random.uniform(-0.0005, 0.0005),  # trend sottile
            "volatility": random.uniform(0.001, 0.005),
        }

    state = _fake_state[symbol]
    ohlcv = []

    for i in range(limit):
        ts = now - (limit - i) * interval_ms

        # Random walk with drift + occasional mean reversion
        noise = random.gauss(0, state["volatility"])
        if random.random() < 0.05:  # 5% chance reverse drift
            state["drift"] = random.uniform(-0.0005, 0.0005)

        price = state["price"] * (1 + state["drift"] + noise)

        # Mean reversion verso base_price (debole)
        price += (base_price - price) * 0.001 * random.random()

        # Non zero, non negativo
        price = max(price, base_price * 0.5)
        state["price"] = price

        spread = price * state["volatility"] * random.uniform(0.5, 1.5)
        o = price - spread * random.uniform(0, 0.5)
        h = price + spread * random.uniform(0.3, 0.7)
        l = price - spread * random.uniform(0.3, 0.7)
        c = price + spread * random.uniform(-0.3, 0.3)
        v = random.uniform(10, 100) * (1 + 5 * (1 if random.random() < 0.05 else 0))  # occasional volume spike

        ohlcv.append([ts, round(o, 2), round(h, 2), round(l, 2), round(c, 2), round(v, 2)])

    return ohlcv


class DenaroOpportunisticCore:
    def __init__(self, bot_name="Generic", config_file=None, test_mode=False):
        self.bot_name = bot_name
        self.test_mode = test_mode
        self.logger = logging.getLogger(f"Squadra-{bot_name}")
        self.logger.setLevel(logging.DEBUG)
        self.config = {}
        if config_file:
            self.load_config(config_file)

        if test_mode:
            self.logger.info("🧪 TEST MODE — no real exchange connection, fake data")
            self.exchange = None
            self.balance = {"EUR": 100.0}  # fake balance
            self.open_orders = []
        else:
            api_key = os.getenv("BINANCE_API_KEY", "")
            api_secret = os.getenv("BINANCE_API_SECRET", "")
            if not api_key or not api_secret:
                self.logger.error("API keys not found in .env")
                raise ValueError("BINANCE_API_KEY / BINANCE_API_SECRET missing")

            self.exchange = ccxt.binance({
                "apiKey": api_key,
                "secret": api_secret,
                "enableRateLimit": True,
                "options": {"defaultType": "spot", "warnOnFetchOpenOrdersWithoutSymbol": False},
            })

            self.balance = {}
            self.open_orders = []

        self.positions = {}
        self.running = False

        # ── Kill Switch persistente (spietato) ──
        db_path = os.path.join(PARENT_DIR, "trades.db")
        lock_file = os.path.join(PARENT_DIR, "bot_lock.json")
        self.kill_switch = KillSwitchManager(db_path, lock_file)

        # ── Per-bot drawdown tracking (stop-loss individuale) ──
        self.max_drawdown_eur = self.config.get("max_drawdown_eur", DEFAULT_MAX_DRAWDOWN_EUR)
        self.max_consecutive_losses = self.config.get("max_consecutive_losses", DEFAULT_CONSECUTIVE_LOSS_LIMIT)
        self._initial_balance_eur = 0.0    # captured at first balance refresh
        self._balance_snapshot_taken = False
        self._drawdown_stopped = False      # True if this bot was killed by its own drawdown
        self._total_pnl_eur = 0.0           # running EUR P&L since session start
        self._peak_balance_eur = 0.0
        # Trade-level P&L tracking
        self._last_trade_pnl_pct = 0.0      # P&L % of last completed trade
        self._last_entry_price = 0.0        # for trade-level SL/TP check in cycle

        # DB persistence
        self.db = TradeDB(db_path)
        self._phantom_cleaned = False
        self._startup_validated = False

    def load_config(self, config_file):
        config_path = os.path.join(SCRIPT_DIR, "config", config_file)
        if not os.path.exists(config_path):
            config_path = os.path.join(SCRIPT_DIR, config_file)
        if os.path.exists(config_path):
            with open(config_path) as f:
                self.config = json.load(f)
            self.logger.info(f"Config '{config_file}' loaded.")
        else:
            self.logger.warning(f"Config '{config_file}' not found")

    async def refresh_balance(self):
        if self.test_mode:
            # In test mode balance changes only via simulated trades
            return
        try:
            bal = await self.exchange.fetch_balance()
            self.balance = bal.get("free", {})

            # Snapshot iniziale per calcolo drawdown reale
            total_eur = float(bal.get("total", {}).get("EUR", 0) or 0)
            if not self._balance_snapshot_taken and total_eur > 0:
                self._initial_balance_eur = total_eur
                self._peak_balance_eur = total_eur
                self._balance_snapshot_taken = True
                self.logger.info(
                    f"📸 Balance snapshot: {self._initial_balance_eur:.2f}€ | "
                    f"drawdown limit: {self.max_drawdown_eur:.1f}€"
                )
            elif self._balance_snapshot_taken:
                self._total_pnl_eur = total_eur - self._initial_balance_eur
                if total_eur > self._peak_balance_eur:
                    self._peak_balance_eur = total_eur

            self.logger.debug(f"Balance refreshed: {len(self.balance)} assets, EUR={total_eur:.2f}")
        except Exception as e:
            self.logger.error(f"Balance refresh error: {e}")

    async def refresh_open_orders(self):
        if self.test_mode:
            return
        try:
            symbol = self.config.get("symbol") or self.config.get("symbol_a")
            if symbol:
                self.open_orders = await self.exchange.fetch_open_orders(symbol)
            else:
                self.open_orders = await self.exchange.fetch_open_orders()
        except Exception as e:
            self.logger.error(f"Open orders error: {e}")

    async def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=50):
        if self.test_mode:
            return _generate_fake_ohlcv(symbol, timeframe, limit)
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            self.logger.error(f"OHLCV error {symbol}: {e}")
            return []

    async def create_limit_buy(self, symbol, amount, price, reduce=False):
        if self.test_mode:
            cost = amount * price
            eur = self.balance.get("EUR", 0)
            if eur >= cost:
                self.balance["EUR"] = eur - cost
                base = symbol.split("/")[0]
                self.balance[base] = self.balance.get(base, 0) + amount
                self.logger.info(f"🧪 TEST BUY {symbol} {amount:.4f} @ {price:.2f} | EUR left: {self.balance['EUR']:.2f}")
            else:
                self.logger.warning(f"🧪 TEST BUY {symbol} FAILED: insufficient EUR ({eur:.2f} < {cost:.2f})")
            return {"id": "test_fake", "status": "closed", "symbol": symbol, "amount": amount, "price": price}
        try:
            order = await self.exchange.create_limit_buy_order(symbol, amount, price)
            self.logger.info(f"BUY {symbol} {amount:.4f} @ {price:.2f}")
            return order
        except Exception as e:
            self.logger.error(f"Buy error {symbol}: {e}")
            return None

    async def create_limit_sell(self, symbol, amount, price, reduce=False):
        if self.test_mode:
            base = symbol.split("/")[0]
            held = self.balance.get(base, 0)
            if held >= amount:
                self.balance[base] = held - amount
                self.balance["EUR"] = self.balance.get("EUR", 0) + amount * price
                self.logger.info(f"🧪 TEST SELL {symbol} {amount:.4f} @ {price:.2f} | EUR now: {self.balance['EUR']:.2f}")
            else:
                self.logger.warning(f"🧪 TEST SELL {symbol} FAILED: insufficient {base} ({held:.4f} < {amount:.4f})")
            return {"id": "test_fake", "status": "closed", "symbol": symbol, "amount": amount, "price": price}
        try:
            order = await self.exchange.create_limit_sell_order(symbol, amount, price)
            self.logger.info(f"SELL {symbol} {amount:.4f} @ {price:.2f}")
            return order
        except Exception as e:
            self.logger.error(f"Sell error {symbol}: {e}")
            return None

    async def create_market_buy(self, symbol, amount):
        if self.test_mode:
            cost = amount * (self.config.get("last_price", 100))
            eur = self.balance.get("EUR", 0)
            if eur >= cost:
                self.balance["EUR"] = eur - cost
                base = symbol.split("/")[0]
                self.balance[base] = self.balance.get(base, 0) + amount
                self.logger.info(f"🧪 MARKET BUY {symbol} {amount:.4f} | EUR left: {self.balance['EUR']:.2f}")
            return {"id": "test_fake", "status": "closed"}
        try:
            order = await self.exchange.create_market_buy_order(symbol, amount)
            self.logger.info(f"MARKET BUY {symbol} {amount:.4f} @ {order.get('price', '?')}")
            return order
        except Exception as e:
            self.logger.error(f"Market buy error {symbol}: {e}")
            return None

    async def create_market_sell(self, symbol, amount):
        if self.test_mode:
            base = symbol.split("/")[0]
            held = self.balance.get(base, 0)
            if held >= amount:
                self.balance[base] = held - amount
                self.balance["EUR"] = self.balance.get("EUR", 0) + amount * (self.config.get("last_price", 100))
                self.logger.info(f"🧪 MARKET SELL {symbol} {amount:.4f} | EUR now: {self.balance['EUR']:.2f}")
            return {"id": "test_fake", "status": "closed"}
        try:
            # Round down to LOT_SIZE step to avoid Binance precision errors
            base = symbol.split('/')[0]
            LOT_STEPS = {'ETH': 0.0001, 'BTC': 0.00001, 'BNB': 0.001, 'SOL': 0.001, 'DOGE': 1.0}
            step = LOT_STEPS.get(base, 0.0001 if base not in ('DOGE',) else 1.0)
            safe_amount = math.floor(amount / step) * step
            if safe_amount <= 0:
                self.logger.error(f"Market sell {symbol}: amount {amount:.8f} rounds to 0 (step={step})")
                return None
            order = await self.exchange.create_market_sell_order(symbol, safe_amount)
            self.logger.info(f"MARKET SELL {symbol} {safe_amount:.4f} @ {order.get('price', '?')}")
            return order
        except Exception as e:
            self.logger.error(f"Market sell error {symbol}: {e}")
            return None

    # ── DB persistence ────────────────────────────────
    def save_position_to_db(self):
        bot_name = self.bot_name
        if not hasattr(self, 'entry_price') or not hasattr(self, 'entry_amount'):
            return
        self.db.save_bot_state(
            bot_name=bot_name,
            is_in_position=self.in_position if hasattr(self, 'in_position') else False,
            entry_price=self.entry_price if hasattr(self, 'entry_price') else 0.0,
            quantity=self.entry_amount if hasattr(self, 'entry_amount') else 0.0,
            tp=self.tp_pct if hasattr(self, 'tp_pct') else 0.0,
            sl=self.sl_pct if hasattr(self, 'sl_pct') else 0.0,
            entry_time=time.time(),
            exchange_name='binance',
        )
        self.logger.debug(f"State saved: {'IN POS' if getattr(self, 'in_position', False) else 'FLAT'}")

    def load_position_from_db(self):
        self.logger.debug(f"load_position_from_db: querying DB for {self.bot_name}")
        state = self.db.load_bot_state(self.bot_name)
        self.logger.debug(f"load_position_from_db: state={state}")
        if state and state.get('is_in_position') and state.get('quantity', 0) > 0:
            self.in_position = True
            self.entry_price = state['entry_price']
            self.entry_amount = state['quantity']
            self.logger.info(
                f"♻️ Restored position: {getattr(self, 'symbol', '?')} "
                f"{self.entry_amount:.4f} @ {self.entry_price:.2f}")
            return True
        return False

    # ── Balance validation ────────────────────────────
    async def validate_balance_before_sell(self, asset: str, required_qty: float) -> bool:
        if self.test_mode:
            # In test mode, balance is tracked locally
            held = self.balance.get(asset, 0)
            if held < required_qty * 0.99:
                self.logger.warning(f"🧪 {self.bot_name}: phantom position! DB says {required_qty:.4f} "
                                    f"{asset} but local balance has {held:.4f}")
                await self._clean_phantom_position(asset, held)
                return False
            return True
        try:
            bal = await self.exchange.fetch_balance()
            free_bal = float(bal.get(asset, {}).get('free', 0) or 0)
            total_bal = float(bal.get(asset, {}).get('total', 0) or 0)
            actual_bal = max(free_bal, total_bal)
            if actual_bal < required_qty * 0.99:
                self.logger.warning(
                    f"👻 {self.bot_name}: phantom position! DB says {required_qty:.4f} "
                    f"{asset} but exchange has {actual_bal:.4f}. Cleaning up.")
                await self._clean_phantom_position(asset, actual_bal)
                return False
            return True
        except Exception as e:
            self.logger.debug(f"Balance check error {self.bot_name}: {e}")
            return True

    async def _clean_phantom_position(self, asset: str, actual_bal: float):
        self.logger.info(f"🧹 {self.bot_name}: cleaning phantom position for {asset}")
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self.save_position_to_db()
        self._phantom_cleaned = True

    async def startup_validate_position(self, asset: str):
        if self._startup_validated:
            return
        self._startup_validated = True
        if not getattr(self, 'in_position', False) or getattr(self, 'entry_amount', 0) <= 0:
            return
        if self.test_mode:
            self.logger.info(f"🧪 Startup: test mode, skipping exchange check for {asset}")
            return
        try:
            bal = await self.exchange.fetch_balance()
            free_bal = float(bal.get(asset, {}).get('free', 0) or 0)
            total_bal = float(bal.get(asset, {}).get('total', 0) or 0)
            actual_bal = max(free_bal, total_bal)
            if actual_bal < self.entry_amount * 0.99:
                await self._clean_phantom_position(asset, actual_bal)
                self.logger.info(f"✅ Startup validation: cleaned phantom {asset}")
            else:
                self.logger.info(f"✅ Startup validation: position confirmed {asset}")
        except Exception as e:
            self.logger.warning(f"Startup validation error {self.bot_name}: {e}")

    # ── Per-bot drawdown / stop-loss ─────────────────────────
    def check_drawdown(self) -> bool:
        """
        Controlla se questo bot ha superato il suo stop-loss individuale.
        Returns True = still OK, False = drawdown exceeded → bot should stop.
        """
        if self.max_drawdown_eur <= 0 or not self._balance_snapshot_taken:
            return True  # no limit or no snapshot yet

        # P&L relativo al picco (non all'inizio): massimo drawdown storico
        current_eur = self._initial_balance_eur + self._total_pnl_eur
        drawdown_from_peak = self._peak_balance_eur - current_eur

        if drawdown_from_peak >= self.max_drawdown_eur:
            self.logger.error(
                f"☠️ PER-BOT STOP-LOSS {self.bot_name}: "
                f"drawdown {drawdown_from_peak:.2f}€ >= limit {self.max_drawdown_eur:.1f}€ | "
                f"initial={self._initial_balance_eur:.2f} current={current_eur:.2f} peak={self._peak_balance_eur:.2f}"
            )
            self._drawdown_stopped = True
            return False

        if self._drawdown_stopped:
            # Bot era già stato fermato, non riattivare
            return False

        return True

    async def _emergency_close_per_bot(self):
        """
        Chiude la posizione di QUESTO bot (market sell) e cancella tutti gli ordini aperti.
        """
        if self.test_mode:
            return

        # 1. Se in posizione → market sell
        if getattr(self, 'in_position', False):
            symbol = getattr(self, 'symbol', None) or getattr(self, 'symbol_a', None)
            amount = getattr(self, 'entry_amount', 0)
            if symbol and amount > 0:
                base = symbol.split('/')[0]
                try:
                    bal = await self.exchange.fetch_balance()
                    actual_amount = float(bal.get(base, {}).get('free', 0) or 0)
                    if actual_amount > 0:
                        sell_amt = actual_amount * 0.997
                        base = symbol.split('/')[0]
                        LOT_STEPS = {'ETH': 0.0001, 'BTC': 0.00001, 'BNB': 0.001, 'SOL': 0.001, 'DOGE': 1.0}
                        step = LOT_STEPS.get(base, 0.0001)
                        rounded = math.floor(sell_amt / step) * step
                        if rounded > 0:
                            self.logger.warning(f"🚨 {self.bot_name}: EMERGENCY MARKET SELL {symbol} {rounded:.8f}")
                            await self.exchange.create_market_sell_order(symbol, rounded)
                        else:
                            self.logger.warning(f"⚠️ {self.bot_name}: {symbol} amount {sell_amt:.8f} rounds to 0 (step={step}) — skipping sell")
                    else:
                        self.logger.warning(f"⚠️ {self.bot_name}: no {base} balance to sell")
                except Exception as e:
                    self.logger.error(f"❌ {self.bot_name}: emergency sell failed: {e}")

                self.in_position = False
                self.entry_price = 0
                self.entry_amount = 0
                self.save_position_to_db()

        # 2. Cancella ordini aperti su questo simbolo
        try:
            sym = getattr(self, 'symbol', None) or getattr(self, 'symbol_a', None)
            if sym:
                orders = await self.exchange.fetch_open_orders(sym)
                for o in orders:
                    try:
                        await self.exchange.cancel_order(o['id'], sym)
                        self.logger.info(f"🗑️ {self.bot_name}: cancelled order {o['id']} ({o['side']} {o['amount']} @ {o['price']})")
                    except Exception as e:
                        self.logger.warning(f"⚠️ {self.bot_name}: cancel order {o['id']} failed: {e}")
        except Exception as e:
            self.logger.warning(f"⚠️ {self.bot_name}: cancel orders failed: {e}")

    async def close(self):
        if self.exchange:
            await self.exchange.close()

    async def run_strategy(self):
        raise NotImplementedError

    async def start(self):
        self.running = True
        interval = self.config.get("interval_sec", 30)

        # ── Kill-switch check all'avvio ──
        if not self.kill_switch.check_bot_can_start(self.bot_name):
            self.logger.error(f"☠️ {self.bot_name}: BLOCKED by kill-switch on startup — not starting.")
            self.running = False
            return

        self.logger.info(f"=== PRE-STARTUP CHECK ===")
        await self.on_startup()
        self.logger.info(f"=== POST-STARTUP (in_position={getattr(self, 'in_position', 'N/A')}) ===")
        self.logger.info(f"{self.bot_name} started (interval={interval}s, test_mode={self.test_mode}).")

        # Tick counter for periodic balance refresh
        tick = 0

        while self.running:
            try:
                # Periodic balance refresh (every 10 ticks or 30s max)
                tick += 1
                if tick % 3 == 0 or tick == 1:
                    await self.refresh_balance()

                await self.refresh_open_orders()

                # Per-bot stop-loss check: se superato, esci e fermati
                if not self._drawdown_stopped and not self.check_drawdown() and not self.test_mode:
                    await self._emergency_close_per_bot()
                    self.kill_switch.lock_bot(self.bot_name)
                    self.logger.error(f"☠️ {self.bot_name}: drawdown limit hit — LOCKED by kill-switch")
                    self.running = False
                    break

                await self.run_strategy()
            except Exception as e:
                self.logger.error(f"Strategy error: {e}", exc_info=True)
            await asyncio.sleep(interval)

    async def on_startup(self):
        """Base startup: kill-switch check. Subclasses can extend."""
        if not self.kill_switch.check_bot_can_start(self.bot_name):
            self.logger.error(f"☠️ {self.bot_name}: kill-switch LOCKED on startup")
            self.running = False

    def _record_completed_trade(self, pnl_pct: float):
        """Registra trade completato nel kill-switch (circuit breaker)."""
        self._last_trade_pnl_pct = pnl_pct
        if pnl_pct < 0:
            tripped = self.kill_switch.record_loss(self.bot_name, self.max_consecutive_losses)
            if tripped:
                self.logger.error(
                    f"🚨 CIRCUIT BREAKER {self.bot_name}: "
                    f"{self.kill_switch.consecutive_losses(self.bot_name)} consecutive losses >= "
                    f"{self.max_consecutive_losses} — bot LOCKED"
                )
        else:
            self.kill_switch.record_win(self.bot_name)

    def stop(self):
        self.running = False

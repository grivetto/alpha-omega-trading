"""                                                                                                                                                                                                             
DenaroOpportunisticCore v2.1 — Base asincrona per la Squadra Denaro Opportunistico.                                                         
v2.1: Aggiunto TradeDB persistence + balance check pre-sell + startup validation.                                                            
Legge .env dalla directory padre (denaro/), fornisce exchange + OHLCV + logging.                                                            
"""                                                                                                                                                                                                         
import os, json, logging, asyncio, time                                                                                                     
import ccxt.async_support as ccxt                                                                                                           
from dotenv import load_dotenv                                                                                                              
                                                                                                                                            
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))                                                                                     
PARENT_DIR = os.path.dirname(SCRIPT_DIR)                                                                                                    
ENV_PATH = os.path.join(PARENT_DIR, ".env")                                                                                                 
load_dotenv(ENV_PATH)                                                                                                                       
                                                                                                                                            
# Import TradeDB from parent directory                                                                                                      
import sys                                                                                                                                  
sys.path.insert(0, PARENT_DIR)                                                                                                              
from trade_db import TradeDB

class DenaroOpportunisticCore:
    def __init__(self, bot_name="Generic", config_file=None):
        self.bot_name = bot_name
        self.logger = logging.getLogger(f"Squadra-{bot_name}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.debug(f"Logger initialized for {bot_name}, effective level: {self.logger.getEffectiveLevel()}, root level: {logging.getLogger().getEffectiveLevel()}")
        self.config = {}
        if config_file:
            self.load_config(config_file)
        
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
        self.positions = {}
        self.open_orders = []
        self.running = False
        
        # v2.1: DB persistence
        self.db = TradeDB(os.path.join(PARENT_DIR, "trades.db"))
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
        try:
            bal = await self.exchange.fetch_balance()
            self.balance = bal.get("free", {})
            self.logger.debug(f"Balance refreshed: {len(self.balance)} assets")
        except Exception as e:
            self.logger.error(f"Balance refresh error: {e}")

    async def refresh_open_orders(self):
        try:
            symbol = self.config.get("symbol") or self.config.get("symbol_a")
            if symbol:
                self.open_orders = await self.exchange.fetch_open_orders(symbol)
            else:
                self.open_orders = await self.exchange.fetch_open_orders()
        except Exception as e:
            self.logger.error(f"Open orders error: {e}")

    async def fetch_ohlcv(self, symbol: str, timeframe="1m", limit=50):
        try:
            ohlcv = await self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            return ohlcv
        except Exception as e:
            self.logger.error(f"OHLCV error {symbol}: {e}")
            return []

    async def create_limit_buy(self, symbol, amount, price, reduce=False):
        try:
            order = await self.exchange.create_limit_buy_order(symbol, amount, price)
            self.logger.info(f"BUY {symbol} {amount:.4f} @ {price:.2f}")
            return order
        except Exception as e:
            self.logger.error(f"Buy error {symbol}: {e}")
            return None

    async def create_limit_sell(self, symbol, amount, price, reduce=False):
        try:
            order = await self.exchange.create_limit_sell_order(symbol, amount, price)
            self.logger.info(f"SELL {symbol} {amount:.4f} @ {price:.2f}")
            return order
        except Exception as e:
            self.logger.error(f"Sell error {symbol}: {e}")
            return None

    # ── v2.1: DB persistence ────────────────────────────────
    def save_position_to_db(self):
        """Save current position state to SQLite."""
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
        """Restore position state from SQLite. Returns True if a position was restored."""
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

    # ── v2.1: Balance validation ────────────────────────────
    async def validate_balance_before_sell(self, asset: str, required_qty: float) -> bool:
        """Check if we actually own the asset before selling.
        Returns True if balance is sufficient, False if phantom."""
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
            # On error, allow the sell to proceed (better than blocking a real sell)
            return True

    async def _clean_phantom_position(self, asset: str, actual_bal: float):
        """Reset position state without selling on exchange."""
        self.logger.info(f"🧹 {self.bot_name}: cleaning phantom position for {asset}")
        self.in_position = False
        self.entry_price = 0.0
        self.entry_amount = 0.0
        self.save_position_to_db()
        self._phantom_cleaned = True

    async def startup_validate_position(self, asset: str):
        """Validate position against real balance at startup."""
        if self._startup_validated:
            return
        self._startup_validated = True
        if not getattr(self, 'in_position', False) or getattr(self, 'entry_amount', 0) <= 0:
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

    async def close(self):
        await self.exchange.close()

    async def run_strategy(self):
        """Override nelle sottoclassi"""
        raise NotImplementedError

    async def start(self):
        self.running = True
        interval = self.config.get("interval_sec", 30)
        self.logger.info(f"=== PRE-STARTUP CHECK ===")
        await self.on_startup()
        self.logger.info(f"=== POST-STARTUP (in_position={getattr(self, 'in_position', 'N/A')}) ===")
        self.logger.info(f"{self.bot_name} started (interval={interval}s).")
        while self.running:
            try:
                # Update heartbeat
                self.db.save_bot_state(self.bot_name, self.in_position,
                    getattr(self, 'entry_price', 0), getattr(self, 'entry_amount', 0),
                    self.tp_pct if hasattr(self, 'tp_pct') else 0,
                    self.sl_pct if hasattr(self, 'sl_pct') else 0,
                    time.time(), 'binance')
                await self.refresh_balance()
                await self.refresh_open_orders()
                await self.run_strategy()
            except Exception as e:
                self.logger.error(f"Strategy error: {e}")
            await asyncio.sleep(interval)

    async def on_startup(self):
        """Override in subclasses for startup validation."""
        pass

    def stop(self):
        self.running = False

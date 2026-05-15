"""
DenaroOpportunisticCore v2.0 — Base asincrona per la Squadra Denaro Opportunistico.
Legge .env dalla directory padre (denaro/), fornisce exchange + OHLCV + logging.
"""
import os, json, logging, asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)
ENV_PATH = os.path.join(PARENT_DIR, ".env")
load_dotenv(ENV_PATH)

class DenaroOpportunisticCore:
    def __init__(self, bot_name="Generic", config_file=None):
        self.bot_name = bot_name
        self.logger = logging.getLogger(f"Squadra-{bot_name}")
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

    async def close(self):
        await self.exchange.close()

    async def run_strategy(self):
        """Override nelle sottoclassi"""
        raise NotImplementedError

    async def start(self):
        self.running = True
        interval = self.config.get("interval_sec", 30)
        self.logger.info(f"{self.bot_name} started (interval={interval}s).")
        while self.running:
            try:
                await self.refresh_balance()
                await self.refresh_open_orders()
                await self.run_strategy()
            except Exception as e:
                self.logger.error(f"Strategy error: {e}")
            await asyncio.sleep(interval)

    def stop(self):
        self.running = False

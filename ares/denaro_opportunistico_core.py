"""DenaroOpportunisticCore — Base class for opportunistic Denaro trading bots.
Uses ccxt.async_support (free) instead of ccxt.pro (paid).
"""
import os, json, logging, asyncio
import ccxt.async_support as ccxt
from dotenv import load_dotenv

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))         # es: /home/sergio/denaro/ares/
BASE_DIR   = os.path.dirname(SCRIPT_DIR)                        # es: /home/sergio/denaro/
load_dotenv(os.path.join(BASE_DIR, ".env"))                     # .env in denaro/

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(message)s')

class DenaroOpportunisticCore:
    """Base class for opportunistic trading bots — async, config-driven."""

    def __init__(self, bot_name="OpportunisticBot"):
        self.bot_name = bot_name
        self.logger = logging.getLogger(self.bot_name)
        self.config = {}
        self.exchange = None
        self.is_running = False

    def load_config(self, config_file):
        """Load config from JSON file."""
        config_path = os.path.join(SCRIPT_DIR, config_file)
        try:
            with open(config_path) as f:
                self.config = json.load(f)
            self.logger.info(f"Config '{config_file}' loaded.")
        except FileNotFoundError:
            self.logger.warning(f"Config '{config_file}' not found, using defaults.")
            self.config = {}
        except Exception as e:
            self.logger.error(f"Config error: {e}")
            self.config = {}

    async def _create_exchange(self):
        """Create async ccxt exchange client."""
        self.exchange = ccxt.binance({
            'apiKey': os.getenv("BINANCE_API_KEY"),
            'secret': os.getenv("BINANCE_API_SECRET"),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
                'defaultFeeCurrency': 'BNB',
            },
        })
        # Load markets
        await self.exchange.load_markets()
        self.logger.info("Exchange initialized.")

    async def fetch_balance(self, currency='EUR'):
        """Fetch free balance for a currency."""
        try:
            bal = await self.exchange.fetch_balance()
            return bal['free'].get(currency, 0)
        except Exception as e:
            self.logger.error(f"Balance fetch error: {e}")
            return 0

    async def create_limit_buy_order(self, symbol, amount, price):
        """Create a limit buy order."""
        try:
            order = await self.exchange.create_limit_buy_order(symbol, amount, price)
            self.logger.info(f"LIMIT BUY {amount} {symbol} @ {price}")
            return order
        except Exception as e:
            self.logger.error(f"Limit buy failed: {e}")
            return None

    async def create_limit_sell_order(self, symbol, amount, price):
        """Create a limit sell order."""
        try:
            order = await self.exchange.create_limit_sell_order(symbol, amount, price)
            self.logger.info(f"LIMIT SELL {amount} {symbol} @ {price}")
            return order
        except Exception as e:
            self.logger.error(f"Limit sell failed: {e}")
            return None

    async def start(self):
        """Start the bot main loop."""
        await self._create_exchange()
        self.is_running = True
        self.logger.info(f"{self.bot_name} started.")
        while self.is_running:
            try:
                await self.run_strategy()
                await asyncio.sleep(self.config.get("interval_sec", 60))
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Loop error: {e}")
                await asyncio.sleep(30)

    async def stop(self):
        """Stop the bot."""
        self.is_running = False
        if self.exchange:
            await self.exchange.close()
        self.logger.info(f"{self.bot_name} stopped.")

    async def run_strategy(self):
        """Override in subclass."""
        raise NotImplementedError

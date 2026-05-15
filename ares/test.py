#!/home/sergio/denaro/venv/bin/python3
import asyncio, logging, sys
sys.path.insert(0, '/home/sergio/denaro/ares')
from ares_intraday_bot import AresIntradayTrendBot
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

async def test():
    bot = AresIntradayTrendBot()
    await bot._create_exchange()
    await bot._fetch_ohlcv()
    print(f"Price: {bot.current_price}")
    print(f"Signal: {bot._generate_signal()}")
    print(f"Candles: {len(bot.close_prices)}")
    await bot.stop()

asyncio.run(test())

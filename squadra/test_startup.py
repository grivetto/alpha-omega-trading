#!/home/sergio/denaro/venv/bin/python3
"""Test startup logging"""
import sys, os, logging
sys.path.insert(0, '/home/sergio/denaro/squadra')

# Configure logging FIRST
logging.basicConfig(level=logging.DEBUG, force=True,
    handlers=[logging.StreamHandler()])

from core import DenaroOpportunisticCore
from ares_bot import AresIntradayTrendBot
import asyncio

async def test():
    bot = AresIntradayTrendBot()
    print(f"BOT NAME: {bot.bot_name}")
    print(f"LOGGER LEVEL: {bot.logger.level}")
    print(f"ROOT LEVEL: {logging.getLogger().level}")
    print(f"IN_POSITION before: {bot.in_position}")
    # Check DB
    print(f"DB state: {bot.db.load_bot_state('Ares')}")
    # Test load_position_from_db
    result = bot.load_position_from_db()
    print(f"load_position_from_db returned: {result}")
    print(f"IN_POSITION after load: {bot.in_position}")

asyncio.run(test())

#!/home/sergio/denaro/venv/bin/python3
import sys, os
sys.path.insert(0, '/home/sergio/denaro/squadra')
from orchestrator import SquadraOrchestrator
import asyncio, logging

# Force root logger to DEBUG
root = logging.getLogger()
root.setLevel(logging.DEBUG)
for h in root.handlers[:]:
    root.removeHandler(h)

handler = logging.FileHandler('/home/sergio/denaro/squadra/squadra.log')
handler.setLevel(logging.DEBUG)
fmt = logging.Formatter("%(asctime)s - %(name)s - %(message)s")
handler.setFormatter(fmt)
root.addHandler(handler)

# Silenzia i log DEBUG di ccxt (spamma exchangeInfo)
logging.getLogger("ccxt").setLevel(logging.WARNING)
logging.getLogger("ccxt.base.exchange").setLevel(logging.WARNING)

orch = SquadraOrchestrator()
try:
    asyncio.run(orch.run())
except KeyboardInterrupt:
    orch.stop()
    logging.info("Squadra stopped.")

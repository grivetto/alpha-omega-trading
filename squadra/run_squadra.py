#!/home/sergio/denaro/venv/bin/python3
import sys, os
# Squadra directory FIRST — ensures core.py, strategies/, etc. from squadra/ win
SQUADRA_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SQUADRA_DIR)
sys.path.insert(0, SQUADRA_DIR)
# Remove PARENT_DIR from sys.path to avoid shadowing (there's a denaro/core/ and
# denaro/strategies/ that conflict with squadra/ versions)
sys.path = [p for p in sys.path if os.path.realpath(p or '.') != os.path.realpath(PARENT_DIR)]
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

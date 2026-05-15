#!/home/sergio/denaro/venv/bin/python3
import sys, os
sys.path.insert(0, '/home/sergio/denaro/squadra')
from orchestrator import SquadraOrchestrator
import asyncio, logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/home/sergio/denaro/squadra/squadra.log')
    ]
)

orch = SquadraOrchestrator()
try:
    asyncio.run(orch.run())
except KeyboardInterrupt:
    orch.stop()
    logging.info("Squadra stopped.")

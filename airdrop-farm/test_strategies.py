import sys
sys.path.insert(0, "")

from core.config import get_config
from core.orchestrator import Orchestrator

cfg = get_config("config.nuvola.yaml")
orch = Orchestrator("config.nuvola.yaml")
print(f"Strategies loaded: {list(orch.strategies.keys())}")

# Test each strategy
from strategies.airdrop_strategy import AirdropStrategy
from strategies.mexc_strategy import MexcLaunchpadStrategy

airdrop = AirdropStrategy(orch)
mexc = MexcLaunchpadStrategy(orch)

print("\n--- Airdrop Strategy ---")
for i in range(3):
    r = airdrop.execute_dry_run(None)
    print(f"  {r['action']} | gas=${r.get('gas_estimate_usd',0):.2f} | {r.get('details','')}")

print("\n--- MEXC Launchpad Strategy ---")
for i in range(3):
    r = mexc.execute_dry_run(None)
    print(f"  {r['action']} | gas=${r.get('gas_estimate_usd',0):.2f} | {r.get('details','')}")
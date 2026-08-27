#!/usr/bin/env python3
"""
ATLAS EXCHANGE — Main loop exchange-agnostico (route verso ATLAS).

La vecchia famiglia di engine (main_v5.py, main_mexc.py, denaro.*) e' stata
rimossa: TUTTI gli exchange girano ora sull'engine unico `atlas` (ccxt-based).

  EXCHANGE=kraken|okx|mexc|bybit  ->  atlas.main (engine unico)

La selezione per-exchange avviene tramite config/exchanges.yaml (chiavi per
exchange). Se EXCHANGE non e' settata, atlas carica tutte le exchange abilitate.

NOTA: `import run` NON avvia il bot — serve la guardia __main__ (come main.py).
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

env_path = Path(__file__).parent / ".env"
if not env_path.exists():
    env_path = Path.home() / "denaro" / ".env"

exchange = os.environ.get("EXCHANGE", "")
if not exchange and env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("EXCHANGE="):
                exchange = line.split("=", 1)[1].strip().strip('"').strip("'").lower()

SUPPORTED = {"kraken", "okx", "mexc", "bybit", ""}
if exchange not in SUPPORTED:
    print(f"Unknown exchange: {exchange!r} (supported: {sorted(SUPPORTED - {''})})")
    sys.exit(1)


def main() -> None:
    print(f"ATLAS Exchange Router: exchange={exchange or 'all (config)'}")
    import main as _launcher  # noqa: PLC0415  (stesso entry point ATLAS)
    _launcher.main()


if __name__ == "__main__":
    main()

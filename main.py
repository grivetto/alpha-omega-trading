#!/usr/bin/env python3
"""
ATLAS — launcher (entry point).

The engine lives in the `atlas` package (atlas/main.py). This file is a thin
backward-compatible wrapper so existing deploy scripts (`python main.py`) keep
working after the denaro-v6 package removal.

Run:  python main.py            (reads config/ + .env)
      python -m atlas.main      (same engine, package entry)
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

# ─── Env surface (legacy, kept for deploy-script compatibility) ─────────────
SYMBOL      = os.environ.get("SYMBOL", "DOGE/EUR")
CAPITAL     = float(os.environ.get("CAPITAL", "100.0"))
LEVELS      = int(os.environ.get("LEVELS", "5"))
BASE_SPREAD = float(os.environ.get("SPREAD", "0.025"))
TAKE_PROFIT = float(os.environ.get("TAKE_PROFIT", "0.03"))
COOLDOWN    = int(os.environ.get("COOLDOWN", "30"))
MAX_DEPLOYED = float(os.environ.get("MAX_DEPLOYED", "0.50"))
MIN_ORDER_EUR = float(os.environ.get("MIN_ORDER_EUR", "1.0"))
SHADOW_MODE = os.environ.get("SHADOW_MODE", "1") == "1"
MOCK_MODE   = os.environ.get("MOCK_MODE", "0") == "1"
LOG_FILE    = Path(os.environ.get("LOG_FILE", str(Path(__file__).parent / "atlas_bot.log")))
HEALTH_PORT = int(os.environ.get("HEALTH_PORT", "8909"))


def main() -> None:
    # Safety guard STRETTA: l'engine atlas NON implementa shadow/mock (legge
    # config/exchanges.yaml con sandbox:false e piazza ordini reali).
    # Default DENY: serve ATLAS_ALLOW_LIVE=1 esplicito per ogni avvio live.
    if os.environ.get("ATLAS_ALLOW_LIVE") != "1":
        print(
            "FATAL: ATLAS piazza ordini REALI (shadow/mock non implementato).\n"
            "  Imposta ATLAS_ALLOW_LIVE=1 SOLO se vuoi davvero tradare con capitale reale.",
            file=sys.stderr,
        )
        sys.exit(2)

    try:
        from atlas.main import main as atlas_main
    except ImportError as e:
        print(f"FATAL: ATLAS engine non importabile: {e}", file=sys.stderr)
        print("Verifica che il package `atlas` esista (git submodule/checkout).", file=sys.stderr)
        sys.exit(1)

    mode = "SHADOW" if SHADOW_MODE else "MOCK" if MOCK_MODE else "LIVE"
    print(f"ATLAS launcher: env={mode} health_port={HEALTH_PORT} log={LOG_FILE}")
    try:
        asyncio.run(atlas_main())
    except KeyboardInterrupt:
        print("Interrotto da segnale.")


if __name__ == "__main__":
    main()

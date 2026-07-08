#!/usr/bin/env python3
"""Generate main_mexc.py from main_v5.py template."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))

src = Path(__file__).resolve().parent / "main_v5.py"
dst = Path(__file__).resolve().parent / "main_mexc.py"

content = src.read_text(encoding="utf-8")
content = content.replace(
    "from bybit_engine import BybitEngine, SYMBOL as _DEFAULT_SYMBOL",
    "from mexc_engine import MexcEngine, SYMBOL as _DEFAULT_SYMBOL"
)
content = content.replace("BybitEngine", "MexcEngine")
content = content.replace("bybit_v5", "mexc_v1")
content = content.replace("bybit_bot.log", "mexc_bot.log")
content = content.replace("bybit_core_state.json", "mexc_core_state.json")
content = content.replace("BYBIT_API", "MEXC_API")
content = content.replace("BYBIT_SECRET", "MEXC_SECRET")
content = content.replace("HEALTH_PORT = 8911", "HEALTH_PORT = 8912")
content = content.replace("DENARO v5", "DENARO MEXC")
content = content.replace("Denaro v5", "Denaro MEXC")
content = content.replace("v5", "mexc")
content = content.replace("SU Denaro MEXC", "SU Denaro MEXC")  # prevent double replace

dst.write_text(content, encoding="utf-8")
print(f"Created {dst}")

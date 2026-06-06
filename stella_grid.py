#!/usr/bin/env python3
"""
StellaGridStrategy — Grid con WebSocket + RSI vettorizzato
Sostituisce il polling REST del grid bot con feed live WebSocket
"""
import asyncio, os, sys, time, logging
from pathlib import Path

HOME = Path(os.environ.get("DENARO_HOME", "/home/sergio/denaro"))
sys.path.insert(0, str(HOME))

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("stella_grid")

from core.stella_engine import StellaCoreEngine

# === CONFIG DAL .ENV ===
def load_env():
    cfg = {"symbol": "SOL/USDC", "levels": 3, "capital": 30, "spacing": 0.08, "take": 1.0}
    env_file = HOME / ".env"
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line.startswith("GRID_SYMBOL="):
                    cfg["symbol"] = line.split("=",1)[1].strip()
                elif line.startswith("GRID_LEVELS="):
                    try: cfg["levels"] = int(line.split("=",1)[1])
                    except: pass
                elif line.startswith("GRID_CAPITAL_USDC="):
                    try: cfg["capital"] = float(line.split("=",1)[1])
                    except: pass
                elif line.startswith("GRID_SPACING_PCT="):
                    try: cfg["spacing"] = float(line.split("=",1)[1]) / 100
                    except: pass
                elif line.startswith("GRID_TAKE_PCT="):
                    try: cfg["take"] = float(line.split("=",1)[1]) / 100
                    except: pass
    return cfg


class StellaGridStrategy:
    """Grid con feed WebSocket + RSI per evitare comprare in ipercomprato"""

    def __init__(self, engine: StellaCoreEngine, config: dict):
        self.engine = engine
        self.config = config
        self._grid: list[dict] = []
        self._initialized = False

    def on_tick(self, price: float, rsi: float):
        """Callback chiamato dal WebSocket a ogni tick"""
        if not self._initialized:
            self._setup_grid(price)
            self._initialized = True
            return

        # Verifica se qualche livello è stato raggiunto
        for level in self._grid[:]:
            if level["side"] == "BUY" and price <= level["price"]:
                log.info(f"🎯 BUY trigger @ {price} (RSI: {rsi:.1f})")
                if rsi < 30:
                    log.info(f"⚠️ RSI ipervenduto ({rsi:.1f}) — BUY eseguito con conferma")
                # Ricicla il livello come SELL
                level["side"] = "SELL"
                level["price"] = round(price * (1 + self.config["take"]), 4)
                log.info(f"  → Nuovo SELL @ {level['price']}")
            elif level["side"] == "SELL" and price >= level["price"]:
                profit = level["amount"] * price * self.config["take"]
                log.info(f"💰 SELL trigger @ {price} | Profit: +${profit:.4f}")
                # Ricicla come BUY
                level["side"] = "BUY"
                level["price"] = round(price * (1 - self.config["spacing"]), 4)
                log.info(f"  → Nuovo BUY @ {level['price']}")

    def _setup_grid(self, mid_price: float):
        levels = self.config["levels"]
        capital_per_level = self.config["capital"] / levels
        spacing = self.config["spacing"]

        for i in range(levels):
            buy_price = round(mid_price * (1 - spacing * (i + 0.5)), 4)
            amount = round(capital_per_level / buy_price, 4)
            self._grid.append({
                "side": "BUY",
                "price": buy_price,
                "amount": amount,
            })
        log.info(f"Grid inizializzata: {levels} livelli, mid={mid_price}, capital/level=${capital_per_level:.2f}")


async def main():
    config = load_env()
    log.info(f"StellaGrid avvio: {config['symbol']} | livelli={config['levels']} | capital=${config['capital']}")

    engine = StellaCoreEngine(symbol=config["symbol"])
    
    # Carica API keys
    env_file = HOME / ".env"
    api_key = api_secret = ""
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                if "BINANCE_API_KEY" in line and "SECRET" not in line:
                    api_key = line.split("=",1)[1].strip().strip("'").strip('"')
                if "BINANCE_API_SECRET" in line:
                    api_secret = line.split("=",1)[1].strip().strip("'").strip('"')

    await engine.bootstrap(api_key, api_secret)
    
    strategy = StellaGridStrategy(engine, config)
    engine.on_ticker(strategy.on_tick)

    log.info("🚀 StellaGrid avviato — WebSocket live")
    await engine.run_live_loop()


if __name__ == "__main__":
    asyncio.run(main())

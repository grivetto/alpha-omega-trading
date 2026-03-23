import os
import time
import subprocess
import logging
from datetime import datetime

# Configurazione Log
LOG_FILE = "/root/.openclaw/workspace/fleet_guardian.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Guardian")

# Mappa delle Risorse Progettate (Nome -> Script)
BOT_REGISTRY = {
    "FLASH-UNIT": "flash_surge_unit.py",
    "LIQUID-HARV": "liquidity_harvester.py",
    "NEURAL-PLS": "neural_pulse_v2.py",
    "CENTURION-REV": "centurion_reversion_squad.py",
    "LIQUIDATOR": "liquidator_prime.py",
    "OSCILLATOR": "oscillator_counter_unit.py",
    "FORCED-PROFIT": "forced_profit_unit.py",
    "GRID-ENGINE": "smart_grid_engine.py",
    "MULTI-BOT": "binance_bot_multi.py",
    "VOL-HUNTER": "volatility_hunter.py",
    "REB-SNIPER": "rebound_sniper.py",
    "SHADOW-TR": "shadow_trend_tracer.py",
    "GHOST-RID": "ghost_rider_swing.py",
    "OMEGA-REV": "contrarian_omega_squad.py",
    "OMEGA-FEED": "omega_bottom_feeder.py",
    "SIGMA-CHAOS": "sigma_chaos_engine.py",
    "ARCHITECT": "architect_ai.py",
    "EVOLUTION": "evolution_engine.py",
    "WAR-MACHINE": "war_machine.py",
    "OMEGA-WAR": "omega_war_machine.py",
    "BAIT-TRAP": "bait_and_trap_engine.py",
    "CASH-OUT": "rapid_cash_out.py",
    "BTC-SNIPER": "btc_volatility_sniper.py",
    "ALPHA-WAVE": "sergio_wave_rider.py",
    "SYS-AUTOMA": "triad_sentinel_automa.py",
    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}

# Directory di lavoro e ambiente
WORKSPACE = "/root/.openclaw/workspace"
VENV_PYTHON = f"{WORKSPACE,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}/trading_bot_env/bin/python3"
SYSTEM_PYTHON = "/usr/bin/python3"

def is_running(script_name):
    """Controlla se lo script è in esecuzione."""
    try:
        output = subprocess.check_output(["pgrep", "-f", script_name])
        return len(output) > 0
    except subprocess.CalledProcessError:
        return False

def start_bot(name, script_name):
    """Avvia il bot usando l'interprete corretto (venv o system)."""
    script_path = os.path.join(WORKSPACE, script_name)
    if not os.path.exists(script_path):
        logger.error(f"❌ Script non trovato: {script_path,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}")
        return

    # Alcuni script sono configurati per il sistema, altri per il venv
    # Proviamo prima col venv se esiste, altrimenti system
    python_bin = VENV_PYTHON if os.path.exists(VENV_PYTHON) else SYSTEM_PYTHON
    
    # Comandi speciali per alcuni bot se necessario (al momento standard)
    cmd = [python_bin, script_path]
    
    try:
        # Avvio in background senza bloccare il guardian
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=WORKSPACE)
        logger.info(f"🚀 Avviato {name,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
} ({script_name,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
})")
    except Exception as e:
        logger.error(f"💥 Errore durante l'avvio di {name,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}: {str(e),    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}")

def monitor_and_revive():
    """Ciclo infinito di monitoraggio."""
    logger.info("🛡️ Fleet Guardian Attivo. Protezione risorse avviata.")
    while True:
        for name, script in BOT_REGISTRY.items():
            if not is_running(script):
                logger.warning(f"⚠️ {name,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
} ({script,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
}) è OFFLINE. Tentativo di rianimazione...")
                start_bot(name, script)
            else:
                # logger.debug(f"✅ {name,    "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py",
    "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py",
    "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py",
    "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py",
    "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py"
} è online.")
                pass
        
        # Attesa tra i controlli (30 secondi per non sovraccaricare il sistema)
        time.sleep(30)

if __name__ == "__main__":
    monitor_and_revive()

# Aggiunto monitoraggio Dashboard alla fine
def start_reporter():
    subprocess.Popen([SYSTEM_PYTHON, "/root/.openclaw/workspace/fleet_reporter.py"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=WORKSPACE)
    logger.info("📊 Fleet Reporter per Dashboard avviato.")


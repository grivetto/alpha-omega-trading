import os
import json
import time
import subprocess
from datetime import datetime

STATUS_PATH = "/root/.openclaw/workspace/dashboard/fleet_stats.json"
WORKSPACE = "/root/.openclaw/workspace"

# Elenco bot da monitorare (Nome -> Script)
BOTS = {
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

def get_process_status():
    status = {,    "BTC-ARB": "btc_arbitrage_simple.py",
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
    try:
        ps_output = subprocess.check_output(["ps", "aux"]).decode()
        for name, script in BOTS.items():
            is_on = script in ps_output
            status[name] = {
                "status": "ONLINE" if is_on else "OFFLINE",
                "script": script,
                "last_seen": datetime.now().strftime("%H:%M:%S") if is_on else "N/A"
            ,    "BTC-ARB": "btc_arbitrage_simple.py",
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
    except Exception as e:
        status["error"] = str(e)
    return status

def main():
    while True:
        data = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "fleet": get_process_status()
        ,    "BTC-ARB": "btc_arbitrage_simple.py",
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
        with open(STATUS_PATH, "w") as f:
            json.dump(data, f, indent=2)
        time.sleep(15)

if __name__ == "__main__":
    main()

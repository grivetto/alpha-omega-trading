import os, time, subprocess, logging
logging.basicConfig(level=logging.INFO, filename="fleet_guardian.log", format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger("Guardian")

BOT_REGISTRY = {
    "FLASH-UNIT": "flash_surge_unit.py", "LIQUID-HARV": "liquidity_harvester.py",
    "NEURAL-PLS": "neural_pulse_v2.py", "CENTURION-REV": "centurion_reversion_squad.py",
    "LIQUIDATOR": "liquidator_prime.py", "OSCILLATOR": "oscillator_counter_unit.py",
    "FORCED-PROFIT": "forced_profit_unit.py", "GRID-ENGINE": "smart_grid_engine.py",
    "MULTI-BOT": "binance_bot_multi.py", "VOL-HUNTER": "volatility_hunter.py",
    "REB-SNIPER": "rebound_sniper.py", "SHADOW-TR": "shadow_trend_tracer.py",
    "GHOST-RID": "ghost_rider_swing.py", "OMEGA-REV": "contrarian_omega_squad.py",
    "OMEGA-FEED": "omega_bottom_feeder.py", "SIGMA-CHAOS": "sigma_chaos_engine.py",
    "ARCHITECT": "architect_ai.py", "EVOLUTION": "evolution_engine.py",
    "WAR-MACHINE": "war_machine.py", "OMEGA-WAR": "omega_war_machine.py",
    "BAIT-TRAP": "bait_and_trap_engine.py", "CASH-OUT": "rapid_cash_out.py",
    "BTC-SNIPER": "btc_volatility_sniper.py", "ALPHA-WAVE": "sergio_wave_rider.py",
    "SYS-AUTOMA": "triad_sentinel_automa.py", "BTC-ARB": "btc_arbitrage_simple.py",
    "ETH-MM": "eth_market_maker.py", "BNB-REVERSION": "bnb_mean_reversion.py",
    "SOL-MOMENTUM": "sol_momentum_hunter.py", "WHALE-TRACK": "whale_order_tracker.py",
    "SENTIMENT": "sentiment_analyzer_bot.py", "REBALANCER": "multi_coin_rebalancer.py",
    "FLASH-BUYER": "flash_crash_buyer.py", "BREAKOUT": "breakout_volatility_unit.py",
    "GAS-TRADER": "eth_gas_price_trader.py", "SCALPER-AGG": "aggressive_scalper_aggregator.py",
    "GOAL-TRACKER": "profit_accelerator_goal.py", "TRI-ARB": "triangle_arbitrage_v1.py",
    "HYPER-MM": "hyper_mm_sol.py", "WHALE-PR": "whale_pressure_scaler.py",
    "INV-CORR": "inverse_corr_bot.py", "EMA-CROSS": "ema_cross_scalper.py",
    "MM-BTC": "strategies/concept_gen_20.py", "MM-ETH": "strategies/concept_gen_21.py",
    "SC-BNB": "strategies/concept_gen_22.py", "SC-SOL": "strategies/concept_gen_23.py",
    "VOL-DOGE": "strategies/concept_gen_24.py", "VOL-ADA": "strategies/concept_gen_25.py",
    "VOL-AVAX": "strategies/concept_gen_26.py", "VOL-DOT": "strategies/concept_gen_27.py",
    "QUANT-MAX": "advanced_quant_bot.py", "ARB-PRO": "arbitrage_sentinel.py"
}

WORKSPACE = "/root/.openclaw/workspace"
VENV_PYTHON = f"{WORKSPACE}/trading_bot_env/bin/python3"
SYSTEM_PYTHON = "/usr/bin/python3"

def is_running(script):
    try: return len(subprocess.check_output(["pgrep", "-f", script])) > 0
    except: return False

def start_bot(name, script):
    py = VENV_PYTHON if os.path.exists(VENV_PYTHON) else SYSTEM_PYTHON
    if not os.path.exists(os.path.join(WORKSPACE, script)): return
    try: subprocess.Popen([py, script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=WORKSPACE)
    except: pass

def main():
    logger.info(f"🛡️ ULTRA-FLEET GUARDIAN ACTIVE: {len(BOT_REGISTRY)} BOTS")
    while True:
        for name, script in BOT_REGISTRY.items():
            if not is_running(script): start_bot(name, script)
        time.sleep(20)

if __name__ == "__main__":
    main()

import os, time, subprocess, logging

LOG_FILE = "/home/sergio/.openclaw/workspace/denaro/lite_guardian.log"
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', handlers=[logging.FileHandler(LOG_FILE)])
logger = logging.getLogger("LiteGuardian2.1")

WORKSPACE = "/home/sergio/.openclaw/workspace/denaro"

# Solo 3 processi essenziali, bassissimo consumo CPU
BOT_REGISTRY = {
    "SNIPER_SQUAD": "sniper_squad.py",
    "DASHBOARD": "dashboard/dashboard_server.py",
    "TG-BOT": "telegram_bot_interactive.py",
    "GARIBAN": "gariban_beggar.py",
    "VAMPIRO": "vampire_grid.py",
    "SCIACALLO": "scavenger_doge.py",
    "PHANTOM": "phantom_maker.py",
    "TSUNAMI": "tsunami_rider.py",
    "SCIAME": "hunter_swarm.py",
    "DARKPOOL": "dark_pool_arb.py",
    "STABLE_SCALPER": "stable_scalper.py",
    "BLACKHOLE": "black_hole_absorber.py",
    "STABLESCALPER": "stable_scalper.py",
    "FLASH_CATCHER": "flash_catcher.py",
    "RSI_HUNTER": "rsi_divergence_hunter.py",
    "FUNDING_SNIFFER": "funding_rate_sniffer.py",
    "FLASH_CRASH_ARB": "flash_crash_arbitrageur.py",
    "ZABBIX": "zabbix_watchdog.py",
    "MICRO_TREND": "micro_trend_tracker.py",
}

def is_running(script):
    try:
        base_name = os.path.basename(script)
        out = subprocess.check_output(["pgrep", "-f", f"python.*{base_name}"])
        return True
    except: return False

def start_bot(name, script):
    path = os.path.join(WORKSPACE, script)
    if not os.path.exists(path): return
    try:
        subprocess.Popen(["/usr/bin/python3", path], stdout=open(f"{WORKSPACE}/{name}.log", "a"), stderr=subprocess.STDOUT, cwd=WORKSPACE)
        logger.info(f"Started {name}")
    except Exception as e:
        logger.error(f"Failed to start {name}: {e}")

def main():
    logger.info("🛡️ LITE GUARDIAN 2.1: REINFORCED FOR 100 EUR TARGET")
    # Kill i vecchi processi che occupano memoria e fanno schizzare il server in OOM
    os.system("pkill -f 'binance_bot_aggressive|omega_war_machine|volatility_hunter|fleet_reporter|vault_manager|flash_surge_unit'")
    
    while True:
        for name, script in BOT_REGISTRY.items():
            if not is_running(script):
                logger.info(f"{name} is not running, starting...")
                start_bot(name, script)
                time.sleep(2) 
        time.sleep(15)


    
    # Aggiungi il Gariban Beggar alla flotta Lite Guardian
    BOT_REGISTRY["GARIBAN"] = "gariban_beggar.py"

# --- LEGIONNAIRES (28 BOTS) ---
    BOT_REGISTRY["LEGION_ADA"] = "legion_01_ada.py"
    BOT_REGISTRY["LEGION_AVAX"] = "legion_02_avax.py"
    BOT_REGISTRY["LEGION_LINK"] = "legion_03_link.py"
    BOT_REGISTRY["LEGION_MATIC"] = "legion_04_matic.py"
    BOT_REGISTRY["LEGION_DOT"] = "legion_05_dot.py"
    BOT_REGISTRY["LEGION_UNI"] = "legion_06_uni.py"
    BOT_REGISTRY["LEGION_LTC"] = "legion_07_ltc.py"
    BOT_REGISTRY["LEGION_ATOM"] = "legion_08_atom.py"
    BOT_REGISTRY["LEGION_ETC"] = "legion_09_etc.py"
    BOT_REGISTRY["LEGION_XLM"] = "legion_10_xlm.py"
    BOT_REGISTRY["LEGION_BCH"] = "legion_11_bch.py"
    BOT_REGISTRY["LEGION_ALGO"] = "legion_12_algo.py"
    BOT_REGISTRY["LEGION_VET"] = "legion_13_vet.py"
    BOT_REGISTRY["LEGION_FIL"] = "legion_14_fil.py"
    BOT_REGISTRY["LEGION_AAVE"] = "legion_15_aave.py"
    BOT_REGISTRY["LEGION_EOS"] = "legion_16_eos.py"
    BOT_REGISTRY["LEGION_XTZ"] = "legion_17_xtz.py"
    BOT_REGISTRY["LEGION_MANA"] = "legion_18_mana.py"
    BOT_REGISTRY["LEGION_SAND"] = "legion_19_sand.py"
    BOT_REGISTRY["LEGION_AXS"] = "legion_20_axs.py"
    BOT_REGISTRY["LEGION_GALA"] = "legion_21_gala.py"
    BOT_REGISTRY["LEGION_ENJ"] = "legion_22_enj.py"
    BOT_REGISTRY["LEGION_CHZ"] = "legion_23_chz.py"
    BOT_REGISTRY["LEGION_ZIL"] = "legion_24_zil.py"
    BOT_REGISTRY["LEGION_BAT"] = "legion_25_bat.py"
    BOT_REGISTRY["LEGION_MKR"] = "legion_26_mkr.py"
    BOT_REGISTRY["LEGION_NEAR"] = "legion_27_near.py"
    BOT_REGISTRY["LEGION_FTM"] = "legion_28_ftm.py"

if __name__ == "__main__":
    main()

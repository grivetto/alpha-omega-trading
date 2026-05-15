import gc
import os, time, logging, subprocess, json, gc
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s',
                    handlers=[logging.FileHandler("/home/sergio/denaro/ZABBIX.log"), logging.StreamHandler()])
logger = logging.getLogger("Zabbix")

WORKSPACE = "/home/sergio/denaro"
METRICS_FILE = os.path.join(WORKSPACE, "dashboard", "zabbix_metrics.json")
HISTORY_FILE = os.path.join(WORKSPACE, "zabbix_history.json")

BOTS = {
    "LEGION_MANAGER": "legion_manager_production.py",
    "TG_BOT": "telegram_bot_interactive.py",
    "DASHBOARD": "dashboard_server.py",
}

def get_process_info(script_name):
    try:
        out = subprocess.check_output(f"ps aux | grep '{script_name}' | grep -v grep || true", shell=True).decode().strip()
        if not out: return None
        lines = out.split('\n')
        # Return sum of cpu/mem if multiple
        total_cpu = 0.0
        total_mem = 0.0
        pid = lines[0].split()[1] # take first pid
        for l in lines:
            parts = l.split()
            if len(parts) >= 4:
                total_cpu += float(parts[2])
                total_mem += float(parts[3])
                
        return {
            "pid": pid,
            "cpu": total_cpu,
            "mem": total_mem
        }
    except:
        return None

def main():
    logger.info("👁️ ZABBIX WATCHDOG AVVIATO. Monitoraggio Salute Server e OOM Prevention.")
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r') as f:
                history = json.load(f)
        except: pass

    while True:
        try:
            metrics = {}
            total_cpu = 0.0
            total_mem = 0.0
            
            for name, script in BOTS.items():
                info = get_process_info(script)
                
                # Resolving correct log paths
                if name == "LEGION_MANAGER": log_name = "legion_production.log"
                elif name == "TG_BOT": log_name = "TG-BOT.log"
                elif name == "DASHBOARD": log_name = "DASHBOARD.log"
                else: log_name = f"{name}.log"
                
                log_path = os.path.join(WORKSPACE, log_name)
                
                status = "OFFLINE"
                last_log_sec = 0
                
                if info:
                    status = "ONLINE"
                    total_cpu += info["cpu"]
                    total_mem += info["mem"]
                    
                    if os.path.exists(log_path):
                        last_log_sec = time.time() - os.path.getmtime(log_path)
                        # Zombie if no log update in 15 minutes (900 seconds) AND log exists
                        if last_log_sec > 600 and not name.startswith("LEGION") and name not in ["TG_BOT", "DASHBOARD", "YIELD_FARMER", "LITE_GUARDIAN"]:
                            status = "ZOMBIE"
                            logger.warning(f"🧟 {name} IN STATO ZOMBIE! Log bloccato da {last_log_sec:.0f}s. UCCISIONE IN CORSO PID {info['pid']}!")
                            os.system(f"kill -9 {info['pid']}")
                            info = None
                            status = "KILLED"
                
                metrics[name] = {
                    "status": status,
                    "cpu": round(info["cpu"], 1) if info else 0.0,
                    "mem": round(info["mem"], 1) if info else 0.0,
                    "pid": info["pid"] if info else "---",
                    "log_age_s": round(last_log_sec) if info else 0
                }
                
            now_str = datetime.now().strftime("%H:%M")
            
            history.append({
                "time": now_str,
                "cpu": round(total_cpu, 2),
                "mem": round(total_mem, 2)
            })
            
            if len(history) > 60: history = history[-60:]
                
            try:
                with open(HISTORY_FILE, 'w') as f:
                    json.dump(history, f)
            except: pass
                
            try:
                with open(METRICS_FILE, 'w') as f:
                    json.dump({"timestamp": now_str, "bots": metrics, "history": history}, f)
            except: pass
            
            # Watchdog frequency 1 min
            time.sleep(60)
            gc.collect()
            
        except Exception as e:
            logger.error(f"Errore Watchdog: {e}")
            time.sleep(30)

if __name__ == "__main__":
    main()

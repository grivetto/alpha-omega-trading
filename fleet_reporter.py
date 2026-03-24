import os, json, time, subprocess
from datetime import datetime

STATUS_PATH = "/home/sergio/.openclaw/workspace/denaro/dashboard/fleet_stats.json"

BOTS = {
    "SNIPER-SQUAD": "sniper_squad.py",
    "VAULT-MANAGER": "vault_manager.py",
    "TG-BOT": "telegram_bot_interactive.py",
    "DASHBOARD": "dashboard_server.py"
}

def main():
    while True:
        status = {}
        try:
            ps = subprocess.check_output(["ps", "aux"]).decode()
            
            # Controllo manuale logica vault da sniper squad se non c'è vault manager
            sniper_running = "sniper_squad.py" in ps
            
            for n, s in BOTS.items():
                on = s in ps
                
                # Se sniper squad è in esecuzione, il vault 33% è in esecuzione (integrato nel codice)
                if n == "VAULT-MANAGER" and sniper_running:
                    on = True
                    s = "integrato in sniper_squad"

                status[n] = {
                    "status": "ONLINE" if on else "OFFLINE", 
                    "script": s, 
                    "last_seen": datetime.now().strftime("%H:%M:%S") if on else "N/A"
                }
            
            with open(STATUS_PATH, "w") as f:
                json.dump({"timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "fleet": status}, f, indent=2)
        except Exception as e: 
            print("Errore", e)
        time.sleep(15)

if __name__ == "__main__":
    main()

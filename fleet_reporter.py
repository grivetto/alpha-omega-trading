import os
import json
import time
import logging
from datetime import datetime

# Aggregatore di log per la Dashboard Web
# Scopo: analizzare i file .log di tutti i bot e creare un file JSON cronologico delle azioni

LOG_FILES = {
    "Binance SOL": "sol_scalper.log",
    "Crypto SOL": "cryptocom_scalper.log",
    "BTC Grid": "smart_grid.log",
    "Whale": "whale_monitor.log",
    "Sentinel": "sentinel_trend.log",
    "Commander": "neural_commander.log"
}

def build_fleet_report():
    report = []
    for bot_name, filename in LOG_FILES.items():
        if os.path.exists(filename):
            try:
                with open(filename, 'r') as f:
                    # Prendi le ultime 5 righe significative
                    lines = f.readlines()
                    for line in lines[-10:]:
                        if " - INFO - " in line:
                            parts = line.split(" - INFO - ")
                            report.append({
                                "time": parts[0].split(",")[0],
                                "bot": bot_name,
                                "action": parts[1].strip()
                            })
            except:
                continue
    
    # Ordina per tempo decrescente
    report.sort(key=lambda x: x['time'], reverse=True)
    
    with open('/root/.openclaw/workspace/dashboard/fleet_activity.json', 'w') as f:
        json.dump(report[:30], f, indent=2)

if __name__ == "__main__":
    while True:
        build_fleet_report()
        time.sleep(30)

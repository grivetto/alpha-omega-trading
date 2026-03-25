#!/usr/bin/env python3
"""
Dashboard Server - Orbital Command Edition
"""

import http.server
import socketserver
import os
import sys
import json
from dotenv import load_dotenv
from binance.client import Client

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
BASE_DIR = '/home/sergio/.openclaw/workspace/denaro'
DASHBOARD_DIR = os.path.join(BASE_DIR, 'dashboard')

def get_realtime_balances():
    try:
        load_dotenv(os.path.join(BASE_DIR, '.env'))
        client = Client(os.getenv('BINANCE_API_KEY'), os.getenv('BINANCE_API_SECRET'))
        
        # Recupera vault
        vault_file = os.path.join(BASE_DIR, 'vault.json')
        vault = 0.0
        if os.path.exists(vault_file):
            with open(vault_file, 'r') as f:
                vault = float(json.load(f).get("LOCKED_EUR", 0.0))
                
        # Recupera missione giornaliera (Target e Profit)
        mission_file = os.path.join(BASE_DIR, 'daily_mission.json')
        target = 10.0
        profit_today = 0.0
        if os.path.exists(mission_file):
            with open(mission_file, 'r') as f:
                m = json.load(f)
                target = m.get("target_eur", 10.0)
                profit_today = m.get("profit_today", 0.0)
                
        try:
            eur = float(client.get_asset_balance(asset='EUR')['free'])
        except:
            eur = 0.0
            
        liquid = eur - vault
        if liquid < 0: liquid = 0.0
        
        return {
            "vault": f"{vault:.2f}",
            "liquid": f"{liquid:.2f}",
            "target": f"{target:.2f}",
            "profit_today": f"{profit_today:.2f}"
        }
    except Exception as e:
        return {"vault": "ERR", "liquid": "ERR", "target": "ERR", "profit_today": "ERR"}


def get_combined_logs():
    try:
        # Prende le ultime 30 righe dai log principali per il terminale
        import subprocess
        import json
        log_files = [os.path.join(BASE_DIR, f) for f in ["sniper_squad.log", "GARIBAN.log", "VAMPIRE.log", "SCAVENGER.log", "PHANTOM.log", "TSUNAMI.log", "HUNTER_SWARM.log", "DARKPOOL.log", "BLACKHOLE.log", "STABLE_SCALPER.log", "RSI_HUNTER.log", "FUNDING_SNIFFER.log", "FLASH_CRASH.log", "MICRO_TREND.log", "LIQUIDITY_VACUUM.log", "EUR_USDT_SCALPER.log", "SOL_PULSE_SNIPER.log", "NEON_SNIPER_ZERO.log", "EUR_USDC_NANO.log", "OB_WALL_SNIPER.log"]]
        cmd = ["cat"] + [f for f in log_files if os.path.exists(f)]
        cat_out = subprocess.check_output(cmd)
        
        # Ordina per timestamp grezzo (le prime 19 char sono la data YYYY-MM-DD HH:MM:SS)
        lines = cat_out.decode().splitlines()
        lines = [l for l in lines if len(l) > 20 and l[0:4] == "2026"]
        lines.sort(key=lambda x: x[0:19])
        
        # Prende le ultime 50
        return json.dumps(lines[-50:])
    except:
        return "[]"

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        super().end_headers()
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.path = '/index.html'
        elif self.path == '/fleet_stats.json' or self.path.startswith('/fleet_stats.json?'):
            self.send_json_file(os.path.join(DASHBOARD_DIR, 'fleet_stats.json'))
            return
        elif self.path == '/balances.json' or self.path.startswith('/balances.json?'):
            data = json.dumps(get_realtime_balances())
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data.encode())
            return
        elif self.path == '/syslogs.json' or self.path.startswith('/syslogs.json?'):
            data = get_combined_logs()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data.encode())
            return
        elif self.path == '/zabbix_metrics.json' or self.path.startswith('/zabbix_metrics.json?'):
            self.send_json_file(os.path.join(DASHBOARD_DIR, 'zabbix_metrics.json'))
            return
        elif self.path.startswith('/profit_chart.png'):
            # Generiamo il chart al volo
            os.system("/home/sergio/.openclaw/workspace/denaro/trading_bot_env/bin/python3 /home/sergio/.openclaw/workspace/denaro/generate_profit_chart.py")
            try:
                with open(os.path.join(BASE_DIR, 'profit_chart.png'), 'rb') as f:
                    data = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'image/png')
                self.end_headers()
                self.wfile.write(data)
                return
            except:
                self.send_error(404)
                return
                
        return super().do_GET()
    
    def send_json_file(self, filepath):
        try:
            with open(filepath, 'r') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(data.encode())
        except Exception as e:
            self.send_error(404, str(e))

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    allow_reuse_address = True

if __name__ == '__main__':
    print(f"🚀 Orbital Dashboard Server: http://localhost:{PORT}")
    with ThreadedHTTPServer(("0.0.0.0", PORT), Handler) as httpd:
        httpd.serve_forever()
import sys; sys.path.append('..'); import stablecoin_scalper
# Micro Spread Sniper module integrated

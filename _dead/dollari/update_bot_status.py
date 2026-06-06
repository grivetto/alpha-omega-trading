import psutil
import json
import time
import subprocess

CACHE_FILE = "/home/sergio/denaro/bot_status_cache.json"

def get_remote_processes(ip, port="22", user="sergio", key_file=None):
    try:
        cmd = ["sudo", "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5", "-p", port]
        if key_file:
            cmd.extend(["-i", key_file])
        cmd.append(f"{user}@{ip}")
        cmd.append("ps aux | grep python")
        
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return res.stdout
    except:
        return ""

def update_status():
    while True:
        status = {}
        
        # Local Nuvola
        local_cmds = []
        for proc in psutil.process_iter(['cmdline']):
            try:
                if proc.info['cmdline']:
                    local_cmds.append(' '.join(proc.info['cmdline']))
            except: pass
            
        mc2_cmds = get_remote_processes("93.43.252.114", "2222", "sergio")
        mc3_cmds = get_remote_processes("87.106.222.123", "22", "root", "/home/sergio/.ssh/id_ed25519")
        mc4_cmds = get_remote_processes("18.181.175.176", "22", "ubuntu", "/home/sergio/.ssh/tokyo.pem")
        mc5_cmds = get_remote_processes("52.207.9.162", "22", "ubuntu", "/home/sergio/.ssh/newyork.pem")
        
        all_cmds_str = "\\n".join(local_cmds) + "\\n" + mc2_cmds + "\\n" + mc3_cmds + "\\n" + mc4_cmds + "\\n" + mc5_cmds
        
        status['alpha'] = 'alpha_strike_scalper.py' in all_cmds_str
        status['delta'] = 'squadra_delta_orderflow.py' in all_cmds_str
        status['gamma'] = 'squadra_gamma_pairs.py' in all_cmds_str
        status['kamikaze'] = 'kamikaze_bitget_futures.py' in all_cmds_str
        
        status['strozzino'] = 'funding_arbitrage_estremo.py' in all_cmds_str
        status['dca'] = 'dca_accumulator.py' in all_cmds_str
        status['mev'] = 'mev_sandwich_bot.py' in all_cmds_str
        status['gariban'] = 'gariban_beggar.py' in all_cmds_str
        
        count = 0
        for line in all_cmds_str.split('\\n'):
            if 'python' in line and '.py' in line and ('/denaro/' in line or '/autonomous_bot/' in line):
                count += 1
                
        status['active_bots_count'] = count
        
        with open(CACHE_FILE, 'w') as f:
            json.dump(status, f)
            
        time.sleep(15)

if __name__ == '__main__':
    update_status()
# BOT_STATUS_CACHE.log

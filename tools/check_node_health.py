#!/usr/bin/env python3
"""
tools/check_node_health.py
Atomic health check for a single Denaro node.
Returns JSON Node Health Response (gemini.md schema).
Usage: check_node_health.py <node_name> <ssh_alias> <node_type> [env_path]
"""
import sys, json, subprocess
from datetime import datetime, timezone

def make_ssh_check(node_type):
    """Returns an ssh_check function bound to node_type."""
    def ssh_check(host, cmd, timeout=10):
        try:
            if node_type == "local":
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                                   timeout=timeout, cwd="/home/sergio/denaro")
            else:
                r = subprocess.run(["ssh","-o","StrictHostKeyChecking=no",
                                    "-o",f"ConnectTimeout={timeout//2}",host,cmd],
                                   capture_output=True, text=True, timeout=timeout)
            return r.stdout.strip(), r.stderr.strip(), r.returncode
        except subprocess.TimeoutExpired:
            return "","SSH_TIMEOUT",-1
        except Exception as e:
            return "",str(e),-1
    return ssh_check

def parse_uptime(stdout):
    try:
        parts = stdout.split()
        # Format: "HH:MM:SS up 22:31, 3 users, load average: 4,68, 4,75, 5,07"
        # Or: "up 10 days, 3:13, load average: 0.11, 0.14, 0.10"
        uidx = parts.index("up")
        load_idx = parts.index("average:")
        days = 0
        us = parts[uidx+1].rstrip(",")
        if "," in us or ":" in us:
            # European format: "22:31," or "1,2"
            if ":" in us:
                hm = us.rstrip(",").split(":")
                hours = int(hm[0]) + int(hm[1])/60
            else:
                hours = float(us.replace(",","."))
        else:
            hours = float(us)
        total_h = days*24+hours
        # Load avg: "4,68," "4,75," "5,07\n" — strip commas and newlines
        def fix_num(s):
            return float(s.rstrip(",\n").replace(",","."))
        la = [fix_num(parts[load_idx+1]), fix_num(parts[load_idx+2]), fix_num(parts[load_idx+3])]
        return total_h, la
    except Exception as e:
        return 0.0, [0.0, 0.0, 0.0]

def parse_meminfo(stdout):
    """Parse free -m output: return (free_mb, available_mb)."""
    try:
        lines = stdout.strip().split("\n")
        # Find the Mem: line (last occurrence)
        mem_line = None
        for line in lines:
            if line.startswith("Mem:"):
                mem_line = line
        if not mem_line:
            return 0, 0
        parts = mem_line.split()
        # Format: Mem: total used free buff/cache available
        if len(parts) >= 7:
            total = int(parts[1])
            used = int(parts[2])
            free = int(parts[3])
            avail = int(parts[6])  # available column
            return free, avail
        return 0, 0
    except Exception as e:
        return 0, 0

if __name__ == "__main__":
    node_name = sys.argv[1]
    ssh_alias = sys.argv[2]
    node_type = sys.argv[3] if len(sys.argv)>3 else "remote"
    env_path = sys.argv[4] if len(sys.argv)>4 else None

    ssh_check = make_ssh_check(node_type)

    res = {
        "node": node_name, "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "DEAD", "uptime_hours": 0.0, "load_avg": [0.0,0.0,0.0],
        "memory_free_mb": 0, "memory_available_mb": 0, "disk_free_gb": 0,
        "grid_bot": {"pid":None,"running":False,"symbol":"SOL/EUR","invested_eur":0.0,"profit_eur":0.0,"open_orders":0,"last_log_age_s":999999},
        "atr": None, "current_price_eur": None, "drawdown_pct": 0.0,
        "binance_balance_eur": 0.0, "binance_balance_sol": 0.0,
        "ssh_connectivity": False, "error": None
    }

    # SSH connectivity
    pong, err, rc = ssh_check(ssh_alias, "echo pong", 10)
    res["ssh_connectivity"] = (rc == 0)
    if not res["ssh_connectivity"] and node_type != "local":
        res["error"] = f"SSH_FAILED: {err[:100]}"
        print(json.dumps(res)); sys.exit(0)

    # System
    out,err,rc = ssh_check(ssh_alias,"uptime"); 
    if rc==0: res["uptime_hours"],res["load_avg"]=parse_uptime(out)

    out,err,rc = ssh_check(ssh_alias,"free -m")
    if rc==0: res["memory_free_mb"],res["memory_available_mb"]=parse_meminfo(out)

    out,err,rc = ssh_check(ssh_alias,"df -BG / | tail -1")
    if rc==0:
        try: res["disk_free_gb"]=int(out.strip().split()[3].rstrip("G"))
        except: pass

    # Grid bot — get PID from ps, log age from file mtime or last log timestamp
    # PID from ps
    ps_out, ps_err, ps_rc = ssh_check(ssh_alias, "ps aux | grep -E 'grid_bot_v3|grid_bot\\.py|grid_v3\\.py' | grep -v grep | head -1")
    pid = None
    if ps_rc == 0 and ps_out.strip():
        parts = ps_out.split()
        try: pid = int(parts[1])
        except: pass

    # Log age from file mtime
    log_paths=["/home/sergio/denaro/logs/grid.log","/home/sergio/denaro/logs/grid_bot.log",
               "/home/marco/denaro/logs/grid.log","/home/marco/denaro/logs/grid_bot.log"]
    if node_type=="local":
        log_paths=["/home/sergio/denaro/logs/grid.log","/home/sergio/denaro/logs/grid_bot.log"]

    log_age = 999999
    orders = 0
    symbol = "SOL/EUR"
    last_line = ""
    for lp in log_paths:
        mtime_out, mtime_err, mtime_rc = ssh_check(ssh_alias, f"stat -c '%Y' {lp} 2>/dev/null || echo NOT_FOUND")
        if mtime_rc == 0 and "NOT_FOUND" not in mtime_out:
            try:
                mtime = int(mtime_out.strip())
                import time
                age = int(time.time()) - mtime
                if age < log_age:
                    log_age = age
                # Also get last log line for orders count
                ll_out, ll_err, ll_rc = ssh_check(ssh_alias, f"tail -1 {lp}")
                if ll_rc == 0 and ll_out.strip():
                    last_line = ll_out.strip()
                    # Parse: "2026-05-02 00:37:15,845 - [GRID] - Price: 71.24€ | Orders: 6"
                    import re
                    m = re.search(r"Orders:\s*(\d+)", last_line)
                    if m: orders = int(m.group(1))
                    m = re.search(r"Symbol:\s*([A-Z]+/[A-Z]+)", last_line)
                    if m: symbol = m.group(1)
            except: pass
            break

    bot_state = {
        "pid": pid,
        "running": pid is not None,
        "symbol": symbol,
        "invested_eur": 0.0,  # Not available in minimal log
        "profit_eur": 0.0,     # Not available in minimal log
        "open_orders": orders,
        "last_log_age_s": log_age
    }
    res["grid_bot"].update(bot_state)

    if res["grid_bot"]["running"] and res["grid_bot"]["last_log_age_s"]<300:
        res["status"]="ALIVE"
    elif res["ssh_connectivity"] or node_type=="local":
        res["status"]="STALE"

    # Determine venv python and env path per node
    if node_type == "local":
        venv_python = "/home/sergio/denaro/venv/bin/python3"
        env_dir = "/home/sergio/denaro"
    elif node_name == "MARCODG1":
        venv_python = "/home/marco/denaro/venv/bin/python3"
        env_dir = "/home/marco/denaro"
    elif node_name == "nuvola":
        venv_python = "/home/sergio/denaro/venv/bin/python3"
        env_dir = "/home/sergio/denaro"
    else:
        venv_python = "/home/sergio/denaro/venv/bin/python3"
        env_dir = "/home/sergio/denaro"

    bal_script = "/tmp/_bal_fetch.py"
    bal_script_content = f"""
import ccxt, os
from dotenv import load_dotenv
load_dotenv('{env_dir}/.env')
c = ccxt.binance({{'apiKey': os.getenv('BINANCE_API_KEY'), 'secret': os.getenv('BINANCE_API_SECRET'), 'enableRateLimit': True}})
bal = c.fetch_balance()
print(f"EUR:{{bal['free'].get('EUR', 0)}}|SOL:{{bal['free'].get('SOL', 0)}}")
"""
    if node_type == "local":
        with open("/tmp/_bal_fetch.py", "w") as f:
            f.write(bal_script_content)
        out, err, rc = ssh_check(ssh_alias, f"{venv_python} /tmp/_bal_fetch.py")
    else:
        ssh_check(ssh_alias, f"mkdir -p /tmp && cat > /tmp/_bal_fetch.py << 'BALSCRIPT'\n{bal_script_content}BALSCRIPT", timeout=15)
        out, err, rc = ssh_check(ssh_alias, f"{venv_python} /tmp/_bal_fetch.py", timeout=15)
    if rc == 0 and "EUR:" in out:
        try:
            parts = out.split("|")
            res["binance_balance_eur"] = float(parts[0].split(":")[1])
            res["binance_balance_sol"] = float(parts[1].split(":")[1])
        except: pass

    print(json.dumps(res))

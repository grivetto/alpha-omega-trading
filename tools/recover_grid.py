#!/usr/bin/env python3
"""
tools/recover_grid.py
Recovers grid bot on a remote node.
Usage: recover_grid.py <node_name> <ssh_alias> [bot_script]
Output: JSON {recovered, pid, error}
"""
import sys
import json
import subprocess
import time

def ssh_check(host, cmd, timeout=20):
    try:
        result = subprocess.run(
            ["ssh", host, cmd],
            capture_output=True, text=True, timeout=timeout
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "SSH_TIMEOUT", -1
    except Exception as e:
        return "", str(e), -1

def main():
    if len(sys.argv) < 3:
        print(json.dumps({"error": "Usage: recover_grid.py <node_name> <ssh_alias> [bot_script]"}))
        sys.exit(1)
    
    node_name = sys.argv[1]
    ssh_alias = sys.argv[2]
    bot_script = sys.argv[3] if len(sys.argv) > 3 else "grid_bot_v3.py"
    
    result = {"recovered": False, "pid": None, "error": None}
    
    # Step 1: Verify node reachable
    out, err, rc = ssh_check(ssh_alias, "echo PING")
    if rc != 0:
        result["error"] = f"Node unreachable: {err}"
        print(json.dumps(result))
        sys.exit(1)
    
    # Step 2: Kill stale processes
    kill_cmd = f"pkill -f 'grid_bot_v3.py'; pkill -f 'denaro_ultimate.py'; pkill -f 'simple_grid.py'"
    ssh_check(ssh_alias, kill_cmd)
    time.sleep(2)
    
    # Step 3: Check disk and memory before restart
    mem_out, _, _ = ssh_check(ssh_alias, "free -m | grep Mem")
    disk_out, _, _ = ssh_check(ssh_alias, "df -h / | tail -1")
    try:
        avail_gb = float(disk_out.split()[-3].replace("G", ""))
        if avail_gb < 10:
            result["error"] = "Insufficient disk space (<10GB)"
            print(json.dumps(result))
            sys.exit(1)
    except: pass
    
    try:
        parts = mem_out.split()
        avail_mb = int(parts[6]) if len(parts) > 6 else int(parts[3])
        if avail_mb < 200:
            result["error"] = "Insufficient memory (<200MB)"
            print(json.dumps(result))
            sys.exit(1)
    except: pass
    
    # Step 4: Start grid bot (screen-based)
    start_cmd = (
        f"cd ~/*/denaro && "
        f"screen -S denaro -dm bash -c 'source venv/bin/activate 2>/dev/null; "
        f"python3 {bot_script} 2>&1 | tee -a logs/grid_recovery.log'"
    )
    ssh_check(ssh_alias, start_cmd)
    time.sleep(10)
    
    # Step 5: Verify bot started
    bot_out, _, _ = ssh_check(ssh_alias, 
        "ps aux | grep grid_bot_v3 | grep -v grep | grep -v watchdog | awk '{print $2}'")
    if bot_out.strip():
        try:
            result["recovered"] = True
            result["pid"] = int(bot_out.strip().split()[0])
        except:
            result["recovered"] = True  # Started but PID parse failed
    else:
        result["error"] = "Bot process not found after recovery"
    
    print(json.dumps(result))
    sys.exit(0)

if __name__ == "__main__":
    main()

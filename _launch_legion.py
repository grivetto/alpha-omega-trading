#!/usr/bin/env python3
"""Lancia LegionManager PROD su tutte le macchine e verifica."""
import subprocess, time

hosts = [
    ("nuvola",    "/home/sergio/denaro",               "sergio"),
    ("mc2",       "/home/sergio/denaro",               "sergio"),
    ("MARCODG1",  "/home/marco/denaro",                "marco"),
]

results = {}

for host, base_dir, user in hosts:
    print(f"\n{'='*60}")
    print(f">> {host}")
    print(f"{'='*60}")

    launch_cmd = (
        f"source {base_dir}/venv/bin/activate && "
        f"cd {base_dir} && "
        f"python3 -u legion_manager_production.py >> legion_production.log 2>&1 & "
        f"echo LAUNCHED_PID=$!"
    )

    try:
        proc = subprocess.Popen(
            ["ssh", "-o", "ConnectTimeout=5", "-t", f"{user}@{host}", launch_cmd],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        out, err = proc.communicate(timeout=30)
        print(f"Launch output: {out.strip()}")
        if err.strip():
            print(f"Stderr: {err.strip()}")
    except Exception as e:
        print(f"Error launching on {host}: {e}")
        results[host] = "FAILED"
        continue

    time.sleep(5)

    check_cmd = (
        f"ps aux | grep 'legion_manager_production.py' | grep -v grep; "
        f"echo '---LAST LOG---'; "
        f"tail -8 {base_dir}/legion_production.log"
    )
    try:
        check = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", f"{user}@{host}", check_cmd],
            capture_output=True, text=True, timeout=15
        )
        output = check.stdout + check.stderr
        print(output)

        if "legion_manager_production.py" in output or "LegionManager PROD avviato" in output:
            results[host] = "RUNNING"
        else:
            results[host] = "FAILED"
    except Exception as e:
        print(f"Error checking {host}: {e}")
        results[host] = "CHECK_ERROR"

print(f"\n{'='*60}")
print("RIASSUNTO FINALE DEPLOY")
print(f"{'='*60}")
for h, s in results.items():
    status = "✅" if s == "RUNNING" else "❌"
    print(f"  {h}: {status} ({s})")
print(f"{'='*60}")
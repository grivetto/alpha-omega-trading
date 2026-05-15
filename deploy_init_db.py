#!/usr/bin/env python3
"""Deploy helper: init TradeDB on a remote host via SSH."""
import subprocess, sys

hosts = [
    ("nuvola", "/home/sergio/denaro", "sergio"),
    ("mc2", "/home/sergio/denaro", "sergio"),
    ("MARCODG1", "/home/marco/denaro", "marco"),
]

for host, base_dir, user in hosts:
    print(f"\n{'='*50}")
    print(f"▶ {host} ({user})")
    print(f"{'='*50}")

    # Init DB script
    init_script = f"""
import sys
sys.path.insert(0, '{base_dir}')
from trade_db import TradeDB
db = TradeDB('{base_dir}/trades.db')
print('DB tables:', db.get_all_tables())
"""
    # Write init script locally, copy, run
    script_path = f"/tmp/init_db_{host}.py"
    with open(script_path, "w") as f:
        f.write(init_script)

    # Copy
    scp = subprocess.run(
        ["scp", "-o", "ConnectTimeout=5", script_path, f"{user}@{host}:{base_dir}/init_db_tmp.py"],
        capture_output=True, text=True
    )
    if scp.returncode != 0:
        print(f"  ❌ SCP failed: {scp.stderr.strip()}")
        continue
    print(f"  ✅ Script copied")

    # Run
    cmd = f"source {base_dir}/venv/bin/activate && cd {base_dir} && python3 init_db_tmp.py && rm init_db_tmp.py"
    result = subprocess.run(
        ["ssh", "-o", "ConnectTimeout=5", f"{user}@{host}", cmd],
        capture_output=True, text=True, timeout=30
    )
    print(result.stdout.strip())
    if result.stderr.strip():
        print("  STDERR:", result.stderr.strip())
    print(f"  {'✅' if result.returncode == 0 else '❌'} {host} done")
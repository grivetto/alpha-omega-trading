#!/usr/bin/env python3
"""
Denaro Auto-Healer v2 — verifica e ripara automaticamente i bot
"""
import subprocess, time, os, sys, json, socket
from pathlib import Path
from datetime import datetime

HOME = Path(os.environ.get("DENARO_HOME", "/home/sergio/denaro"))
LOG_FILE = HOME / "auto_heal.log"
HOSTNAME = socket.gethostname().split('.')[0].upper()

def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")

NODE_HOSTS = {
    "Nuvola": "sergio@nuvola",
    "MC2": "sergio@mc2",
    "MARCODG1": "marco@MARCODG1",
}
NODE_HOMES = {
    "Nuvola": "/home/sergio/denaro",
    "MC2": "/home/sergio/denaro",
    "MARCODG1": "/home/marco/denaro",
}

def is_local(node: str) -> bool:
    return node.upper() == HOSTNAME

def run_cmd(node: str, cmd: str) -> tuple[int, str, str]:
    """Esegue comando localmente o via SSH"""
    if is_local(node):
        try:
            r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=15)
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            return -1, "", str(e)
    else:
        host = NODE_HOSTS.get(node, "sergio@nuvola")
        try:
            r = subprocess.run(
                ["ssh", "-o", "ConnectTimeout=5", host, cmd],
                capture_output=True, text=True, timeout=15
            )
            return r.returncode, r.stdout.strip(), r.stderr.strip()
        except Exception as e:
            return -1, "", str(e)

def check_service(node: str, svc_name: str) -> str:
    code, out, err = run_cmd(node, f"sudo systemctl is-active {svc_name} 2>/dev/null")
    return out.strip() if code == 0 else "unknown"

def check_grid_health(node: str, log_file: str) -> dict:
    home = NODE_HOMES.get(node, "/home/sergio/denaro")
    code, out, err = run_cmd(node, f"tail -30 {home}/{log_file} 2>/dev/null | grep -E 'Active levels|ERROR|Capping|insufficient|Traceback|SyntaxError'")
    result = {"active_levels": -1, "errors": [], "warnings": []}
    for line in out.split("\n"):
        if "Active levels:" in line:
            try:
                parts = line.split("Active levels:")[1].strip()
                active = int(parts.split("/")[0])
                result["active_levels"] = active
            except: pass
        if "ERROR" in line or "Traceback" in line or "SyntaxError" in line:
            result["errors"].append(line[-200:])
        if "insufficient" in line.lower() or "Capping" in line:
            result["warnings"].append(line[-200:])
    return result

def restart_service(node: str, svc_name: str) -> bool:
    code, out, err = run_cmd(node, f"sudo systemctl restart {svc_name} 2>&1")
    return code == 0

def fix_port_conflict(node: str) -> bool:
    code, out, err = run_cmd(node, "for port in 8001 8002 8003 8004 8005; do sudo fuser -k $port/tcp 2>/dev/null; done; echo FIXED")
    return "FIXED" in out

def fix_syntax(node: str) -> bool:
    home = NODE_HOMES.get(node, "/home/sergio/denaro")
    code, out, err = run_cmd(node, f"""
        cd {home}
        python3 -c "import py_compile; py_compile.compile('strategies/base.py', doraise=True); py_compile.compile('strategies/grid.py', doraise=True); py_compile.compile('strategies/scalper.py', doraise=True)" 2>&1 && echo SYNTAX_OK || echo SYNTAX_ERROR
    """)
    if "SYNTAX_OK" not in out:
        log(f"  ⚠️ Errori di sintassi su {node} — serve intervento manuale")
        return False
    return True

SERVICES = {
    "Nuvola": [
        {"name": "denaro-stella", "type": "stella", "log": None, "enabled": True},
        {"name": "denaro-flash-crash", "type": "monitor", "enabled": True},
    ],
    "MC2": [
        {"name": "denaro-mc2", "type": "grid", "log": "grid_bot_v3.log", "enabled": True},
        {"name": "denaro-flash-crash", "type": "monitor", "enabled": True},
    ],
    "MARCODG1": [
        {"name": "denaro-marcodg1", "type": "grid", "log": "marcodg1.log", "enabled": True},
        {"name": "denaro-flash-crash", "type": "monitor", "enabled": True},
        {"name": "denaro-pattern-pro", "type": "pattern", "enabled": True},
    ],
}

def heal_node(node: str, services: list):
    log(f"🔍 {node}...")
    for svc in services:
        if not svc.get("enabled", True):
            continue
        name = svc["name"]
        status = check_service(node, name)
        if status == "active":
            if svc.get("log") and svc.get("type") == "grid":
                health = check_grid_health(node, svc["log"])
                if health["active_levels"] == 0:
                    log(f"  🔄 {name}: 0 livelli — restart")
                    restart_service(node, name)
                elif health["errors"]:
                    log(f"  🔄 {name}: errori — restart")
                    restart_service(node, name)
                elif health["warnings"]:
                    log(f"  ⚠️ {name}: warning — {health['warnings'][-1][:80] if health['warnings'] else ''}")
                else:
                    log(f"  ✅ {name}: livelli={health['active_levels']}" if health['active_levels'] > 0 else f"  ✅ {name}: OK")
            else:
                log(f"  ✅ {name}")
        elif status in ("inactive", "failed"):
            log(f"  🔴 {name}: {status} — restart...")
            restart_service(node, name)
            time.sleep(3)
            new = check_service(node, name)
            log(f"     → {new}")
        else:
            log(f"  ❓ {name}: stato sconosciuto")
    
    # Syntax check
    fix_syntax(node)

def main():
    log("=" * 50)
    log(f"AUTO-HEALER [{HOSTNAME}] — scansione")
    log("=" * 50)
    for node, services in SERVICES.items():
        try:
            heal_node(node, services)
        except Exception as e:
            log(f"  ❌ {node}: {str(e)[:200]}")
    log("Scansione completata.\n")

if __name__ == "__main__":
    main()

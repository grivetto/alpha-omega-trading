"""Brain — helper SSH: esegue comandi in locale o sulle macchine remote."""
from __future__ import annotations

import subprocess

from . import config


def ssh_args(machine: str) -> list[str]:
    base = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8"]
    return base + config.MACHINES[machine]["ssh"]


def run(machine: str, cmd: str, timeout: float = 25.0) -> tuple[int, str]:
    """Esegue `cmd` (bash) su `machine`. Ritorna (rc, stdout+stderr)."""
    try:
        if machine == "marcodg1":
            r = subprocess.run(["bash", "-c", cmd], capture_output=True,
                               text=True, timeout=timeout)
        else:
            r = subprocess.run(ssh_args(machine) + ["bash", "-c", cmd],
                               capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except Exception as e:  # noqa: BLE001
        return -1, f"ssh/exec error: {e}"


def run_sudo(machine: str, cmd: str, timeout: float = 30.0) -> tuple[int, str]:
    """Esegue con sudo -n (passwordless)."""
    return run(machine, f"sudo -n {cmd}", timeout)


def read_json_files(machine: str, paths: list[str]) -> dict[str, dict]:
    """Legge piu' file JSON via ssh in un colpo: {path: dict|None}."""
    if not paths:
        return {}
    quoted = " ".join(f'"{p}"' for p in paths)
    cmd = f'for f in {quoted}; do echo "===F==="; cat "$f" 2>/dev/null; echo; done'
    rc, out = run(machine, cmd, timeout=25.0)
    if rc != 0:
        return {p: None for p in paths}
    result: dict[str, dict] = {}
    blocks = out.split("===F===")[1:]
    for p, block in zip(paths, blocks):
        lines = block.strip().splitlines()
        if not lines:
            result[p] = None
            continue
        try:
            result[p] = json.loads(lines[-1]) if isinstance(
                json.loads(lines[-1]), dict) else None
        except Exception:  # noqa: BLE001
            result[p] = None
    return result

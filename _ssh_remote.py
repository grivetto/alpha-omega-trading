#!/usr/bin/env python3
"""SSH helper via paramiko — uses sergio's id_ed25519 and ~/.ssh/config.

Usage:
    python _ssh_remote.py <host_alias> "<remote command>"

Hosts resolved from %USERPROFILE%\\.ssh\\config (nuvola, MARCODG1, mc2 ...).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko


def load_ssh_config() -> dict:
    """Minimal parser: Host alias -> {hostname, user, port}."""
    cfg_path = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".ssh" / "config"
    hosts: dict = {}
    current = None
    if cfg_path.exists():
        for line in cfg_path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split(None, 1)
            if len(parts) < 2:
                continue
            key, val = parts[0].lower(), parts[1]
            if key == "host":
                current = val.split()[0]
                hosts.setdefault(current, {"hostname": None, "user": None, "port": 22})
            elif current and key in ("hostname", "user", "port"):
                if key == "port":
                    hosts[current][key] = int(val)
                else:
                    hosts[current][key] = val
    return hosts


def connect(alias: str):
    cfg = load_ssh_config()
    if alias not in cfg:
        sys.stderr.write(f"unknown host alias: {alias}\n")
        sys.exit(2)
    host = cfg[alias]
    hostname = host["hostname"] or alias
    user = host["user"] or os.environ.get("USERNAME", "sergio")
    port = host["port"] or 22

    ssh_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".ssh"
    key = None
    for kname in ("id_ed25519", "id_rsa"):
        kpath = ssh_dir / kname
        if kpath.exists():
            key = paramiko.Ed25519Key.from_private_key_file(str(kpath)) if kname == "id_ed25519" \
                else paramiko.RSAKey.from_private_key_file(str(kpath))
            break
    if key is None:
        sys.stderr.write("no ssh key found in ~/.ssh\n")
        sys.exit(2)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname, port=port, username=user, pkey=key,
                   timeout=15, banner_timeout=15, auth_timeout=15,
                   allow_agent=True, look_for_keys=False)
    return client, hostname, user


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python _ssh_remote.py <host> \"<command>\"")
        return 2
    alias, command = sys.argv[1], sys.argv[2]
    client, hostname, user = connect(alias)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=60)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if out:
            print(out, end="")
        if err:
            print("[stderr]", err, end="")
        print(f"EXIT={code}")
        return 0 if code == 0 else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())

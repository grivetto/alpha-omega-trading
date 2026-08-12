#!/usr/bin/env python3
"""Run a remote command read from stdin (no cmd quoting issues).

Usage:
    python _ssh_run.py <host> < _remote_script.sh

Reads the whole stdin, executes it on the remote via paramiko, prints output.
"""
from __future__ import annotations

import sys

from _ssh_remote import connect


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python _ssh_run.py <host>  (command from stdin)")
        return 2
    alias = sys.argv[1]
    command = sys.stdin.read()
    if not command.strip():
        print("empty command from stdin")
        return 2

    client, hostname, user = connect(alias)
    try:
        stdin, stdout, stderr = client.exec_command(command, timeout=120)
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

#!/usr/bin/env python3
"""Robust remote exec: no stdin, channel timeout, bounded recv loop.

Usage:
    python _ssh_exec.py <host> "<remote command>" [timeout_secs]

Never hangs: total runtime is bounded by the deadline; partial output is
returned on timeout so you can see where the remote got stuck.
"""
from __future__ import annotations

import sys
import time

from _ssh_remote import connect


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: python _ssh_exec.py <host> \"<command>\" [timeout]")
        return 2
    alias = sys.argv[1]
    command = " ".join(sys.argv[2:])          # argv join → no cmd quoting needed
    if len(command) >= 2 and command[0] in "\"'" and command[-1] == command[0]:
        command = command[1:-1]
    deadline = 120.0
    # last numeric arg (if any) is the timeout
    for tok in sys.argv[2:]:
        try:
            deadline = float(tok)
        except ValueError:
            pass

    client, hostname, user = connect(alias)
    try:
        chan = client.get_transport().open_session()
        chan.settimeout(15)
        chan.exec_command(command)
        chan.shutdown_write()          # never feed stdin
        chan.settimeout(5)

        out, err = [], []
        start = time.time()
        timed_out = False
        while time.time() - start < deadline:
            try:
                if chan.recv_ready():
                    chunk = chan.recv(65536)
                    if chunk:
                        out.append(chunk.decode("utf-8", errors="replace"))
                        continue
                if chan.recv_stderr_ready():
                    chunk = chan.recv_stderr(65536)
                    if chunk:
                        err.append(chunk.decode("utf-8", errors="replace"))
                        continue
                if chan.exit_status_ready():
                    break
                time.sleep(0.25)
            except Exception:
                break
        else:
            timed_out = True
            try:
                chan.close()
            except Exception:
                pass

        if out:
            sys.stdout.write("".join(out))
        if err:
            sys.stderr.write("".join(err))
        if timed_out:
            print(f"\n[TIMEOUT after {deadline:.0f}s — partial output above]")
            return 124
        code = chan.recv_exit_status() if chan.exit_status_ready() else -1
        print(f"EXIT={code}")
        return 0 if code == 0 else 1
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())

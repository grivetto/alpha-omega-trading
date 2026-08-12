#!/usr/bin/env python3
"""Upload a local file to a remote path via SFTP (paramiko).

Usage:
    python _ssh_sftp.py <host> <local_path> <remote_path>
"""
from __future__ import annotations

import sys

from _ssh_remote import connect


def main() -> int:
    if len(sys.argv) < 4:
        print("usage: python _ssh_sftp.py <host> <local> <remote>")
        return 2
    alias, local, remote = sys.argv[1], sys.argv[2], sys.argv[3]
    client, hostname, user = connect(alias)
    try:
        sftp = client.open_sftp()
        sftp.put(local, remote)
        sftp.close()
        print(f"UPLOADED {local} -> {hostname}:{remote}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())

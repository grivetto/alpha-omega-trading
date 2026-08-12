#!/usr/bin/env python3
"""Check paramiko availability and ssh key files."""
import importlib.util
import os
from pathlib import Path

spec = importlib.util.find_spec("paramiko")
print("PARAMIKO", spec is not None, spec.origin if spec else "")

ssh_dir = Path(os.environ.get("USERPROFILE", str(Path.home()))) / ".ssh"
for name in ["id_ed25519", "id_rsa", "id_ed25519.pub", "known_hosts", "config"]:
    p = ssh_dir / name
    print(f"{name}: {'present' if p.exists() else 'missing'}")

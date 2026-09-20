#!/usr/bin/env python3
"""dsh_status.py — endpoint /api/dsh.json per dashboard.

Espone stato DSH/Stella bridge per monitoraggio real-time.
Da integrare in serve_dashboard.py o come servizio standalone.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

DSH_DIR = Path("/home/sergio/hermes_bridge/dsh")
STELLA_DIR = Path("/home/sergio/hermes_bridge/stella")

def parse_requests_md() -> list[dict]:
    """Parse requests.md → lista richieste con status."""
    path = DSH_DIR / "requests.md"
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    reqs = []
    current = None
    for line in lines:
        if line.startswith("## "):
            if current:
                reqs.append(current)
            parts = line[3:].split(" | ")
            if len(parts) >= 3:
                req_id = parts[0].strip()
                ts = parts[1].strip()
                status = parts[2].strip()
                current = {"id": req_id, "ts": ts, "status": status, "text": ""}
            else:
                current = None
        elif current and line.strip():
            current["text"] += line + "\n"
    if current:
        reqs.append(current)
    return reqs


def parse_results_md() -> list[dict]:
    """Parse results.md → lista risultati."""
    path = DSH_DIR / "results.md"
    if not path.exists():
        return []
    content = path.read_text(encoding="utf-8", errors="replace")
    lines = content.splitlines()
    res = []
    current = None
    for line in lines:
        if line.startswith("## "):
            if current:
                res.append(current)
            parts = line[3:].split(" | ")
            if len(parts) >= 3:
                req_id = parts[0].strip()
                ts = parts[1].strip()
                status = parts[2].strip()
                current = {"id": req_id, "ts": ts, "status": status, "text": ""}
            else:
                current = None
        elif current and line.strip():
            current["text"] += line + "\n"
    if current:
        res.append(current)
    return res


def get_bridge_status() -> dict:
    """Stato bridge Stella/Hermes."""
    state_file = STELLA_DIR / ".bridge_state.json"
    pump_log = STELLA_DIR / "pump.log"
    bridge_log = STELLA_DIR / "bridge.jsonl"
    
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            pass
    
    pump_lines = 0
    if pump_log.exists():
        pump_lines = len(pump_log.read_text().splitlines())
    
    bridge_lines = 0
    if bridge_log.exists():
        bridge_lines = len(bridge_log.read_text().splitlines())
    
    return {
        "state": state,
        "pump_log_lines": pump_lines,
        "bridge_log_lines": bridge_lines,
        "session_id": state.get("session_id", ""),
        "last_pump": state.get("last_pump", ""),
        "pump_count": state.get("pump_count", 0),
    }


def get_fast_bridge_status() -> dict:
    """Stato fast bridge (polling 2.5s)."""
    log_file = STELLA_DIR / "fast_bridge.log"
    state_file = STELLA_DIR / ".bridge_state.json"
    
    state = {}
    if state_file.exists():
        try:
            state = json.loads(state_file.read_text())
        except Exception:
            pass
    
    last_lines = []
    if log_file.exists():
        lines = log_file.read_text().splitlines()
        last_lines = lines[-10:]
    
    return {
        "active": "fast_last_ts" in state,
        "fast_last_ts": state.get("fast_last_ts", 0),
        "fast_last_poll": state.get("fast_last_poll", ""),
        "fast_count": state.get("fast_count", 0),
        "recent_log": last_lines,
    }


def build_dsh_status() -> dict[str, Any]:
    """Costruisce payload completo per /api/dsh.json."""
    requests = parse_requests_md()
    results = parse_results_md()
    
    pending = [r for r in requests if r.get("status") == "PENDING"]
    done = [r for r in requests if r.get("status") == "DONE"]
    
    return {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "timestamp": time.time(),
        "queue": {
            "total": len(requests),
            "pending": len(pending),
            "done": len(done),
            "pending_items": pending[:10],  # max 10
        },
        "recent_results": results[-5:],  # ultimi 5
        "bridge": get_bridge_status(),
        "fast_bridge": get_fast_bridge_status(),
        "dsh_dir": str(DSH_DIR),
        "stella_dir": str(STELLA_DIR),
    }


if __name__ == "__main__":
    print(json.dumps(build_dsh_status(), indent=2, ensure_ascii=False))
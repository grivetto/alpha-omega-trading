#!/usr/bin/env python3
"""
Zabbix monitoring for Alpha-Omega Fleet.
Pushes bot health, PnL, and positions to Zabbix using Zabbix trapper protocol.
Uses SSH to check health endpoints on remote nodes.
"""
import json
import logging
import socket
import struct
import subprocess
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("alpha_omega.zabbix")

# Zabbix configuration
ZABBIX_SERVER = "127.0.0.1"
ZABBIX_PORT = 10051

# Node SSH configuration
NODES = {
    "nuvola": {"ssh_host": "nuvola", "health_port": 8900},
    "marcodg1": {"ssh_host": "marcodg1", "health_port": 8900}
}


def send_to_zabbix(metrics: list) -> bool:
    """Send metrics to Zabbix using trapper protocol."""
    try:
        data = {"request": "sender data", "data": metrics}
        json_data = json.dumps(data)
        
        header = b'ZBXD\x01'
        json_bytes = json_data.encode('utf-8')
        length = struct.pack('<Q', len(json_bytes))
        packet = header + length + json_bytes
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((ZABBIX_SERVER, ZABBIX_PORT))
        sock.sendall(packet)
        response = sock.recv(1024)
        sock.close()
        
        log.info(f"Sent {len(metrics)} metrics to Zabbix")
        return True
    except Exception as e:
        log.warning(f"Failed to send to Zabbix: {e}")
        return False


def fetch_health_via_ssh(ssh_host: str, port: int) -> Optional[Dict[str, Any]]:
    """Fetch health status from fleet coordinator via SSH."""
    try:
        cmd = ["ssh", ssh_host, f"curl -s http://localhost:{port}/health"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0 and result.stdout:
            return json.loads(result.stdout)
        log.warning(f"SSH health check failed: {result.stderr}")
        return None
    except Exception as e:
        log.warning(f"SSH health check error: {e}")
        return None


def monitor_node(node: str, config: dict):
    """Monitor a single fleet coordinator node."""
    log.info(f"Monitoring {node} via SSH")
    
    health = fetch_health_via_ssh(config["ssh_host"], config["health_port"])
    
    metrics = []
    host = f"alpha-omega-{node}"
    import time
    clock = int(time.time())
    
    if health is None:
        metrics.append({"host": host, "key": "fleet.status", "value": "0", "clock": clock})
        metrics.append({"host": host, "key": "fleet.active_bots", "value": "0", "clock": clock})
        metrics.append({"host": host, "key": "fleet.equity", "value": "0", "clock": clock})
        send_to_zabbix(metrics)
        log.warning(f"{node}: DOWN")
        return
    
    active_bots = health.get("active_bots", 0)
    total_bots = health.get("total_bots", 0)
    equity = health.get("fleet_equity", 0)
    positions = health.get("total_positions", 0)
    
    metrics.append({"host": host, "key": "fleet.status", "value": "1", "clock": clock})
    metrics.append({"host": host, "key": "fleet.active_bots", "value": str(active_bots), "clock": clock})
    metrics.append({"host": host, "key": "fleet.total_bots", "value": str(total_bots), "clock": clock})
    metrics.append({"host": host, "key": "fleet.equity", "value": f"{equity:.2f}", "clock": clock})
    metrics.append({"host": host, "key": "fleet.positions", "value": str(positions), "clock": clock})
    
    bots = health.get("bots", [])
    for bot in bots:
        symbol = bot.get("symbol", "unknown").replace("/", "_")
        bot_status = 1 if bot.get("status") == "running" else 0
        bot_equity = bot.get("equity", 0)
        bot_pnl = bot.get("total_pnl", 0)
        
        metrics.append({"host": host, "key": f"bot[{symbol}].status", "value": str(bot_status), "clock": clock})
        metrics.append({"host": host, "key": f"bot[{symbol}].equity", "value": f"{bot_equity:.2f}", "clock": clock})
        metrics.append({"host": host, "key": f"bot[{symbol}].pnl", "value": f"{bot_pnl:.2f}", "clock": clock})
    
    send_to_zabbix(metrics)
    log.info(f"{node}: {active_bots}/{total_bots} bots, equity={equity:.2f}, positions={positions}")


def main():
    """Main monitoring loop."""
    log.info("Starting Zabbix fleet monitoring")
    
    for node, config in NODES.items():
        try:
            monitor_node(node, config)
        except Exception as e:
            log.error(f"Error monitoring {node}: {e}")
    
    log.info("Monitoring complete")


if __name__ == "__main__":
    main()

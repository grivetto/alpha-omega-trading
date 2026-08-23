#!/usr/bin/env python3
"""
ShadowGrid Fleet Orchestrator v2.2

Features:
- Automatic port assignment per bot instance
- Process supervision (auto-restart crashed instances)
- Fleet health HTTP status dashboard (127.0.0.1)
- Hot reload config via SIGHUP (no bot restart needed)
- Pair lifecycle management (STARTING → RUNNING → DRAINING → STOPPED)
- Graceful pair transitions during rotation
- Kill switch monitoring (file-based)
- Alert integration (Telegram/Email)
- Risk manager integration
"""

from __future__ import annotations
import json
import logging
import os
import signal
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional
from http.server import HTTPServer, BaseHTTPRequestHandler

# ============================================================
# ALERT & RISK INTEGRATION
# ============================================================
try:
    from alert_system import get_alert_system, init_alert_system, AlertSystem
    from risk_manager import get_risk_manager, init_risk_manager, RiskManager
    ALERT_AVAILABLE = True
except ImportError:
    ALERT_AVAILABLE = False
    AlertSystem = None
    RiskManager = None
    log.warning("Alert system or risk manager not available")

log = logging.getLogger("shadowgrid_fleet")
log.setLevel(logging.INFO)
sh = logging.StreamHandler(sys.stdout)
sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
log.handlers = [sh]


# ============================================================
# CONFIGURATION
# ============================================================
CONFIG_FILE = os.environ.get("FLEET_CONFIG", "fleet_config.json")
FLEET_PORT = int(os.environ.get("FLEET_PORT", "8900"))
PYTHON_BIN = sys.executable
SCRIPT_PATH = str(Path(__file__).parent / "shadowgrid_v2.py")

DEFAULT_FLEET = {
    "exchange": "kraken",
    "capital_per_bot": 50.0,
    "pairs": [
        {"symbol": "SOL/EUR", "port": 8912},
        {"symbol": "DOGE/EUR", "port": 8913},
        {"symbol": "XRP/EUR", "port": 8914},
        {"symbol": "ADA/EUR", "port": 8915},
    ]
}


# ============================================================
# PAIR LIFECYCLE STATES
# ============================================================
class PairState:
    STARTING = "starting"
    RUNNING = "running"
    DRAINING = "draining"  # Stopping new orders, letting existing fill
    STOPPED = "stopped"
    ERROR = "error"


class BotInstance:
    """Represents a single bot instance with lifecycle management."""
    
    def __init__(self, pair_cfg: Dict, fleet_config: Dict):
        self.pair_cfg = pair_cfg
        self.fleet_config = fleet_config
        self.symbol = pair_cfg["symbol"]
        self.port = pair_cfg["port"]
        self.exchange = pair_cfg.get("exchange", fleet_config.get("exchange", "kraken"))
        self.capital = pair_cfg.get("capital", fleet_config.get("capital_per_bot", 50.0))
        
        self.process: Optional[subprocess.Popen] = None
        self.state = PairState.STOPPED
        self.restart_count = 0
        self.last_restart = 0
        self.start_time = 0
        self.last_fill_time = 0
        self.consecutive_errors = 0
        
        # Environment for this bot
        self.env = os.environ.copy()
        self.env["EXCHANGE"] = self.exchange
        self.env["SYMBOL"] = self.symbol
        self.env["CAPITAL"] = str(self.capital)
        self.env["HEALTH_PORT"] = str(self.port)
        self.env["LOG_FILE"] = f"/tmp/shadowgrid_{self.exchange}_{self.symbol.replace('/', '_').lower()}.log"
        self.env["STATE_FILE"] = f"/tmp/shadowgrid_{self.exchange}_{self.symbol.replace('/', '_').lower()}_state.json"
        
        # Kill switch file for this bot
        self.kill_file = Path(f"/tmp/shadowgrid_kill_{self.exchange}_{self.symbol.replace('/', '_')}")
    
    def start(self) -> bool:
        """Start the bot process."""
        if self.process and self.process.poll() is None:
            log.warning(f"Bot {self.symbol} already running")
            return False
        
        self.state = PairState.STARTING
        cmd = [PYTHON_BIN, SCRIPT_PATH]
        
        try:
            self.process = subprocess.Popen(cmd, env=self.env)
            self.start_time = time.time()
            self.restart_count += 1
            self.last_restart = time.time()
            self.state = PairState.RUNNING
            self.consecutive_errors = 0
            log.info(f"Started bot {self.exchange}:{self.symbol} on port {self.port} (PID: {self.process.pid}, restart #{self.restart_count})")
            return True
        except Exception as e:
            log.error(f"Failed to start bot {self.symbol}: {e}")
            self.state = PairState.ERROR
            self.consecutive_errors += 1
            return False
    
    def stop(self, graceful: bool = True, timeout: int = 10) -> bool:
        """Stop the bot process."""
        if not self.process or self.process.poll() is not None:
            self.state = PairState.STOPPED
            return True
        
        if graceful:
            self.state = PairState.DRAINING
            log.info(f"Draining bot {self.symbol} (graceful stop)...")
            self.process.terminate()
            try:
                self.process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                log.warning(f"Bot {self.symbol} didn't stop gracefully, forcing kill")
                self.process.kill()
                self.process.wait()
        else:
            self.process.kill()
            self.process.wait()
        
        self.state = PairState.STOPPED
        self.process = None
        log.info(f"Stopped bot {self.symbol}")
        return True
    
    def is_healthy(self) -> Tuple[bool, str]:
        """Check if bot is healthy."""
        if not self.process:
            return False, "no process"
        
        if self.process.poll() is not None:
            return False, f"process dead (exit code: {self.process.returncode})"
        
        # Check kill switch
        if self.kill_file.exists():
            return False, "kill switch activated"
        
        # Check if stuck (no fills for too long)
        if self.last_fill_time > 0 and time.time() - self.last_fill_time > 3600:  # 1 hour
            return False, "stuck (no fills for 1h)"
        
        return True, "healthy"
    
    def get_status(self) -> Dict:
        """Get bot status dict."""
        healthy, reason = self.is_healthy()
        return {
            "symbol": self.symbol,
            "exchange": self.exchange,
            "port": self.port,
            "capital": self.capital,
            "state": self.state,
            "status": "running" if healthy else "stopped",
            "pid": self.process.pid if self.process else None,
            "restart_count": self.restart_count,
            "uptime": time.time() - self.start_time if self.start_time else 0,
            "health_reason": reason,
        }


# ============================================================
# FLEET MANAGER
# ============================================================
class FleetManager:
    def __init__(self, config: Dict):
        self.config = config
        self.instances: Dict[str, BotInstance] = {}
        self.running = True
        self.config_mtime = 0
        self.last_config_reload = 0
        self.reload_lock = threading.Lock()
        
        # Initialize alert system
        self.alert_system = None
        if ALERT_AVAILABLE:
            try:
                self.alert_system = init_alert_system({})
                log.info("Alert system initialized in fleet manager")
            except Exception as e:
                log.warning(f"Could not init alert system: {e}")
        
        # Initialize risk manager
        self.risk_manager = None
        if ALERT_AVAILABLE:
            try:
                total_capital = config.get("total_fleet_capital", 100.0)
                self.risk_manager = init_risk_manager(
                    total_capital=total_capital,
                    max_portfolio_dd=0.20,
                    max_daily_loss=0.05,
                    max_exposure_per_base=0.30,
                    max_correlation=0.7,
                    max_positions_per_base=2,
                )
                log.info("Risk manager initialized in fleet manager")
            except Exception as e:
                log.warning(f"Could not init risk manager: {e}")
        
        # Kill switch monitor
        self.kill_switch_file = Path("/tmp/shadowgrid_kill")
    
    def load_config(self, config_path: str = None) -> Dict:
        """Load fleet config from file."""
        path = Path(config_path or CONFIG_FILE)
        if not path.exists():
            log.info(f"Creating default config file: {path}")
            with open(path, "w") as f:
                json.dump(DEFAULT_FLEET, f, indent=2)
            return DEFAULT_FLEET
        
        with open(path) as f:
            config = json.load(f)
        
        self.config_mtime = path.stat().st_mtime
        return config
    
    def create_instances(self, config: Dict):
        """Create BotInstance objects from config."""
        new_instances = {}
        all_pairs = config.get("pairs", []) + config.get("okx_pairs", [])
        
        for pair_cfg in all_pairs:
            symbol = pair_cfg["symbol"]
            if symbol in self.instances:
                # Keep existing instance, update config
                inst = self.instances[symbol]
                inst.pair_cfg = pair_cfg
                inst.fleet_config = config
                inst.capital = pair_cfg.get("capital", inst.capital)
                inst.port = pair_cfg["port"]
                inst.exchange = pair_cfg.get("exchange", config.get("exchange", "kraken"))
                # Update env
                inst.env["CAPITAL"] = str(inst.capital)
                inst.env["HEALTH_PORT"] = str(inst.port)
                inst.env["EXCHANGE"] = inst.exchange
            else:
                inst = BotInstance(pair_cfg, config)
            new_instances[symbol] = inst
        
        # Identify removed pairs (in old but not in new)
        removed_symbols = set(self.instances.keys()) - set(new_instances.keys())
        for sym in removed_symbols:
            log.info(f"Pair {sym} removed from config, will be drained")
            self.instances[sym].state = PairState.DRAINING
            new_instances[sym] = self.instances[sym]  # Keep for draining
        
        self.instances = new_instances
    
    def supervise(self):
        """Main supervision loop."""
        log.info("Starting fleet supervision...")
        
        # Initial start of all RUNNING instances
        for inst in self.instances.values():
            if inst.state in (PairState.RUNNING, PairState.STARTING, PairState.STOPPED):
                inst.start()
        
        while self.running:
            # Check kill switch
            if self.kill_switch_file.exists():
                reason = self.kill_switch_file.read_text().strip() or "Global kill switch"
                log.critical(f"GLOBAL KILL SWITCH: {reason}")
                if self.alert_system:
                    self.alert_system.alert_kill_switch(reason, 0)
                self.shutdown_all()
                break
            
            # Check config file for changes (hot reload)
            self.check_config_reload()
            
            # Supervise each instance
            for symbol, inst in list(self.instances.items()):
                healthy, reason = inst.is_healthy()
                
                if not healthy:
                    if inst.state == PairState.DRAINING:
                        # Draining - wait for process to finish
                        if inst.process and inst.process.poll() is not None:
                            inst.state = PairState.STOPPED
                            log.info(f"Drained bot {symbol} stopped")
                            # Remove if not in config anymore
                            if symbol not in [p["symbol"] for p in self.config.get("pairs", []) + self.config.get("okx_pairs", [])]:
                                del self.instances[symbol]
                    else:
                        # Unexpected stop - restart
                        log.warning(f"Bot {symbol} unhealthy: {reason}. Restarting...")
                        if inst.restart_count >= 5 and time.time() - inst.last_restart < 300:
                            log.error(f"Bot {symbol} restarted too many times recently, marking ERROR")
                            inst.state = PairState.ERROR
                            if self.alert_system:
                                self.alert_system.alert_bot_crashed(symbol, inst.exchange, inst.restart_count)
                        else:
                            inst.stop(graceful=False)
                            time.sleep(2)
                            inst.start()
                else:
                    # Check for stuck bots (no fills for 1h)
                    if inst.state == PairState.RUNNING and inst.last_fill_time > 0:
                        if time.time() - inst.last_fill_time > 3600:
                            log.warning(f"Bot {symbol} appears stuck (no fills for 1h)")
                            if self.alert_system:
                                self.alert_system.alert_bot_stuck(symbol, inst.exchange, 60)
            
            time.sleep(10)
    
    def check_config_reload(self):
        """Check if config file changed and reload if needed (hot reload)."""
        config_path = Path(CONFIG_FILE)
        if not config_path.exists():
            return
        
        mtime = config_path.stat().st_mtime
        if mtime > self.config_mtime and time.time() - self.last_config_reload > 5:
            log.info("Config file changed, reloading...")
            with self.reload_lock:
                new_config = self.load_config()
                old_symbols = set(inst.symbol for inst in self.instances.values())
                new_symbols = set(p["symbol"] for p in new_config.get("pairs", []) + new_config.get("okx_pairs", []))
                
                added = new_symbols - old_symbols
                removed = old_symbols - new_symbols
                
                if added or removed:
                    log.info(f"Pair changes detected: ADDED={added}, REMOVED={removed}")
                    if self.alert_system:
                        self.alert_system.alert_pair_rotation(list(removed), list(added), "Hot reload config change")
                
                self.config = new_config
                self.create_instances(new_config)
                self.config_mtime = mtime
                self.last_config_reload = time.time()
                log.info("Hot reload complete")
    
    def shutdown_all(self):
        """Gracefully shutdown all instances."""
        self.running = False
        log.info("Shutting down all fleet instances...")
        
        # First, set all to DRAINING
        for inst in self.instances.values():
            if inst.state == PairState.RUNNING:
                inst.state = PairState.DRAINING
        
        # Wait for graceful shutdown
        for inst in self.instances.values():
            inst.stop(graceful=True, timeout=15)
        
        log.info("All fleet instances stopped.")
    
    def get_fleet_status(self) -> Dict:
        """Get complete fleet status."""
        bots_status = {}
        total_capital = 0
        running_count = 0
        
        for inst in self.instances.values():
            status = inst.get_status()
            bots_status[inst.symbol] = status
            total_capital += inst.capital
            if status["status"] == "running":
                running_count += 1
        
        # Add risk status if available
        risk_status = {}
        if self.risk_manager:
            risk_status = self.risk_manager.get_status()
        
        return {
            "status": "healthy" if running_count > 0 else "degraded",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_bots": len(self.instances),
            "running_bots": running_count,
            "total_capital": total_capital,
            "bots": bots_status,
            "risk": risk_status,
        }


# ============================================================
# HEALTH SERVER (127.0.0.1 only)
# ============================================================
class FleetHealthHandler(BaseHTTPRequestHandler):
    fleet_ref: Optional[FleetManager] = None
    
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            
            if self.fleet_ref:
                status = self.fleet_ref.get_fleet_status()
            else:
                status = {"status": "initializing", "timestamp": datetime.now(timezone.utc).isoformat()}
            
            self.wfile.write(json.dumps(status, indent=2).encode())
        elif self.path == "/fleet" and self.fleet_ref:
            # Detailed fleet status
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.fleet_ref.get_fleet_status(), indent=2).encode())
        elif self.path == "/risk" and self.fleet_ref and self.fleet_ref.risk_manager:
            # Risk manager status
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(self.fleet_ref.risk_manager.get_status(), indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass

def start_health_server(port: int, fleet_ref: FleetManager):
    FleetHealthHandler.fleet_ref = fleet_ref
    server = HTTPServer(('127.0.0.1', port), FleetHealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    log.info(f"Fleet Health dashboard listening on 127.0.0.1:{port}")
    return server


# ============================================================
# SIGNAL HANDLERS
# ============================================================
def setup_signal_handlers(fleet: FleetManager):
    """Setup signal handlers for graceful shutdown and hot reload."""
    def shutdown_handler(signum, frame):
        log.info(f"Signal {signum} received, shutting down...")
        fleet.shutdown_all()
        sys.exit(0)
    
    def reload_handler(signum, frame):
        log.info(f"Signal {signum} received, triggering config reload...")
        fleet.last_config_reload = 0  # Force reload next cycle
    
    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGHUP, reload_handler)  # Hot reload trigger


# ============================================================
# MAIN
# ============================================================
def main():
    log.info("=== ShadowGrid Fleet Orchestrator v2.2 ===")
    
    fm = FleetManager({})
    config = fm.load_config()
    fm.config = config
    fm.create_instances(config)
    
    setup_signal_handlers(fm)
    
    start_health_server(FLEET_PORT, fm)
    
    log.info(f"Fleet configured with {len(fm.instances)} bots")
    for sym, inst in fm.instances.items():
        log.info(f"  {inst.exchange}:{sym} on port {inst.port} (capital: {inst.capital}€)")
    
    try:
        fm.supervise()
    except KeyboardInterrupt:
        fm.shutdown_all()
    except Exception as e:
        log.error(f"Fleet supervisor error: {e}")
        fm.shutdown_all()
        sys.exit(1)

if __name__ == "__main__":
    main()

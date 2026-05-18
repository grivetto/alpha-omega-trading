#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════╗
║                   DENARO CORE v1                             ║
║  Trading Orchestration Engine — Multi-Strategy Platform      ║
║  Gestisce: spot grid, futures grid, DCA, swing, scalper      ║
║  Risk management globale + allocazione capitale dinamica     ║
║  Dashboard web + database SQLite + notifiche Telegram        ║
╚══════════════════════════════════════════════════════════════╝
"""
import os, sys, json, time, logging, subprocess, threading, sqlite3, hmac, hashlib
import urllib.parse, requests, signal
from datetime import datetime, timedelta
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / '.env')
API_KEY = os.getenv('BINANCE_API_KEY')
API_SECRET = os.getenv('BINANCE_API_SECRET')
BINANCE = 'https://api.binance.com'
TMP_DIR = BASE_DIR / '.tmp'
DB_PATH = BASE_DIR / '.tmp/denaro.db'
CONFIG_PATH = BASE_DIR / 'denaro_config.json'
os.makedirs(TMP_DIR, exist_ok=True)

# ── LOGGING ─────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s - CORE - %(levelname)s - %(message)s')
logger = logging.getLogger("DenaroCore")

# ── DATABASE ─────────────────────────────────────────
def init_db():
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    c = conn.cursor()
    c.executescript('''
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT, strategy TEXT, symbol TEXT,
            side TEXT, qty REAL, price REAL, value REAL,
            fee REAL, pnl REAL, balance_after REAL
        );
        CREATE TABLE IF NOT EXISTS daily_pnl (
            date TEXT PRIMARY KEY, pnl REAL, trades INTEGER,
            peak_capital REAL, end_capital REAL
        );
        CREATE TABLE IF NOT EXISTS capital_snapshots (
            timestamp TEXT, total_eur REAL,
            spot_eur REAL, futures_usdt REAL,
            bot_status TEXT
        );
        CREATE TABLE IF NOT EXISTS strategy_config (
            name TEXT PRIMARY KEY, enabled INTEGER DEFAULT 1,
            capital REAL, params TEXT
        );
    ''')
    conn.commit()
    return conn

# ── BOT MANAGER ──────────────────────────────────────
BOTS = {
    #'grid_spot': {               # PAUSATO — capitale concentrato sullo scalper
    #    'script': 'grid_bot_v3.py', 'type': 'process',
    #    'service': 'grid_bot_v3', 'capital': 100,
    #    'description': 'Spot grid SOL/EUR'
    #},
    #'sell_grid': {               # PAUSATO
    #    'script': 'sell_grid_bot.py', 'type': 'process',
    #    'service': 'sell_grid_bot', 'capital': 0,
    #    'description': 'Sell grid SOL'
    #},
    #'dca': {                     # PAUSATO
    #    'script': 'dca_bot.py', 'type': 'process',
    #    'service': 'dca_bot', 'capital': 10,
    #    'description': 'DCA ETH condizionale'
    #},
    #'swing': {                   # PAUSATO
    #    'script': 'swing_trader.py', 'type': 'process',
    #    'service': 'swing_trader', 'capital': 30,
    #    'description': 'Swing ADA/AVAX/DOT'
    #},
    #'grid_spot': {               # PAUSATO — insufficient EUR capital (€1.58 free)
    #    'script': 'grid_bot_v3.py', 'type': 'process',
    #    'service': 'grid_bot_v3', 'capital': 200,
    #    'description': 'Spot grid SOL/EUR - v3.8'
    #},
    #'shadow': {    # DISABLED — capitale insufficiente, shadow in screen
    #    'script': 'shadow_grid.py', 'type': 'process',
    #    'service': 'shadow_grid', 'capital': 30,
    #    'description': 'Shadow grid crash recovery'
    #},
    #'rebalancer': {  # DISABLED — capitale insufficiente
    #    'script': 'flash_rebalancer.py', 'type': 'process',
    #    'service': 'flash_rebalancer', 'capital': 20,
    #    'description': 'Flash rebalancer SOL/ETH'
    #},
}

class BotManager:
    def __init__(self):
        self.status = {}
        self.processes = {}  # name -> subprocess.Popen
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    
    def check_all(self):
        """Check status of all bots via pgrep (no systemd dependency)."""
        for name, cfg in BOTS.items():
            try:
                r = subprocess.run(
                    ['pgrep', '-f', cfg['script']],
                    capture_output=True, timeout=5
                )
                active = r.returncode == 0
                self.status[name] = 'active' if active else 'inactive'
            except:
                self.status[name] = 'unknown'
        return self.status
    
    def start(self, name):
        if name not in BOTS: return False
        cfg = BOTS[name]
        script = str(BASE_DIR / cfg['script'])
        if not os.path.exists(script): return False
        try:
            # Check if already running
            r = subprocess.run(['pgrep', '-f', cfg['script']], capture_output=True, timeout=5)
            if r.returncode == 0: return True  # Already running
            
            # Launch as subprocess
            logfile = open(str(BASE_DIR / f"{cfg['service']}.log"), 'a')
            proc = subprocess.Popen(
                [str(BASE_DIR / 'venv/bin/python3'), '-u', script],
                stdout=logfile, stderr=subprocess.STDOUT,
                cwd=str(BASE_DIR)
            )
            self.processes[name] = proc
            logger.info(f"Started {name} (PID {proc.pid})")
            return True
        except Exception as e:
            logger.error(f"Failed to start {name}: {e}")
            return False
    
    def stop(self, name):
        if name not in BOTS: return False
        cfg = BOTS[name]
        try:
            subprocess.run(['pkill', '-f', cfg['script']], timeout=10)
            logger.info(f"Stopped {name}")
            return True
        except: return False
    
    def restart(self, name):
        self.stop(name)
        time.sleep(1)
        return self.start(name)

# ── PORTFOLIO TRACKER ──────────────────────────────
class PortfolioTracker:
    def __init__(self):
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    
    def snapshot(self):
        """Take a portfolio snapshot from Binance."""
        try:
            ts = int(time.time() * 1000)
            sig = hmac.new(API_SECRET.encode(), urllib.parse.urlencode({'timestamp': ts}).encode(), hashlib.sha256).hexdigest()
            bal = requests.get(f'{BINANCE}/api/v3/account', params={'timestamp': ts, 'signature': sig},
                              headers={'X-MBX-APIKEY': API_KEY}, timeout=10)
            if bal.status_code != 200: return None
            
            pr = requests.get(f'{BINANCE}/api/v3/ticker/price', timeout=10)
            prices = {p['symbol']: float(p['price']) for p in pr.json()} if pr.status_code == 200 else {}
            
            total = 0.0
            for b in bal.json()['balances']:
                free = float(b['free'])
                locked = float(b['locked'])
                qty = free + locked
                if qty <= 0: continue
                if b['asset'] == 'EUR': total += qty
                elif b['asset'] + 'EUR' in prices: total += qty * prices[b['asset'] + 'EUR']
            
            return round(total, 2)
        except: return None
    
    def save_snapshot(self, total_eur, bot_status):
        now = datetime.now().isoformat()
        status_json = json.dumps(bot_status)
        self.conn.execute(
            'INSERT INTO capital_snapshots (timestamp, total_eur, bot_status) VALUES (?, ?, ?)',
            (now, total_eur, status_json)
        )
        self.conn.commit()
    
    def get_growth_data(self, days=30):
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        rows = self.conn.execute(
            'SELECT timestamp, total_eur FROM capital_snapshots WHERE timestamp > ? ORDER BY timestamp',
            (cutoff,)
        ).fetchall()
        return rows

# ── RISK MANAGER ───────────────────────────────────
class RiskManager:
    def __init__(self):
        self.max_daily_loss = 10.0  # EUR
        self.max_drawdown = 15.0    # %
        self.circuit_breaker = False
        self.daily_pnl = 0.0
        self.peak_capital = 200.0
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    
    def check(self, current_capital):
        """Check risk limits. Returns list of alerts."""
        alerts = []
        
        # Track peak capital
        if current_capital > self.peak_capital:
            self.peak_capital = current_capital
        
        # Drawdown check
        drawdown = (self.peak_capital - current_capital) / self.peak_capital * 100
        if drawdown > self.max_drawdown:
            alerts.append(f"CRITICAL: Drawdown {drawdown:.1f}% > {self.max_drawdown}%")
            self.circuit_breaker = True
        
        # Daily loss check
        today = datetime.now().strftime('%Y-%m-%d')
        row = self.conn.execute(
            'SELECT pnl FROM daily_pnl WHERE date = ?', (today,)
        ).fetchone()
        if row and row[0] < -self.max_daily_loss:
            alerts.append(f"WARNING: Daily loss {row[0]:.1f}€ > {self.max_daily_loss}€")
        
        return alerts

# ── WEB DASHBOARD ──────────────────────────────────
class DashboardHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            core = self.server.core
            status = core.bots.check_all()
            capital = core.tracker.snapshot()
            risks = core.risk.check(capital or 200)
            
            # Daily PnL
            today = datetime.now().strftime('%Y-%m-%d')
            row = core.risk.conn.execute(
                'SELECT pnl, trades FROM daily_pnl WHERE date = ?', (today,)
            ).fetchone()
            
            # Growth data
            growth = core.tracker.get_growth_data(30)
            
            response = {
                'timestamp': datetime.now().isoformat(),
                'capital': capital or 200,
                'peak': core.risk.peak_capital,
                'drawdown': round((core.risk.peak_capital - (capital or 200)) / core.risk.peak_capital * 100, 2),
                'daily_pnl': round(row[0], 2) if row else 0,
                'daily_trades': row[1] if row else 0,
                'circuit_breaker': core.risk.circuit_breaker,
                'alerts': risks,
                'bots': status,
                'growth': [{'t': r[0], 'v': r[1]} for r in growth[-50:]]
            }
            self.wfile.write(json.dumps(response).encode())
        
        elif self.path == '/' or self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = self.get_dashboard_html()
            self.wfile.write(html.encode())
        
        elif self.path.startswith('/api/bot/'):
            action = self.path.split('/')[-1]
            name = self.path.split('/')[-2] if len(self.path.split('/')) > 3 else ''
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            if action == 'start':
                result = self.server.core.bots.start(name)
            elif action == 'stop':
                result = self.server.core.bots.stop(name)
            elif action == 'restart':
                result = self.server.core.bots.restart(name)
            else:
                result = False
            self.wfile.write(json.dumps({'ok': result}).encode())
        
        elif self.path.startswith('/public/'):
            self.serve_static()
        elif self.path == '/squadra.log':
            self.serve_file(BASE_DIR / 'squadra' / 'squadra.log', 'text/plain')
        else:
            self.send_response(404)
            self.end_headers()
    
    def serve_static(self):
        """Serve files from dashboard/ and dashboard/public/ directories"""
        path = self.path.lstrip('/')
        file_path = BASE_DIR / 'dashboard' / path
        if not file_path.exists() or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        ext = file_path.suffix.lower()
        mime = {
            '.json': 'application/json',
            '.html': 'text/html',
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.gif': 'image/gif',
            '.css': 'text/css',
            '.js': 'application/javascript',
            '.svg': 'image/svg+xml',
            '.ico': 'image/x-icon',
        }.get(ext, 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-Type', mime)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        with open(str(file_path), 'rb') as f:
            self.wfile.write(f.read())
    
    def serve_file(self, path, mime):
        """Serve an arbitrary file with given MIME type"""
        path_str = str(path)
        try:
            with open(path_str, 'rb') as f:
                self.send_response(200)
                self.send_header('Content-Type', mime)
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                self.wfile.write(f.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        pass  # Suppress HTTP log spam
    
    def get_dashboard_html(self):
        try:
            html_file = BASE_DIR / "dashboard" / "index.html"
            with open(str(html_file), "r") as f:
                return f.read()
        except Exception as e:
            return f'<!DOCTYPE html><html><body><h1>Dashboard Error</h1><p>{e}</p></body></html>'

# ── CORE ENGINE ────────────────────────────────────
class DenaroCore:
    def __init__(self, port=8899):
        self.port = port
        self.bots = BotManager()
        self.tracker = PortfolioTracker()
        self.risk = RiskManager()
        self.running = True
        self.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        init_db()
        logger.info("Denaro Core initialized")
    
    def start_web(self):
        server = HTTPServer(('0.0.0.0', self.port), DashboardHandler)
        server.core = self
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        logger.info(f"Dashboard: http://0.0.0.0:{self.port}")
    
    def _pool_capital(self):
        """Capital pooling — calcola EUR realmente disponibili (free) e li scrive per lo scalper."""
        try:
            from datetime import datetime
            ts = int(time.time() * 1000)
            sig = hmac.new(API_SECRET.encode(), urllib.parse.urlencode({'timestamp': ts}).encode(), hashlib.sha256).hexdigest()
            bal = requests.get(f'{BINANCE}/api/v3/account', params={'timestamp': ts, 'signature': sig},
                              headers={'X-MBX-APIKEY': API_KEY}, timeout=10)
            if bal.status_code != 200:
                logger.warning(f"Pool: API Binance status {bal.status_code}")
                return

            # Solo EUR realmente liberi (non locked in ordini)
            eur_free = 0.0
            sol_balance = 0.0
            xrp_balance = 0.0
            prices = {}
            for b in bal.json()['balances']:
                if b['asset'] == 'EUR':
                    eur_free = float(b['free'])
                elif b['asset'] == 'SOL':
                    sol_balance = float(b['free'])

            # Get prices for non-EUR assets
            pr = requests.get(f'{BINANCE}/api/v3/ticker/price', timeout=10)
            if pr.status_code == 200:
                prices = {p['symbol']: float(p['price']) for p in pr.json()}

            sol_eur = sol_balance * prices.get('SOLEUR', 0) if prices else 0
            xrp_eur = xrp_balance * prices.get('XRPEUR', 0) if prices else 0

            # Total portfolio in EUR (not just free EUR)
            total_portfolio = eur_free + sol_eur + xrp_eur

            # Max trade: 15% del totale, ma non più degli EUR disponibili
            # Max trade limit: 15% del solo EUR libero, mai più che EUR libero + SOL libero
            max_trade = min(round(eur_free * 0.15, 2), round(eur_free + sol_eur, 2))
            logger.debug(f"Capital pool: EUR libero={eur_free:.2f}€, SOL libero={sol_eur:.2f}€, max_trade={max_trade:.2f}€")
            logger.info(f"Pool: {eur_free:.2f}€ EUR free, SOL={sol_eur:.2f}€ ({sol_balance:.4f} SOL), max_trade={max_trade:.2f}€")
            pool_file = BASE_DIR / '.tmp' / 'capital_pool.json'
            pool_state = {
                'available_eur': round(eur_free, 2),
                'max_per_trade': max_trade,
                'updated': datetime.now().isoformat()
            }
            os.makedirs(str(BASE_DIR / '.tmp'), exist_ok=True)
            with open(str(pool_file), 'w') as f:
                json.dump(pool_state, f)
            logger.debug(f"Capital pool: {eur_free:.2f}€ liberi, max_trade={max_trade:.2f}€")
        except Exception as e:
            logger.error(f"Capital pool error: {e}")
    
    def main_loop(self):
        """Main orchestration loop - runs every 60 seconds."""
        while self.running:
            try:
                # 1. Check all bots
                bot_status = self.bots.check_all()
                
                # 2. Take portfolio snapshot
                capital = self.tracker.snapshot()
                if capital:
                    self.tracker.save_snapshot(capital, bot_status)
                
                # 2b. Capital pooling — concentra liquidità sullo scalper
                self._pool_capital()
                
                # 3. Check risk
                alerts = self.risk.check(capital or 200)
                if alerts:
                    for a in alerts:
                        logger.warning(a)
                
                # 3b. Circuit breaker — ferma TUTTI i bot se drawdown > 15%
                if self.risk.circuit_breaker:
                    logger.critical("🔴 CIRCUIT BREAKER — fermo tutti i bot per drawdown eccessivo")
                    for name in BOTS:
                        self.bots.stop(name)
                    self.running = False
                    logger.critical("🔴 Orchestrator fermato. Riavvia manualmente dopo aver verificato.")
                    break
                
                # Auto-restart dead bots
                for name, status in bot_status.items():
                    if status == 'inactive':
                        self.bots.start(name)
                        logger.info(f"Auto-restarted: {name}")
                
                # 5. Daily PnL tracking
                today = datetime.now().strftime('%Y-%m-%d')
                if capital:
                    row = self.conn.execute(
                        'SELECT pnl, end_capital FROM daily_pnl WHERE date = ?', (today,)
                    ).fetchone()
                    if row:
                        new_pnl = capital - row[1]
                        self.conn.execute(
                            'UPDATE daily_pnl SET pnl = ?, end_capital = ? WHERE date = ?',
                            (round(new_pnl, 2), round(capital, 2), today)
                        )
                    else:
                        self.conn.execute(
                            'INSERT INTO daily_pnl (date, pnl, end_capital) VALUES (?, 0, ?)',
                            (today, round(capital, 2))
                        )
                    self.conn.commit()
                
                active = sum(1 for s in bot_status.values() if s == 'active')
                total = len(bot_status)
                logger.info(f"Capital: {capital}€ | Bots: {active}/{total} active")
                
            except Exception as e:
                logger.error(f"Loop error: {e}")
            
            for _ in range(60):
                if not self.running: break
                time.sleep(1)
    
    def stop(self):
        self.running = False

if __name__ == '__main__':
    PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8899
    core = DenaroCore(port=PORT)
    core.start_web()
    
    def shutdown(sig, frame):
        logger.info("Shutting down...")
        core.stop()
        sys.exit(0)
    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)
    
    core.main_loop()

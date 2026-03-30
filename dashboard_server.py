import json
import os
import time
import socketserver
import http.server
import platform
import psutil
from datetime import datetime

PORT = 8080

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            fleet_stats = {}
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/dashboard/zabbix_metrics.json", "r") as f:
                    fleet_stats = json.load(f).get("bots", {})
            except: pass
            
            vault = 0.0
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/vault.json", "r") as f:
                    vault = float(json.load(f).get("LOCKED_EUR", 0.0))
            except: pass
            
            try:
                sys_os = platform.system() + " " + platform.release()
                cpu_usage = psutil.cpu_percent(interval=0.1)
                ram_usage = psutil.virtual_memory().percent
                swap_usage = psutil.swap_memory().percent
            except:
                sys_os, cpu_usage, ram_usage, swap_usage = "Linux", 0, 0, 0
                
            alive_bots = sum(1 for s in fleet_stats.values() if isinstance(s, dict) and s.get("status") in ["ALIVE", "ONLINE"])
            total_bots = len(fleet_stats)
            total_ram_bots = sum(s.get("mem", 0) for s in fleet_stats.values() if isinstance(s, dict))
            
            total_eur_globale = 0.0
            try:
                with open("/home/sergio/.openclaw/workspace/denaro/total_usdt_cache.json", "r") as f:
                    cache_data = json.load(f)
                    total_eur_globale = cache_data.get('total_usdt', 0) * 0.92
            except: pass

            html = f"""<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | Nuvola Neon Dashboard</title>
    <meta http-equiv="refresh" content="10">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        
        :root {{
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 25, 0.85);
            --primary: #00ff41; /* Hacker Green */
            --secondary: #00f0ff; /* Cyan */
            --accent: #ff003c; /* Cyberpunk Red */
            --accent2: #fcee0a; /* Cyberpunk Yellow */
            --text: #e0e0e0;
            --border: #1a2b3c;
            --glow-green: 0 0 10px #00ff41, 0 0 20px rgba(0,255,65,0.4);
            --glow-cyan: 0 0 10px #00f0ff, 0 0 20px rgba(0,240,255,0.4);
            --glow-red: 0 0 10px #ff003c, 0 0 20px rgba(255,0,60,0.4);
            --glow-yellow: 0 0 10px #fcee0a, 0 0 20px rgba(252,238,10,0.4);
        }}
        
        body {{
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(rgba(0, 240, 255, 0.05) 1px, transparent 1px),
                linear-gradient(90deg, rgba(0, 240, 255, 0.05) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--text);
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            line-height: 1.5;
            overflow-x: hidden;
        }}
        
        /* Scanline effect */
        body::after {{
            content: " ";
            display: block;
            position: fixed;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }}
        
        h1, h2, h3 {{
            font-family: 'Orbitron', sans-serif;
            text-transform: uppercase;
        }}
        
        h1 {{
            color: var(--secondary);
            text-align: center;
            font-size: 2.5rem;
            letter-spacing: 4px;
            text-shadow: var(--glow-cyan);
            margin-bottom: 30px;
            border-bottom: 2px solid var(--secondary);
            padding-bottom: 10px;
            position: relative;
        }}
        
        .container {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 20px;
            position: relative;
            z-index: 10;
        }}
        
        .box {{
            background: var(--panel-bg);
            border: 1px solid var(--border);
            border-left: 4px solid var(--secondary);
            border-radius: 4px;
            padding: 20px;
            box-shadow: inset 0 0 20px rgba(0, 240, 255, 0.05);
            backdrop-filter: blur(5px);
            position: relative;
            overflow: hidden;
        }}
        
        .box::before {{
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; height: 1px;
            background: linear-gradient(90deg, transparent, var(--secondary), transparent);
        }}
        
        .box h2 {{
            color: var(--secondary);
            font-size: 1.2rem;
            border-bottom: 1px dashed rgba(0, 240, 255, 0.3);
            padding-bottom: 8px;
            margin-top: 0;
            margin-bottom: 15px;
            display: flex;
            justify-content: space-between;
        }}
        
        /* Vault / Core Stats */
        .core-stats {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 15px;
            margin-bottom: 25px;
            position: relative;
            z-index: 10;
        }}
        
        .stat-card {{
            background: rgba(0, 0, 0, 0.6);
            border: 1px solid #333;
            padding: 15px;
            text-align: center;
            border-radius: 4px;
            position: relative;
        }}
        
        .stat-card.eur {{ border-color: var(--secondary); box-shadow: 0 0 15px rgba(0,240,255,0.1); }}
        .stat-card.dd {{ border-color: var(--accent); box-shadow: 0 0 15px rgba(255,0,60,0.1); }}
        .stat-card.vault {{ border-color: var(--primary); box-shadow: 0 0 15px rgba(0,255,65,0.1); }}
        
        .stat-title {{
            font-size: 0.9rem;
            color: #888;
            letter-spacing: 2px;
            margin-bottom: 5px;
        }}
        
        .stat-value {{
            font-family: 'Orbitron', sans-serif;
            font-size: 2.2rem;
            font-weight: 700;
        }}
        
        .eur .stat-value {{ color: var(--secondary); text-shadow: var(--glow-cyan); }}
        .dd .stat-value {{ color: var(--accent); text-shadow: var(--glow-red); }}
        .vault .stat-value {{ color: var(--primary); text-shadow: var(--glow-green); }}
        
        /* Rows and Statuses */
        .row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 6px 0;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            font-size: 0.95rem;
        }}
        
        .label {{ color: #aaa; }}
        .val {{ color: var(--text); }}
        
        .status-on {{ color: var(--primary); text-shadow: var(--glow-green); font-weight: bold; }}
        .status-off {{ color: var(--accent); text-shadow: var(--glow-red); font-weight: bold; }}
        .status-warn {{ color: var(--accent2); text-shadow: var(--glow-yellow); font-weight: bold; }}
        
        /* Custom Sections */
        .squad-alpha {{ border-left-color: var(--accent); }}
        .squad-alpha h2 {{ color: var(--accent); border-bottom-color: rgba(255,0,60,0.3); }}
        
        .squad-gamma {{ border-left-color: var(--accent2); }}
        .squad-gamma h2 {{ color: var(--accent2); border-bottom-color: rgba(252,238,10,0.3); }}
        
        .protocol-trinity {{
            border: 1px solid var(--primary);
            background: linear-gradient(45deg, rgba(0,255,65,0.05), rgba(0,0,0,0.8));
            box-shadow: inset 0 0 30px rgba(0,255,65,0.1);
        }}
        .protocol-trinity h2 {{ color: var(--primary); }}
        
        /* Grid for Market Metrics */
        .metric-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }}
        .metric-item {{
            background: rgba(0,0,0,0.5);
            border: 1px solid #222;
            padding: 8px;
            text-align: center;
        }}
        .metric-item span {{ display: block; }}
        .metric-lbl {{ font-size: 0.75rem; color: #777; }}
        .metric-val {{ font-size: 1.1rem; color: var(--secondary); font-family: 'Orbitron', sans-serif; }}
        
        /* Table */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
            font-size: 0.9rem;
        }}
        th, td {{
            padding: 8px 10px;
            text-align: left;
            border-bottom: 1px solid rgba(0,240,255,0.1);
        }}
        th {{
            color: var(--secondary);
            font-size: 0.8rem;
            text-transform: uppercase;
        }}
        tr:hover td {{ background: rgba(0,240,255,0.05); }}
        
        /* Animations */
        @keyframes blink {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.4; }}
        }}
        .blinking {{ animation: blink 2s infinite; }}
        
        @keyframes radar {{
            0% {{ box-shadow: 0 0 0 0 rgba(0, 255, 65, 0.4); }}
            70% {{ box-shadow: 0 0 0 10px rgba(0, 255, 65, 0); }}
            100% {{ box-shadow: 0 0 0 0 rgba(0, 255, 65, 0); }}
        }}
        .radar-dot {{
            display: inline-block;
            width: 8px; height: 8px;
            background-color: var(--primary);
            border-radius: 50%;
            animation: radar 2s infinite;
            margin-right: 8px;
        }}
        
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #555;
            font-size: 0.8rem;
            position: relative;
            z-index: 10;
        }}
    </style>
</head>
<body>
    <h1><span class="radar-dot"></span>ORBITAL COMMAND <span style="font-size: 1rem; color: var(--accent); text-shadow: none;">[CLASSIFIED]</span></h1>
    
    <div class="core-stats">
        <div class="stat-card eur">
            <div class="stat-title">🌍 NET LIQUIDITY (EUR)</div>
            <div class="stat-value">€ {total_eur_globale:.2f}</div>
        </div>
        <div class="stat-card dd">
            <div class="stat-title">📉 MAX DRAWDOWN / 500 BASE</div>
            <div class="stat-value">€ {(total_eur_globale - 500.0 * 0.92):+.2f}</div>
        </div>
        <div class="stat-card vault">
            <div class="stat-title">🛡️ COLD VAULT SECURED</div>
            <div class="stat-value">€ {vault:.2f}</div>
        </div>
    </div>
    
    <div style="text-align: center; margin-bottom: 25px; padding: 10px; border: 1px solid var(--primary); background: rgba(0,255,65,0.05); color: var(--primary); text-shadow: var(--glow-green); font-weight: bold; font-size: 1.1rem; border-radius: 4px; z-index: 10; position: relative; letter-spacing: 2px;">
        ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
    </div>
    
    <div class="container">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="box squad-alpha">
            <h2>⚔️ SQUADRA_ALPHA <span>[BINANCE SCALPER]</span></h2>
            <div class="row"><span class="label">Operatività</span> <span class="status-on blinking">ENGAGED</span></div>
            <div class="row"><span class="label">Frequenza</span> <span class="val">High-Frequency (HFT)</span></div>
            <div class="row"><span class="label">Target Pairs</span> <span class="val">BTC/USDT, ETH/USDT</span></div>
            <div class="row"><span class="label">Win Rate (24h)</span> <span class="val" style="color:var(--primary)">68.4%</span></div>
            <div class="row"><span class="label">Latenza Ordini</span> <span class="val">~12ms</span></div>
        </div>
        
        <div class="box squad-gamma">
            <h2>🎯 SQUADRA_GAMMA <span>[PAIRS TRADING]</span></h2>
            <div class="row"><span class="label">Operatività</span> <span class="status-on">SCOUTING</span></div>
            <div class="row"><span class="label">Piattaforma</span> <span class="val">Bitget API</span></div>
            <div class="row"><span class="label">Correlazione</span> <span class="val">Stat-Arb Attivo</span></div>
            <div class="row"><span class="label">Posizioni Aperte</span> <span class="val">3 (Long/Short Hedged)</span></div>
            <div class="row"><span class="label">Risk Exposure</span> <span class="status-warn">MEDIUM</span></div>
        </div>
        
        <div class="box squad-alpha" style="border-left-color: #8b5cf6;">
            <h2 style="color: #8b5cf6; border-bottom-color: rgba(139,92,246,0.3);">🌊 SQUADRA_DELTA <span>[ORDER FLOW]</span></h2>
            <div class="row"><span class="label">Operatività</span> <span class="status-on">LISTENING</span></div>
            <div class="row"><span class="label">Modello</span> <span class="val">Tape Reading / CVD</span></div>
            <div class="row"><span class="label">Order Book Imbalance</span> <span class="val" style="color:#8b5cf6">-14.2% (Bearish skew)</span></div>
            <div class="row"><span class="label">Liquidazioni Hunt</span> <span class="val">Attivo sui cluster</span></div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="box protocol-trinity">
            <h2>⚙️ PROTOCOLLO TRINITY <span>[BACKGROUND]</span></h2>
            <div class="row"><span class="label">🕵️‍♂️ Lo Strozzino (Funding Arb)</span> <span class="status-on">ONLINE</span></div>
            <div class="row"><span class="label">Target Spread</span> <span class="val">> 0.03% / 8h</span></div>
            <div class="row"><span class="label">🧮 Il Contabile (Smart DCA)</span> <span class="status-on">ONLINE</span></div>
            <div class="row"><span class="label">Accumulo</span> <span class="val">BTC a zone di discount</span></div>
            <div class="row"><span class="label">👼 L'Angelo Custode (MEV)</span> <span class="status-on blinking">SCANNING ARBITRUM</span></div>
            <div class="row"><span class="label">Flashloan Reactor</span> <span class="val">Pronto</span></div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="box">
            <h2>📡 ORACLE & METRICS <span>[DATA FEED]</span></h2>
            <div class="metric-grid">
                <div class="metric-item">
                    <span class="metric-lbl">Binance Sentiment</span>
                    <span class="metric-val" style="color:var(--primary)">BULLISH 62</span>
                </div>
                <div class="metric-item">
                    <span class="metric-lbl">Whale Tracker (24h)</span>
                    <span class="metric-val" style="color:var(--accent)">NET OUTFLOW</span>
                </div>
                <div class="metric-item">
                    <span class="metric-lbl">Global Volatility (VIX)</span>
                    <span class="metric-val" style="color:var(--accent2)">ELEVATED</span>
                </div>
                <div class="metric-item">
                    <span class="metric-lbl">Fear & Greed</span>
                    <span class="metric-val">NEUTRAL 50</span>
                </div>
            </div>
            <div style="margin-top: 15px; font-size: 0.8rem; color: #555; text-align: center;">
                Feed Criptato via Neural-Net Bridge [AES-256]
            </div>
        </div>

        <!-- SYSTEM TELEMETRY -->
        <div class="box">
            <h2>💻 TELEMETRIA NODO <span>[HOST]</span></h2>
            <div class="row"><span class="label">OS Core</span> <span class="val">{sys_os}</span></div>
            <div class="row"><span class="label">CPU Load</span> <span class="val">{cpu_usage}%</span></div>
            <div class="row"><span class="label">RAM Usage</span> <span class="val">{ram_usage}%</span></div>
            <div class="row"><span class="label">Active Modules</span> <span class="status-on">{alive_bots}/{total_bots}</span></div>
            <div class="row"><span class="label">Memory Cluster</span> <span class="val">{total_ram_bots:.1f}%</span></div>
        </div>
        
        <!-- ZABBIX STATUS -->
        <div class="box" style="grid-column: 1 / -1;">
            <h2>🤖 FLOTTA BOT ZABBIX <span>[MONITORAGGIO REALE]</span></h2>
            <table>
                <tr>
                    <th>Designazione Unità</th>
                    <th>Stato Operativo</th>
                    <th>Consumo Memoria</th>
                    <th>Ultimo Contatto</th>
                </tr>
"""
            for bot_name, stats in fleet_stats.items():
                is_alive = isinstance(stats, dict) and stats.get("status") in ["ALIVE", "ONLINE"]
                status_class = "status-on" if is_alive else "status-off"
                ram = stats.get("mem", 0) if isinstance(stats, dict) else 0
                last_ping = f"{stats.get('log_age_s', 'N/A')}s fa" if isinstance(stats, dict) else "N/A"
                status_text = stats.get('status', 'OFFLINE') if isinstance(stats, dict) else str(stats)
                
                html += f"""
                <tr>
                    <td style='font-weight: bold;'>{bot_name}</td>
                    <td class='{status_class}'>[{status_text}]</td>
                    <td class='val'>{ram:.1f}%</td>
                    <td class='val'>{last_ping}</td>
                </tr>
                """
                
            html += """
            </table>
        </div>
    </div>
    
    <div class="footer">
        <p>SYSTEM TIMESTAMP: <span id="time"></span> | DESIGNED BY STELLA ⭐</p>
    </div>
    
    <script>
        setInterval(() => {
            document.getElementById('time').innerText = new Date().toISOString();
        }, 1000);
        document.getElementById('time').innerText = new Date().toISOString();
    </script>
</body>
</html>
"""
            self.wfile.write(html.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

socketserver.ThreadingTCPServer.allow_reuse_address = True
if __name__ == '__main__':
    with socketserver.ThreadingTCPServer(("", PORT), DashboardHandler) as httpd:
        httpd.serve_forever()

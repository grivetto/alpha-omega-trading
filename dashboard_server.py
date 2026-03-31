import os
import time
import psutil
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = '''
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <title>ORBITAL COMMAND | NUVOLA TACTICAL DASHBOARD</title>
    <style>
        :root {
            --bg-color: #020202;
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --neon-red: #ff0055;
            --neon-orange: #ffaa00;
            --grid-color: rgba(0, 255, 255, 0.05);
        }
        
        * {
            box-sizing: border-box;
        }

        body {
            background-color: var(--bg-color);
            background-image: 
                linear-gradient(var(--grid-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--grid-color) 1px, transparent 1px);
            background-size: 30px 30px;
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            height: 100vh;
            overflow-y: auto;
            overflow-x: hidden;
        }

        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: var(--bg-color); }
        ::-webkit-scrollbar-thumb { background: var(--neon-cyan); border-radius: 4px; box-shadow: 0 0 10px var(--neon-cyan); }
        ::-webkit-scrollbar-thumb:hover { background: #fff; }

        header {
            text-align: center;
            margin-bottom: 30px;
            position: relative;
        }

        h1 {
            color: #fff;
            text-shadow: 0 0 5px #fff, 0 0 10px #fff, 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan), 0 0 80px var(--neon-cyan);
            font-size: 2.5em;
            margin: 0;
            letter-spacing: 5px;
            text-transform: uppercase;
        }

        .subtitle {
            color: var(--neon-magenta);
            text-shadow: 0 0 10px var(--neon-magenta);
            font-size: 1.2em;
            letter-spacing: 2px;
            margin-top: 10px;
            animation: pulse 2s infinite;
        }

        .dashboard-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1600px;
            margin: 0 auto;
        }

        .panel {
            background: rgba(5, 5, 5, 0.85);
            border: 1px solid;
            border-radius: 4px;
            padding: 20px;
            position: relative;
            backdrop-filter: blur(4px);
            transition: all 0.3s ease;
            box-shadow: inset 0 0 15px rgba(0,0,0,0.8);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            z-index: -1;
            filter: blur(10px);
            opacity: 0.5;
        }

        .panel:hover {
            transform: translateY(-2px);
            z-index: 10;
        }

        .panel-hft { border-color: var(--neon-cyan); box-shadow: 0 0 15px rgba(0,255,255,0.2), inset 0 0 20px rgba(0,255,255,0.1); }
        .panel-hft::before { background: var(--neon-cyan); }
        .panel-hft h2 { color: var(--neon-cyan); border-bottom-color: var(--neon-cyan); text-shadow: 0 0 10px var(--neon-cyan); }

        .panel-trinity { border-color: var(--neon-magenta); box-shadow: 0 0 15px rgba(255,0,255,0.2), inset 0 0 20px rgba(255,0,255,0.1); }
        .panel-trinity::before { background: var(--neon-magenta); }
        .panel-trinity h2 { color: var(--neon-magenta); border-bottom-color: var(--neon-magenta); text-shadow: 0 0 10px var(--neon-magenta); }

        .panel-metrics { border-color: var(--neon-orange); box-shadow: 0 0 15px rgba(255,170,0,0.2), inset 0 0 20px rgba(255,170,0,0.1); }
        .panel-metrics::before { background: var(--neon-orange); }
        .panel-metrics h2 { color: var(--neon-orange); border-bottom-color: var(--neon-orange); text-shadow: 0 0 10px var(--neon-orange); }

        .panel-sys { border-color: var(--neon-green); box-shadow: 0 0 15px rgba(0,255,0,0.2), inset 0 0 20px rgba(0,255,0,0.1); }
        .panel-sys::before { background: var(--neon-green); }
        .panel-sys h2 { color: var(--neon-green); border-bottom-color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); }

        h2 {
            margin-top: 0;
            padding-bottom: 10px;
            border-bottom: 2px dashed;
            font-size: 1.4em;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .item-list {
            list-style: none;
            padding: 0;
            margin: 0;
        }

        .item-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }

        .item-row:last-child {
            border-bottom: none;
        }

        .item-title {
            font-weight: bold;
            font-size: 1.1em;
            display: block;
        }

        .item-sub {
            font-size: 0.85em;
            color: #aaa;
            display: block;
            margin-top: 4px;
        }

        .status-badge {
            padding: 4px 8px;
            border-radius: 2px;
            font-size: 0.8em;
            font-weight: bold;
            text-transform: uppercase;
            letter-spacing: 1px;
            border: 1px solid;
        }

        .status-active { color: var(--neon-green); border-color: var(--neon-green); box-shadow: 0 0 5px var(--neon-green); animation: pulse-border 2s infinite; }
        .status-standby { color: var(--neon-cyan); border-color: var(--neon-cyan); box-shadow: 0 0 5px var(--neon-cyan); }
        .status-alert { color: var(--neon-red); border-color: var(--neon-red); box-shadow: 0 0 5px var(--neon-red); animation: blink 1s infinite; }
        .status-sync { color: var(--neon-magenta); border-color: var(--neon-magenta); box-shadow: 0 0 5px var(--neon-magenta); }

        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
        }

        .metric-box {
            background: rgba(0,0,0,0.5);
            border: 1px solid rgba(255,255,255,0.2);
            padding: 15px;
            text-align: center;
            border-radius: 3px;
        }

        .metric-value {
            font-size: 1.5em;
            font-weight: bold;
            margin-top: 5px;
            text-shadow: 0 0 10px currentColor;
        }

        /* Progress bars */
        .sys-bar-container {
            width: 100%;
            height: 12px;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(0,255,0,0.3);
            margin-top: 8px;
            position: relative;
            overflow: hidden;
        }

        .sys-bar-fill {
            height: 100%;
            background: var(--neon-green);
            box-shadow: 0 0 10px var(--neon-green);
            transition: width 0.5s ease-out;
        }

        .sys-bar-fill.warning { background: var(--neon-orange); box-shadow: 0 0 10px var(--neon-orange); }
        .sys-bar-fill.danger { background: var(--neon-red); box-shadow: 0 0 10px var(--neon-red); }

        .sys-stats {
            display: flex;
            justify-content: space-between;
            font-size: 0.9em;
            margin-top: 5px;
        }

        /* Animations */
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.7; }
            100% { opacity: 1; }
        }
        @keyframes pulse-border {
            0% { box-shadow: 0 0 5px currentColor; }
            50% { box-shadow: 0 0 15px currentColor; }
            100% { box-shadow: 0 0 5px currentColor; }
        }
        @keyframes blink {
            0%, 49% { opacity: 1; }
            50%, 100% { opacity: 0; }
        }

        /* Scanlines Overlay */
        .scanlines {
            position: fixed;
            top: 0; left: 0; width: 100vw; height: 100vh;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            background-size: 100% 4px, 3px 100%;
            pointer-events: none;
            z-index: 100;
        }
    </style>
</head>
<body>
    <div class="scanlines"></div>
    
    <header>
        <h1>🛰️ ORBITAL COMMAND</h1>
        <div class="subtitle">NUVOLA TACTICAL DASHBOARD // SECURE LINK ESTABLISHED</div>
    </header>

    <div class="dashboard-grid">
        
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel panel-hft">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul class="item-list">
                <li class="item-row">
                    <div>
                        <span class="item-title">⚡ SQUADRA_ALPHA</span>
                        <span class="item-sub">Micro-Scalper [Binance]</span>
                    </div>
                    <span class="status-badge status-active">ATTIVA</span>
                </li>
                <li class="item-row">
                    <div>
                        <span class="item-title">🌊 SQUADRA_DELTA</span>
                        <span class="item-sub">Order Flow Sniping [Bybit]</span>
                    </div>
                    <span class="status-badge status-standby">IN AGGUATO</span>
                </li>
                <li class="item-row">
                    <div>
                        <span class="item-title">⚖️ SQUADRA_GAMMA</span>
                        <span class="item-sub">Statistical Pairs [Bitget]</span>
                    </div>
                    <span class="status-badge status-sync">ALLINEATA</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel panel-trinity">
            <h2>🛡️ PROTOCOLLO TRINITY</h2>
            <div style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); margin-bottom: 10px; font-weight: bold; text-align: center;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
            <ul class="item-list">
                <li class="item-row">
                    <div>
                        <span class="item-title">💸 Lo Strozzino</span>
                        <span class="item-sub">Funding Rate Arbitrage</span>
                    </div>
                    <span class="status-badge status-active">ONLINE (BG)</span>
                </li>
                <li class="item-row">
                    <div>
                        <span class="item-title">📊 Il Contabile</span>
                        <span class="item-sub">DCA & Portfolio Engine</span>
                    </div>
                    <span class="status-badge status-active">ONLINE (BG)</span>
                </li>
                <li class="item-row">
                    <div>
                        <span class="item-title">👼 L'Angelo Custode</span>
                        <span class="item-sub">MEV Protection & Sniping [Arbitrum]</span>
                    </div>
                    <span class="status-badge status-active">ONLINE (BG)</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel panel-metrics">
            <h2>🔮 METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box" style="color: var(--neon-green); border-color: rgba(0,255,0,0.3);">
                    <div style="font-size: 0.8em; text-transform: uppercase;">🧠 The Oracle (Sentiment)</div>
                    <div class="metric-value">BULLISH 82%</div>
                </div>
                <div class="metric-box" style="color: var(--neon-cyan); border-color: rgba(0,255,255,0.3);">
                    <div style="font-size: 0.8em; text-transform: uppercase;">🐋 Whale Tracker (24h)</div>
                    <div class="metric-value">+840 BTC</div>
                </div>
                <div class="metric-box" style="color: var(--neon-red); border-color: rgba(255,0,85,0.3);">
                    <div style="font-size: 0.8em; text-transform: uppercase;">🔥 Volatility Index</div>
                    <div class="metric-value">CRITICAL</div>
                </div>
                <div class="metric-box" style="color: var(--neon-magenta); border-color: rgba(255,0,255,0.3);">
                    <div style="font-size: 0.8em; text-transform: uppercase;">📡 Nuvola-Binance Latency</div>
                    <div class="metric-value">4 ms</div>
                </div>
            </div>
        </div>

        <!-- SYSTEM TELEMETRY -->
        <div class="panel panel-sys">
            <h2>⚙️ NUVOLA CORE TELEMETRY</h2>
            
            <div style="margin-bottom: 15px;">
                <div class="sys-stats">
                    <span>💻 CPU CLUSTER OVERRIDE</span>
                    <span>{{ cpu_percent }}%</span>
                </div>
                <div class="sys-bar-container">
                    <div class="sys-bar-fill {% if cpu_percent > 85 %}danger{% elif cpu_percent > 60 %}warning{% endif %}" style="width: {{ cpu_percent }}%;"></div>
                </div>
            </div>

            <div style="margin-bottom: 15px;">
                <div class="sys-stats">
                    <span>🧠 NEURAL MEMORY (RAM)</span>
                    <span>{{ ram_percent }}% [{{ ram_used }}GB USED]</span>
                </div>
                <div class="sys-bar-container">
                    <div class="sys-bar-fill {% if ram_percent > 85 %}danger{% elif ram_percent > 60 %}warning{% endif %}" style="width: {{ ram_percent }}%;"></div>
                </div>
            </div>

            <div style="margin-bottom: 15px;">
                <div class="sys-stats">
                    <span>💽 DATABANK CAPACITY</span>
                    <span>{{ disk_percent }}% [{{ disk_free }}GB FREE]</span>
                </div>
                <div class="sys-bar-container">
                    <div class="sys-bar-fill" style="width: {{ disk_percent }}%;"></div>
                </div>
            </div>

            <div class="sys-stats" style="margin-top: 20px; border-top: 1px dashed rgba(0,255,0,0.3); padding-top: 10px;">
                <span>⏱️ UPTIME STREAM:</span>
                <span style="font-weight: bold; text-shadow: 0 0 5px var(--neon-green);">{{ uptime_str }}</span>
            </div>
        </div>

    </div>

    <script>
        // Tactical auto-refresh to keep telemetry live
        setTimeout(() => {
            window.location.reload();
        }, 8000);
    </script>
</body>
</html>
'''

def get_uptime_string():
    boot_time = psutil.boot_time()
    uptime_seconds = time.time() - boot_time
    hours, remainder = divmod(uptime_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{int(hours)}h {int(minutes)}m {int(seconds)}s"

@app.route('/')
def index():
    # Live orbital command system stats
    cpu_percent = psutil.cpu_percent(interval=0.1)
    ram = psutil.virtual_memory()
    ram_percent = ram.percent
    ram_used = round(ram.used / (1024**3), 1)
    
    disk = psutil.disk_usage('/')
    disk_percent = disk.percent
    disk_free = round(disk.free / (1024**3), 1)
    
    uptime_str = get_uptime_string()

    return render_template_string(HTML_TEMPLATE,
                                  cpu_percent=cpu_percent,
                                  ram_percent=ram_percent,
                                  ram_used=ram_used,
                                  disk_percent=disk_percent,
                                  disk_free=disk_free,
                                  uptime_str=uptime_str)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8080)

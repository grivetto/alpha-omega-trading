import os
from flask import Flask, render_template_string
import threading
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola | Orbital Command</title>
    <style>
        :root {
            --neon-green: #39ff14;
            --neon-blue: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 10, 10, 0.9);
            --scanline-color: rgba(255, 255, 255, 0.05);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 30px;
            text-transform: uppercase;
            overflow-x: hidden;
            background-image: 
                linear-gradient(var(--scanline-color) 1px, transparent 1px),
                linear-gradient(90deg, var(--scanline-color) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        
        /* CRT Effect Overlay */
        body::after {
            content: " ";
            display: block;
            position: absolute;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            background: linear-gradient(rgba(18, 16, 16, 0) 50%, rgba(0, 0, 0, 0.25) 50%), linear-gradient(90deg, rgba(255, 0, 0, 0.06), rgba(0, 255, 0, 0.02), rgba(0, 0, 255, 0.06));
            z-index: 2;
            background-size: 100% 2px, 3px 100%;
            pointer-events: none;
        }

        h1 {
            text-align: center;
            color: var(--neon-blue);
            text-shadow: 0 0 10px var(--neon-blue), 0 0 20px var(--neon-blue), 0 0 40px var(--neon-blue);
            letter-spacing: 5px;
            font-size: 2.5em;
            margin-bottom: 5px;
            animation: glitch 3s infinite;
        }
        
        .subtitle {
            text-align: center; 
            color: var(--neon-pink); 
            margin-bottom: 40px;
            font-size: 1.2em;
            text-shadow: 0 0 5px var(--neon-pink);
            letter-spacing: 2px;
        }

        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 30px;
            position: relative;
            z-index: 3;
        }

        .panel {
            background-color: var(--panel-bg);
            border: 2px solid var(--neon-green);
            padding: 20px;
            box-shadow: inset 0 0 15px rgba(57, 255, 20, 0.1), 0 0 15px rgba(57, 255, 20, 0.2);
            border-radius: 4px;
            position: relative;
            transition: all 0.3s ease;
        }
        
        .panel:hover {
            box-shadow: inset 0 0 25px rgba(57, 255, 20, 0.2), 0 0 25px rgba(57, 255, 20, 0.4);
            transform: scale(1.02);
        }

        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            background: linear-gradient(45deg, var(--neon-green), transparent 40%, transparent 60%, var(--neon-green));
            z-index: -1;
            filter: blur(10px);
            opacity: 0.5;
        }

        .panel h2 {
            color: var(--neon-pink);
            border-bottom: 1px dashed var(--neon-pink);
            padding-bottom: 10px;
            text-shadow: 0 0 8px var(--neon-pink);
            font-size: 1.4em;
            margin-top: 0;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .status-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin: 15px 0;
            padding: 8px;
            background: rgba(255,255,255,0.02);
            border-left: 3px solid transparent;
        }
        
        .status-row:hover {
            border-left-color: var(--neon-blue);
            background: rgba(0, 255, 255, 0.05);
        }

        .name { font-weight: bold; }
        
        .online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: pulse 2s infinite;
        }
        
        .active-process {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
        }
        
        .metric {
            color: #fff;
            background: rgba(0,0,0,0.5);
            padding: 2px 8px;
            border: 1px solid var(--neon-pink);
            border-radius: 2px;
            box-shadow: 0 0 5px var(--neon-pink);
        }

        .logs {
            margin-top: 20px;
            font-size: 0.85em;
            color: #888;
            border-top: 1px solid #333;
            padding-top: 10px;
            font-family: monospace;
        }
        
        .log-line { margin: 5px 0; }
        .log-time { color: #555; }

        @keyframes pulse {
            0%, 100% { opacity: 1; text-shadow: 0 0 5px var(--neon-green); }
            50% { opacity: 0.5; text-shadow: none; }
        }

        @keyframes glitch {
            0% { transform: translate(0) }
            20% { transform: translate(-2px, 2px) }
            40% { transform: translate(-2px, -2px) }
            60% { transform: translate(2px, 2px) }
            80% { transform: translate(2px, -2px) }
            100% { transform: translate(0) }
        }

        .footer {
            margin-top: 50px;
            text-align: center;
            font-size: 0.9em;
            color: #444;
            border-top: 1px solid #222;
            padding-top: 20px;
        }
        
        .progress-bar {
            width: 100%;
            height: 4px;
            background: #222;
            margin-top: 5px;
            overflow: hidden;
            position: relative;
        }
        
        .progress-fill {
            height: 100%;
            background: var(--neon-blue);
            width: 50%;
            animation: load 3s ease-in-out infinite alternate;
            box-shadow: 0 0 10px var(--neon-blue);
        }
        
        @keyframes load {
            0% { width: 10%; }
            100% { width: 90%; }
        }
    </style>
</head>
<body>
    <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
    <div class="subtitle">[ SECURE UPLINK ESTABLISHED - CLUSTER NOMAD-01 ]</div>
    <div class="subtitle" style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="status-row">
                <span class="name">SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="online">[ENGAGED] 🟢</span>
            </div>
            
            <div class="status-row">
                <span class="name">SQUADRA_DELTA (Order Flow)</span>
                <span class="online">[ENGAGED] 🟢</span>
            </div>
            
            <div class="status-row">
                <span class="name">SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="online">[ENGAGED] 🟢</span>
            </div>

            <div class="logs">
                <div class="log-line"><span class="log-time">[sys.log]</span> > Executing high-frequency tactical maneuvers...</div>
                <div class="log-line"><span class="log-time">[alpha]</span> > 142 ms execution | target locked</div>
                <div class="log-line"><span class="log-time">[gamma]</span> > Arbitrage spread detected: 0.12%</div>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel" style="border-color: var(--neon-blue);">
            <h2 style="color: var(--neon-blue); border-bottom-color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue);">
                🛡️ PROTOCOLLO TRINITY
            </h2>
            
            <div class="status-row">
                <span class="name">Lo Strozzino (Funding Arb)</span>
                <span class="active-process">[ACTIVE] ⚡</span>
            </div>
            
            <div class="status-row">
                <span class="name">Il Contabile (DCA Engine)</span>
                <span class="active-process">[ACTIVE] ⚡</span>
            </div>
            
            <div class="status-row">
                <span class="name">L'Angelo Custode (MEV Arbitrum)</span>
                <span class="active-process">[ACTIVE] ⚡</span>
            </div>

            <div class="logs">
                <div class="log-line"><span class="log-time">[trinity]</span> > Wealth preservation matrices initialized</div>
                <div class="log-line"><span class="log-time">[strozzino]</span> > Harvesting yield... Apy ~18.4%</div>
                <div class="progress-bar"><div class="progress-fill"></div></div>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="border-color: var(--neon-pink);">
            <h2>📡 METRICHE DI MERCATO</h2>
            
            <div class="status-row">
                <span class="name">The Oracle (Sentiment)</span>
                <span class="metric">BULLISH 78% 🐂</span>
            </div>
            
            <div class="status-row">
                <span class="name">Whale Tracker (Inflows)</span>
                <span class="metric">+$452M 🐳</span>
            </div>
            
            <div class="status-row">
                <span class="name">Global Volatility Index</span>
                <span class="metric" style="color: yellow; border-color: yellow; box-shadow: 0 0 5px yellow;">ELEVATED ⚠️</span>
            </div>
            
            <div class="status-row">
                <span class="name">Liquidity Heatmap</span>
                <span class="online">[MAPPING...] 🗺️</span>
            </div>
            
            <div class="logs">
                <div class="log-line"><span class="log-time">[oracle]</span> > Ingesting social & volume metrics</div>
                <div class="log-line"><span class="log-time">[tracker]</span> > Large USDT mint detected at Treasury</div>
            </div>
        </div>
    </div>

    <div class="footer">
        NUVOLA CORE v9.2.1 | LATENCY: 12ms | UPTIME: 99.99% | ALL SYSTEMS NOMINAL
    </div>
    
    <script>
        // Simple script to occasionally blink or update logs for realism
        setInterval(() => {
            const logs = document.querySelectorAll('.log-time');
            const randomLog = logs[Math.floor(Math.random() * logs.length)];
            randomLog.style.color = '#fff';
            setTimeout(() => randomLog.style.color = '#555', 200);
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)

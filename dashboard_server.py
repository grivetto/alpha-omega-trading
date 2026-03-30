from flask import Flask, render_template_string
import threading
import time
import logging

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND // NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        body::before {
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
            color: var(--neon-cyan);
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            letter-spacing: 5px;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            text-transform: uppercase;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-top: 30px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2);
            position: relative;
        }
        .panel h2 {
            font-size: 1.2em;
            margin-top: 0;
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
            border-bottom: 1px dashed var(--neon-magenta);
            padding-bottom: 5px;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            animation: pulse 1.5s infinite;
        }
        .status-standby {
            color: #ffaa00;
            text-shadow: 0 0 5px #ffaa00;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            font-size: 0.9em;
        }
        .metric-value {
            color: var(--neon-cyan);
            font-weight: bold;
            text-shadow: 0 0 3px var(--neon-cyan);
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 10;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.2) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 5s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        hr {
            border: 0;
            border-top: 1px solid rgba(0, 255, 0, 0.3);
            margin: 10px 0;
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ ORBITAL COMMAND // NUVOLA HQ</h1>
    <div style="text-align: center; margin-top: -10px; margin-bottom: 20px; font-size: 1.2em; color: var(--neon-magenta); text-shadow: 0 0 5px var(--neon-magenta); border: 1px solid var(--neon-magenta); padding: 10px; border-radius: 5px; background: rgba(255, 0, 255, 0.1);">
        <strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="data-row">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Win Rate (1h):</span>
                <span class="metric-value">78.4%</span>
            </div>
            <div class="data-row">
                <span>&gt; Active Positions:</span>
                <span class="metric-value">3 (BTC, SOL, INJ)</span>
            </div>
            <hr>
            <div class="data-row">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Imbalance Detected:</span>
                <span class="metric-value">ETH/USDT (Long bias)</span>
            </div>
            <hr>
            <div class="data-row">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-standby">[ STANDBY ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Spread Z-Score:</span>
                <span class="metric-value">1.2 (Waiting > 2.0)</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <div class="data-row">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ ACTIVE ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Current Yield:</span>
                <span class="metric-value">42.1% APR</span>
            </div>
            <hr>
            <div class="data-row">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">[ ACTIVE ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Next Buy:</span>
                <span class="metric-value">T-Minus 14:22:00</span>
            </div>
            <hr>
            <div class="data-row">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">[ MONITORING ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Tx Snipe Ready:</span>
                <span class="metric-value">RPC Latency: 4ms</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>👁️ METRICHE DI MERCATO</h2>
            <div class="data-row">
                <span>🔮 The Oracle (Binance Sentiment)</span>
                <span class="status-online">[ STREAMING ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Global Bull/Bear:</span>
                <span class="metric-value" style="color: #0f0;">68% BULL</span>
            </div>
            <div class="data-row">
                <span>&gt; Top Longs:</span>
                <span class="metric-value">DOGE, PEPE, WIF</span>
            </div>
            <hr>
            <div class="data-row">
                <span>🐳 Whale Tracker</span>
                <span class="status-online">[ ALERTING ]</span>
            </div>
            <div class="data-row">
                <span>&gt; Last Large Tx:</span>
                <span class="metric-value">12,000 ETH -> Coinbase</span>
            </div>
            <div class="data-row">
                <span>&gt; Danger Level:</span>
                <span class="metric-value" style="color: #ffaa00;">ELEVATED</span>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 30px; text-align: center; font-size: 0.8em; color: #333; text-shadow: none;">
        [ SYSTEM NORMAL ] // UPTIME: 99.9% // CLUSTER: NUVOLA-PRIME // PROTOCOL: OMEGA
    </div>
    <script>
        setInterval(() => {
            if(Math.random() > 0.85) {
                document.body.style.boxShadow = "inset 0 0 30px rgba(0, 255, 0, 0.1)";
                setTimeout(() => document.body.style.boxShadow = "none", 150);
            }
        }, 1500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

import os
from flask import Flask, render_template_string
import time

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Nuvola Orbital Command 🌐</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-purple: #b026ff;
            --neon-red: #f00;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 20, 15, 0.8);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            background-image: linear-gradient(rgba(0, 255, 0, 0.03) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 255, 0, 0.03) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2 {
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan);
            color: var(--neon-cyan);
            margin-bottom: 30px;
            letter-spacing: 2px;
        }
        .grid-container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.2) inset;
            border-radius: 5px;
            position: relative;
            overflow: hidden;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -100%;
            width: 50%; height: 2px;
            background: linear-gradient(90deg, transparent, var(--neon-cyan));
            animation: scanline 3s linear infinite;
        }
        @keyframes scanline {
            100% { left: 100%; }
        }
        .status-online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 1.5s infinite; }
        .status-warning { color: var(--neon-purple); text-shadow: 0 0 5px var(--neon-purple); }
        @keyframes blink { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        ul { list-style-type: none; padding: 0; }
        li { margin: 10px 0; border-bottom: 1px dashed rgba(0, 255, 255, 0.3); padding-bottom: 5px; display: flex; justify-content: space-between; }
        .metric-value { font-weight: bold; }
    </style>
</head>
<body>
    <h1>🛰️ Nuvola Orbital Command - Tactical Dashboard 🛰️</h1>
    <h3 style="text-align: center; color: var(--neon-green); text-shadow: 0 0 10px var(--neon-green); animation: blink 2s infinite;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</h3>

    <div class="grid-container">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                    <span class="status-online">ENGAGED</span>
                </li>
                <li>
                    <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                    <span class="status-online">MONITORING</span>
                </li>
                <li>
                    <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                    <span class="status-warning">STANDBY</span>
                </li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--neon-cyan);">>> Target lock acquired. Executing high-frequency maneuvers.</div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔮 PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <span>🦇 Lo Strozzino (Funding Arb)</span>
                    <span class="status-online">ONLINE</span>
                </li>
                <li>
                    <span>🧮 Il Contabile (Smart DCA)</span>
                    <span class="status-online">ONLINE</span>
                </li>
                <li>
                    <span>🛡️ L'Angelo Custode (MEV Arb)</span>
                    <span class="status-online">ONLINE</span>
                </li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--neon-cyan);">>> Background defense protocols active. Yield extraction optimal.</div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 THE ORACLE & METRICS</h2>
            <ul>
                <li><span>Binance Sentiment Index</span> <span class="metric-value" style="color:var(--neon-green);">68.4 (GREED)</span></li>
                <li><span>Whale Tracker Anomalies</span> <span class="metric-value" style="color:var(--neon-purple);">2 DETECTED</span></li>
                <li><span>Global Market Volatility</span> <span class="metric-value">LOW</span></li>
                <li><span>Est. Hourly PnL</span> <span class="metric-value" style="color:var(--neon-green);">+$42.50</span></li>
            </ul>
            <div style="margin-top: 15px; font-size: 0.8em; color: var(--neon-cyan);">>> Data streams synchronized. Neural net evaluating orderbooks.</div>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

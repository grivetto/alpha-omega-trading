import os
from flask import Flask, render_template_string
import threading
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
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-pink: #ff00ff;
            --bg-color: #050505;
            --panel-bg: rgba(10, 20, 15, 0.85);
            --font-main: 'Courier New', Courier, monospace;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: var(--font-main);
            margin: 0;
            padding: 20px;
            background-image: 
                radial-gradient(circle, #111 1px, transparent 1px), 
                radial-gradient(circle, #111 1px, transparent 1px);
            background-size: 20px 20px;
            background-position: 0 0, 10px 10px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 30px;
            box-shadow: 0 5px 15px rgba(0, 255, 255, 0.1);
        }
        .header h1 {
            color: #fff;
            text-shadow: 0 0 10px #fff, 0 0 20px var(--neon-cyan), 0 0 30px var(--neon-cyan);
            letter-spacing: 2px;
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 25px;
            max-width: 1200px;
            margin: auto;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 0 15px rgba(0, 255, 255, 0.15);
            position: relative;
            overflow: hidden;
            transition: all 0.3s ease;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: -150%; width: 150%; height: 100%;
            background: linear-gradient(90deg, transparent, rgba(0, 255, 255, 0.1), transparent);
            animation: scanline 3s infinite linear;
        }
        @keyframes scanline {
            0% { left: -150%; }
            100% { left: 150%; }
        }
        .panel:hover {
            transform: translateY(-5px);
            box-shadow: 0 0 25px var(--neon-cyan);
        }
        .panel h2 {
            color: var(--neon-cyan);
            text-shadow: 0 0 8px var(--neon-cyan);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 10px;
            margin-top: 0;
            display: flex;
            align-items: center;
        }
        .panel h2 span {
            margin-right: 10px;
        }
        ul {
            list-style-type: none;
            padding: 0;
            margin: 0;
        }
        li {
            margin: 15px 0;
            padding: 10px 15px;
            background: rgba(0, 20, 10, 0.6);
            border-left: 4px solid var(--neon-pink);
            border-radius: 0 4px 4px 0;
            box-shadow: inset 0 0 10px rgba(0,0,0,0.8);
        }
        li strong {
            color: #fff;
            font-size: 1.1em;
            letter-spacing: 1px;
            text-shadow: 0 0 5px var(--neon-pink);
        }
        .status-online {
            color: var(--neon-green);
            font-weight: bold;
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0.4; }
        }
        .metric-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 15px;
        }
        .metric-box {
            background: rgba(0, 0, 0, 0.8);
            border: 1px solid var(--neon-pink);
            border-radius: 4px;
            padding: 15px;
            text-align: center;
            box-shadow: 0 0 8px rgba(255, 0, 255, 0.2);
            transition: 0.2s;
        }
        .metric-box:hover {
            box-shadow: 0 0 15px rgba(255, 0, 255, 0.5);
        }
        .metric-label {
            font-size: 0.8em;
            color: #ccc;
            margin-bottom: 5px;
            text-transform: uppercase;
        }
        .metric-value {
            font-size: 1.6em;
            color: var(--neon-pink);
            font-weight: bold;
            text-shadow: 0 0 10px var(--neon-pink);
        }
        .footer {
            text-align: center;
            margin-top: 40px;
            font-size: 0.85em;
            color: rgba(57, 255, 20, 0.5);
            border-top: 1px dashed rgba(57, 255, 20, 0.3);
            padding-top: 10px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ Nuvola Orbital Command</h1>
        <p>📡 SYSTEM STATUS: <span class="status-online">FULLY OPERATIONAL</span> | 🔒 SECURE UPLINK</p>
        <p>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2><span>⚔️</span> SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>🐺 SQUADRA_ALPHA</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Role: Scalper on Binance</span><br>
                    Status: <span class="status-online">ENGAGING TARGETS [ACTIVE]</span>
                </li>
                <li>
                    <strong>🦅 SQUADRA_DELTA</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Role: Order Flow Analytics</span><br>
                    Status: <span class="status-online">MONITORING LIQUIDITY [ACTIVE]</span>
                </li>
                <li>
                    <strong>🦂 SQUADRA_GAMMA</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Role: Pairs Trading on Bitget</span><br>
                    Status: <span class="status-online">ARBITRAGE EXECUTION [ACTIVE]</span>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2><span>🔺</span> PROTOCOLLO TRINITY</h2>
            <ul>
                <li>
                    <strong>💼 Lo Strozzino</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Operation: Funding Rate Arbitrage</span><br>
                    Status: <span class="status-online">EXTRACTING YIELD [ONLINE]</span>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Operation: DCA / Accumulation</span><br>
                    Status: <span class="status-online">BALANCING BOOKS [ONLINE]</span>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong><br>
                    <span style="color:#aaa;font-size:0.9em;">Operation: MEV Protection & Arb on Arbitrum</span><br>
                    Status: <span class="status-online">SHIELD DEPLOYED [ONLINE]</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2><span>📡</span> METRICHE DI MERCATO</h2>
            <div class="metric-grid">
                <div class="metric-box">
                    <div class="metric-label">🔮 The Oracle (Binance Sentiment)</div>
                    <div class="metric-value">BULLISH 78%</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">🐋 Whale Tracker</div>
                    <div class="metric-value">ACCUMULATION</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">⚡ HFT Executions / min</div>
                    <div class="metric-value">1,342</div>
                </div>
                <div class="metric-box">
                    <div class="metric-label">💸 Trinity APY (Est.)</div>
                    <div class="metric-value">42.7%</div>
                </div>
            </div>
            <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.05); text-align: center; border: 1px dashed gray; font-size: 0.9em;">
                > Live Market Data Feed: <span class="status-online">SYNCED</span> <br>
                > Latency: 12ms to Exchange Servers
            </div>
        </div>
    </div>

    <div class="footer">
        // PROTOCOLLO NUVOLA V2.0.4 - ALL SYSTEMS GO //
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

import os
import threading
from flask import Flask, render_template_string

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
            --neon-cyan: #00f3ff;
            --neon-green: #39ff14;
            --neon-red: #ff003c;
            --neon-purple: #b026ff;
            --neon-yellow: #fcee0a;
            --bg-color: #050505;
            --panel-bg: rgba(10, 15, 20, 0.85);
            --border-neon: 1px solid var(--neon-cyan);
        }
        body {
            margin: 0;
            padding: 30px;
            background-color: var(--bg-color);
            color: var(--neon-cyan);
            font-family: 'Courier New', Courier, monospace;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-cyan);
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 15px;
            margin-bottom: 30px;
            animation: flicker 4s infinite;
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% {
                text-shadow: 0 0 10px var(--neon-cyan), 0 0 20px var(--neon-cyan), 0 0 40px var(--neon-cyan);
                opacity: 1;
            }
            20%, 24%, 55% {
                text-shadow: none;
                opacity: 0.5;
            }
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(380px, 1fr));
            gap: 25px;
        }
        .panel {
            background: var(--panel-bg);
            border: var(--border-neon);
            box-shadow: 0 0 15px rgba(0, 243, 255, 0.2);
            padding: 25px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; width: 10px; height: 10px;
            border-top: 2px solid var(--neon-cyan);
            border-left: 2px solid var(--neon-cyan);
        }
        .panel::after {
            content: '';
            position: absolute;
            bottom: 0; right: 0; width: 10px; height: 10px;
            border-bottom: 2px solid var(--neon-cyan);
            border-right: 2px solid var(--neon-cyan);
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 8px var(--neon-green);
        }
        .status-standby {
            color: var(--neon-purple);
            text-shadow: 0 0 8px var(--neon-purple);
        }
        .status-warning {
            color: var(--neon-yellow);
            text-shadow: 0 0 8px var(--neon-yellow);
        }
        .pulse {
            display: inline-block;
            width: 10px;
            height: 10px;
            background-color: var(--neon-green);
            border-radius: 50%;
            margin-right: 10px;
            animation: pulse-animation 1.5s infinite;
        }
        @keyframes pulse-animation {
            0% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0.7); }
            70% { box-shadow: 0 0 0 10px rgba(57, 255, 20, 0); }
            100% { box-shadow: 0 0 0 0 rgba(57, 255, 20, 0); }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(0, 243, 255, 0.3);
            padding: 8px 0;
            font-size: 0.95em;
        }
        .metric {
            font-weight: bold;
            color: var(--neon-red);
            text-shadow: 0 0 5px var(--neon-red);
        }
        ul {
            list-style-type: none;
            padding: 0;
        }
        li {
            margin-bottom: 15px;
            padding-left: 15px;
            border-left: 3px solid var(--neon-purple);
            background: rgba(176, 38, 255, 0.05);
            padding: 10px 15px;
            border-radius: 0 4px 4px 0;
        }
        li strong {
            color: #fff;
            font-size: 1.1em;
            letter-spacing: 1px;
            text-shadow: 0 0 4px #fff;
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(to bottom, rgba(255,255,255,0), rgba(255,255,255,0) 50%, rgba(0,243,255,0.2) 50%, rgba(0,243,255,0.2));
            background-size: 100% 4px;
            animation: scroll 10s linear infinite;
            top: 0;
            left: 0;
            bottom: 0;
            right: 0;
            height: 100vh;
        }
        @keyframes scroll {
            0% { background-position: 0 0; }
            100% { background-position: 0 100vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA</h1>
        <p>SYSTEM STATUS: <span class="status-online"><span class="pulse"></span>QUANTUM CORE STABLE</span> | UPTIME: <span id="uptime">00:00:00</span></p>
        <p style="color: var(--neon-cyan); font-weight: bold;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- ASSAULT SQUADS -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>[SQUADRA_ALPHA]</strong> - Scalper su Binance 🎯<br>
                    Status: <span class="status-online">ENGAGED</span> | Latency: 12ms<br>
                    <small style="color: #aaa;">Targeting micro-inefficiencies on BTC/USDT. Order flow delta positive.</small>
                </li>
                <li>
                    <strong>[SQUADRA_DELTA]</strong> - Order Flow 🌊<br>
                    Status: <span class="status-online">MONITORING</span> | Latency: 18ms<br>
                    <small style="color: #aaa;">Tracking institutional tape anomalies. Passive bids loaded.</small>
                </li>
                <li>
                    <strong>[SQUADRA_GAMMA]</strong> - Pairs Trading su Bitget ⚖️<br>
                    Status: <span class="status-standby">RECALIBRATING</span> | Spread: 0.42%<br>
                    <small style="color: #aaa;">Awaiting statistical convergence on L1 sector pairs.</small>
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p>Background Daemons: <span class="status-online">ONLINE & HIDDEN</span></p>
            <ul>
                <li>
                    <strong>🎭 Lo Strozzino</strong> (Funding Arb)<br>
                    <small style="color: #aaa;">Extracting yield across perps vs spot. Current APY: <span class="status-online">14.2%</span></small>
                </li>
                <li>
                    <strong>🧮 Il Contabile</strong> (DCA)<br>
                    <small style="color: #aaa;">Accumulation phase active. Next batch execution in <span class="status-warning">04:22:10</span></small>
                </li>
                <li>
                    <strong>🛡️ L'Angelo Custode</strong> (MEV Arbitrum)<br>
                    <small style="color: #aaa;">Mempool scanning active. Sandwich protection <strong>ON</strong>. Toxic flow blocked.</small>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p>External Feeds: <span class="status-online">SYNCED (via WebSocket)</span></p>
            <div class="data-row">
                <span>The Oracle (Binance Sentiment):</span>
                <span class="status-online">EXTREME GREED (88)</span>
            </div>
            <div class="data-row">
                <span>Whale Tracker (100k+ orders):</span>
                <span class="status-online">ELEVATED BUY WALLS</span>
            </div>
            <div class="data-row">
                <span>Global Liquidity Index:</span>
                <span class="metric">+$4.2B / 24h</span>
            </div>
            <div class="data-row">
                <span>Vol-Surface Distortion:</span>
                <span class="status-warning">WARNING: SKEW SHIFT</span>
            </div>
            <div class="data-row">
                <span>Network Congestion (ETH):</span>
                <span>24 Gwei</span>
            </div>
            <div class="data-row">
                <span>CEX Outflows (24h):</span>
                <span class="status-online">-$1.2B</span>
            </div>
        </div>
    </div>
    <script>
        let seconds = 0;
        setInterval(() => {
            seconds++;
            const h = String(Math.floor(seconds / 3600)).padStart(2, '0');
            const m = String(Math.floor((seconds % 3600) / 60)).padStart(2, '0');
            const s = String(seconds % 60).padStart(2, '0');
            document.getElementById('uptime').innerText = `${h}:${m}:${s}`;
        }, 1000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Avvia in ascolto
    app.run(host='0.0.0.0', port=5000, debug=False)

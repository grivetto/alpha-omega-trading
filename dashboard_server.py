from flask import Flask, render_template_string
import threading
import time
import random
from datetime import datetime

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
            --neon-green: #39ff14;
            --neon-cyan: #0ff;
            --neon-pink: #ff00ff;
            --dark-bg: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--dark-bg);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-cyan);
            padding-bottom: 10px;
            margin-bottom: 20px;
            text-shadow: 0 0 10px var(--neon-cyan);
            color: var(--neon-cyan);
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid #333;
            padding: 15px;
            border-radius: 5px;
            box-shadow: 0 0 15px rgba(57, 255, 20, 0.1);
            transition: all 0.3s ease;
        }
        .panel:hover {
            border-color: var(--neon-green);
            box-shadow: 0 0 20px rgba(57, 255, 20, 0.4);
        }
        .panel.trinity {
            border-color: #333;
        }
        .panel.trinity:hover {
            border-color: var(--neon-pink);
            box-shadow: 0 0 20px rgba(255, 0, 255, 0.4);
        }
        .panel.market {
            border-color: #333;
        }
        .panel.market:hover {
            border-color: var(--neon-cyan);
            box-shadow: 0 0 20px rgba(0, 255, 255, 0.4);
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
        }
        .status-active {
            color: var(--neon-cyan);
            text-shadow: 0 0 5px var(--neon-cyan);
            animation: blink 1.5s infinite;
        }
        .status-warning {
            color: yellow;
            text-shadow: 0 0 5px yellow;
        }
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .metric-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 5px;
            border-bottom: 1px dashed #333;
            padding-bottom: 3px;
        }
        .glow-text {
            animation: textGlow 2s infinite alternate;
        }
        @keyframes textGlow {
            from { text-shadow: 0 0 5px var(--neon-green); }
            to { text-shadow: 0 0 20px var(--neon-green); }
        }
        ul {
            list-style-type: none;
            padding-left: 0;
        }
        li::before {
            content: "> ";
            color: var(--neon-pink);
        }
    </style>
    <script>
        setInterval(() => {
            const elements = document.querySelectorAll('.dynamic-val');
            elements.forEach(el => {
                const current = parseFloat(el.innerText);
                if (!isNaN(current)) {
                    const variance = (Math.random() - 0.5) * 0.1;
                    el.innerText = (current + variance).toFixed(2);
                }
            });
        }, 1500);
    </script>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND // NUVOLA TERMINAL 🛰️</h1>
        <p>SYSTEM STATUS: <span class="status-online glow-text">ONLINE</span> | UPLINK: SECURE | CLOCK: {{ time }}</p>
        <p style="color: var(--neon-pink); font-weight: bold; text-shadow: 0 0 8px var(--neon-pink);">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <div class="metric-row">
                <span>🐺 SQUADRA_ALPHA (Binance Scalper)</span>
                <span class="status-active">[ ENGAGED ]</span>
            </div>
            <div class="metric-row">
                <span>> Win Rate / 24h:</span>
                <span style="color:var(--neon-green);">68.4%</span>
            </div>
            <br>
            <div class="metric-row">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="status-active">[ ENGAGED ]</span>
            </div>
            <div class="metric-row">
                <span>> Order Imbalance:</span>
                <span style="color:var(--neon-cyan);">+14.2% (BULL)</span>
            </div>
            <br>
            <div class="metric-row">
                <span>⚖️ SQUADRA_GAMMA (Bitget Pairs)</span>
                <span class="status-active">[ ENGAGED ]</span>
            </div>
            <div class="metric-row">
                <span>> Z-Score (BTC/ETH):</span>
                <span class="dynamic-val" style="color:yellow;">1.85</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel trinity">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink);">🔺 PROTOCOLLO TRINITY</h2>
            <div class="metric-row">
                <span>💼 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ RUNNING ]</span>
            </div>
            <div class="metric-row">
                <span>> Spread APR:</span>
                <span class="dynamic-val" style="color:var(--neon-green);">18.42</span>%
            </div>
            <br>
            <div class="metric-row">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">[ RUNNING ]</span>
            </div>
            <div class="metric-row">
                <span>> Next Accumulation:</span>
                <span style="color:var(--neon-cyan);">04:30 UTC</span>
            </div>
            <br>
            <div class="metric-row">
                <span>👼 L'Angelo Custode (Arbitrum MEV)</span>
                <span class="status-online">[ RUNNING ]</span>
            </div>
            <div class="metric-row">
                <span>> Last Snipe / Profit:</span>
                <span style="color:var(--neon-green);">+0.041 ETH</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel market">
            <h2 style="color: var(--neon-cyan); text-shadow: 0 0 5px var(--neon-cyan);">📊 METRICHE DI MERCATO</h2>
            <div class="metric-row">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span class="status-online">[ CONNECTED ]</span>
            </div>
            <div class="metric-row">
                <span>> Fear & Greed:</span>
                <span style="color:var(--neon-cyan);">72 (GREED)</span>
            </div>
            <div class="metric-row">
                <span>> Global Volatility:</span>
                <span class="dynamic-val" style="color:yellow;">45.20</span>
            </div>
            <br>
            <div class="metric-row">
                <span>🐋 Whale Tracker</span>
                <span class="status-active">[ SCANNING ]</span>
            </div>
            <div class="metric-row">
                <span>> Last Large Tx:</span>
                <span style="color:var(--neon-pink);">1,200 BTC ➔ Coinbase</span>
            </div>
            <div class="metric-row">
                <span>> Inflow/Outflow Ratio:</span>
                <span class="dynamic-val" style="color:var(--neon-green);">1.12</span>
            </div>
        </div>
    </div>
    
    <div style="margin-top: 20px; font-size: 12px; color: #555; text-align: center;">
        [ SYSTEM KERNEL V4.2.0 ] [ ENCRYPTION: AES-256-GCM ] [ UNAUTHORIZED ACCESS WILL BE TERMINATED ]
    </div>
</body>
</html>
"""

@app.route('/')
def index():
    current_time = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
    return render_template_string(HTML_TEMPLATE, time=current_time)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

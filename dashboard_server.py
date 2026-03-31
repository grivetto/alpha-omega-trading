from flask import Flask, render_template_string
import threading
import time
import random

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: rgba(0, 20, 0, 0.8);
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2 {
            text-align: center;
            text-transform: uppercase;
            text-shadow: 0 0 10px var(--neon-green), 0 0 20px var(--neon-green);
            margin-bottom: 30px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-green);
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 0, 0.2), inset 0 0 10px rgba(0, 255, 0, 0.1);
            transition: all 0.3s ease;
        }
        .panel:hover {
            box-shadow: 0 0 15px var(--neon-green), inset 0 0 15px var(--neon-green);
        }
        .panel h3 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
            margin-top: 0;
        }
        .status-online {
            color: var(--neon-green);
            animation: blink 1.5s infinite;
        }
        .status-active {
            color: var(--neon-pink);
            text-shadow: 0 0 5px var(--neon-pink);
        }
        @keyframes blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
        .data-row {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 0.9em;
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
            100% { top: 100vh; }
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <h2>[ CYBER-WARFARE FINANCIAL DASHBOARD ]</h2>
    <div style="text-align: center; margin-bottom: 20px; font-weight: bold; padding: 10px; border: 1px solid var(--neon-green); background: var(--panel-bg); color: var(--neon-green); box-shadow: 0 0 10px var(--neon-green);">
        <span class="status-online">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</span>
    </div>

    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h3>⚔️ SQUADRE D'ASSALTO (HFT)</h3>
            <div class="data-row">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span>> Win Rate (1h):</span>
                <span class="status-active">78.4%</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>⚡ SQUADRA_DELTA (Order Flow)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span>> Imbalance Detection:</span>
                <span class="status-active">ACTIVE</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status-online">[ ENGAGED ]</span>
            </div>
            <div class="data-row">
                <span>> Spread Z-Score:</span>
                <span class="status-active">+2.14 σ</span>
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h3>🛡️ PROTOCOLLO TRINITY</h3>
            <div class="data-row">
                <span>🦇 Lo Strozzino (Funding Arb)</span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div class="data-row">
                <span>> APY Proiettato:</span>
                <span style="color: yellow;">14.2%</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div class="data-row">
                <span>> Accumulo in corso:</span>
                <span style="color: yellow;">BTC/ETH</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>👼 L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status-online">[ ONLINE ]</span>
            </div>
            <div class="data-row">
                <span>> Flashloans Eseguiti (24h):</span>
                <span style="color: yellow;">12</span>
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h3>📊 METRICHE DI MERCATO</h3>
            <div class="data-row">
                <span>🔮 The Oracle (Binance Sentiment)</span>
                <span class="status-active">BULLISH</span>
            </div>
            <div class="data-row">
                <span>> Fear & Greed Index:</span>
                <span style="color: #0f0;">72 (Greed)</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>🐋 Whale Tracker</span>
                <span class="status-online">[ SCANNING ]</span>
            </div>
            <div class="data-row">
                <span>> Ultimo movimento:</span>
                <span style="color: #f00;">500 BTC -> Coinbase</span>
            </div>
            <div class="data-row" style="margin-top: 15px;">
                <span>🌐 Nuvola Core Latency</span>
                <span class="status-active">14ms</span>
            </div>
            <div class="data-row">
                <span>> System Load:</span>
                <span style="color: #0f0;">12%</span>
            </div>
        </div>
    </div>

    <script>
        setInterval(() => {
            const els = document.querySelectorAll('.status-active');
            if(els.length > 0) {
                els[0].style.opacity = Math.random() > 0.8 ? 0.5 : 1;
            }
        }, 500);
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)

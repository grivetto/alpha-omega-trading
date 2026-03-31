import os
import random
from flask import Flask, render_template_string

app = Flask(__name__)

# Tactical cyberpunk HTML/CSS template
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND [NUVOLA]</title>
    <style>
        :root {
            --neon-blue: #00f3ff;
            --neon-pink: #ff00ff;
            --neon-green: #00ff00;
            --neon-red: #ff003c;
            --bg-dark: #050505;
            --panel-bg: rgba(0, 20, 30, 0.8);
        }
        body {
            background-color: var(--bg-dark);
            color: var(--neon-blue);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
            background-image: linear-gradient(rgba(0, 243, 255, 0.05) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(0, 243, 255, 0.05) 1px, transparent 1px);
            background-size: 20px 20px;
        }
        h1, h2, h3 {
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 0;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-blue);
            padding-bottom: 15px;
            margin-bottom: 30px;
            text-shadow: 0 0 10px var(--neon-blue);
        }
        .container {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: inset 0 0 15px rgba(0, 243, 255, 0.2), 0 0 10px rgba(0, 243, 255, 0.4);
            padding: 20px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: -2px; left: -2px; right: -2px; bottom: -2px;
            z-index: -1;
            background: linear-gradient(45deg, var(--neon-blue), var(--neon-pink), var(--neon-blue));
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        .panel:hover::before {
            opacity: 0.5;
        }
        .status {
            font-weight: bold;
            display: inline-block;
            margin-left: 10px;
        }
        .status.online { color: var(--neon-green); text-shadow: 0 0 5px var(--neon-green); animation: blink 2s infinite; }
        .status.active { color: var(--neon-blue); text-shadow: 0 0 5px var(--neon-blue); }
        .status.offline { color: var(--neon-red); text-shadow: 0 0 5px var(--neon-red); }
        .status.standby { color: #ffaa00; text-shadow: 0 0 5px #ffaa00; }
        
        @keyframes blink {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        .stat-row {
            display: flex;
            justify-content: space-between;
            border-bottom: 1px dashed rgba(0, 243, 255, 0.3);
            padding: 5px 0;
        }
        .glitch {
            position: relative;
        }
        .glitch::before, .glitch::after {
            content: attr(data-text);
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: var(--bg-dark);
        }
        .glitch::before {
            left: 2px;
            text-shadow: -1px 0 red;
            animation: glitch-anim-1 2s infinite linear alternate-reverse;
        }
        .glitch::after {
            left: -2px;
            text-shadow: -1px 0 blue;
            animation: glitch-anim-2 3s infinite linear alternate-reverse;
        }
        .log-window {
            height: 150px;
            overflow-y: hidden;
            font-size: 0.8em;
            color: #ccc;
            background: #000;
            border: 1px solid #333;
            padding: 10px;
            margin-top: 10px;
        }
        .log-line {
            margin: 2px 0;
            font-family: monospace;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1 class="glitch" data-text="🛰️ ORBITAL COMMAND 🛰️">🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>NUVOLA QUANTITATIVE DASHBOARD v3.0 [ENCRYPTED CONNECTION]</p>
        <div style="margin-top: 15px; padding: 10px; border: 1px solid var(--neon-green); color: var(--neon-green); background: rgba(0, 255, 0, 0.1); font-weight: bold; display: inline-block; box-shadow: 0 0 10px rgba(0,255,0,0.2);">
            ⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)
        </div>
    </div>

    <div class="container">
        <!-- SEZIONE 1: SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 8px var(--neon-pink);">⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            
            <div class="stat-row">
                <span>🐺 SQUADRA_ALPHA (Scalper Binance)</span>
                <span class="status online">[ONLINE] 🟢</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ APM: ~420 | PnL (24h): +1.24%</span>
            </div>

            <div class="stat-row" style="margin-top: 10px;">
                <span>🌊 SQUADRA_DELTA (Order Flow)</span>
                <span class="status online">[ENGAGED] 🔵</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ Imbalance detect: High | Positions: 4</span>
            </div>

            <div class="stat-row" style="margin-top: 10px;">
                <span>⚖️ SQUADRA_GAMMA (Pairs Bitget)</span>
                <span class="status active">[ACTIVE] 🟣</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ Z-Score: 2.1 | Spread Arb: Running</span>
            </div>
        </div>

        <!-- SEZIONE 2: PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 style="color: var(--neon-green); text-shadow: 0 0 8px var(--neon-green);">♅ PROTOCOLLO TRINITY</h2>
            
            <div class="stat-row">
                <span>🎩 Lo Strozzino (Funding Arb)</span>
                <span class="status standby">[MONITORING] 🟡</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ Yield target: >15% APR</span>
            </div>

            <div class="stat-row" style="margin-top: 10px;">
                <span>🧮 Il Contabile (DCA)</span>
                <span class="status online">[BACKGROUND] 🟢</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ Accruing BTC/ETH on support levels</span>
            </div>

            <div class="stat-row" style="margin-top: 10px;">
                <span>🛡️ L'Angelo Custode (MEV Arbitrum)</span>
                <span class="status online">[PATROLLING] 🟢</span>
            </div>
            <div class="stat-row" style="font-size: 0.8em; color: #888;">
                <span>↳ Flashbots connected | Sandwich defense ON</span>
            </div>
        </div>

        <!-- SEZIONE 3: METRICHE DI MERCATO -->
        <div class="panel">
            <h2 style="color: var(--neon-blue); text-shadow: 0 0 8px var(--neon-blue);">📊 MARKET METRICS</h2>
            
            <div class="stat-row">
                <span>👁️ The Oracle (Binance Sentiment)</span>
                <span class="status active" id="oracle-val">Bullish (0.68)</span>
            </div>
            <div class="stat-row">
                <span>🐋 Whale Tracker</span>
                <span class="status standby">Alert: 2k BTC moved</span>
            </div>
            <div class="stat-row">
                <span>⚡ Volatility Index (Nuvola-VIX)</span>
                <span class="status online">ELEVATED [42.1]</span>
            </div>
            
            <div class="log-window">
                <div class="log-line">> [SYS] Connecting to data stream... OK</div>
                <div class="log-line">> [ALPHA] Executed LIMIT BUY BTCUSDT 65400</div>
                <div class="log-line" style="color: var(--neon-pink);">> [ORACLE] Sudden volume spike detected!</div>
                <div class="log-line">> [GAMMA] Rebalancing pair ETH/SOL</div>
                <div class="log-line">> [STROZZINO] Funding rate divergence found.</div>
            </div>
        </div>
    </div>

    <script>
        // Simple script to make some values flicker
        setInterval(() => {
            const oracle = document.getElementById('oracle-val');
            const vals = ['Bullish (0.68)', 'Bullish (0.69)', 'Neutral (0.55)', 'Bullish (0.71)'];
            oracle.innerText = vals[Math.floor(Math.random() * vals.length)];
        }, 3000);
    </script>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(DASHBOARD_HTML)

if __name__ == '__main__':
    # Start Nuvola Orbital Command Dashboard
    app.run(host='0.0.0.0', port=5000, debug=False)
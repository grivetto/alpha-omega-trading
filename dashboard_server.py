import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>NUVOLA ORBITAL COMMAND</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Share+Tech+Mono&display=swap');
        body {
            background-color: #050505;
            color: #00ffcc;
            font-family: 'Share Tech Mono', monospace;
            margin: 0;
            padding: 20px;
            background-image: radial-gradient(circle at center, #0a192f 0%, #000000 100%);
        }
        h1 {
            text-align: center;
            color: #ff00ff;
            text-shadow: 0 0 10px #ff00ff, 0 0 20px #ff00ff;
            letter-spacing: 5px;
            border-bottom: 2px solid #ff00ff;
            padding-bottom: 10px;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }
        .panel {
            background: rgba(0, 20, 20, 0.6);
            border: 1px solid #00ffcc;
            border-radius: 5px;
            padding: 15px;
            box-shadow: 0 0 10px rgba(0, 255, 204, 0.2), inset 0 0 10px rgba(0, 255, 204, 0.1);
            animation: pulse 4s infinite alternate;
        }
        .panel h2 {
            color: #ffff00;
            text-shadow: 0 0 5px #ffff00;
            border-bottom: 1px dashed #ffff00;
            padding-bottom: 5px;
            margin-top: 0;
        }
        .status-online {
            color: #00ff00;
            text-shadow: 0 0 5px #00ff00;
        }
        .status-active {
            color: #ff00ff;
            text-shadow: 0 0 5px #ff00ff;
        }
        .blink {
            animation: blinker 1.5s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        @keyframes pulse {
            0% { box-shadow: 0 0 10px rgba(0, 255, 204, 0.2); border-color: #00ffcc; }
            100% { box-shadow: 0 0 20px rgba(0, 255, 204, 0.6); border-color: #00ffff; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid rgba(0, 255, 204, 0.3);
            padding: 8px;
            text-align: left;
        }
        th {
            background: rgba(0, 255, 204, 0.1);
        }
        .scan-line {
            width: 100%;
            height: 2px;
            background-color: rgba(0, 255, 204, 0.5);
            position: absolute;
            top: 0;
            left: 0;
            animation: scan 5s linear infinite;
            pointer-events: none;
            z-index: 9999;
        }
        @keyframes scan {
            0% { top: 0; }
            100% { top: 100%; }
        }
        .container {
            position: relative;
            overflow: hidden;
        }
    </style>
</head>
<body>
    <div class="scan-line"></div>
    <h1>🛰️ NUVOLA ORBITAL COMMAND 🛰️</h1>
    <div style="text-align: center; margin-bottom: 20px; font-size: 1.2em; font-weight: bold; color: #00ffcc;" class="blink">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</div>
    <div class="grid">
        
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <table>
                <tr><th>Squadra</th><th>Ruolo</th><th>Target</th><th>Status</th></tr>
                <tr><td>SQUADRA_ALPHA</td><td>Scalper</td><td>Binance</td><td><span class="status-active blink">ENGAGED</span></td></tr>
                <tr><td>SQUADRA_DELTA</td><td>Order Flow</td><td>Cross-EX</td><td><span class="status-online">STANDBY</span></td></tr>
                <tr><td>SQUADRA_GAMMA</td><td>Pairs Trading</td><td>Bitget</td><td><span class="status-active">ARBITRAGING</span></td></tr>
            </table>
            <p style="margin-top:10px; font-size: 0.9em; color:#888;">> Sub-millisecond execution vectors nominal.</p>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <table>
                <tr><th>Agente</th><th>Specializzazione</th><th>Network</th><th>Status</th></tr>
                <tr><td>Lo Strozzino</td><td>Funding Arb</td><td>Perp/Spot</td><td><span class="status-online">ONLINE</span></td></tr>
                <tr><td>Il Contabile</td><td>DCA & Yield</td><td>DeFi</td><td><span class="status-online">ONLINE</span></td></tr>
                <tr><td>L'Angelo Custode</td><td>MEV & Protection</td><td>Arbitrum</td><td><span class="status-online">ONLINE</span></td></tr>
            </table>
            <p style="margin-top:10px; font-size: 0.9em; color:#888;">> Trinity backbone active in background.</p>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <table>
                <tr><th>Modulo</th><th>Metrica</th><th>Valore</th></tr>
                <tr><td>The Oracle</td><td>Binance Sentiment</td><td><span style="color:#00ff00;">BULLISH (82%)</span></td></tr>
                <tr><td>Whale Tracker</td><td>Inflow/Outflow</td><td><span style="color:#ff0000;">-12.4K BTC</span></td></tr>
                <tr><td>Liquidity Map</td><td>Order Book Imbalance</td><td><span style="color:#00ffff;">SKEWED (BID)</span></td></tr>
            </table>
            <p style="margin-top:10px; font-size: 0.9em; color:#888;">> Awaiting next datastream packet...</p>
        </div>

        <!-- SYSTEM LOGS -->
        <div class="panel" style="grid-column: 1 / -1;">
            <h2>💻 TERMINAL / LOGS</h2>
            <div style="font-size: 0.9em; line-height: 1.5; color: #aaa;">
                [SYSTEM] Orbital Command initialized... <br>
                [SYSTEM] Neural link established with Nuvola Core. <br>
                [SQUADRA_ALPHA] Captured spread on BTC/USDT: +0.02% <br>
                [STROZZINO] Rebalancing funding rates across Binance/Bybit. <br>
                [ANGELO_CUSTODE] MEV opportunity detected on Camelot DEX. Executing flashbots bundle... <br>
                <span class="blink">_</span>
            </div>
        </div>

    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Run on port 5000 by default, accessible on local network
    app.run(host='0.0.0.0', port=5000)

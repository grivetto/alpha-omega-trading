from flask import Flask, render_template_string
import os

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND | NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-cyan: #0ff;
            --neon-magenta: #f0f;
            --bg-dark: #050505;
            --panel-bg: rgba(10, 20, 10, 0.8);
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
        h1, h2, h3 {
            text-transform: uppercase;
            text-shadow: 0 0 5px var(--neon-green);
            letter-spacing: 2px;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 3s infinite;
        }
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-cyan);
            box-shadow: 0 0 10px rgba(0, 255, 255, 0.2);
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel::before {
            content: '';
            position: absolute;
            top: 0; left: 0; right: 0; bottom: 0;
            box-shadow: inset 0 0 20px rgba(0, 255, 255, 0.1);
            pointer-events: none;
        }
        .panel h2 {
            color: var(--neon-cyan);
            border-bottom: 1px dashed var(--neon-cyan);
            padding-bottom: 5px;
            margin-top: 0;
        }
        .status-online {
            color: var(--neon-green);
            font-weight: bold;
            animation: pulse 1.5s infinite;
        }
        .status-warning {
            color: #ff0;
        }
        .status-magenta {
            color: var(--neon-magenta);
            text-shadow: 0 0 5px var(--neon-magenta);
        }
        ul {
            list-style-type: none;
            padding-left: 0;
        }
        li {
            margin-bottom: 8px;
            border-left: 2px solid var(--neon-cyan);
            padding-left: 10px;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; text-shadow: 0 0 8px var(--neon-green); }
            20%, 22%, 24%, 55% { opacity: 0.4; text-shadow: none; }
        }
        .scanline {
            width: 100%;
            height: 100px;
            z-index: 9999;
            position: absolute;
            pointer-events: none;
            background: linear-gradient(0deg, rgba(0,0,0,0) 0%, rgba(0,255,0,0.1) 50%, rgba(0,0,0,0) 100%);
            opacity: 0.1;
            animation: scan 6s linear infinite;
        }
        @keyframes scan {
            0% { top: -100px; }
            100% { top: 100%; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }
        th, td {
            border: 1px solid #333;
            padding: 5px;
            text-align: left;
            font-size: 0.9em;
        }
        th {
            color: var(--neon-cyan);
        }
    </style>
</head>
<body>
    <div class="scanline"></div>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND 🛰️</h1>
        <p>SYSTEM: <span class="status-online">ONLINE</span> | UPLINK: SECURE | SEC-LEVEL: OMEGA</p>
    </div>
    
    <div class="grid">
        <!-- SQUADRE D'ASSALTO -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <ul>
                <li>
                    <strong>SQUADRA_ALPHA</strong> 🐺<br>
                    <small>Target: Binance (Scalper)</small><br>
                    Status: <span class="status-online">[ ENGAGED ]</span> Latenza: 12ms
                </li>
                <li>
                    <strong>SQUADRA_DELTA</strong> 🦅<br>
                    <small>Target: Order Flow Analysis</small><br>
                    Status: <span class="status-online">[ MONITORING ]</span>
                </li>
                <li>
                    <strong>SQUADRA_GAMMA</strong> 🕷️<br>
                    <small>Target: Bitget (Pairs Trading)</small><br>
                    Status: <span class="status-online">[ ACTIVE ]</span> Spread: 0.15%
                </li>
            </ul>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2 class="status-magenta">🔺 PROTOCOLLO TRINITY</h2>
            <p><strong>⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</strong><br><em>Sottosistemi in background...</em></p>
            <ul>
                <li>
                    <strong>Lo Strozzino</strong> 🎩<br>
                    <small>Funding Arbitrage</small> <span class="status-online">» RUNNING</span>
                </li>
                <li>
                    <strong>Il Contabile</strong> 🧮<br>
                    <small>DCA Engine</small> <span class="status-online">» RUNNING</span>
                </li>
                <li>
                    <strong>L'Angelo Custode</strong> 🛡️<br>
                    <small>MEV Arbitrum Protection</small> <span class="status-online">» RUNNING</span>
                </li>
            </ul>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel">
            <h2>📊 METRICHE DI MERCATO</h2>
            <p>Data Feed: <strong>The Oracle</strong> 👁️ / <strong>Whale Tracker</strong> 🐋</p>
            <table>
                <thead>
                    <tr>
                        <th>ASSET</th>
                        <th>SENTIMENT</th>
                        <th>WHALE FLOW</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BTC/USDT</td>
                        <td class="status-online">BULLISH 88%</td>
                        <td>+1,240 BTC</td>
                    </tr>
                    <tr>
                        <td>ETH/USDT</td>
                        <td class="status-online">BULLISH 75%</td>
                        <td>+8,500 ETH</td>
                    </tr>
                    <tr>
                        <td>SOL/USDT</td>
                        <td class="status-warning">NEUTRAL 50%</td>
                        <td>-120 SOL</td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route("/")
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)

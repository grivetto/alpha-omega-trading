import os
from flask import Flask, render_template_string

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ORBITAL COMMAND - NUVOLA</title>
    <style>
        :root {
            --neon-green: #0f0;
            --neon-blue: #0ff;
            --neon-pink: #f0f;
            --bg-color: #050505;
            --panel-bg: #111;
        }
        body {
            background-color: var(--bg-color);
            color: var(--neon-green);
            font-family: 'Courier New', Courier, monospace;
            margin: 0;
            padding: 20px;
            overflow-x: hidden;
        }
        h1, h2, h3 {
            text-shadow: 0 0 5px var(--neon-green), 0 0 10px var(--neon-green);
            text-transform: uppercase;
        }
        .header {
            text-align: center;
            border-bottom: 2px solid var(--neon-green);
            padding-bottom: 10px;
            margin-bottom: 20px;
            animation: flicker 3s infinite;
        }
        .container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .panel {
            background: var(--panel-bg);
            border: 1px solid var(--neon-blue);
            box-shadow: 0 0 10px var(--neon-blue) inset;
            padding: 15px;
            border-radius: 5px;
            position: relative;
        }
        .panel h2 {
            color: var(--neon-blue);
            text-shadow: 0 0 5px var(--neon-blue);
            border-bottom: 1px dashed var(--neon-blue);
            padding-bottom: 5px;
            margin-top: 0;
        }
        .status-online {
            color: var(--neon-green);
            text-shadow: 0 0 5px var(--neon-green);
            font-weight: bold;
        }
        .status-offline {
            color: red;
            text-shadow: 0 0 5px red;
        }
        .blink {
            animation: blinker 1s linear infinite;
        }
        @keyframes blinker {
            50% { opacity: 0; }
        }
        @keyframes flicker {
            0%, 19%, 21%, 23%, 25%, 54%, 56%, 100% { opacity: 1; }
            20%, 24%, 55% { opacity: 0.5; }
        }
        table {
            width: 100%;
            border-collapse: collapse;
            color: var(--neon-pink);
            text-shadow: 0 0 3px var(--neon-pink);
            margin-top: 15px;
        }
        th, td {
            border: 1px solid var(--neon-pink);
            padding: 10px;
            text-align: left;
        }
        th {
            background: rgba(255, 0, 255, 0.1);
        }
        .tactical-btn {
            background: transparent;
            color: var(--neon-green);
            border: 1px solid var(--neon-green);
            padding: 5px 10px;
            cursor: pointer;
            text-transform: uppercase;
            font-family: inherit;
            font-weight: bold;
            transition: all 0.2s;
        }
        .tactical-btn:hover {
            background: var(--neon-green);
            color: #000;
            box-shadow: 0 0 10px var(--neon-green);
        }
        .log-box {
            font-size: 0.8em;
            color: #aaa;
            margin-top: 10px;
            height: 60px;
            overflow: hidden;
            border-top: 1px dashed #444;
            padding-top: 5px;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🛰️ ORBITAL COMMAND - NUVOLA 🛰️</h1>
        <p>STATUS: <span class="status-online blink">SYSTEMS NOMINAL</span> | SEC-LEVEL: OMEGA | UPLINK: ESTABLISHED</p>
    </div>

    <div class="container">
        <!-- SQUADRE D'ASSALTO (HFT) -->
        <div class="panel">
            <h2>⚔️ SQUADRE D'ASSALTO (HFT)</h2>
            <p>⚡ <strong>SQUADRA_ALPHA</strong> (Scalper - Binance): <span class="status-online">ACTIVE</span> [WinRate: 68.4%]</p>
            <p>🌊 <strong>SQUADRA_DELTA</strong> (Order Flow): <span class="status-online">ACTIVE</span> [Volume 24h: 2.45M]</p>
            <p>⚖️ <strong>SQUADRA_GAMMA</strong> (Pairs Trading - Bitget): <span class="status-online">ACTIVE</span> [Spread Target: 0.12%]</p>
            <div class="log-box">
                > ALPHA: Order filled at 69420.00 (0.01s)<br>
                > DELTA: Detecting heavy spoofing on Ask side... ignoring.<br>
                > GAMMA: Hedging ratio adjusted to 1.05.
            </div>
        </div>

        <!-- PROTOCOLLO TRINITY -->
        <div class="panel">
            <h2>🔺 PROTOCOLLO TRINITY</h2>
            <p class="status-online blink" style="margin-top: -5px; margin-bottom: 15px;">⚙️ PROTOCOLLO TRINITY: Online (DCA, Funding, MEV)</p>
            <p>💼 <strong>Lo Strozzino</strong> (Funding Arb): <span class="status-online blink">BACKGROUND</span> [APR Target: 14.2%]</p>
            <p>🧮 <strong>Il Contabile</strong> (DCA Core): <span class="status-online blink">BACKGROUND</span> [Next buy: 4h 12m]</p>
            <p>🛡️ <strong>L'Angelo Custode</strong> (MEV - Arbitrum): <span class="status-online blink">BACKGROUND</span> [Protected: $1.2M]</p>
            <div class="log-box">
                > STROZZINO: Short perpetual open, farming premium...<br>
                > CONTABILE: Waiting for scheduled TWAP execution.<br>
                > ANGELO_CUSTODE: Mempool clear, no sandwich attacks detected.
            </div>
        </div>

        <!-- METRICHE DI MERCATO -->
        <div class="panel" style="grid-column: span 2; border-color: var(--neon-pink); box-shadow: 0 0 15px var(--neon-pink) inset;">
            <h2 style="color: var(--neon-pink); text-shadow: 0 0 5px var(--neon-pink); border-color: var(--neon-pink);">📊 METRICHE DI MERCATO (THE ORACLE & WHALE TRACKER)</h2>
            <table>
                <thead>
                    <tr>
                        <th>ASSET</th>
                        <th>SENTIMENT (ORACLE)</th>
                        <th>WHALE FLOW (24h)</th>
                        <th>ACTION</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>BTC/USDT</td>
                        <td><span style="color: var(--neon-green)">BULLISH (74%)</span></td>
                        <td>+ $450M (INFLOW)</td>
                        <td><button class="tactical-btn">DEPLOY</button></td>
                    </tr>
                    <tr>
                        <td>ETH/USDT</td>
                        <td><span style="color: #aaa">NEUTRAL (51%)</span></td>
                        <td>- $12M (OUTFLOW)</td>
                        <td><button class="tactical-btn" style="border-color: #aaa; color: #aaa;">HOLD</button></td>
                    </tr>
                    <tr>
                        <td>SOL/USDT</td>
                        <td><span style="color: var(--neon-green)">HYPER-BULL (89%)</span></td>
                        <td>+ $89M (INFLOW)</td>
                        <td><button class="tactical-btn">SCALP</button></td>
                    </tr>
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

@app.route('/')
def dashboard():
    return render_template_string(HTML_TEMPLATE)

if __name__ == '__main__':
    # Default port 5000, accessible externally if needed
    app.run(host='0.0.0.0', port=5000)
